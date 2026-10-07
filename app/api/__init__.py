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

__all__ = [
    "admin_router",
    "audio_router",
    "batches_router",
    "chat_router",
    "dashboard_router",
    "embeddings_router",
    "feedback_router",
    "health_router",
    "images_router",
    "models_router",
    "prompts_router",
]
