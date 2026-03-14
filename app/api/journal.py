from fastapi import APIRouter, HTTPException, Depends, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timedelta, timezone
import uuid
import logging
import traceback

from app.db.dependencies import get_db
from app.db.session import async_session_maker
from app.api.deps import get_current_active_user
from app.services.journal_service import JournalService
from app.services.streak_service import streak_service
from app.services.soul_bar_service import soul_bar_service
from app.services.ai.pipeline import process_journal_entry
from app.api.ws import connection_manager
from app.models.user import User
from app.models.journal_entry import JournalEntry
from app.models.user_ai_profile import UserAIProfile
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalEntryListItem,
    JournalEntryListResponse,
    TagsSummary,
    AIResponseSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter()

journal_service = JournalService()


def _entry_response(entry) -> JournalEntryResponse:
    """Build response with optional tags and AI response from relationships."""
    tags = None
    if entry.entry_tags:
        et = entry.entry_tags
        tags = TagsSummary(
            emotion_primary=et.emotion_primary,
            emotion_secondary=et.emotion_secondary,
            emotion_intensity=et.emotion_intensity,
            nervous_system_state=et.nervous_system_state,
            topics=et.topics,
            coping_mechanisms=et.coping_mechanisms,
            self_talk_style=et.self_talk_style,
            crisis_flag=et.crisis_flag,
        )

    ai_resp = None
    if entry.ai_response:
        ai_resp = AIResponseSummary(
            text=entry.ai_response.response_text,
            mode=entry.ai_response.mode,
        )

    return JournalEntryResponse(
        id=str(entry.id),
        raw_text=entry.raw_text,
        mood=entry.mood,
        ai_processing_status=entry.ai_processing_status,
        is_draft=entry.is_draft,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=tags,
        ai_response=ai_resp,
    )


