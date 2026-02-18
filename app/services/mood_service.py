import uuid
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_mood import DailyMood


class MoodService:
    async def upsert_daily_mood(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        filled_count: int,
    ) -> DailyMood:
        today = date.today()
        result = await db.execute(
            select(DailyMood).where(
                DailyMood.user_id == user_id,
                DailyMood.date == today,
            )
        )
        mood = result.scalar_one_or_none()

        if mood:
            mood.filled_count = filled_count
            mood.updated_at = datetime.now(timezone.utc)
        else:
            mood = DailyMood(
                user_id=user_id,
                date=today,
                filled_count=filled_count,
            )
            db.add(mood)

        await db.flush()
        await db.refresh(mood)
        return mood

    async def get_daily_mood(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        target_date: Optional[date] = None,
    ) -> Optional[DailyMood]:
        if target_date is None:
            target_date = date.today()
        result = await db.execute(
            select(DailyMood).where(
                DailyMood.user_id == user_id,
                DailyMood.date == target_date,
            )
        )
        return result.scalar_one_or_none()
