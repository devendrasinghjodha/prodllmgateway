import json
import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_keys import AuthenticatedUser
from app.auth.middleware import get_current_user
from app.cache.redis import CacheManager, generate_cache_key, get_redis
from app.cache.singleflight import SingleFlight
from app.config import settings
from app.database.repository import DatabaseRepository, get_db_session
from app.limits.quota import QuotaManager
from app.limits.rate_limit import RateLimiter
from app.observability.metrics import (
    LLM_CACHE_HITS_TOTAL,
    LLM_CACHE_MISSES_TOTAL,
    LLM_ERRORS_TOTAL,
    LLM_FALLBACK_TOTAL,
    LLM_IN_FLIGHT_REQUESTS,
    LLM_RATE_LIMIT_TOTAL,
    LLM_REQUEST_LATENCY_SECONDS,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_TOTAL,
)
from app.observability.tracing import get_tracer
from app.providers.base import ChatRequest, ChatResponse
from app.queue.priority_queue import BackpressureQueueFullError, scheduler
from app.reliability.fallback import AllProvidersFailedError, FallbackOrchestrator
from app.reliability.hedging import HedgingOrchestrator
from app.routing.router import router
from app.routing.scoring import scorer

logger = logging.getLogger("prodllm.api.chat")
chat_router = APIRouter(prefix="/v1", tags=["Chat Completions"])


async def log_request_audit(
    request_id: str,
    user_id: str | None,
    api_key_id: str | None,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: float,
    status: str,
    error_type: str | None,
    estimated_cost: float,
    idempotency_key: str | None,
):
    try:
        from app.database.repository import async_session_factory
        if async_session_factory:
            async with async_session_factory() as session:
                repo = DatabaseRepository(session)
                await repo.log_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    status=status,
                    error_type=error_type,
                    estimated_cost=estimated_cost,
                    idempotency_key=idempotency_key,
                )
                await session.commit()
    except Exception as e:
        logger.error(f"Failed to record request audit log: {e}")


