import time
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

models_router = APIRouter(prefix="/v1", tags=["Models"])


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = int(time.time())
    owned_by: str = "prodllm"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelCard]


SUPPORTED_MODELS = [
    # Virtual Routing Aliases
    ModelCard(id="auto", owned_by="prodllm-router"),
    ModelCard(id="fast", owned_by="prodllm-router"),
    ModelCard(id="cheap", owned_by="prodllm-router"),
    ModelCard(id="local", owned_by="prodllm-router"),
    # Gemini Models
    ModelCard(id="gemini", owned_by="google"),
    ModelCard(id="gemini-1.5-flash", owned_by="google"),
    ModelCard(id="gemini-1.5-pro", owned_by="google"),
    ModelCard(id="gemini-2.0-flash", owned_by="google"),
    # OpenRouter Models
    ModelCard(id="openrouter", owned_by="openrouter"),
    ModelCard(id="meta-llama/llama-3.2-3b-instruct:free", owned_by="meta"),
    ModelCard(id="google/gemini-2.0-flash-exp:free", owned_by="google"),
    # Agnes AI Models
    ModelCard(id="agnes", owned_by="agnes-ai"),
    ModelCard(id="agnes-standard", owned_by="agnes-ai"),
    ModelCard(id="agnes-pro", owned_by="agnes-ai"),
    # Mock Provider
    ModelCard(id="mock", owned_by="prodllm-bench"),
]


@models_router.get("/models", response_model=ModelListResponse)
async def list_models():
    """List available LLM models and gateway virtual aliases."""
    return ModelListResponse(data=SUPPORTED_MODELS)
