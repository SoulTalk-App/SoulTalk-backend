"""Pipeline test runner — feeds persona journal entries through the full AI pipeline.

Exercises: Tag (Haiku) → Embed (Voyage) → Mode Select → Retrieve → Respond (Sonnet)
Reports: tag quality, mode accuracy, response quality, and DB storage validation.

Usage:
    python -m tests.test_pipeline [--persona maya] [--dry-run] [--skip-embed] [--skip-respond]

Requires:
    - PostgreSQL running with pgvector and migrations applied
    - ANTHROPIC_API_KEY and VOYAGE_API_KEY set in env
    - Scenario playbooks seeded (migration 016)
"""

import asyncio
import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import async_session_maker, engine
from app.models.user import User
from app.models.journal_entry import JournalEntry
from app.models.entry_tags import EntryTags
from app.models.ai_response import AIResponse
from app.models.user_ai_profile import UserAIProfile
from app.services.ai.tagging_service import tagging_service
from app.services.ai.embedding_service import embedding_service
from app.services.ai.mode_selector import select_mode, ModeResult
from app.services.ai.retrieval_service import retrieval_service
from app.services.ai.response_service import response_service
from app.services.ai.safety import is_crisis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PERSONAS_PATH = Path(__file__).parent / "test_data" / "personas.json"

# Test user email domain — easy to identify and clean up
TEST_EMAIL_DOMAIN = "test.soultalk.local"


def load_personas(filter_id: str | None = None) -> list[dict]:
    with open(PERSONAS_PATH) as f:
        data = json.load(f)
    personas = data["personas"]
    if filter_id:
        personas = [p for p in personas if p["id"] == filter_id]
        if not personas:
            raise ValueError(f"Persona '{filter_id}' not found. Available: {[p['id'] for p in data['personas']]}")
    return personas


