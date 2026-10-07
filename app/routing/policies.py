import hashlib
import random
from abc import ABC, abstractmethod

from app.config import settings
from app.providers.base import ChatRequest, LLMProvider
from app.routing.scoring import scorer


class RoutingPolicy(ABC):
    @abstractmethod
    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        """Return an ordered list of providers (primary followed by fallback candidates)."""


class RuleBasedPolicy(RoutingPolicy):
    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        model = (request.model or "auto").lower()
        provider_map = {p.name.lower(): p for p in available_providers}

        # Specific provider requested
        if model in provider_map:
            primary = provider_map[model]
            fallbacks = [p for p in available_providers if p != primary]
            return [primary] + fallbacks

        if model in ["cheap", "free"]:
            preferred = ["openrouter", "agnes", "gemini"]
        elif model in ["fast", "gemini"]:
            preferred = ["gemini", "agnes", "openrouter"]
        elif model in ["agnes", "standard"]:
            preferred = ["agnes", "gemini", "openrouter"]
        else:  # auto / default
            preferred = ["gemini", "agnes", "openrouter"]

        ordered = []
        for name in preferred:
            if name in provider_map:
                ordered.append(provider_map[name])
        for p in available_providers:
            if p not in ordered:
                ordered.append(p)
        return ordered


class LatencyBasedPolicy(RoutingPolicy):
    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        # Sort by lowest average latency
        return sorted(available_providers, key=lambda p: scorer.get_avg_latency(p.name))


class CostOptimizedPolicy(RoutingPolicy):
    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        # Free / cheapest first (openrouter free / agnes -> gemini)
        return sorted(available_providers, key=lambda p: scorer.cost_ratings.get(p.name, 0.5))


class ABTestPolicy(RoutingPolicy):
    """
    Deterministic A/B Testing partitioned by user_id hash.
    0-49 -> Model A (e.g. Gemini)
    50-99 -> Model B (e.g. OpenRouter)
    """

    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        uid = user_id or request.user or "anon_user"
        bucket = int(hashlib.md5(uid.encode("utf-8")).hexdigest(), 16) % 100

        provider_map = {p.name.lower(): p for p in available_providers}
        if bucket < 50 and "gemini" in provider_map:
            primary = provider_map["gemini"]
        elif "openrouter" in provider_map:
            primary = provider_map["openrouter"]
        else:
            primary = available_providers[0]

        fallbacks = [p for p in available_providers if p != primary]
        return [primary] + fallbacks


class CanaryPolicy(RoutingPolicy):
    """
    Canary Deployment Policy with configurable traffic weight.
    E.g., 10% to Canary model, 90% to Baseline model.
    """

    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        provider_map = {p.name.lower(): p for p in available_providers}
        canary_target = settings.CANARY_TARGET_MODEL.lower()
        canary_weight = settings.CANARY_WEIGHT

        is_canary = random.random() < canary_weight
        if is_canary and canary_target in provider_map:
            primary = provider_map[canary_target]
        else:
            primary = provider_map.get("gemini", available_providers[0])

        fallbacks = [p for p in available_providers if p != primary]
        return [primary] + fallbacks


class CompositeScoringPolicy(RoutingPolicy):
    """
    Multi-factor optimization scoring (latency + cost - quality).
    """

    def select_providers(
        self,
        request: ChatRequest,
        available_providers: list[LLMProvider],
        user_id: str | None = None,
    ) -> list[LLMProvider]:
        return sorted(available_providers, key=lambda p: scorer.compute_score(p.name))
