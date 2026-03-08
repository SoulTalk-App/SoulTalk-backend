from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.deps import get_current_active_user
from app.schemas.transcription import TranscriptionResponse
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Placeholder for future server-side transcription.

    Currently the mobile app uses on-device transcription.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Server-side transcription is not yet implemented. Use on-device transcription.",
    )
