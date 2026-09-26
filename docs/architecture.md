# ProdLLM Gateway — System Architecture

## Overview
ProdLLM Gateway is a high-performance, OpenAI-compatible AI gateway built with FastAPI, Redis, and PostgreSQL. It acts as an intelligent proxy and routing layer across multiple LLM providers (Google Gemini, OpenRouter, and Agnes AI), providing resilience, cost optimization, caching, rate limiting, and distributed tracing.

```
                    ┌──────────────────────┐
                    │      Client App      │
                    │ OpenAI SDK / curl    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   ProdLLM Gateway    │
                    │      FastAPI         │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        Authentication    Rate Limiter      Request ID
         (SHA256 Keys)  (Sliding Window)   (Correlation)
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │    Model Router      │
                    │ latency/cost/health  │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
              ▼                ▼                 ▼
        ┌──────────┐     ┌──────────┐      ┌──────────┐
        │  Gemini  │     │OpenRouter│      │ Agnes AI │
        │ Provider │     │ Provider │      │ Provider │
        └──────────┘     └──────────┘      └──────────┘
              │                │                 │
              └────────────────┼─────────────────┘
                               ▼
                         Normalized Response
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
          Redis             Metrics           Logging
          Cache           Prometheus          /Tracing
        (SingleFlight)     (/metrics)         (Jaeger)
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                         Client Response
```

## Key Subsystems

### 1. Unified Provider Abstraction
The abstract base class `LLMProvider` decouples the core routing and reliability engine from individual provider network protocols. Every provider translates requests to and from the standard OpenAI chat completions format.

### 2. Fast Caching & Single-Flight Coalescing
Deterministic SHA-256 hash generation captures all query parameters (`model`, `messages`, `temperature`, `max_tokens`, etc.). In-flight coalescing via distributed locks guarantees that 100 simultaneous duplicate requests trigger only 1 upstream LLM call.

### 3. Reliability Engine
- **Exponential Backoff with Full Jitter**: Automatically retries 429, 500, 502, 503, 504 and network timeouts while avoiding retrying 400, 401, or 403 client errors.
- **Custom Stateful Circuit Breaker**: Tracks consecutive failures and trips to `OPEN` state to prevent cascading failures.
- **Automatic Fallback**: Transparent failover across ordered provider candidate lists.
- **Request Hedging**: Concurrently fires secondary provider requests if primary latency exceeds threshold.
