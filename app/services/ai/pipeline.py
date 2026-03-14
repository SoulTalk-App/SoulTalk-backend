"""Pipeline orchestrator — runs the full AI processing chain for a journal entry.

Steps:
1. Tag (Haiku) → commit entry_tags
2. Embed (Voyage AI) → commit embedding on entry_tags
3. Select mode (pure Python, no commit)
4. Retrieve (scenarios + similar entries + recent context)
5. Generate response (Sonnet) → commit ai_responses
6. Update journal_entries.ai_processing_status = "complete"

Each step is wrapped in try/except. On failure, status is set to "failed"
with the error stored. Prior steps are NOT rolled back.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entry_tags import EntryTags
from app.models.ai_response import AIResponse
from app.models.journal_entry import JournalEntry
from app.services.ai.tagging_service import tagging_service
from app.services.ai.embedding_service import embedding_service
from app.services.ai.mode_selector import select_mode
from app.services.ai.retrieval_service import retrieval_service
from app.services.ai.response_service import response_service
from app.services.ai.safety import is_crisis

logger = logging.getLogger(__name__)


async def process_journal_entry(
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    raw_text: str,
    created_at: datetime,
    session_maker: async_sessionmaker[AsyncSession],
    main_focus: str = "",
    tone_preference: str = "balanced",
) -> None:
    """Run the full AI pipeline for a single journal entry.

    Uses an independent DB session so it doesn't conflict with
    the request's session. Each step commits independently.
    """
    entry_id_str = str(entry_id)
    user_id_str = str(user_id)
    created_at_str = created_at.isoformat() if created_at else ""

    try:
        # ── Step 1: Tag ──
        logger.info(f"[Pipeline] Step 1: Tagging entry {entry_id_str}")
        tags = await tagging_service.tag_entry(
            raw_text=raw_text,
            entry_id=entry_id_str,
            user_id=user_id_str,
            created_at=created_at_str,
        )

        async with session_maker() as db:
            # Delete stale tags/response from prior failed runs
            old_tags = (await db.execute(
                select(EntryTags).where(EntryTags.entry_id == entry_id)
            )).scalar_one_or_none()
            if old_tags:
                await db.delete(old_tags)
            old_resp = (await db.execute(
                select(AIResponse).where(AIResponse.entry_id == entry_id)
            )).scalar_one_or_none()
            if old_resp:
                await db.delete(old_resp)
            await db.flush()

            entry_tags = EntryTags(
                entry_id=entry_id,
                user_id=user_id,
                schema_version="v1",
                tags=tags.model_dump(),
                emotion_primary=tags.emotions.primary,
                emotion_secondary=tags.emotions.secondary,
                emotion_intensity=tags.emotions.intensity,
                emotion_valence=tags.emotions.valence,
                nervous_system_state=tags.nervous_system.state,
                topics=list(tags.topics) if tags.topics else None,
                coping_mechanisms=[str(m) for m in tags.coping.mechanisms] if tags.coping.mechanisms else None,
                self_talk_style=tags.self_talk.style,
                self_talk_harshness=tags.self_talk.harshness_level,
                crisis_flag=tags.risk.crisis_flag,
                confidence_overall=tags.confidence.overall,
                insight_overload_risk=tags.load.insight_overload_risk,
                continuity_fear_present=tags.continuity.continuity_fear_present,
            )
            db.add(entry_tags)
            await _set_status(db, entry_id, "tagged")
            await db.commit()
            logger.info(f"[Pipeline] Step 1 complete: tags committed for {entry_id_str}")

        # ── Step 2: Embed ──
        logger.info(f"[Pipeline] Step 2: Embedding entry {entry_id_str}")
        vector = await embedding_service.embed(raw_text)

        async with session_maker() as db:
            result = await db.execute(
                select(EntryTags).where(EntryTags.entry_id == entry_id)
            )
            et = result.scalar_one()
            et.embedding = vector
            et.embedding_model = "voyage-3-lite"
            await db.commit()
            logger.info(f"[Pipeline] Step 2 complete: embedding committed for {entry_id_str}")

        # ── Step 3: Select mode ──
        logger.info(f"[Pipeline] Step 3: Selecting mode for {entry_id_str}")
        mode_result = select_mode(tags, tone_preference=tone_preference)
        logger.info(f"[Pipeline] Step 3 complete: mode={mode_result.mode}, hints={mode_result.hints}")

        # ── Step 4: Retrieve ──
        logger.info(f"[Pipeline] Step 4: Retrieving context for {entry_id_str}")
        async with session_maker() as db:
            scenarios = await retrieval_service.retrieve_scenarios(tags, db)

            similar_entries = []
            if not is_crisis(tags):
                similar_entries = await retrieval_service.retrieve_similar_entries(
                    embedding=vector,
                    user_id=user_id_str,
                    current_entry_id=entry_id_str,
                    db=db,
                )

            recent_context = await retrieval_service.build_recent_context(user_id_str, db)

        logger.info(f"[Pipeline] Step 4 complete: {len(scenarios)} scenarios, {len(similar_entries)} similar entries")

        # ── Step 5: Generate response ──
        logger.info(f"[Pipeline] Step 5: Generating response for {entry_id_str}")
        resp = await response_service.generate_response(
            raw_text=raw_text,
            tags=tags,
            mode_result=mode_result,
            scenarios=scenarios,
            recent_context=recent_context,
            main_focus=main_focus,
            tone_preference=tone_preference,
        )

        async with session_maker() as db:
            ai_resp = AIResponse(
                entry_id=entry_id,
                user_id=user_id,
                response_text=resp.text,
                mode=mode_result.mode,
                hints=mode_result.hints,
                model_used=resp.model_used,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                generation_time_ms=resp.generation_time_ms,
            )
            db.add(ai_resp)
            await db.commit()
            logger.info(f"[Pipeline] Step 5 complete: response committed for {entry_id_str}")

        # ── Step 6: Mark complete ──
        async with session_maker() as db:
            await _set_status(db, entry_id, "complete")
            await db.commit()

        logger.info(f"[Pipeline] Entry {entry_id_str} processing complete")

    except Exception as e:
        logger.error(f"[Pipeline] FAILED for entry {entry_id_str}: {type(e).__name__}: {e}")
        try:
            async with session_maker() as db:
                await _set_status(db, entry_id, "failed", error=str(e))
                await db.commit()
        except Exception as db_err:
            logger.error(f"[Pipeline] Failed to update status: {db_err}")
        raise


async def _set_status(
    db: AsyncSession,
    entry_id: uuid.UUID,
    status: str,
    error: str = None,
) -> None:
    """Update AI processing status on a journal entry."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.ai_processing_status = status
        entry.ai_processing_error = error
