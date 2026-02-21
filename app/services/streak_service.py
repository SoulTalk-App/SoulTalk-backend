import uuid
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_streak import UserStreak


class StreakService:
    async def get_or_create(self, db: AsyncSession, user_id: uuid.UUID) -> UserStreak:
        result = await db.execute(
            select(UserStreak).where(UserStreak.user_id == user_id)
        )
        streak = result.scalar_one_or_none()
        if not streak:
            streak = UserStreak(user_id=user_id)
            db.add(streak)
            await db.flush()
            await db.refresh(streak)
        return streak

    async def record_journal_entry(self, db: AsyncSession, user_id: uuid.UUID) -> UserStreak:
        streak = await self.get_or_create(db, user_id)
        today = date.today()

        if streak.last_journal_date == today:
            return streak

        if streak.last_journal_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak

        streak.last_journal_date = today
        streak.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(streak)
        return streak


streak_service = StreakService()
