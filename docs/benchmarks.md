# Benchmarking Guide

## Running k6 Load Tests

### Prerequisites
Install k6:
```bash
# MacOS
brew install k6

# Windows (winget or chocolatey)
winget install k6
```

### 1. Run 10K Peak Concurrency Load Test
```bash
k6 run benchmarks/k6/load_test_10k.js
```

### 2. Run Constant Rate Stress Test (1,500 RPS)
```bash
k6 run benchmarks/k6/stress_test.js
```

### Key Metrics to Observe
- **RPS (Requests Per Second)**: Sustainable gateway throughput.
- **P95 / P99 Latency**: Tail latencies under sustained load.
- **Cache Hit Ratio**: `llm_cache_hits_total` vs `llm_cache_misses_total` in Prometheus/Grafana.
- **Circuit Breaker Status**: `/health/providers` status transitions.