@chat_router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    request: Request,
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_priority: str | None = Header(None, alias="X-Priority"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession | None = Depends(get_db_session),
):
    """
    OpenAI-compatible Chat Completion endpoint with multi-provider routing,
    caching, single-flight coalescing, rate limiting, quotas, and fallback reliability.
    """
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    LLM_IN_FLIGHT_REQUESTS.inc()

    tracer = get_tracer()
    r_client = await get_redis()
    cache_mgr = CacheManager(r_client)
    limiter = RateLimiter(r_client)
    quota_mgr = QuotaManager(r_client)
    singleflight = SingleFlight(cache_mgr, r_client)
    fallback_orchestrator = FallbackOrchestrator()
    hedging_orchestrator = HedgingOrchestrator()

    priority = x_priority or body.priority or "normal"

    try:
        with tracer.start_as_current_span("chat_completion") as span:
            span.set_attribute("llm.request_id", req_id)
            span.set_attribute("llm.user_id", user.user_id)
            span.set_attribute("llm.model", body.model)

            # 1. Guardrail Safety Check
            from app.guardrails import guardrails
            is_safe, safety_error = guardrails.validate_messages(body.messages)
            if not is_safe:
                LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="guardrail_violation").inc()
                raise HTTPException(
                    status_code=400,
                    detail={"error": {"type": "content_policy_violation", "message": safety_error}},
                )

            # 2. PII Masking & Context Pruning
            from app.cache.semantic import semantic_cache
            from app.guardrails.pii import pii_masker
            from app.routing.shadow import shadow_orchestrator
            from app.utils.compression import prune_chat_context

            masked_messages, pii_mapping = pii_masker.mask_messages(body.messages)
            effective_messages = prune_chat_context(masked_messages)
            routed_request = body.model_copy(update={"messages": effective_messages})

            # 3. Idempotency Check (Section 32)
            if idempotency_key:
                cached_idempotent = await cache_mgr.get_idempotent_response(idempotency_key)
                if cached_idempotent:
                    logger.info(f"Idempotent response hit for key: {idempotency_key}")
                    LLM_CACHE_HITS_TOTAL.inc()
                    LLM_REQUESTS_TOTAL.labels(model=body.model, status="success", cached="true").inc()
                    return cached_idempotent

            # 4. Rate Limiting Check (Section 8)
            with tracer.start_as_current_span("rate_limit_check"):
                allowed, count, remaining = await limiter.check_sliding_window(user.api_key_id)
                if not allowed:
                    LLM_RATE_LIMIT_TOTAL.labels(reason="rate_limit").inc()
                    LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="rate_limited").inc()
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": {
                                "type": "rate_limit_exceeded",
                                "message": f"Rate limit exceeded (max {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} req/min).",
                            }
                        },
                    )

            # 5. Quota Check (Section 23)
            with tracer.start_as_current_span("quota_check"):
                quota_ok, used_tok, rem_tok = await quota_mgr.check_quota(user.user_id)
                if not quota_ok:
                    LLM_RATE_LIMIT_TOTAL.labels(reason="quota_exceeded").inc()
                    LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="quota_exceeded").inc()
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": {
                                "type": "quota_exceeded",
                                "message": "Daily token quota exceeded.",
                            }
                        },
                    )

            # 6. Team Monthly Spend Budget & Graceful Downgrade Check
            from app.limits.budget import budget_manager
            budget_allowed, need_downgrade, team_spend, team_limit = await budget_manager.check_budget(user.team_id)
            if not budget_allowed:
                LLM_RATE_LIMIT_TOTAL.labels(reason="budget_exceeded").inc()
                LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="budget_exceeded").inc()
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "type": "budget_exceeded",
                            "message": f"Team monthly spend budget (${team_limit:.2f}) exceeded (Current: ${team_spend:.4f}).",
                        }
                    },
                )

            if need_downgrade:
                logger.warning(
                    f"Team '{user.team_id}' exceeded monthly spend limit (${team_spend:.2f}/${team_limit:.2f}). "
                    f"Gracefully downgrading request from '{body.model}' to free tier ('cheap')."
                )
                routed_request.model = "cheap"

            # 7. Response Caching (Exact Key & Semantic Vector Match)
            cache_key = generate_cache_key(routed_request)
            if not body.stream:
                with tracer.start_as_current_span("cache_lookup"):
                    # Exact Match
                    cached_resp = await cache_mgr.get_cached_response(cache_key)
                    if cached_resp:
                        latency_ms = (time.time() - start_time) * 1000
                        LLM_CACHE_HITS_TOTAL.inc()
                        LLM_REQUESTS_TOTAL.labels(model=body.model, status="success", cached="true").inc()
                        logger.info(f"Exact Cache HIT for key: {cache_key[:16]}... ({latency_ms:.2f}ms)")
                        if pii_mapping:
                            for c in cached_resp.choices:
                                c.message.content = pii_masker.unmask_text(c.message.content or "", pii_mapping)
                        return cached_resp

                    # Semantic Vector Match
                    sem_match = await semantic_cache.search(routed_request.messages, body.model)
                    if sem_match:
                        sem_resp, score = sem_match
                        latency_ms = (time.time() - start_time) * 1000
                        LLM_CACHE_HITS_TOTAL.inc()
                        LLM_REQUESTS_TOTAL.labels(model=body.model, status="success", cached="true").inc()
                        logger.info(f"Semantic Cache HIT (score: {score:.2f}) in {latency_ms:.2f}ms")
                        if pii_mapping:
                            for c in sem_resp.choices:
                                c.message.content = pii_masker.unmask_text(c.message.content or "", pii_mapping)
                        return sem_resp

                LLM_CACHE_MISSES_TOTAL.inc()

            # 7. Routing Selection (Section 12, 13, 24, 25)
            with tracer.start_as_current_span("model_routing"):
                candidate_providers = router.route(routed_request, user_id=user.user_id)
                if not candidate_providers:
                    raise HTTPException(
                        status_code=503,
                        detail={"error": {"type": "no_providers_available", "message": "No healthy LLM providers configured"}},
                    )

            # 8. Streaming Handler (Section 18)
            if body.stream:
                async def stream_generator():
                    try:
                        async for chunk in fallback_orchestrator.execute_stream(candidate_providers, routed_request):
                            yield f"data: {chunk.model_dump_json()}\n\n"
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Streaming error: {e}")
                        err_payload = json.dumps({"error": {"message": str(e), "type": "streaming_error"}})
                        yield f"data: {err_payload}\n\n"
                    finally:
                        LLM_IN_FLIGHT_REQUESTS.dec()

                return StreamingResponse(stream_generator(), media_type="text/event-stream")

            # 7. Non-Streaming Execution with Priority Queue & Single-Flight Coalescing
            async def execute_upstream() -> ChatResponse:
                with tracer.start_as_current_span("provider_call"):
                    def on_fallback(failed_p: str, exc: Exception):
                        LLM_FALLBACK_TOTAL.labels(
                            primary_provider=failed_p,
                            fallback_provider=candidate_providers[1].name if len(candidate_providers) > 1 else "none",
                        ).inc()

                    if settings.HEDGING_ENABLED and len(candidate_providers) >= 2:
                        return await hedging_orchestrator.execute(candidate_providers, routed_request)
                    else:
                        return await fallback_orchestrator.execute_chat(
                            candidate_providers, routed_request, on_provider_fallback=on_fallback
                        )

            try:
                # Wrap with Priority Queue Backpressure and SingleFlight
                async def scheduled_task():
                    resp, _ = await singleflight.execute(cache_key, execute_upstream)
                    return resp

                response = await scheduler.schedule(scheduled_task, priority=priority)

            except BackpressureQueueFullError:
                LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="backpressure_shed").inc()
                raise HTTPException(
                    status_code=503,
                    detail={"error": {"type": "server_overloaded", "message": "Gateway queue full. Shedding load."}},
                )
            except AllProvidersFailedError as e:
                LLM_ERRORS_TOTAL.labels(provider="all", error_type="all_providers_failed").inc()
                raise HTTPException(
                    status_code=502,
                    detail={"error": {"type": "bad_gateway", "message": str(e)}},
                )

            # Store in Semantic Cache & Unmask PII
            background_tasks.add_task(semantic_cache.store, routed_request.messages, body.model, response)

            # Shadow Traffic Mirroring (if alternative provider exists)
            shadow_candidate = candidate_providers[1] if len(candidate_providers) > 1 else None
            background_tasks.add_task(
                shadow_orchestrator.maybe_shadow_request,
                shadow_candidate,
                routed_request,
                response.id,
            )

            # Unmask PII in final response
            if pii_mapping:
                for choice in response.choices:
                    choice.message.content = pii_masker.unmask_text(choice.message.content or "", pii_mapping)

            # 8. Post-Execution Metrics & Quota Consumption
            latency_ms = (time.time() - start_time) * 1000
            response.latency_ms = latency_ms

            if response.provider:
                scorer.record_latency(response.provider, latency_ms)

            # Record Prometheus Metrics
            LLM_REQUESTS_TOTAL.labels(model=body.model, status="success", cached="false").inc()
            LLM_REQUEST_LATENCY_SECONDS.labels(
                provider=response.provider or "unknown",
                model=response.model,
                status="success",
            ).observe(latency_ms / 1000.0)
            LLM_TOKENS_TOTAL.labels(
                type="prompt", provider=response.provider or "unknown", model=response.model
            ).inc(response.usage.prompt_tokens)
            LLM_TOKENS_TOTAL.labels(
                type="completion", provider=response.provider or "unknown", model=response.model
            ).inc(response.usage.completion_tokens)
            LLM_TOKENS_TOTAL.labels(
                type="total", provider=response.provider or "unknown", model=response.model
            ).inc(response.usage.total_tokens)

            # Deduct Token Quota asynchronously
            background_tasks.add_task(quota_mgr.consume_tokens, user.user_id, response.usage.total_tokens)

            # Record Team Monthly USD Spend asynchronously
            if user.team_id:
                background_tasks.add_task(budget_manager.record_spend, user.team_id, response.usage.estimated_cost)

            # Idempotency storage
            if idempotency_key:
                background_tasks.add_task(cache_mgr.set_idempotent_response, idempotency_key, response)

            # DB Audit Logging in background
            background_tasks.add_task(
                log_request_audit,
                request_id=response.id,
                user_id=user.user_id,
                api_key_id=user.api_key_id,
                provider=response.provider or "unknown",
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                latency_ms=latency_ms,
                status="success",
                error_type=None,
                estimated_cost=response.usage.estimated_cost,
                idempotency_key=idempotency_key,
            )

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unhandled exception in chat completion: {e}")
        LLM_ERRORS_TOTAL.labels(provider="gateway", error_type="unhandled_exception").inc()
        raise HTTPException(
            status_code=500,
            detail={"error": {"type": "internal_server_error", "message": str(e)}},
        )
    finally:
        if not body.stream:
            LLM_IN_FLIGHT_REQUESTS.dec()
