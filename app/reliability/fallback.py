import logging
from typing import AsyncGenerator, Callable, Dict, List, Optional
from app.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    LLMProvider,
)
from app.reliability.circuit_breaker import (
    CircuitBreakerOpenError,
    circuit_breakers,
)
from app.reliability.retry import with_retry

logger = logging.getLogger("prodllm.fallback")


class AllProvidersFailedError(Exception):
    """Raised when all candidate providers in the fallback list have failed."""
    def __init__(self, errors: dict[str, str]):
        super().__init__(f"All providers failed: {errors}")
        self.errors = errors


class FallbackOrchestrator:
    """
    Executes a chat or stream request with automatic fallback across an ordered list of providers.
    Each provider call goes through its circuit breaker and retry policy.
    """

    async def execute_chat(
        self,
        providers: List[LLMProvider],
        request: ChatRequest,
        on_provider_fallback: Optional[Callable] = None,
    ) -> ChatResponse:
        errors = {}
        for index, provider in enumerate(providers):
            p_name = provider.name
            breaker = circuit_breakers.get_breaker(p_name)

            # 1. Circuit Breaker Check
            if not await breaker.can_execute():
                logger.warning(
                    f"Skipping provider {p_name} because its circuit breaker is OPEN."
                )
                errors[p_name] = f"Circuit breaker is OPEN (wait {breaker.get_remaining_recovery_time():.1f}s)"
                continue

            # 2. Execute with Retry
            try:
                logger.info(f"Attempting provider: {p_name} (candidate {index + 1}/{len(providers)})")
                response = await with_retry(lambda: provider.chat(request))
                await breaker.record_success()
                return response
            except Exception as e:
                logger.error(f"Provider {p_name} failed: {e}")
                await breaker.record_failure(e)
                errors[p_name] = str(e)
                if on_provider_fallback:
                    on_provider_fallback(p_name, e)

        raise AllProvidersFailedError(errors=errors)

    async def execute_stream(
        self,
        providers: List[LLMProvider],
        request: ChatRequest,
    ) -> AsyncGenerator[ChatStreamChunk, None]:
        errors = {}
        for index, provider in enumerate(providers):
            p_name = provider.name
            breaker = circuit_breakers.get_breaker(p_name)

            if not await breaker.can_execute():
                logger.warning(f"Skipping provider {p_name} in stream (circuit OPEN).")
                errors[p_name] = "Circuit breaker OPEN"
                continue

            try:
                # Test stream start
                stream_gen = provider.stream(request)
                first_chunk = await stream_gen.__anext__()
                await breaker.record_success()

                yield first_chunk
                async for chunk in stream_gen:
                    yield chunk
                return
            except StopAsyncIteration:
                await breaker.record_success()
                return
            except Exception as e:
                logger.error(f"Provider {p_name} stream failed: {e}")
                await breaker.record_failure(e)
                errors[p_name] = str(e)

        raise AllProvidersFailedError(errors=errors)