async def create_test_user(db: AsyncSession, persona: dict) -> User:
    """Create or fetch a test user for this persona."""
    email = f"{persona['id']}@{TEST_EMAIL_DOMAIN}"

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        logger.info(f"  Found existing test user: {email} ({user.id})")
        return user

    name_parts = persona["name"].split(" ", 1)
    user = User(
        id=uuid.uuid4(),
        email=email,
        first_name=name_parts[0],
        last_name=name_parts[1] if len(name_parts) > 1 else "",
        password_hash="test-not-a-real-hash",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    logger.info(f"  Created test user: {email} ({user.id})")
    return user


async def create_ai_profile(db: AsyncSession, user_id: uuid.UUID, profile_data: dict) -> None:
    """Create or update the AI profile for a test user."""
    result = await db.execute(select(UserAIProfile).where(UserAIProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserAIProfile(user_id=user_id)
        db.add(profile)

    profile.main_focus = profile_data.get("main_focus", "")
    profile.tone_preference = profile_data.get("tone_preference", "balanced")
    profile.soulpal_name = profile_data.get("soulpal_name")
    if "spiritual_metadata" in profile_data:
        profile.spiritual_metadata = profile_data["spiritual_metadata"]

    await db.flush()


async def create_journal_entry(
    db: AsyncSession,
    user_id: uuid.UUID,
    entry_data: dict,
    day_offset: int,
) -> JournalEntry:
    """Create a journal entry for a test persona."""
    entry_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc) - timedelta(days=15 - day_offset)

    entry = JournalEntry(
        id=entry_id,
        user_id=user_id,
        raw_text=entry_data["text"],
        mood=entry_data.get("mood"),
        is_draft=False,
        ai_processing_status="pending",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(entry)
    await db.flush()
    return entry


async def run_pipeline_for_entry(
    entry: JournalEntry,
    user_id: uuid.UUID,
    tone_preference: str,
    main_focus: str,
    expected_mode: str | None,
    skip_embed: bool,
    skip_respond: bool,
) -> dict:
    """Run the pipeline steps individually so we can inspect each result."""

    result = {
        "entry_id": str(entry.id),
        "day": None,
        "text_preview": entry.raw_text[:80] + "...",
        "tags": None,
        "mode": None,
        "expected_mode": expected_mode,
        "mode_match": None,
        "hints": [],
        "scenarios_count": 0,
        "similar_count": 0,
        "response_preview": None,
        "response_mode": None,
        "tokens": {"input": 0, "output": 0},
        "error": None,
    }

    try:
        # Step 1: Tag
        tags = await tagging_service.tag_entry(
            raw_text=entry.raw_text,
            entry_id=str(entry.id),
            user_id=str(user_id),
            created_at=entry.created_at.isoformat(),
        )

        result["tags"] = {
            "emotion_primary": tags.emotions.primary,
            "emotion_secondary": tags.emotions.secondary,
            "emotion_intensity": tags.emotions.intensity,
            "valence": tags.emotions.valence,
            "blend": tags.emotions.blend,
            "ns_state": tags.nervous_system.state,
            "somatic_cues": tags.nervous_system.somatic_cues,
            "topics": list(tags.topics),
            "coping": list(tags.coping.mechanisms) if tags.coping.mechanisms else [],
            "self_talk_style": tags.self_talk.style,
            "self_talk_harshness": tags.self_talk.harshness_level,
            "distortions": list(tags.cognition.distortions) if tags.cognition.distortions else [],
            "loops": list(tags.cognition.loops) if tags.cognition.loops else [],
            "crisis_flag": tags.risk.crisis_flag,
            "confidence_overall": tags.confidence.overall,
            "load": {
                "self_surveillance": tags.load.self_surveillance_present,
                "insight_overload": tags.load.insight_overload_risk,
                "self_fixing": tags.load.self_fixing_pressure,
            },
            "continuity": {
                "fear_present": tags.continuity.continuity_fear_present,
                "fear_of_forgetting": tags.continuity.fear_of_forgetting_ideas,
                "momentum_dependence": tags.continuity.momentum_dependence,
            },
        }

        # Save tags to DB
        async with async_session_maker() as db:
            entry_tags = EntryTags(
                entry_id=entry.id,
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
            await db.commit()

        # Step 2: Embed
        vector = None
        if not skip_embed:
            vector = await embedding_service.embed(entry.raw_text)
            async with async_session_maker() as db:
                et_result = await db.execute(
                    select(EntryTags).where(EntryTags.entry_id == entry.id)
                )
                et = et_result.scalar_one()
                et.embedding = vector
                et.embedding_model = "voyage-3-lite"
                await db.commit()

        # Step 3: Mode select
        mode_result = select_mode(tags, tone_preference=tone_preference)
        result["mode"] = mode_result.mode
        result["hints"] = mode_result.hints
        result["mode_match"] = (mode_result.mode == expected_mode) if expected_mode else None

        # Step 4: Retrieve
        async with async_session_maker() as db:
            scenarios = await retrieval_service.retrieve_scenarios(tags, db)
            result["scenarios_count"] = len(scenarios)

            similar_entries = []
            if not skip_embed and vector and not is_crisis(tags):
                similar_entries = await retrieval_service.retrieve_similar_entries(
                    embedding=vector,
                    user_id=str(user_id),
                    current_entry_id=str(entry.id),
                    db=db,
                )
            result["similar_count"] = len(similar_entries)

            recent_context = await retrieval_service.build_recent_context(str(user_id), db)

        # Step 5: Respond
        if not skip_respond:
            resp = await response_service.generate_response(
                raw_text=entry.raw_text,
                tags=tags,
                mode_result=mode_result,
                scenarios=scenarios,
                recent_context=recent_context,
                main_focus=main_focus,
                tone_preference=tone_preference,
            )
            result["response_preview"] = resp.text[:200] + "..." if len(resp.text) > 200 else resp.text
            result["response_mode"] = mode_result.mode
            result["tokens"] = {"input": resp.input_tokens, "output": resp.output_tokens}

            # Save response to DB
            async with async_session_maker() as db:
                ai_resp = AIResponse(
                    entry_id=entry.id,
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

                # Update journal entry status
                je_result = await db.execute(
                    select(JournalEntry).where(JournalEntry.id == entry.id)
                )
                je = je_result.scalar_one()
                je.ai_processing_status = "complete"
                await db.commit()

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.error(f"  Pipeline error: {result['error']}")

    return result


async def cleanup_persona(db: AsyncSession, persona_id: str) -> None:
    """Remove all test data for a persona."""
    email = f"{persona_id}@{TEST_EMAIL_DOMAIN}"
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        return

    # Delete in order: ai_responses, entry_tags, journal_entries, user_ai_profiles, user
    await db.execute(delete(AIResponse).where(AIResponse.user_id == user.id))
    await db.execute(delete(EntryTags).where(EntryTags.user_id == user.id))
    await db.execute(delete(JournalEntry).where(JournalEntry.user_id == user.id))
    await db.execute(delete(UserAIProfile).where(UserAIProfile.user_id == user.id))
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    logger.info(f"  Cleaned up persona: {persona_id}")


async def run_persona(persona: dict, args: argparse.Namespace) -> dict:
    """Run the full pipeline for all entries of a persona."""
    persona_id = persona["id"]
    logger.info(f"\n{'='*60}")
    logger.info(f"PERSONA: {persona['name']} ({persona_id})")
    logger.info(f"Bio: {persona['bio']}")
    logger.info(f"{'='*60}")

    # Clean up previous test data
    async with async_session_maker() as db:
        await cleanup_persona(db, persona_id)

    # Create test user and profile
    async with async_session_maker() as db:
        user = await create_test_user(db, persona)
        await create_ai_profile(db, user.id, persona.get("ai_profile", {}))
        await db.commit()
        user_id = user.id

    tone_preference = persona.get("ai_profile", {}).get("tone_preference", "balanced")
    main_focus = persona.get("ai_profile", {}).get("main_focus", "")

    # Process entries sequentially (order matters for context building)
    entries_results = []
    for entry_data in persona["entries"]:
        day = entry_data["day"]
        logger.info(f"\n  --- Day {day} (mood: {entry_data.get('mood', 'N/A')}) ---")
        logger.info(f"  Text: {entry_data['text'][:100]}...")

        # Create journal entry
        async with async_session_maker() as db:
            entry = await create_journal_entry(db, user_id, entry_data, day)
            await db.commit()
            entry_id = entry.id
            created_at = entry.created_at

        # Re-fetch to get a detached entry object with the data we need
        async with async_session_maker() as db:
            result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
            entry = result.scalar_one()

        # Run pipeline
        entry_result = await run_pipeline_for_entry(
            entry=entry,
            user_id=user_id,
            tone_preference=tone_preference,
            main_focus=main_focus,
            expected_mode=entry_data.get("expected_mode"),
            skip_embed=args.skip_embed,
            skip_respond=args.skip_respond,
        )
        entry_result["day"] = day

        # Log summary
        mode_icon = "✓" if entry_result["mode_match"] else "✗" if entry_result["mode_match"] is False else "?"
        logger.info(f"  Emotion: {entry_result['tags']['emotion_primary'] if entry_result['tags'] else 'N/A'} "
                     f"(intensity {entry_result['tags']['emotion_intensity'] if entry_result['tags'] else '?'})")
        logger.info(f"  NS: {entry_result['tags']['ns_state'] if entry_result['tags'] else 'N/A'}")
        logger.info(f"  Mode: {entry_result['mode']} (expected: {entry_result['expected_mode']}) {mode_icon}")
        if entry_result["hints"]:
            logger.info(f"  Hints: {', '.join(entry_result['hints'])}")
        logger.info(f"  Scenarios: {entry_result['scenarios_count']}, Similar: {entry_result['similar_count']}")
        if entry_result["response_preview"]:
            logger.info(f"  Response: {entry_result['response_preview'][:120]}...")
        if entry_result["error"]:
            logger.error(f"  ERROR: {entry_result['error']}")

        entries_results.append(entry_result)

    # Persona summary
    total = len(entries_results)
    mode_matches = sum(1 for r in entries_results if r["mode_match"] is True)
    mode_mismatches = sum(1 for r in entries_results if r["mode_match"] is False)
    errors = sum(1 for r in entries_results if r["error"])
    total_input_tokens = sum(r["tokens"]["input"] for r in entries_results)
    total_output_tokens = sum(r["tokens"]["output"] for r in entries_results)

    summary = {
        "persona": persona_id,
        "name": persona["name"],
        "total_entries": total,
        "mode_matches": mode_matches,
        "mode_mismatches": mode_mismatches,
        "mode_accuracy": mode_matches / (mode_matches + mode_mismatches) if (mode_matches + mode_mismatches) > 0 else None,
        "errors": errors,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "entries": entries_results,
    }

    logger.info(f"\n  SUMMARY: {persona['name']}")
    logger.info(f"  Mode accuracy: {mode_matches}/{mode_matches + mode_mismatches} "
                f"({summary['mode_accuracy']:.0%})" if summary['mode_accuracy'] is not None else "  Mode accuracy: N/A")
    logger.info(f"  Errors: {errors}/{total}")
    logger.info(f"  Tokens: {total_input_tokens} in / {total_output_tokens} out")

    return summary


async def main():
    parser = argparse.ArgumentParser(description="Test AI pipeline with persona journal entries")
    parser.add_argument("--persona", type=str, help="Run only this persona (maya, kai, priya, sam, alex)")
    parser.add_argument("--dry-run", action="store_true", help="Just load personas and validate structure")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding step (saves Voyage API calls)")
    parser.add_argument("--skip-respond", action="store_true", help="Skip response generation (saves Sonnet calls)")
    parser.add_argument("--cleanup-only", action="store_true", help="Only clean up test data, don't run pipeline")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    personas = load_personas(args.persona)
    logger.info(f"Loaded {len(personas)} persona(s): {[p['id'] for p in personas]}")
    total_entries = sum(len(p["entries"]) for p in personas)
    logger.info(f"Total entries to process: {total_entries}")

    if args.dry_run:
        for p in personas:
            logger.info(f"\n  {p['name']} ({p['id']}): {len(p['entries'])} entries")
            for e in p["entries"]:
                logger.info(f"    Day {e['day']}: {e.get('expected_mode', '?')} | {e['text'][:60]}...")
        logger.info("\nDry run complete. Use without --dry-run to execute pipeline.")
        return

    if args.cleanup_only:
        async with async_session_maker() as db:
            for p in personas:
                await cleanup_persona(db, p["id"])
        logger.info("Cleanup complete.")
        await engine.dispose()
        return

    # Run pipeline for each persona
    all_results = []
    for persona in personas:
        result = await run_persona(persona, args)
        all_results.append(result)

    # Overall summary
    logger.info(f"\n{'='*60}")
    logger.info("OVERALL RESULTS")
    logger.info(f"{'='*60}")

    total_mode_matches = sum(r["mode_matches"] for r in all_results)
    total_mode_mismatches = sum(r["mode_mismatches"] for r in all_results)
    total_errors = sum(r["errors"] for r in all_results)
    grand_input = sum(r["total_input_tokens"] for r in all_results)
    grand_output = sum(r["total_output_tokens"] for r in all_results)

    if total_mode_matches + total_mode_mismatches > 0:
        overall_accuracy = total_mode_matches / (total_mode_matches + total_mode_mismatches)
        logger.info(f"Mode accuracy: {total_mode_matches}/{total_mode_matches + total_mode_mismatches} ({overall_accuracy:.0%})")
    logger.info(f"Errors: {total_errors}/{total_entries}")
    logger.info(f"Total tokens: {grand_input} in / {grand_output} out")

    # Mode distribution
    mode_counts: dict[str, int] = {}
    for r in all_results:
        for e in r["entries"]:
            if e["mode"]:
                mode_counts[e["mode"]] = mode_counts.get(e["mode"], 0) + 1
    logger.info(f"\nMode distribution:")
    for mode, count in sorted(mode_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {mode}: {count}")

    # Mismatches detail
    mismatches = []
    for r in all_results:
        for e in r["entries"]:
            if e["mode_match"] is False:
                mismatches.append({
                    "persona": r["persona"],
                    "day": e["day"],
                    "expected": e["expected_mode"],
                    "actual": e["mode"],
                    "text": e["text_preview"],
                })
    if mismatches:
        logger.info(f"\nMode mismatches ({len(mismatches)}):")
        for m in mismatches:
            logger.info(f"  {m['persona']} day {m['day']}: expected {m['expected']}, got {m['actual']}")
            logger.info(f"    {m['text']}")

    # Save results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        logger.info(f"\nResults saved to {output_path}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
