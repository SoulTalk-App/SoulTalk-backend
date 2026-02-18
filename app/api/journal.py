from fastapi import APIRouter, HTTPException, Depends, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
import logging

from app.db.dependencies import get_db
from app.db.session import async_session_maker
from app.api.deps import get_current_active_user
from app.services.journal_service import JournalService
from app.services.ai_service import ai_service
from app.api.ws import connection_manager
from app.models.user import User
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalEntryListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

journal_service = JournalService()


def _entry_response(entry) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=str(entry.id),
        raw_text=entry.raw_text,
        mood=entry.mood,
        emotion_primary=entry.emotion_primary,
        emotion_secondary=entry.emotion_secondary,
        emotion_intensity=entry.emotion_intensity,
        nervous_system_state=entry.nervous_system_state,
        topics=entry.topics,
        coping_mechanisms=entry.coping_mechanisms,
        self_talk_style=entry.self_talk_style,
        time_focus=entry.time_focus,
        ai_response=entry.ai_response,
        is_ai_processed=entry.is_ai_processed,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def process_journal_ai(entry_id: uuid.UUID, user_id: uuid.UUID, raw_text: str):
    """Background task: analyze journal entry via OpenAI and push result via WebSocket."""
    try:
        analysis = await ai_service.analyze_journal_entry(raw_text)

        async with async_session_maker() as db:
            try:
                entry = await journal_service.update_ai_fields(
                    db=db,
                    entry_id=entry_id,
                    emotion_primary=analysis.emotion_primary,
                    emotion_secondary=analysis.emotion_secondary,
                    emotion_intensity=analysis.emotion_intensity,
                    nervous_system_state=analysis.nervous_system_state,
                    topics=analysis.topics,
                    coping_mechanisms=analysis.coping_mechanisms,
                    self_talk_style=analysis.self_talk_style,
                    time_focus=analysis.time_focus,
                    ai_response=analysis.ai_response,
                )
                await db.commit()

                # Push to mobile via WebSocket
                await connection_manager.send_to_user(str(user_id), {
                    "event": "journal_ai_complete",
                    "entry_id": str(entry_id),
                    "emotion_primary": analysis.emotion_primary,
                    "emotion_secondary": analysis.emotion_secondary,
                    "emotion_intensity": analysis.emotion_intensity,
                    "nervous_system_state": analysis.nervous_system_state,
                    "topics": analysis.topics,
                    "coping_mechanisms": analysis.coping_mechanisms,
                    "self_talk_style": analysis.self_talk_style,
                    "time_focus": analysis.time_focus,
                    "ai_response": analysis.ai_response,
                    "is_ai_processed": True,
                })
            except Exception:
                await db.rollback()
                raise

    except Exception as e:
        logger.error(f"AI processing failed for entry {entry_id}: {e}")


@router.post("/", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    data: JournalEntryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new journal entry"""
    entry = await journal_service.create_entry(
        db=db,
        user_id=current_user.id,
        raw_text=data.raw_text,
        mood=data.mood.value if data.mood else None,
    )

    # Schedule AI analysis in background
    background_tasks.add_task(process_journal_ai, entry.id, current_user.id, data.raw_text)

    return _entry_response(entry)


@router.get("/", response_model=JournalEntryListResponse)
async def list_journal_entries(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    mood: Optional[str] = Query(None),
    is_ai_processed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries with optional year/month/mood/reflected filtering"""
    entries, total = await journal_service.list_entries(
        db=db,
        user_id=current_user.id,
        year=year,
        month=month,
        mood=mood,
        is_ai_processed=is_ai_processed,
        page=page,
        per_page=per_page,
    )
    return JournalEntryListResponse(
        entries=[_entry_response(e) for e in entries],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single journal entry"""
    try:
        entry = await journal_service.get_entry(db, entry_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return _entry_response(entry)


@router.put("/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: uuid.UUID,
    data: JournalEntryUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a journal entry"""
    try:
        entry = await journal_service.update_entry(
            db=db,
            entry_id=entry_id,
            user_id=current_user.id,
            raw_text=data.raw_text,
            mood=data.mood.value if data.mood else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Re-analyze if text changed
    if data.raw_text is not None:
        background_tasks.add_task(process_journal_ai, entry_id, current_user.id, data.raw_text)

    return _entry_response(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journal_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a journal entry"""
    try:
        await journal_service.delete_entry(db, entry_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
