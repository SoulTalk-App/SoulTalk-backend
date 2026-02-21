from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.api.deps import get_current_active_user
from app.services.streak_service import streak_service
from app.schemas.streak import StreakResponse
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=StreakResponse)
async def get_streak(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's journal streak"""
    streak = await streak_service.get_or_create(db, current_user.id)
    return StreakResponse(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_journal_date=streak.last_journal_date,
    )
