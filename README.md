<div align="center">

# ⚡ ProdLLM Gateway

**Universal High-Performance AI Gateway with Smart Multi-Provider Routing, Distributed Semantic Caching, Circuit Breaking, Financial Governance & Embedded Observability.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5.svg?logo=kubernetes&logoColor=white)](k8s/)
[![Redis](https://img.shields.io/badge/Redis-Vector_Cache-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Async_Storage-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

[Features](#-key-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Providers](#-supported-providers) • [API Specs](#-api-endpoints) • [Dashboard](#-operations-dashboard) • [Deployment](#-production-deployment)

</div>

---

## 📖 Overview

**ProdLLM Gateway** is a production-oriented, zero-budget AI routing and governance engine written in Python (FastAPI). It sits between your client applications (OpenAI SDK, LangChain, LlamaIndex, curl) and upstream LLM providers (Google Gemini, OpenRouter, Agnes AI), delivering:

- **Latency and cost controls** via exact SHA-256 and semantic vector caching.
- **Resilient Multi-Provider Fallbacks** with per-provider Circuit Breakers, Jittered Retries, and Request Hedging.
- **Enterprise Multi-Tenancy & Financial Governance** with monthly USD spend limits, sliding-window rate limits, and graceful $0 free-tier downgrades.
- **Real-Time Guardrails & PII Masking** redacting sensitive customer data before sending it upstream.
- **Dynamic Prompt Registry, Automated Heuristic Evals, and OpenAI Batch API Processing**.
- **Embedded Real-Time Web Control Plane** at `/dashboard`.

---

## 🏗️ Architecture

```
                                  ┌─────────────────────────────┐
                                  │      Client Application     │
                                  │  OpenAI SDK / LangChain / UI │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
               ┌──────────────────────────────────────────────────────────────────┐
               │                     ProdLLM Gateway (FastAPI)                    │
               │  Correlation ID Middleware (X-Request-ID) & Latency Profiling    │
               └─────────────────────────────────┬────────────────────────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   │                             │                             │
                   ▼                             ▼                             ▼
         ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
         │  Auth & Hierarchy │         │ Security Filters  │         │  Traffic Controls │
         │  Org → Team → User│         │  • PII Masking    │         │ • Sliding Win RLim│
         │  SHA-256 Auth Pool│         │  • Jailbreak Block│         │ • Monthly USD Budg│
         └─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
                   │                             │                             │
                   └─────────────────────────────┼─────────────────────────────┘
                                                 │
                                                 ▼
                               ┌──────────────────────────────────┐
                               │   Multi-Tier Distributed Cache   │
                               │  • Semantic Vector (Cosine Sim)  │
                               │  • Exact SHA-256 Redis Cache     │
                               │  • SingleFlight Request Lock     │
                               └─────────────────┬────────────────┘
                                                 │ (Cache Miss)
                                                 ▼
                               ┌──────────────────────────────────┐
                               │    Smart Model Router Mesh       │
                               │  • Context-Length Routing        │
                               │  • Health/Latency/Cost Scoring   │
                               │  • Dark Shadow Traffic Mirroring │
                               │  • Canary & Deterministic A/B    │
                               └─────────────────┬────────────────┘
                                                 │
         ┌───────────────────────────────────────┼───────────────────────────────────────┐
         │                                       │                                       │
         ▼                                       ▼                                       ▼
   ┌───────────┐                           ┌───────────┐                           ┌───────────┐
   │  Google   │                           │OpenRouter │                           │ Agnes AI  │
   │  Gemini   │                           │  Gateway  │                           │ Standard  │
   │ (REST/SSE)│                           │(DeepSeek) │                           │ (FastAPI) │
   └─────┬─────┘                           └─────┬─────┘                           └─────┬─────┘
         │                                       │                                       │
         └───────────────────────────────────────┼───────────────────────────────────────┘
                                                 │
                                                 ▼
                               ┌──────────────────────────────────┐
                               │   Resilience & Failover Layer    │
                               │  • Circuit Breaker (Closed/Open) │
                               │  • Jittered Exponential Retry    │
                               │  • Speculative Request Hedging   │
                               │  • Dead Letter Queue (DLQ)       │
                               └─────────────────┬────────────────┘
                                                 │
                                                 ▼
                               ┌──────────────────────────────────┐
                               │     Observability & Insights     │
                               │  • Prometheus Metrics (/metrics) │
                               │  • OpenTelemetry Traces (Jaeger) │
                               │  • Dynamic Prompt Registry       │
                               │  • Real-time Evals & CSAT Store  │
                               │  • Embedded Web Dashboard UI     │
                               └──────────────────────────────────┘
```

---

## 🚀 Key Features

### 1. Unified Multimodal API Surface (OpenAI-Compatible)
- `POST /v1/chat/completions`: Full support for non-streaming and Server-Sent Events (SSE) streaming.
- `POST /v1/embeddings`: Vector embeddings generation with dimension validation.
- `POST /v1/images/generations`: Image synthesis routing.
- `POST /v1/audio/transcriptions`: Speech-to-text audio transcriptions.
- `GET /v1/models`: Provider model catalog and virtual routing aliases (`auto`, `gemini`, `openrouter`, `agnes`, `cheap`, `fast`).

### 2. Universal Tool & Function Calling Adapter
- Automatically translates standard OpenAI `tools` / `tool_calls` schemas to Google Gemini `functionDeclarations`.
- Maps Gemini `functionCall` responses back to standard OpenAI `tool_calls` seamlessly.

### 3. Multi-Tier Distributed Caching
- **Exact Hash Caching**: SHA-256 request payload caching in Redis.
- **Semantic Vector Caching**: Cosine similarity vector search (threshold 0.88) eliminating upstream LLM calls for semantically identical questions.
- **Single-Flight Coalescing**: Distributed Redis `SETNX` mutex locks preventing stampeding herds on identical concurrent prompts.
- **Context Pruning**: Intelligent conversational history token pruning reducing token usage by 20–40%.

### 4. Enterprise Security & Guardrails
- **Real-Time PII Masking**: Automatically detects & redacts Emails, Phone Numbers, Credit Cards, SSNs, and IP addresses before reaching upstream LLMs, restoring them transparently in client responses.
- **Prompt Injection Defense**: Pre-flight regex filtering blocking jailbreak attempts.
- **Upstream Key Rotation**: Automatic round-robin key rotation across pools per provider.

### 5. Financial Governance & Multi-Tenancy
- Hierarchical governance: `Organization` $\rightarrow$ `Team` $\rightarrow$ `User`.
- **Monthly USD Budgets**: Enforces spend caps per team.
- **Graceful Free-Tier Downgrade**: Seamlessly downgrades requests to $0 free-tier models rather than hard-failing when budgets are reached.
- **Sliding-Window Rate Limiter**: Redis-backed token bucket & request rate limits.

### 6. Traffic Engineering & Smart Routing
- **Dark Shadow Traffic Mirroring**: Asynchronously duplicates live traffic samples to candidate models with zero impact on client latency.
- **Context-Length Routing**: Automatically routes prompts (>8K tokens) to large context windows and short prompts (<2K tokens) to fast models.
- **Canary & A/B Testing**: Deterministic user routing based on `hash(user_id) % 100`.

### 7. Reliability & Resilience
- **Exponential Backoff with Full Jitter** on transient 429/5xx errors.
- **Stateful Circuit Breaker** (`CLOSED`, `OPEN`, `HALF_OPEN`) per provider.
- **Automatic Fallback Chains**: Seamless failover to secondary providers on outage.
- **Request Hedging**: Speculative execution firing secondary provider after timeout threshold.
- **Dead Letter Queue (DLQ)**: Captures fatal failures with one-click manual or automated replay.

### 8. Dynamic Prompt Registry & Automated Evals
- Versioned prompt templates with automatic variable extraction, tag filtering, and one-click execution.
- Automated heuristic evaluations: JSON schema enforcement, prompt leakage checks, safety scanning, and ground-truth keyword scoring.

---

## ⚡ Quick Start

### 1. Local Development (Zero Budget / Zero Setup)

```bash
# Clone the repository
git clone https://github.com/devendrasinghjodha/prodllmgateway.git
cd prodllmgateway

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Run the gateway (SQLite fallback + in-memory cache enabled automatically)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Access the services:
- **Operations Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🎯 Usage Examples

### Using OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="pllm_admin_secret_key_prodllm"
)

response = client.chat.completions.create(
    model="auto",  # Automatically routes to fastest/healthiest model
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Explain how distributed consensus works."}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)
```

### Using cURL

```bash
# Chat Completion (Auto Routing)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer pllm_admin_secret_key_prodllm" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "What is WebAssembly?"}]
  }'

# Semantic Cache Hit (Warm Cache ~3ms)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer pllm_admin_secret_key_prodllm" \
  -d '{
    "model": "gemini",
    "messages": [{"role": "user", "content": "Can you explain what WebAssembly is?"}]
  }'
```

---

## 🌐 Supported Providers

| Provider | Supported Models | Routing Alias | Key Features |
| :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini-1.5-flash`, `gemini-1.5-pro` | `gemini`, `auto` | Free-Tier, 1M+ Context, Universal Tools |
| **OpenRouter** | `meta-llama/llama-3.3-70b-instruct:free`, `deepseek/deepseek-r1:free` | `openrouter`, `auto` | Free Open-Source Models, Fast Inference |
| **Agnes AI** | `agnes-standard`, `agnes-pro` | `agnes`, `fast` | Low-Latency Production Endpoint |
| **Mock Provider** | `mock-gpt-4o` | `mock` | Local Testing & CI/CD Pipelines |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat completion (Streaming & Non-Streaming) |
| `POST` | `/v1/embeddings` | Vector embeddings generation |
| `POST` | `/v1/images/generations` | Image generation routing |
| `POST` | `/v1/audio/transcriptions` | Speech-to-text audio transcriptions |
| `GET` | `/v1/models` | Available model catalog and routing aliases |
| `GET` | `/v1/prompts` | List versioned prompt templates |
| `POST` | `/v1/prompts` | Create or update prompt template |
| `POST` | `/v1/prompts/{name}/execute` | Render template and execute completion |
| `POST` | `/v1/feedback` | Submit end-user ratings & CSAT telemetry |
| `POST` | `/v1/evals/test` | Run automated heuristic checks on LLM responses |
| `POST` | `/v1/batches` | OpenAI Batch API bulk async processor |
| `GET/POST` | `/v1/dlq` | Dead Letter Queue list and item replay |
| `GET` | `/health` | Liveness, readiness, and provider health checks |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint |
| `GET` | `/dashboard` | Embedded real-time operations control plane |

---

## 💻 CLI Tooling

ProdLLM includes a CLI utility (`cli.py`):

```bash
# Run system diagnostics
python cli.py doctor

# Manage tenant API keys
python cli.py keys create --user-id dev_alex --name "Alex Engineer" --team team_ai
python cli.py keys list

# View real-time cluster stats
python cli.py stats
```

---

## 🐳 Production Deployment

### Docker Compose (Full Observability Stack)

Start the entire stack including Gateway, PostgreSQL, Redis, Prometheus, Grafana, and Jaeger:

```bash
docker compose up -d
```

| Service | Endpoint | Credentials |
| :--- | :--- | :--- |
| **ProdLLM Gateway** | `http://localhost:8000` | `Bearer pllm_admin_secret_key_prodllm` |
| **Operations Dashboard** | `http://localhost:8000/dashboard` | Public |
| **Prometheus** | `http://localhost:9090` | Public |
| **Grafana Dashboard** | `http://localhost:3000` | `admin` / `admin` |
| **Jaeger UI** | `http://localhost:16686` | Public |

### Kubernetes Deployment

```bash
# Apply all Kubernetes manifests
kubectl apply -k k8s/

# Verify pods
kubectl get pods -n prodllm
```

---

## 🧪 Testing & Quality Assurance

Run the comprehensive unit, integration, and load testing suites:

```bash
# Run all unit and integration tests with coverage
make test-coverage

# Run load benchmark (k6)
make bench
```

---

## 📄 License

This project is licensed under the **Apache 2.0 License** — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 **Devendra Singh Jodha**.
