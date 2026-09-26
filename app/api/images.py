import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.api_keys import AuthenticatedUser
from app.auth.middleware import get_current_user

images_router = APIRouter(prefix="/v1", tags=["Images"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "dall-e-3"
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[str] = "url"


class ImageData(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageResponse(BaseModel):
    created: int = int(time.time())
    data: List[ImageData]


@images_router.post("/images/generations", response_model=ImageResponse)
async def generate_images(
    body: ImageGenerationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    OpenAI-compatible Image Generation endpoint routing to multi-modal image generators.
    """
    # Demo placeholder / mock URL or upstream Imagen integration
    generated = [
        ImageData(
            url=f"https://images.prodllm.internal/generated/{hash(body.prompt)}_{i}.png",
            revised_prompt=body.prompt,
        )
        for i in range(body.n or 1)
    ]

    return ImageResponse(created=int(time.time()), data=generated)
