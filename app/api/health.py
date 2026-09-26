import time
from typing import Dict
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.routing.router import router
from app.reliability.circuit_breaker import circuit_breakers
from app.database.repository import get_db_session, DatabaseRepository
from app.observability.metrics import get_metrics_payload, CONTENT_TYPE_LATEST

health_router = APIRouter(tags=["Health & Telemetry"])


@health_router.get("/health")
async def health():
    """Liveness & Readiness probe endpoint for Kubernetes / Load Balancer."""
    return {
        "status": "healthy",
        "service": "prodllm-gateway",
        "timestamp": time.time(),
        "circuit_breakers": circuit_breakers.all_states(),
    }


@health_router.get("/health/providers")
async def health_providers():
    """Detailed health check and latency stats across all upstream LLM providers."""
    health_results = await router.check_all_health()
    return {
        "timestamp": time.time(),
        "providers": {
            name: {
                "status": h.status,
                "latency_ms": h.latency_ms,
                "error": h.error,
                "circuit_state": circuit_breakers.get_breaker(name).state.value,
            }
            for name, h in health_results.items()
        },
    }


@health_router.get("/metrics")
async def metrics():
    """Prometheus exposition format metrics endpoint."""
    return Response(content=get_metrics_payload(), media_type=CONTENT_TYPE_LATEST)


@health_router.get("/admin/stats")
async def get_stats(db: AsyncSession = Depends(get_db_session)):
    """Database request audit summary statistics."""
    repo = DatabaseRepository(db)
    summary = await repo.get_usage_summary()
    return {
        "status": "success",
        "usage_summary": summary,
        "circuit_breakers": circuit_breakers.all_states(),
    }
