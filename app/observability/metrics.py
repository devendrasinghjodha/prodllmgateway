from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# 1. LLM Requests Total
LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total number of LLM chat completion requests processed by the gateway",
    ["model", "status", "cached"],
)

# 2. LLM Request Latency Histogram
LLM_REQUEST_LATENCY_SECONDS = Histogram(
    "llm_request_latency_seconds",
    "Latency of LLM requests through the gateway in seconds",
    ["provider", "model", "status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# 3. LLM Tokens Total
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total tokens consumed across all requests",
    ["type", "provider", "model"],  # type = prompt, completion, total
)

# 4. LLM Errors Total
LLM_ERRORS_TOTAL = Counter(
    "llm_errors_total",
    "Total number of request errors",
    ["provider", "error_type"],
)

# 5. LLM Provider Requests Total
LLM_PROVIDER_REQUESTS_TOTAL = Counter(
    "llm_provider_requests_total",
    "Total requests dispatched directly to an upstream provider",
    ["provider", "status"],
)

# 6. Cache Hits & Misses
LLM_CACHE_HITS_TOTAL = Counter(
    "llm_cache_hits_total",
    "Total number of cache hits returning cached LLM responses",
)

LLM_CACHE_MISSES_TOTAL = Counter(
    "llm_cache_misses_total",
    "Total number of cache misses requiring upstream LLM invocation",
)

# 7. Rate Limits & Quota
LLM_RATE_LIMIT_TOTAL = Counter(
    "llm_rate_limit_total",
    "Total number of requests rejected due to rate limits or token quotas",
    ["reason"],  # rate_limit, quota_exceeded
)

# 8. Fallback Invocations
LLM_FALLBACK_TOTAL = Counter(
    "llm_fallback_total",
    "Total number of fallback transitions from a failing provider to a backup",
    ["primary_provider", "fallback_provider"],
)

# 9. Circuit Breaker Trips
LLM_CIRCUIT_BREAKER_OPEN_TOTAL = Counter(
    "llm_circuit_breaker_open_total",
    "Total number of times a provider circuit breaker tripped to OPEN",
    ["provider"],
)

# 10. Concurrency & In-flight Gauge
LLM_IN_FLIGHT_REQUESTS = Gauge(
    "llm_in_flight_requests",
    "Current number of in-flight requests in the gateway",
)


def get_metrics_payload() -> bytes:
    """Export Prometheus format metrics."""
    return generate_latest()
