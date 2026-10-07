import logging

from app.config import settings
from app.providers.agnes import AgnesProvider
from app.providers.base import ChatRequest, LLMProvider, ProviderHealth
from app.providers.gemini import GeminiProvider
from app.providers.mock import MockProvider
from app.providers.openrouter import OpenRouterProvider
from app.routing.policies import (
    ABTestPolicy,
    CanaryPolicy,
    CompositeScoringPolicy,
    CostOptimizedPolicy,
    LatencyBasedPolicy,
    RoutingPolicy,
    RuleBasedPolicy,
)
from app.routing.scoring import scorer

logger = logging.getLogger("prodllm.router")


class ModelRouter:
    """
    Intelligent Model Router managing multi-provider registration,
    routing policy dispatching, and health telemetry updates.
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._policies: dict[str, RoutingPolicy] = {
            "rule": RuleBasedPolicy(),
            "auto": RuleBasedPolicy(),
            "latency": LatencyBasedPolicy(),
            "cost": CostOptimizedPolicy(),
            "ab_test": ABTestPolicy(),
            "canary": CanaryPolicy(),
            "scoring": CompositeScoringPolicy(),
        }
        self._register_default_providers()

    def _register_default_providers(self):
        self.register_provider(GeminiProvider())
        self.register_provider(OpenRouterProvider())
        self.register_provider(AgnesProvider())
        self.register_provider(MockProvider())

    def register_provider(self, provider: LLMProvider):
        self._providers[provider.name.lower()] = provider
        logger.info(f"Registered provider: {provider.name}")

    def get_provider(self, name: str) -> LLMProvider | None:
        return self._providers.get(name.lower())

    def get_all_providers(self) -> list[LLMProvider]:
        return list(self._providers.values())

    def route(
        self,
        request: ChatRequest,
        strategy: str | None = None,
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        """
        Route request to an ordered list of providers based on strategy.
        """
        selected_strategy = (strategy or settings.ROUTING_STRATEGY).lower()
        policy = self._policies.get(selected_strategy, self._policies["auto"])
        available = self.get_all_providers()

        return policy.select_providers(
            request=request,
            available_providers=available,
            user_id=user_id,
        )

    async def check_all_health(self) -> dict[str, ProviderHealth]:
        """Run health check against all registered providers."""
        results = {}
        for name, provider in self._providers.items():
            health = await provider.health_check()
            results[name] = health
            scorer.set_health(name, health.status == "healthy")
            if health.latency_ms > 0:
                scorer.record_latency(name, health.latency_ms)
        return results


router = ModelRouter()
