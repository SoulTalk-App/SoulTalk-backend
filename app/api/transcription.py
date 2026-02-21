from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.deps import get_current_active_user
from app.services.transcription_service import transcription_service
from app.schemas.transcription import TranscriptionResponse
from app.models.user import User

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "audio/m4a", "audio/x-m4a", "audio/mp4",
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/webm",
}
ALLOWED_EXTENSIONS = {".m4a", ".wav", ".mp3", ".webm"}
MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25MB


@router.post("/", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Transcribe an audio file using Whisper"""
    # Validate file extension
    filename = file.filename or "audio.m4a"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate size
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 25MB.",
        )

    result = await transcription_service.transcribe(audio_bytes, filename)
    return TranscriptionResponse(**result)
