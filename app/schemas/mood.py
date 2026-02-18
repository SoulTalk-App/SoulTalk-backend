from pydantic import BaseModel, Field
from datetime import date


class DailyMoodCreate(BaseModel):
    filled_count: int = Field(..., ge=0, le=15)


class DailyMoodResponse(BaseModel):
    date: date
    filled_count: int

    model_config = {"from_attributes": True}
