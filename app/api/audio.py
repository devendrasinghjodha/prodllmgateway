
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.auth.api_keys import AuthenticatedUser
from app.auth.middleware import get_current_user

audio_router = APIRouter(prefix="/v1/audio", tags=["Audio"])


class TranscriptionResponse(BaseModel):
    text: str


@audio_router.post("/transcriptions", response_model=TranscriptionResponse)
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str | None = Form(None),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    OpenAI-compatible Audio Transcription (Speech-to-Text) endpoint.
    """
    filename = file.filename or "audio.mp3"
    return TranscriptionResponse(
        text=f"Transcribed audio file '{filename}' using model '{model}'."
    )
