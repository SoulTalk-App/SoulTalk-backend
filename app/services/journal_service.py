import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal_entry import JournalEntry


class JournalService:
    async def create_entry(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        raw_text: str,
        mood: Optional[str] = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            user_id=user_id,
            raw_text=raw_text,
            mood=mood,
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
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[JournalEntry], int]:
        query = select(JournalEntry).where(JournalEntry.user_id == user_id)
        count_query = select(func.count(JournalEntry.id)).where(JournalEntry.user_id == user_id)

        if year is not None:
            query = query.where(extract("year", JournalEntry.created_at) == year)
            count_query = count_query.where(extract("year", JournalEntry.created_at) == year)
        if month is not None:
            query = query.where(extract("month", JournalEntry.created_at) == month)
            count_query = count_query.where(extract("month", JournalEntry.created_at) == month)

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
    ) -> JournalEntry:
        entry = await self.get_entry(db, entry_id, user_id)

        if raw_text is not None:
            entry.raw_text = raw_text
            # Reset AI fields so they get re-analyzed
            entry.emotion_primary = None
            entry.emotion_secondary = None
            entry.emotion_intensity = None
            entry.nervous_system_state = None
            entry.topics = None
            entry.coping_mechanisms = None
            entry.self_talk_style = None
            entry.time_focus = None
            entry.ai_response = None
            entry.is_ai_processed = False
        if mood is not None:
            entry.mood = mood

        entry.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def update_ai_fields(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        emotion_primary: Optional[str] = None,
        emotion_secondary: Optional[str] = None,
        emotion_intensity: Optional[int] = None,
        nervous_system_state: Optional[str] = None,
        topics: Optional[list] = None,
        coping_mechanisms: Optional[list] = None,
        self_talk_style: Optional[str] = None,
        time_focus: Optional[str] = None,
        ai_response: Optional[str] = None,
    ) -> JournalEntry:
        """Internal method to update AI analysis fields on a journal entry."""
        result = await db.execute(
            select(JournalEntry).where(JournalEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ValueError("Journal entry not found")

        entry.emotion_primary = emotion_primary
        entry.emotion_secondary = emotion_secondary
        entry.emotion_intensity = emotion_intensity
        entry.nervous_system_state = nervous_system_state
        entry.topics = topics
        entry.coping_mechanisms = coping_mechanisms
        entry.self_talk_style = self_talk_style
        entry.time_focus = time_focus
        entry.ai_response = ai_response
        entry.is_ai_processed = True
        entry.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(entry)
        return entry

    async def delete_entry(
        self,
        db: AsyncSession,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        entry = await self.get_entry(db, entry_id, user_id)
        await db.delete(entry)
        await db.flush()