def _entry_list_item(entry) -> JournalEntryListItem:
    return JournalEntryListItem(
        id=str(entry.id),
        raw_text=entry.raw_text,
        mood=entry.mood,
        ai_processing_status=entry.ai_processing_status,
        is_draft=entry.is_draft,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def _run_pipeline(
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    raw_text: str,
    created_at: datetime,
):
    """Background task: run the full AI pipeline and push result via WebSocket."""
    logger.info(f"[AI] Pipeline starting for entry {entry_id}")
    try:
        # Fetch user AI profile for personalization
        main_focus = ""
        tone_preference = "balanced"
        async with async_session_maker() as db:
            result = await db.execute(
                select(UserAIProfile).where(UserAIProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                main_focus = profile.main_focus or ""
                tone_preference = profile.tone_preference or "balanced"

        await process_journal_entry(
            entry_id=entry_id,
            user_id=user_id,
            raw_text=raw_text,
            created_at=created_at,
            session_maker=async_session_maker,
            main_focus=main_focus,
            tone_preference=tone_preference,
        )

        # Push completion to mobile via WebSocket
        async with async_session_maker() as db:
            result = await db.execute(
                select(JournalEntry)
                .options(selectinload(JournalEntry.entry_tags))
                .options(selectinload(JournalEntry.ai_response))
                .where(JournalEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            if entry:
                payload = {
                    "event": "journal_ai_complete",
                    "entry_id": str(entry_id),
                    "ai_processing_status": entry.ai_processing_status,
                }
                if entry.ai_response:
                    payload["response_text"] = entry.ai_response.response_text
                    payload["mode"] = entry.ai_response.mode
                if entry.entry_tags:
                    payload["tags_summary"] = {
                        "emotion_primary": entry.entry_tags.emotion_primary,
                        "nervous_system_state": entry.entry_tags.nervous_system_state,
                        "crisis_flag": entry.entry_tags.crisis_flag,
                    }
                await connection_manager.send_to_user(str(user_id), payload)

        logger.info(f"[AI] Pipeline complete for entry {entry_id}")

    except Exception as e:
        logger.error(f"[AI] Pipeline FAILED for entry {entry_id}: {type(e).__name__}: {e}")
        logger.error(f"[AI] Traceback: {traceback.format_exc()}")


@router.post("/", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    data: JournalEntryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new journal entry"""
    # Enforce 1 non-draft entry per day
    if not data.is_draft:
        if await journal_service.has_entry_today(db, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already journaled today. Come back tomorrow!",
            )

    entry = await journal_service.create_entry(
        db=db,
        user_id=current_user.id,
        raw_text=data.raw_text,
        mood=data.mood.value if data.mood else None,
        is_draft=data.is_draft,
    )

    # Commit now so the background task's independent session can find the entry
    await db.commit()

    # Non-draft entries trigger streak, SoulBar, and AI analysis
    if not data.is_draft:
        async with async_session_maker() as side_db:
            try:
                await streak_service.record_journal_entry(side_db, current_user.id)
                await soul_bar_service.add_point(side_db, current_user.id)
                await side_db.commit()
            except Exception as e:
                await side_db.rollback()
                logger.error(f"[Journal] Streak/SoulBar update failed: {e}")

        background_tasks.add_task(
            _run_pipeline, entry.id, current_user.id, data.raw_text, entry.created_at
        )

    # Fresh entry has no tags/ai_response yet — return directly to avoid lazy load
    return JournalEntryResponse(
        id=str(entry.id),
        raw_text=entry.raw_text,
        mood=entry.mood,
        ai_processing_status=entry.ai_processing_status,
        is_draft=entry.is_draft,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=None,
        ai_response=None,
    )


@router.get("/", response_model=JournalEntryListResponse)
async def list_journal_entries(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    mood: Optional[str] = Query(None),
    ai_processing_status: Optional[str] = Query(None),
    is_draft: Optional[bool] = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries with optional filtering"""
    entries, total = await journal_service.list_entries(
        db=db,
        user_id=current_user.id,
        year=year,
        month=month,
        mood=mood,
        ai_processing_status=ai_processing_status,
        is_draft=is_draft,
        page=page,
        per_page=per_page,
    )
    return JournalEntryListResponse(
        entries=[_entry_list_item(e) for e in entries],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single journal entry with tags and AI response"""
    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.entry_tags))
        .options(selectinload(JournalEntry.ai_response))
        .where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == current_user.id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    # Re-trigger AI if it failed or stuck pending >5min
    if not entry.is_draft:
        should_retrigger = False
        if entry.ai_processing_status in ("failed", "none"):
            should_retrigger = True
        elif entry.ai_processing_status == "pending" and entry.ai_processing_started_at:
            if datetime.now(timezone.utc) - entry.ai_processing_started_at > timedelta(minutes=5):
                should_retrigger = True

        if should_retrigger:
            background_tasks.add_task(
                _run_pipeline, entry.id, current_user.id, entry.raw_text, entry.created_at
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
        # Get the entry before update to check draft status transition
        old_entry = await journal_service.get_entry(db, entry_id, current_user.id)
        was_draft = old_entry.is_draft

        # Enforce 1 non-draft entry per day when finalizing a draft
        if was_draft and data.is_draft is False:
            if await journal_service.has_entry_today(db, current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already journaled today. Come back tomorrow!",
                )

        entry = await journal_service.update_entry(
            db=db,
            entry_id=entry_id,
            user_id=current_user.id,
            raw_text=data.raw_text,
            mood=data.mood.value if data.mood else None,
            is_draft=data.is_draft,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Commit so background task can see updates
    await db.commit()

    # Draft finalized → trigger streak + SoulBar + AI
    if was_draft and data.is_draft is False:
        async with async_session_maker() as side_db:
            try:
                await streak_service.record_journal_entry(side_db, current_user.id)
                await soul_bar_service.add_point(side_db, current_user.id)
                await side_db.commit()
            except Exception as e:
                await side_db.rollback()
                logger.error(f"[Journal] Streak/SoulBar update failed: {e}")

        background_tasks.add_task(
            _run_pipeline, entry_id, current_user.id, entry.raw_text, entry.created_at
        )
    elif not was_draft and data.raw_text is not None:
        # Text changed on non-draft: re-trigger AI only (streak/SoulBar already counted)
        background_tasks.add_task(
            _run_pipeline, entry_id, current_user.id, data.raw_text, entry.created_at
        )

    # Entry was loaded without selectinload — return directly to avoid lazy load
    return JournalEntryResponse(
        id=str(entry.id),
        raw_text=entry.raw_text,
        mood=entry.mood,
        ai_processing_status=entry.ai_processing_status,
        is_draft=entry.is_draft,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=None,
        ai_response=None,
    )


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
