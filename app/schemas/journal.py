from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MoodEnum(str, Enum):
    happy = "Happy"
    sad = "Sad"
    mad = "Mad"
    normal = "Normal"
    chill = "Chill"
    vibing = "Vibing"
    lost = "Lost"
    tired = "Tired"
    sexy = "Sexy"
    fire = "Fire"


class JournalEntryCreate(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=5000)
    mood: Optional[MoodEnum] = None
    is_draft: bool = False


class JournalEntryUpdate(BaseModel):
    raw_text: Optional[str] = Field(None, min_length=1, max_length=5000)
    mood: Optional[MoodEnum] = None
    is_draft: Optional[bool] = None


class TagsSummary(BaseModel):
    emotion_primary: Optional[str] = None
    emotion_secondary: Optional[str] = None
    emotion_intensity: Optional[int] = None
    nervous_system_state: Optional[str] = None
    topics: Optional[List[str]] = None
    coping_mechanisms: Optional[List[str]] = None
    self_talk_style: Optional[str] = None
    crisis_flag: bool = False

    model_config = {"from_attributes": True}


class AIResponseSummary(BaseModel):
    text: Optional[str] = None
    mode: Optional[str] = None

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: str
    raw_text: str
    mood: Optional[str] = None
    ai_processing_status: str = "none"
    is_draft: bool = False
    created_at: datetime
    updated_at: datetime
    tags: Optional[TagsSummary] = None
    ai_response: Optional[AIResponseSummary] = None

    model_config = {"from_attributes": True}


class JournalEntryListItem(BaseModel):
    id: str
    raw_text: str
    mood: Optional[str] = None
    ai_processing_status: str = "none"
    is_draft: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalEntryListResponse(BaseModel):
    entries: List[JournalEntryListItem]
    total: int
    page: int
    per_page: int
