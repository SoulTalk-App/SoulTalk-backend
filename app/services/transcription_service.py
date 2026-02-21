import io
import logging
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(self, audio_bytes: bytes, filename: str) -> dict:
        logger.info(f"[Transcription] Starting transcription for {filename} ({len(audio_bytes)} bytes)")
        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = filename

        transcription = await self.client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
        )

        logger.info(f"[Transcription] Complete: {len(transcription.text)} chars")
        return {
            "text": transcription.text,
            "duration_seconds": getattr(transcription, "duration", None),
        }


transcription_service = TranscriptionService()
