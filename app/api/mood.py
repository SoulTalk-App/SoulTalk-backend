from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.api.deps import get_current_active_user
from app.services.mood_service import MoodService
from app.models.user import User
from app.schemas.mood import DailyMoodCreate, DailyMoodResponse

router = APIRouter()
mood_service = MoodService()


@router.put("/today", response_model=DailyMoodResponse)
async def upsert_today_mood(
    data: DailyMoodCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update today's mood bar count"""
    mood = await mood_service.upsert_daily_mood(
        db=db,
        user_id=current_user.id,
        filled_count=data.filled_count,
    )
    return DailyMoodResponse(date=mood.date, filled_count=mood.filled_count)


@router.get("/today", response_model=DailyMoodResponse)
async def get_today_mood(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get today's mood bar count"""
    mood = await mood_service.get_daily_mood(db=db, user_id=current_user.id)
    if mood:
        return DailyMoodResponse(date=mood.date, filled_count=mood.filled_count)
    from datetime import date
    return DailyMoodResponse(date=date.today(), filled_count=0)
