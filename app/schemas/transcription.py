from pydantic import BaseModel
from typing import Optional


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: Optional[float] = None
