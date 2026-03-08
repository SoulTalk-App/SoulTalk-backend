from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AIProfileUpdate(BaseModel):
    main_focus: Optional[str] = None
    tone_preference: Optional[str] = "balanced"
    spiritual_metadata: Optional[dict] = None
    soulpal_name: Optional[str] = None


class AIProfileResponse(BaseModel):
    main_focus: Optional[str] = None
    tone_preference: str = "balanced"
    spiritual_metadata: Optional[dict] = None
    soulpal_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
