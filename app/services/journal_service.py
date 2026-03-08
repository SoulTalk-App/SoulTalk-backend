import uuid
from datetime import datetime, timezone, date
from typing import Optional, Tuple, List
from sqlalchemy import select, func, extract, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal_entry import JournalEntry


class JournalService:
    async def has_entry_today(self, db: AsyncSession, user_id: uuid.UUID) -> bool:
        """Check if the user already has a non-draft journal entry created today (UTC)."""
        today = date.today()
        result = await db.execute(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.user_id == user_id,
                JournalEntry.is_draft == False,
                cast(JournalEntry.created_at, Date) == today,
            )
        )
        return (result.scalar() or 0) > 0

    async def create_entry(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        raw_text: str,
        mood: Optional[str] = None,
        is_draft: bool = False,
    ) -> JournalEntry:
        entry = JournalEntry(
            user_id=user_id,
            raw_text=raw_text,
            mood=mood,
            is_draft=is_draft,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def get_entry(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JournalEntry:
        result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == entry_id,
                JournalEntry.user_id == user_id,
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ValueError("Journal entry not found")
        return entry

    async def list_entries(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
        mood: Optional[str] = None,
        ai_processing_status: Optional[str] = None,
        is_draft: Optional[bool] = False,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[JournalEntry], int]:
        query = select(JournalEntry).where(JournalEntry.user_id == user_id)
        count_query = select(func.count(JournalEntry.id)).where(JournalEntry.user_id == user_id)

        if is_draft is not None:
            query = query.where(JournalEntry.is_draft == is_draft)
            count_query = count_query.where(JournalEntry.is_draft == is_draft)
        if year is not None:
            query = query.where(extract("year", JournalEntry.created_at) == year)
            count_query = count_query.where(extract("year", JournalEntry.created_at) == year)
        if month is not None:
            query = query.where(extract("month", JournalEntry.created_at) == month)
            count_query = count_query.where(extract("month", JournalEntry.created_at) == month)
        if mood is not None:
            query = query.where(JournalEntry.mood == mood)
            count_query = count_query.where(JournalEntry.mood == mood)
        if ai_processing_status is not None:
            query = query.where(JournalEntry.ai_processing_status == ai_processing_status)
            count_query = count_query.where(JournalEntry.ai_processing_status == ai_processing_status)

        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated entries, newest first
        query = query.order_by(JournalEntry.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        entries = list(result.scalars().all())

        return entries, total

    async def update_entry(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        raw_text: Optional[str] = None,
        mood: Optional[str] = None,
        is_draft: Optional[bool] = None,
    ) -> JournalEntry:
        entry = await self.get_entry(db, entry_id, user_id)

        if raw_text is not None:
            entry.raw_text = raw_text
            # Reset processing status so pipeline re-runs
            entry.ai_processing_status = "none"
            entry.ai_processing_error = None
            entry.ai_processing_started_at = None
        if mood is not None:
            entry.mood = mood
        if is_draft is not None:
            entry.is_draft = is_draft

        entry.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def set_processing_status(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Update AI processing status on a journal entry."""
        result = await db.execute(
            select(JournalEntry).where(JournalEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ValueError("Journal entry not found")

        entry.ai_processing_status = status
        entry.ai_processing_error = error
        if status == "pending":
            entry.ai_processing_started_at = datetime.now(timezone.utc)
        entry.updated_at = datetime.now(timezone.utc)
        await db.flush()

    async def delete_entry(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        entry = await self.get_entry(db, entry_id, user_id)
        await db.delete(entry)
        await db.flush()
