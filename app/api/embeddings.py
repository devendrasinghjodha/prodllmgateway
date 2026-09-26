import time
from typing import List, Union, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx

from app.config import settings
from app.auth.api_keys import AuthenticatedUser
from app.auth.middleware import get_current_user
from app.utils.http_client import get_http_client
from app.cache.semantic import simple_embedding

embeddings_router = APIRouter(prefix="/v1", tags=["Embeddings"])


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = "text-embedding-3-small"
    user: Optional[str] = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


@embeddings_router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    body: EmbeddingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    OpenAI-compatible vector embeddings endpoint with fallback.
    """
    inputs = [body.input] if isinstance(body.input, str) else body.input
    embeddings_list = []
    total_prompt_tokens = 0

    # If Gemini API key configured, use Gemini Embeddings
    if settings.GEMINI_API_KEY:
        try:
            client = get_http_client()
            url = f"{settings.GEMINI_BASE_URL}/models/text-embedding-004:batchEmbedContents"
            requests_payload = [
                {"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}}
                for text in inputs
            ]
            resp = await client.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json={"requests": requests_payload},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                for idx, emb in enumerate(data.get("embeddings", [])):
                    values = emb.get("values", [])
                    embeddings_list.append(EmbeddingData(index=idx, embedding=values))
                total_prompt_tokens = sum(len(t.split()) for t in inputs)
                return EmbeddingResponse(
                    data=embeddings_list,
                    model=body.model,
                    usage=EmbeddingUsage(
                        prompt_tokens=total_prompt_tokens,
                        total_tokens=total_prompt_tokens,
                    ),
                )
        except Exception:
            pass

    # Fast high-performance local normalized embeddings fallback
    for idx, text in enumerate(inputs):
        vec = simple_embedding(text, dim=128)
        embeddings_list.append(EmbeddingData(index=idx, embedding=vec))
        total_prompt_tokens += max(1, len(text.split()))

    return EmbeddingResponse(
        data=embeddings_list,
        model=body.model,
        usage=EmbeddingUsage(
            prompt_tokens=total_prompt_tokens,
            total_tokens=total_prompt_tokens,
        ),
    )
