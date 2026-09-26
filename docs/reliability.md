# Reliability & Fault Tolerance

## 1. Retry with Exponential Backoff and Jitter
The gateway automatically retries transient errors with full jitter to avoid the thundering herd problem.

- **Retried Status Codes**: `429 (Rate Limit)`, `500 (Internal Error)`, `502 (Bad Gateway)`, `503 (Service Unavailable)`, `504 (Gateway Timeout)`, timeouts and connection drops.
- **Ignored (Non-retried)**: `400 (Bad Request)`, `401 (Unauthorized)`, `403 (Forbidden)`, validation errors.

## 2. Circuit Breaker
The gateway implements a custom stateful circuit breaker per provider:
- **CLOSED**: Normal state. If consecutive failures exceed threshold (default 5), transitions to **OPEN**.
- **OPEN**: Rejects calls immediately without network overhead. After cooldown (default 30s), transitions to **HALF_OPEN**.
- **HALF_OPEN**: Allows probe requests. If probe succeeds, transitions back to **CLOSED**; on failure, reopens.

## 3. Automatic Multi-Provider Fallback
```
Client Request
      ↓
   Router
      ↓
 Primary (Gemini) ── Failure / CB OPEN ──→ Fallback (OpenRouter) ── Failure ──→ Fallback (Agnes AI)
```

## 4. Request Hedging
Speculatively sends requests to a secondary provider if the primary provider takes longer than the hedging threshold (e.g. 800ms). The first successful response wins and the slower request is cancelled.
