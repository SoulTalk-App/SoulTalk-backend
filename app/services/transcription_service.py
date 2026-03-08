import logging

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Placeholder for future server-side transcription integration.

    Currently the mobile app uses on-device transcription.
    This service will be implemented when server-side transcription is needed.
    """

    async def transcribe(self, audio_bytes: bytes, filename: str) -> dict:
        raise NotImplementedError("Server-side transcription is not yet implemented")


transcription_service = TranscriptionService()
