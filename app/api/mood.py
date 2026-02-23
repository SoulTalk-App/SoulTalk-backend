from fastapi import APIRouter, Depends
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.api.deps import get_current_active_user
from app.services.mood_service import MoodService
from app.services.soul_bar_service import soul_bar_service
from app.models.user import User
from app.schemas.mood import DailyMoodCreate, DailyMoodResponse

logger = logging.getLogger(__name__)
router = APIRouter()
mood_service = MoodService()


@router.put("/today", response_model=DailyMoodResponse)
async def upsert_today_mood(
    data: DailyMoodCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update today's mood bar count"""
    mood, is_first_fill = await mood_service.upsert_daily_mood(
        db=db,
        user_id=current_user.id,
        filled_count=data.filled_count,
    )

    # Award 0.5 SoulBar point the first time the user fills the mood bar today
    if is_first_fill:
        try:
            await soul_bar_service.add_point(db, current_user.id, amount=0.5)
        except Exception as e:
            logger.error(f"[Mood] SoulBar award failed: {e}")

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
