import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import admin_router
from app.api.audio import audio_router
from app.api.batches import batches_router
from app.api.chat import chat_router
from app.api.dashboard import dashboard_router
from app.api.embeddings import embeddings_router
from app.api.feedback import feedback_router
from app.api.health import health_router
from app.api.images import images_router
from app.api.models import models_router
from app.api.prompts import prompts_router
from app.cache.redis import get_redis
from app.config import settings
from app.database.repository import init_db
from app.observability.logging import setup_logging
from app.observability.tracing import setup_tracing
from app.queue.priority_queue import scheduler
from app.routing.router import router
from app.utils.http_client import close_http_client

# Initialize Structured Logging
setup_logging()
logger = logging.getLogger("prodllm.main")

# Background Health Monitor Worker (Plan Section 14)
async def periodic_health_checker():
    logger.info("Starting background health check worker...")
    while True:
        try:
            await router.check_all_health()
        except Exception as e:
            logger.error(f"Health checker worker error: {e}")
        await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode...")
    
    # Initialize DB schema
    await init_db()
    
    # Initialize Redis connection
    await get_redis()
    
    # Start Priority Queue Worker Pool
    await scheduler.start_workers(num_workers=20)
    
    # Start background health monitoring task
    health_task = asyncio.create_task(periodic_health_checker(), name="health-check-loop")
    
    # Setup OpenTelemetry
    setup_tracing(app)
    
    logger.info(f"{settings.APP_NAME} started and ready to serve requests.")
    yield
    
    # 2. Shutdown
    logger.info("Shutting down ProdLLM Gateway...")
    health_task.cancel()
    await scheduler.stop_workers()
    await close_http_client()
    logger.info("ProdLLM Gateway shutdown complete.")


app = FastAPI(
    title="ProdLLM Gateway",
    description="High-performance, Zero-Budget AI Gateway with Smart Multi-Provider Routing, Distributed Caching, Circuit Breaking, and Observability.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Injects request_id / correlation_id into request state and response headers.
    Measures and logs total HTTP latency.
    """
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id
    start_time = time.time()

    response: Response = await call_next(request)

    latency_ms = (time.time() - start_time) * 1000
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"
    return response


# Include API Routers
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(embeddings_router)
app.include_router(images_router)
app.include_router(audio_router)
app.include_router(dashboard_router)
app.include_router(prompts_router)
app.include_router(feedback_router)
app.include_router(batches_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "ProdLLM Gateway",
        "version": "0.1.0",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "models": "/v1/models",
        "chat_completions": "/v1/chat/completions",
        "embeddings": "/v1/embeddings",
        "images": "/v1/images/generations",
        "audio": "/v1/audio/transcriptions",
        "prompts": "/v1/prompts",
        "feedback": "/v1/feedback",
        "batches": "/v1/batches",
        "dlq": "/v1/dlq",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
