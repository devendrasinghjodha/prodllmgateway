import asyncio
import logging

from app.config import settings
from app.providers.base import ChatRequest, ChatResponse, LLMProvider
from app.reliability.circuit_breaker import circuit_breakers

logger = logging.getLogger("prodllm.hedging")


class HedgingOrchestrator:
    """
    Speculative request execution (Request Hedging).
    Sends request to primary provider. If not completed within delay_ms, sends to secondary concurrently.
    The fastest successful response is returned, and slower background tasks are cancelled.
    """

    async def execute(
        self,
        providers: list[LLMProvider],
        request: ChatRequest,
        delay_ms: int | None = None,
    ) -> ChatResponse:
        if len(providers) < 2 or not settings.HEDGING_ENABLED:
            # Fallback to single primary if hedging disabled or only 1 provider
            return await providers[0].chat(request)

        hedging_delay = (delay_ms or settings.HEDGING_DELAY_MS) / 1000.0
        primary = providers[0]
        secondary = providers[1]

        async def run_provider(provider: LLMProvider) -> ChatResponse:
            breaker = circuit_breakers.get_breaker(provider.name)
            if not await breaker.can_execute():
                raise RuntimeError(f"Circuit breaker for {provider.name} is OPEN")
            try:
                resp = await provider.chat(request)
                await breaker.record_success()
                return resp
            except Exception as e:
                await breaker.record_failure(e)
                raise e

        primary_task = asyncio.create_task(run_provider(primary), name=f"hedge-{primary.name}")

        try:
            # Wait for primary for the hedging delay
            done, _ = await asyncio.wait(
                [primary_task],
                timeout=hedging_delay,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if primary_task in done and not primary_task.cancelled():
                if primary_task.exception() is None:
                    return primary_task.result()
                else:
                    logger.warning(
                        f"Primary provider {primary.name} failed early: {primary_task.exception()}. Triggering secondary."
                    )

            logger.info(
                f"Primary provider {primary.name} did not respond within {hedging_delay*1000:.0f}ms. Launching hedged request to {secondary.name}."
            )
            secondary_task = asyncio.create_task(run_provider(secondary), name=f"hedge-{secondary.name}")

            # Wait for whichever finishes first successfully
            tasks = {primary_task, secondary_task}
            while tasks:
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for finished_task in done:
                    if finished_task.exception() is None:
                        # Winner! Cancel remaining tasks
                        for remaining in tasks:
                            remaining.cancel()
                        winner_name = (
                            primary.name if finished_task is primary_task else secondary.name
                        )
                        logger.info(f"Hedged request winner: {winner_name}")
                        return finished_task.result()
                    else:
                        logger.warning(
                            f"Hedged task {finished_task.get_name()} failed with: {finished_task.exception()}"
                        )

            raise RuntimeError("Both primary and hedged providers failed.")
        finally:
            primary_task.cancel()
