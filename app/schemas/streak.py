from pydantic import BaseModel
from typing import Optional
from datetime import date


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_journal_date: Optional[date] = None

    model_config = {"from_attributes": True}
