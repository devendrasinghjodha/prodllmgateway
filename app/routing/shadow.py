import asyncio
import logging
import random
import time
from typing import Optional
from app.providers.base import ChatRequest, LLMProvider

logger = logging.getLogger("prodllm.shadow")


class ShadowTrafficOrchestrator:
    """
    Asynchronously mirrors a percentage of live production traffic to a shadow provider
    to test new models/versions without impacting user response times.
    """

    def __init__(self, sample_rate: float = 0.05):
        self.sample_rate = sample_rate

    async def maybe_shadow_request(
        self,
        shadow_provider: Optional[LLMProvider],
        request: ChatRequest,
        primary_response_id: str,
    ):
        if not shadow_provider or random.random() > self.sample_rate:
            return

        asyncio.create_task(
            self._execute_shadow(shadow_provider, request, primary_response_id),
            name=f"shadow-{shadow_provider.name}-{primary_response_id}",
        )

    async def _execute_shadow(
        self,
        provider: LLMProvider,
        request: ChatRequest,
        primary_response_id: str,
    ):
        start = time.time()
        try:
            # Execute shadow request (non-streaming)
            shadow_req = request.model_copy(update={"stream": False})
            resp = await provider.chat(shadow_req)
            latency_ms = (time.time() - start) * 1000
            logger.info(
                f"[Shadow Traffic] Provider '{provider.name}' completed in {latency_ms:.1f}ms "
                f"(Tokens: {resp.usage.total_tokens}, Ref: {primary_response_id})"
            )
        except Exception as e:
            logger.warning(
                f"[Shadow Traffic] Provider '{provider.name}' failed during shadow execution: {e} "
                f"(Ref: {primary_response_id})"
            )


shadow_orchestrator = ShadowTrafficOrchestrator()
