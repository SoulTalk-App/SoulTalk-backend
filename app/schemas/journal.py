from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MoodEnum(str, Enum):
    happy = "Happy"
    sad = "Sad"
    mad = "Mad"
    normal = "Normal"


class JournalEntryCreate(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=5000)
    mood: Optional[MoodEnum] = None


class JournalEntryUpdate(BaseModel):
    raw_text: Optional[str] = Field(None, min_length=1, max_length=5000)
    mood: Optional[MoodEnum] = None


class JournalEntryResponse(BaseModel):
    id: str
    raw_text: str
    mood: Optional[str] = None
    emotion_primary: Optional[str] = None
    emotion_secondary: Optional[str] = None
    emotion_intensity: Optional[int] = None
    nervous_system_state: Optional[str] = None
    topics: Optional[list] = None
    coping_mechanisms: Optional[list] = None
    self_talk_style: Optional[str] = None
    time_focus: Optional[str] = None
    ai_response: Optional[str] = None
    is_ai_processed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalEntryListResponse(BaseModel):
    entries: List[JournalEntryResponse]
    total: int
    page: int
    per_page: int
