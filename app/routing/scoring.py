import time
from typing import Dict, Optional


class ProviderStats:
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.samples = []
        self.max_samples = 50
        self.avg_latency_ms: float = 1000.0  # default prior
        self.last_updated = time.time()
        self.is_healthy: bool = True

    def record_latency(self, latency_ms: float):
        self.samples.append(latency_ms)
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
        self.avg_latency_ms = sum(self.samples) / len(self.samples)
        self.last_updated = time.time()


class ProviderScorer:
    """
    Maintains real-time latency statistics and computes multi-dimensional scores for providers.
    score = 0.5 * latency_score + 0.3 * cost_score + 0.2 * quality_score
    """

    def __init__(self):
        self._stats: Dict[str, ProviderStats] = {
            "gemini": ProviderStats("gemini"),
            "openrouter": ProviderStats("openrouter"),
            "agnes": ProviderStats("agnes"),
            "mock": ProviderStats("mock"),
        }
        # Virtual quality ratings (0.0 to 1.0)
        self.quality_ratings: Dict[str, float] = {
            "gemini": 0.95,
            "openrouter": 0.90,
            "agnes": 0.92,
            "mock": 0.99,
        }
        # Normalized virtual cost ranking (0.0=free/cheapest, 1.0=expensive)
        self.cost_ratings: Dict[str, float] = {
            "gemini": 0.3,
            "openrouter": 0.0,
            "agnes": 0.15,
            "mock": 0.0,
        }

    def record_latency(self, provider_name: str, latency_ms: float):
        if provider_name not in self._stats:
            self._stats[provider_name] = ProviderStats(provider_name)
        self._stats[provider_name].record_latency(latency_ms)

    def set_health(self, provider_name: str, is_healthy: bool):
        if provider_name not in self._stats:
            self._stats[provider_name] = ProviderStats(provider_name)
        self._stats[provider_name].is_healthy = is_healthy

    def get_avg_latency(self, provider_name: str) -> float:
        stats = self._stats.get(provider_name)
        return stats.avg_latency_ms if stats else 1000.0

    def compute_score(self, provider_name: str) -> float:
        """
        Lower score is better (cost + latency penalty - quality bonus).
        """
        stats = self._stats.get(provider_name)
        if stats and not stats.is_healthy:
            return 999999.0  # severely penalize unhealthy

        avg_lat = self.get_avg_latency(provider_name)
        # Normalize latency (0 to 3000ms mapped to 0.0 to 1.0)
        norm_lat = min(1.0, avg_lat / 3000.0)
        cost = self.cost_ratings.get(provider_name, 0.5)
        quality = self.quality_ratings.get(provider_name, 0.8)

        score = (0.5 * norm_lat) + (0.3 * cost) - (0.2 * quality)
        return score


scorer = ProviderScorer()
