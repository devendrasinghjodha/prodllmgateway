# Routing Strategies & Policies

ProdLLM Gateway provides flexible routing policies configured statically or dynamically selected via the `model` parameter.

## 1. Rule-Based Routing
Virtual aliases map directly to prioritized provider chains:
- `"model": "cheap"` → OpenRouter ($0 free models) → Agnes AI → Gemini
- `"model": "standard"` / `"model": "agnes"` → Agnes AI → Gemini → OpenRouter
- `"model": "fast"` → Gemini → Agnes AI → OpenRouter
- `"model": "auto"` → Gemini → Agnes AI → OpenRouter

## 2. Latency-Based Routing
The gateway continuously maintains a moving average of provider response times. When `"ROUTING_STRATEGY": "latency"`, requests are dispatched to the provider with lowest latency.

## 3. Cost-Optimized Routing
Routes to the provider with the lowest virtual cost per token.

## 4. Deterministic A/B Testing
When `"ROUTING_STRATEGY": "ab_test"`, incoming traffic is partitioned deterministically per user:
$$\text{bucket} = \text{hash}(\text{user\_id}) \pmod{100}$$
- `0-49`: Model A (e.g. Gemini)
- `50-99`: Model B (e.g. OpenRouter)
This ensures consistent user experience across repeat requests.

## 5. Canary Deployments
Gradual rollout of new models with configurable traffic weights (e.g. 10% to canary model, 90% to baseline).
