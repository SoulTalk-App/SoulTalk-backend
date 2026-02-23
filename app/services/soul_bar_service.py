import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.soul_bar import SoulBar


class SoulBarService:
    async def get_or_create(self, db: AsyncSession, user_id: uuid.UUID) -> SoulBar:
        result = await db.execute(
            select(SoulBar).where(SoulBar.user_id == user_id)
        )
        bar = result.scalar_one_or_none()
        if not bar:
            bar = SoulBar(user_id=user_id)
            db.add(bar)
            await db.flush()
            await db.refresh(bar)
        return bar

    async def add_point(self, db: AsyncSession, user_id: uuid.UUID, amount: float = 1.0) -> SoulBar:
        bar = await self.get_or_create(db, user_id)
        bar.points += amount
        if bar.points >= 6:
            bar.total_filled += 1
            bar.points = 0.0
        bar.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(bar)
        return bar


soul_bar_service = SoulBarService()
