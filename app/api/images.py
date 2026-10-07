import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.api_keys import AuthenticatedUser
from app.auth.middleware import get_current_user

images_router = APIRouter(prefix="/v1", tags=["Images"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str | None = "dall-e-3"
    n: int | None = 1
    size: str | None = "1024x1024"
    response_format: str | None = "url"


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageResponse(BaseModel):
    created: int = int(time.time())
    data: list[ImageData]


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
