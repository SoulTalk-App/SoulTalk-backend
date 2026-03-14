"""Admin API — config CRUD, playbook management, schema/rules display, pipeline debugger."""

import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.services.ai.config_service import config_service, ALL_DEFAULTS
from app.models.scenario_playbook import ScenarioPlaybook

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Auth ──

def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid admin passcode")
    return True


class AuthRequest(BaseModel):
    passcode: str


@router.post("/api/auth")
async def admin_auth(body: AuthRequest):
    if body.passcode != settings.ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")
    return {"token": settings.ADMIN_PASSCODE}


# ── Static page ──

@router.get("/", response_class=HTMLResponse)
async def admin_page():
    import os
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "admin.html")
    with open(html_path) as f:
        return HTMLResponse(f.read())


# ── Config CRUD ──

class ConfigUpdate(BaseModel):
    category: str
    key: str
    value: str


@router.get("/api/config")
async def get_all_config(_=Depends(verify_admin)):
    return config_service.get_all()


@router.put("/api/config")
async def update_config(
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    from app.db.session import async_session_maker
    await config_service.set(body.category, body.key, body.value, async_session_maker)
    return {"status": "ok", "category": body.category, "key": body.key}


@router.post("/api/config/reset")
async def reset_config(
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    """Reset a config value back to its default by deleting the DB override."""
    from app.models.ai_config import AIConfig
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(AIConfig).where(
                AIConfig.category == body.category,
                AIConfig.key == body.key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()

    # Remove from cache so it falls back to default
    if body.category in config_service._cache:
        config_service._cache[body.category].pop(body.key, None)

    default_val = ALL_DEFAULTS.get(body.category, {}).get(body.key, "")
    return {"status": "ok", "value": default_val}


# ── Prompt history ──

@router.get("/api/prompts/{key}/history")
async def get_prompt_history(
    key: str,
    _=Depends(verify_admin),
):
    from app.db.session import async_session_maker
    history = await config_service.get_prompt_history(key, async_session_maker)
    return history


# ── Playbooks ──

@router.get("/api/playbooks")
async def list_playbooks(
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    result = await db.execute(
        select(ScenarioPlaybook).order_by(ScenarioPlaybook.priority)
    )
    playbooks = []
    for p in result.scalars():
        playbooks.append({
            "id": p.id,
            "title": p.title,
            "retrieval_tags": p.retrieval_tags,
            "signals": p.signals,
            "coaching_moves": p.coaching_moves,
            "avoid_list": p.avoid_list,
            "micro_actions": p.micro_actions,
            "example_lines": p.example_lines,
            "priority": p.priority,
            "is_active": p.is_active,
        })
    return playbooks


class PlaybookUpdate(BaseModel):
    id: str
    title: str
    retrieval_tags: list[str]
    signals: str
    coaching_moves: str
    avoid_list: str
    micro_actions: str
    example_lines: str
    priority: int = 100
    is_active: bool = True


@router.put("/api/playbooks")
async def upsert_playbook(
    body: PlaybookUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    result = await db.execute(
        select(ScenarioPlaybook).where(ScenarioPlaybook.id == body.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        for field_name in ["title", "retrieval_tags", "signals", "coaching_moves",
                           "avoid_list", "micro_actions", "example_lines",
                           "priority", "is_active"]:
            setattr(existing, field_name, getattr(body, field_name))
    else:
        db.add(ScenarioPlaybook(**body.model_dump()))
    await db.commit()
    return {"status": "ok", "id": body.id}


@router.delete("/api/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: str,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    result = await db.execute(
        select(ScenarioPlaybook).where(ScenarioPlaybook.id == playbook_id)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await db.delete(existing)
    await db.commit()
    return {"status": "ok"}


# ── Schema (read-only) ──

@router.get("/api/schema")
async def get_schema(_=Depends(verify_admin)):
    """Return TagsV1 schema with all enum values for display."""
    from app.services.ai_schemas.tags_v1 import (
        EmotionEnum, NervousSystemState, SomaticCue, TopicEnum,
        CopingMechanism, CopingFunction, SelfTalkStyle,
        CognitiveDistortion, BehavioralLoop, Valence, TimeFocus,
        AgencyLevel, LevelEnum, CostSignal, RiskLevel, TagsV1,
    )
    import typing

    def get_literal_values(literal_type):
        return list(typing.get_args(literal_type))

    return {
        "enums": {
            "EmotionEnum": get_literal_values(EmotionEnum),
            "NervousSystemState": get_literal_values(NervousSystemState),
            "SomaticCue": get_literal_values(SomaticCue),
            "TopicEnum": get_literal_values(TopicEnum),
            "CopingMechanism": get_literal_values(CopingMechanism),
            "CopingFunction": get_literal_values(CopingFunction),
            "SelfTalkStyle": get_literal_values(SelfTalkStyle),
            "CognitiveDistortion": get_literal_values(CognitiveDistortion),
            "BehavioralLoop": get_literal_values(BehavioralLoop),
            "Valence": get_literal_values(Valence),
            "TimeFocus": get_literal_values(TimeFocus),
            "AgencyLevel": get_literal_values(AgencyLevel),
            "LevelEnum": get_literal_values(LevelEnum),
            "CostSignal": get_literal_values(CostSignal),
            "RiskLevel": get_literal_values(RiskLevel),
        },
        "schema": TagsV1.model_json_schema(),
    }


# ── Mode selector rules (read-only) ──

@router.get("/api/rules")
async def get_mode_rules(_=Depends(verify_admin)):
    """Return mode selector rules for display."""
    return {
        "priority_order": [
            "CRISIS_OVERRIDE",
            "SOFT_LANDING",
            "NO_MORE_HOMEWORK",
            "CONTINUITY_KEEPER",
            "INTEGRATION",
            "CLEAN_MIRROR",
            "DEFAULT_REFLECT",
        ],
        "modes": {
            "CRISIS_OVERRIDE": {
                "description": "Triggered when safety risk is detected",
                "conditions": [
                    "risk.crisis_flag == true",
                    "risk.self_harm_risk in (possible, likely)",
                    "risk.harm_to_others_risk in (possible, likely)",
                    "risk.severe_disorientation_risk in (possible, likely)",
                ],
            },
            "SOFT_LANDING": {
                "description": "Triggered when nervous system is overwhelmed",
                "conditions": [
                    "nervous_system.state == highly_activated AND emotions.intensity >= 4",
                    "nervous_system.state in (collapsed, dissociated)",
                    "emotions.primary in (overwhelm, dread) AND emotions.intensity >= 4",
                ],
            },
            "NO_MORE_HOMEWORK": {
                "description": "Triggered when cognitive/self-improvement load is too high",
                "conditions": [
                    "load.insight_overload_risk == high",
                    "load.self_fixing_pressure == high",
                    "load.self_surveillance_present AND load.internal_performance_review in (medium, high)",
                ],
            },
            "CONTINUITY_KEEPER": {
                "description": "Triggered when user fears losing momentum or ideas",
                "conditions": [
                    "continuity.continuity_fear_present == true",
                    "continuity.external_container_needed == true",
                    "continuity.momentum_dependence == high",
                    "continuity.fear_of_forgetting_ideas == true",
                ],
            },
            "INTEGRATION": {
                "description": "Triggered for spiritual/existential processing",
                "conditions": [
                    "spirituality_integration in topics",
                    "travel_change in topics AND emotions.primary in (overwhelm, sadness, anxiety)",
                ],
            },
            "CLEAN_MIRROR": {
                "description": "Direct pattern-naming for users who can handle it",
                "conditions": [
                    "tone_preference == direct",
                    "self_talk.style in (inner_critic, perfectionistic, catastrophizing) AND orientation.agency_level in (medium, high)",
                    "cognition.distortions includes (catastrophizing, all_or_nothing) AND nervous_system.state in (regulated, mildly_activated)",
                ],
            },
            "DEFAULT_REFLECT": {
                "description": "Standard mirror-pattern-question-action flow",
                "conditions": ["Fallback when no other mode matches"],
            },
        },
        "hints": {
            "REPAIR_NOT_PUNISHMENT": "coping.mechanisms includes (cannabis, food, doomscrolling) AND coping.cost_signal in (medium, high)",
            "CRITIC_SOFTENING": "cognition.distortions includes should_statements AND self_talk.harshness_level >= 4",
            "ATTACHMENT_LOOP": "romantic_relationship in topics AND emotions.primary in (anxiety, dread)",
            "SCARCITY_SPIRAL": "money_stability in topics AND emotions.primary in (fear, anxiety)",
        },
    }


# ── Usage & Cost ──

@router.get("/api/usage")
async def get_usage(
    days: int = 30,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    """Return API usage from DB, aggregated by model and service."""
    from app.models.api_usage_log import APIUsageLog
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # All entries in range
    result = await db.execute(
        select(APIUsageLog)
        .where(APIUsageLog.created_at >= cutoff)
        .order_by(APIUsageLog.created_at.desc())
    )
    entries = result.scalars().all()

    total_input = 0
    total_output = 0
    total_cost = 0.0
    by_model = {}
    by_service = {}
    daily = {}

    for e in entries:
        total_input += e.input_tokens
        total_output += e.output_tokens
        total_cost += e.estimated_cost_usd

        # By model
        if e.model not in by_model:
            by_model[e.model] = {"input": 0, "output": 0, "calls": 0, "cost": 0.0}
        by_model[e.model]["input"] += e.input_tokens
        by_model[e.model]["output"] += e.output_tokens
        by_model[e.model]["calls"] += 1
        by_model[e.model]["cost"] += e.estimated_cost_usd

        # By service
        if e.service not in by_service:
            by_service[e.service] = {"input": 0, "output": 0, "calls": 0, "cost": 0.0}
        by_service[e.service]["input"] += e.input_tokens
        by_service[e.service]["output"] += e.output_tokens
        by_service[e.service]["calls"] += 1
        by_service[e.service]["cost"] += e.estimated_cost_usd

        # Daily
        day_key = e.created_at.strftime("%Y-%m-%d")
        if day_key not in daily:
            daily[day_key] = {"calls": 0, "cost": 0.0, "tokens": 0}
        daily[day_key]["calls"] += 1
        daily[day_key]["cost"] += e.estimated_cost_usd
        daily[day_key]["tokens"] += e.input_tokens + e.output_tokens

    # Round costs
    total_cost = round(total_cost, 6)
    for v in by_model.values():
        v["cost"] = round(v["cost"], 6)
    for v in by_service.values():
        v["cost"] = round(v["cost"], 6)
    for v in daily.values():
        v["cost"] = round(v["cost"], 6)

    # Recent calls (last 50)
    recent = []
    for e in entries[:50]:
        recent.append({
            "time": e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "model": e.model,
            "service": e.service,
            "input_tokens": e.input_tokens,
            "output_tokens": e.output_tokens,
            "cost": round(e.estimated_cost_usd, 6),
        })

    return {
        "days": days,
        "total_calls": len(entries),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": total_cost,
        "by_model": by_model,
        "by_service": by_service,
        "daily": dict(sorted(daily.items())),
        "recent_calls": recent,
    }


# ── Pipeline Debugger ──

class PipelineTagRequest(BaseModel):
    raw_text: str
    language: str = "en"


# ── Personas & Kaggle data ──

@router.get("/api/personas")
async def get_personas(_=Depends(verify_admin)):
    """Return all test personas with their entries."""
    import os
    personas_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "test_data", "personas.json"
    )
    try:
        with open(personas_path) as f:
            data = json.load(f)
        return data["personas"]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="personas.json not found")


@router.post("/api/pipeline/persona-batch")
async def pipeline_persona_batch(
    persona_id: str,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    """Run tag + mode for all entries of a persona. Returns accuracy report."""
    import os
    from app.services.ai.tagging_service import tagging_service
    from app.services.ai.mode_selector import select_mode
    from app.services.ai.retrieval_service import retrieval_service

    personas_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "test_data", "personas.json"
    )
    with open(personas_path) as f:
        data = json.load(f)

    persona = next((p for p in data["personas"] if p["id"] == persona_id), None)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

    tone = persona.get("ai_profile", {}).get("tone_preference", "balanced")
    results = []
    start_all = time.monotonic()

    for entry_data in persona["entries"]:
        entry_start = time.monotonic()
        entry_result = {
            "day": entry_data["day"],
            "mood": entry_data.get("mood"),
            "text_preview": entry_data["text"][:100] + "...",
            "expected_mode": entry_data.get("expected_mode"),
            "expected_tags": entry_data.get("expected_tags", {}),
            "actual_mode": None,
            "actual_hints": [],
            "mode_match": None,
            "tags_summary": None,
            "retrieval_tags": [],
            "elapsed_ms": 0,
            "error": None,
        }

        try:
            tags = await tagging_service.tag_entry(
                raw_text=entry_data["text"],
                entry_id=f"debug-{persona_id}-d{entry_data['day']}",
                user_id="debug-user",
                created_at="2026-01-01T00:00:00Z",
                language="en",
            )

            mode_result = select_mode(tags, tone_preference=tone)
            retrieval_tags = retrieval_service._extract_retrieval_tags(tags)

            entry_result["actual_mode"] = mode_result.mode
            entry_result["actual_hints"] = mode_result.hints
            entry_result["mode_match"] = mode_result.mode == entry_data.get("expected_mode")
            entry_result["retrieval_tags"] = sorted(retrieval_tags)
            entry_result["tags_summary"] = {
                "emotion_primary": tags.emotions.primary,
                "emotion_secondary": tags.emotions.secondary,
                "intensity": tags.emotions.intensity,
                "valence": tags.emotions.valence,
                "ns_state": tags.nervous_system.state,
                "topics": list(tags.topics) if tags.topics else [],
                "self_talk_style": tags.self_talk.style,
                "harshness": tags.self_talk.harshness_level,
                "crisis_flag": tags.risk.crisis_flag,
                "insight_overload": tags.load.insight_overload_risk,
                "self_fixing": tags.load.self_fixing_pressure,
                "self_surveillance": tags.load.self_surveillance_present,
                "continuity_fear": tags.continuity.continuity_fear_present,
                "container_needed": tags.continuity.external_container_needed,
                "momentum_dep": tags.continuity.momentum_dependence,
                "agency": tags.orientation.agency_level,
                "distortions": list(tags.cognition.distortions) if tags.cognition.distortions else [],
                "coping": list(tags.coping.mechanisms) if tags.coping.mechanisms else [],
                "confidence": tags.confidence.overall,
            }
        except Exception as e:
            entry_result["error"] = f"{type(e).__name__}: {e}"

        entry_result["elapsed_ms"] = int((time.monotonic() - entry_start) * 1000)
        results.append(entry_result)

    total = len(results)
    matches = sum(1 for r in results if r["mode_match"] is True)
    mismatches = sum(1 for r in results if r["mode_match"] is False)
    errors = sum(1 for r in results if r["error"])

    return {
        "persona": persona_id,
        "name": persona["name"],
        "bio": persona["bio"],
        "tone_preference": tone,
        "total_entries": total,
        "mode_matches": matches,
        "mode_mismatches": mismatches,
        "mode_accuracy": matches / (matches + mismatches) if (matches + mismatches) > 0 else None,
        "errors": errors,
        "total_elapsed_ms": int((time.monotonic() - start_all) * 1000),
        "entries": results,
    }


@router.post("/api/pipeline/kaggle-sample")
async def pipeline_kaggle_sample(
    limit: int = 10,
    _=Depends(verify_admin),
):
    """Run tagging on random Kaggle entries and return emotion/topic agreement."""
    import os
    import csv
    import random
    from tests.test_data.kaggle_emotion_map import check_emotion_agreement, check_topic_agreement
    from app.services.ai.tagging_service import tagging_service

    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "test_data", "kaggle_journal_emotions.csv"
    )
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="kaggle_journal_emotions.csv not found in tests/test_data/")

    EMOTION_LABELS = [
        "happy", "satisfied", "calm", "proud", "excited",
        "frustrated", "anxious", "surprised", "nostalgic", "bored",
        "sad", "angry", "confused", "disgusted", "afraid",
        "ashamed", "awkward", "jealous",
    ]
    TOPIC_LABELS = [
        "family", "work", "food", "sleep", "friends",
        "health", "recreation", "god", "love", "school", "exercise",
    ]

    # Load all entries
    all_entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []

        emotion_cols = {}
        topic_cols = {}
        for col in columns:
            cl = col.lower()
            for em in EMOTION_LABELS:
                if em in cl and ("f1" in cl or em == cl):
                    emotion_cols[em] = col
                    break
            for tp in TOPIC_LABELS:
                if tp in cl and ("t1" in cl or tp == cl):
                    topic_cols[tp] = col
                    break

        text_col = None
        for col in columns:
            if col.lower() in ("answer", "text", "entry", "journal_entry"):
                text_col = col
                break
        if not text_col:
            text_col = columns[0]

        for i, row in enumerate(reader):
            text = row.get(text_col, "").strip()
            if not text or len(text) < 20:
                continue
            emotions = {em: row.get(col, "false").strip().lower() in ("true", "1", "yes", "t")
                        for em, col in emotion_cols.items()}
            topics = {tp: row.get(col, "false").strip().lower() in ("true", "1", "yes", "t")
                      for tp, col in topic_cols.items()}
            all_entries.append({"index": i, "text": text, "emotions": emotions, "topics": topics})

    # Sample
    sample = random.sample(all_entries, min(limit, len(all_entries)))

    results = []
    start_all = time.monotonic()

    for entry in sample:
        entry_start = time.monotonic()
        result = {
            "index": entry["index"],
            "text_preview": entry["text"][:120] + "...",
            "kaggle_emotions": {k: v for k, v in entry["emotions"].items() if v},
            "kaggle_topics": {k: v for k, v in entry["topics"].items() if v},
            "haiku_primary": None,
            "haiku_secondary": None,
            "haiku_blend": [],
            "haiku_topics": [],
            "emotion_agreement": None,
            "topic_agreement": None,
            "elapsed_ms": 0,
            "error": None,
        }

        try:
            tags = await tagging_service.tag_entry(
                raw_text=entry["text"],
                entry_id=f"kaggle-{entry['index']}",
                user_id="kaggle-debug",
                created_at="2026-01-01T00:00:00Z",
            )
            result["haiku_primary"] = tags.emotions.primary
            result["haiku_secondary"] = tags.emotions.secondary
            result["haiku_blend"] = list(tags.emotions.blend)
            result["haiku_topics"] = list(tags.topics)

            result["emotion_agreement"] = check_emotion_agreement(
                kaggle_emotions=entry["emotions"],
                haiku_primary=tags.emotions.primary,
                haiku_secondary=tags.emotions.secondary,
                haiku_blend=list(tags.emotions.blend),
            )
            result["topic_agreement"] = check_topic_agreement(
                kaggle_topics=entry["topics"],
                haiku_topics=list(tags.topics),
            )
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"

        result["elapsed_ms"] = int((time.monotonic() - entry_start) * 1000)
        results.append(result)

    valid = [r for r in results if not r["error"]]
    emotion_rates = [r["emotion_agreement"]["agreement_rate"] for r in valid if r["emotion_agreement"]]
    topic_rates = [r["topic_agreement"]["agreement_rate"] for r in valid if r["topic_agreement"]]

    return {
        "total_sampled": len(sample),
        "total_available": len(all_entries),
        "successful": len(valid),
        "errors": len(results) - len(valid),
        "avg_emotion_agreement": sum(emotion_rates) / len(emotion_rates) if emotion_rates else None,
        "avg_topic_agreement": sum(topic_rates) / len(topic_rates) if topic_rates else None,
        "total_elapsed_ms": int((time.monotonic() - start_all) * 1000),
        "entries": results,
    }


class PipelineModeRequest(BaseModel):
    tags: dict
    tone_preference: str = "balanced"


class PipelineRetrieveRequest(BaseModel):
    tags: dict


class PipelineRespondRequest(BaseModel):
    raw_text: str
    tags: dict
    mode: str
    hints: list[str] = []
    scenarios: list[str] = []
    recent_context: str = "No recent context available."
    main_focus: str = ""
    tone_preference: str = "balanced"


class PipelineFullRequest(BaseModel):
    raw_text: str
    language: str = "en"
    tone_preference: str = "balanced"
    main_focus: str = ""


@router.post("/api/pipeline/tag")
async def pipeline_tag(
    body: PipelineTagRequest,
    _=Depends(verify_admin),
):
    """Run only Step 1: Tagging. Returns raw tags JSON."""
    from app.services.ai.tagging_service import tagging_service
    from app.services.ai_prompts.tagging import (
        TAGGING_SYSTEM_PROMPT, TAGGING_DEVELOPER_MESSAGE, TAGGING_USER_TEMPLATE,
    )

    start = time.monotonic()
    tags = await tagging_service.tag_entry(
        raw_text=body.raw_text,
        entry_id="debug-entry",
        user_id="debug-user",
        created_at="2026-01-01T00:00:00Z",
        language=body.language,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Build the prompt that was sent (for inspection)
    user_message = TAGGING_USER_TEMPLATE.format(
        entry_id="debug-entry",
        user_id="debug-user",
        created_at="2026-01-01T00:00:00Z",
        language=body.language,
        raw_text=body.raw_text,
    )

    return {
        "step": "tag",
        "elapsed_ms": elapsed_ms,
        "prompt_sent": {
            "system": TAGGING_SYSTEM_PROMPT,
            "developer": TAGGING_DEVELOPER_MESSAGE,
            "user": user_message,
        },
        "tags": tags.model_dump(),
    }


@router.post("/api/pipeline/mode")
async def pipeline_mode(
    body: PipelineModeRequest,
    _=Depends(verify_admin),
):
    """Run only Step 3: Mode selection. Accepts tags JSON, returns mode + hints."""
    from app.services.ai_schemas.tags_v1 import TagsV1
    from app.services.ai.mode_selector import select_mode

    tags = TagsV1.model_validate(body.tags)
    result = select_mode(tags, tone_preference=body.tone_preference)

    return {
        "step": "mode",
        "input": {
            "tone_preference": body.tone_preference,
            "key_fields": {
                "crisis_flag": tags.risk.crisis_flag,
                "self_harm_risk": tags.risk.self_harm_risk,
                "harm_to_others_risk": tags.risk.harm_to_others_risk,
                "severe_disorientation_risk": tags.risk.severe_disorientation_risk,
                "ns_state": tags.nervous_system.state,
                "emotion_primary": tags.emotions.primary,
                "emotion_intensity": tags.emotions.intensity,
                "emotion_valence": tags.emotions.valence,
                "insight_overload_risk": tags.load.insight_overload_risk,
                "self_fixing_pressure": tags.load.self_fixing_pressure,
                "self_surveillance_present": tags.load.self_surveillance_present,
                "internal_performance_review": tags.load.internal_performance_review,
                "continuity_fear_present": tags.continuity.continuity_fear_present,
                "external_container_needed": tags.continuity.external_container_needed,
                "momentum_dependence": tags.continuity.momentum_dependence,
                "fear_of_forgetting_ideas": tags.continuity.fear_of_forgetting_ideas,
                "topics": list(tags.topics) if tags.topics else [],
                "self_talk_style": tags.self_talk.style,
                "self_talk_harshness": tags.self_talk.harshness_level,
                "agency_level": tags.orientation.agency_level,
                "distortions": list(tags.cognition.distortions) if tags.cognition.distortions else [],
                "coping_mechanisms": list(tags.coping.mechanisms) if tags.coping.mechanisms else [],
                "coping_cost_signal": tags.coping.cost_signal,
            },
        },
        "mode": result.mode,
        "hints": result.hints,
    }


@router.post("/api/pipeline/retrieve")
async def pipeline_retrieve(
    body: PipelineRetrieveRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    """Run only Step 4: Retrieval. Returns matched scenarios and retrieval tags."""
    from app.services.ai_schemas.tags_v1 import TagsV1
    from app.services.ai.retrieval_service import retrieval_service

    tags = TagsV1.model_validate(body.tags)

    start = time.monotonic()
    retrieval_tags = retrieval_service._extract_retrieval_tags(tags)
    scenarios = await retrieval_service.retrieve_scenarios(tags, db)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    return {
        "step": "retrieve",
        "elapsed_ms": elapsed_ms,
        "retrieval_tags_extracted": sorted(retrieval_tags),
        "scenarios_matched": scenarios,
        "scenario_count": len(scenarios),
    }


@router.post("/api/pipeline/respond")
async def pipeline_respond(
    body: PipelineRespondRequest,
    _=Depends(verify_admin),
):
    """Run only Step 5: Response generation. Accepts all inputs, returns response + prompt."""
    from app.services.ai_schemas.tags_v1 import TagsV1
    from app.services.ai.mode_selector import ModeResult
    from app.services.ai.response_service import response_service
    from app.services.ai_prompts.response import (
        RESPONSE_SYSTEM_PROMPT, RESPONSE_DEVELOPER_MESSAGE,
        RESPONSE_USER_TEMPLATE, MODE_INSTRUCTIONS,
    )

    tags = TagsV1.model_validate(body.tags)
    mode_result = ModeResult(mode=body.mode, hints=body.hints)

    # Build the prompt for inspection
    mode_instructions = MODE_INSTRUCTIONS.get(body.mode, "")
    scenario_guidance = "\n\n---\n\n".join(body.scenarios) if body.scenarios else "No specific scenario guidance."
    prompt_user = RESPONSE_USER_TEMPLATE.format(
        main_focus=body.main_focus or "not specified",
        tone_preference=body.tone_preference,
        recent_context=body.recent_context,
        scenario_guidance=scenario_guidance,
        raw_text=body.raw_text,
        tags_json=tags.model_dump_json(indent=2),
        mode=body.mode,
        hints=", ".join(body.hints) if body.hints else "none",
        mode_instructions=mode_instructions,
    )

    start = time.monotonic()
    result = await response_service.generate_response(
        raw_text=body.raw_text,
        tags=tags,
        mode_result=mode_result,
        scenarios=body.scenarios,
        recent_context=body.recent_context,
        main_focus=body.main_focus,
        tone_preference=body.tone_preference,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)

    return {
        "step": "respond",
        "elapsed_ms": elapsed_ms,
        "prompt_sent": {
            "system": RESPONSE_SYSTEM_PROMPT,
            "developer": RESPONSE_DEVELOPER_MESSAGE,
            "user": prompt_user,
        },
        "response_text": result.text,
        "model_used": result.model_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }


@router.post("/api/pipeline/full")
async def pipeline_full(
    body: PipelineFullRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_admin),
):
    """Run the full pipeline (tag → mode → retrieve → respond) and return all intermediate outputs."""
    from app.services.ai.tagging_service import tagging_service
    from app.services.ai.embedding_service import embedding_service
    from app.services.ai.mode_selector import select_mode, ModeResult
    from app.services.ai.retrieval_service import retrieval_service
    from app.services.ai.response_service import response_service
    from app.services.ai_prompts.tagging import (
        TAGGING_SYSTEM_PROMPT, TAGGING_DEVELOPER_MESSAGE, TAGGING_USER_TEMPLATE,
    )
    from app.services.ai_prompts.response import (
        RESPONSE_SYSTEM_PROMPT, RESPONSE_DEVELOPER_MESSAGE,
        RESPONSE_USER_TEMPLATE, MODE_INSTRUCTIONS,
    )

    pipeline_start = time.monotonic()
    steps = {}

    # Step 1: Tag
    t0 = time.monotonic()
    tags = await tagging_service.tag_entry(
        raw_text=body.raw_text,
        entry_id="debug-entry",
        user_id="debug-user",
        created_at="2026-01-01T00:00:00Z",
        language=body.language,
    )
    tag_user_msg = TAGGING_USER_TEMPLATE.format(
        entry_id="debug-entry", user_id="debug-user",
        created_at="2026-01-01T00:00:00Z", language=body.language,
        raw_text=body.raw_text,
    )
    steps["tag"] = {
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "prompt_sent": {
            "system": TAGGING_SYSTEM_PROMPT,
            "developer": TAGGING_DEVELOPER_MESSAGE,
            "user": tag_user_msg,
        },
        "tags": tags.model_dump(),
    }

    # Step 2: Embed
    t0 = time.monotonic()
    vector = await embedding_service.embed(body.raw_text)
    steps["embed"] = {
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "model": "voyage-3-lite",
        "dimensions": len(vector) if vector else 0,
    }

    # Step 3: Mode select
    t0 = time.monotonic()
    mode_result = select_mode(tags, tone_preference=body.tone_preference)
    steps["mode"] = {
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "input_key_fields": {
            "crisis_flag": tags.risk.crisis_flag,
            "ns_state": tags.nervous_system.state,
            "emotion_primary": tags.emotions.primary,
            "emotion_intensity": tags.emotions.intensity,
            "emotion_valence": tags.emotions.valence,
            "insight_overload_risk": tags.load.insight_overload_risk,
            "self_fixing_pressure": tags.load.self_fixing_pressure,
            "self_surveillance_present": tags.load.self_surveillance_present,
            "continuity_fear_present": tags.continuity.continuity_fear_present,
            "topics": list(tags.topics) if tags.topics else [],
            "self_talk_style": tags.self_talk.style,
            "agency_level": tags.orientation.agency_level,
            "distortions": list(tags.cognition.distortions) if tags.cognition.distortions else [],
            "tone_preference": body.tone_preference,
        },
        "mode": mode_result.mode,
        "hints": mode_result.hints,
    }

    # Step 4: Retrieve
    t0 = time.monotonic()
    retrieval_tags = retrieval_service._extract_retrieval_tags(tags)
    scenarios = await retrieval_service.retrieve_scenarios(tags, db)
    steps["retrieve"] = {
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "retrieval_tags_extracted": sorted(retrieval_tags),
        "scenarios_matched": scenarios,
        "scenario_count": len(scenarios),
    }

    # Step 5: Respond
    t0 = time.monotonic()
    mode_instructions = MODE_INSTRUCTIONS.get(mode_result.mode, "")
    scenario_guidance = "\n\n---\n\n".join(scenarios) if scenarios else "No specific scenario guidance."
    resp_user_msg = RESPONSE_USER_TEMPLATE.format(
        main_focus=body.main_focus or "not specified",
        tone_preference=body.tone_preference,
        recent_context="No recent context (debug mode).",
        scenario_guidance=scenario_guidance,
        raw_text=body.raw_text,
        tags_json=tags.model_dump_json(indent=2),
        mode=mode_result.mode,
        hints=", ".join(mode_result.hints) if mode_result.hints else "none",
        mode_instructions=mode_instructions,
    )
    resp = await response_service.generate_response(
        raw_text=body.raw_text,
        tags=tags,
        mode_result=mode_result,
        scenarios=scenarios,
        recent_context="No recent context (debug mode).",
        main_focus=body.main_focus,
        tone_preference=body.tone_preference,
    )
    steps["respond"] = {
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "prompt_sent": {
            "system": RESPONSE_SYSTEM_PROMPT,
            "developer": RESPONSE_DEVELOPER_MESSAGE,
            "user": resp_user_msg,
        },
        "response_text": resp.text,
        "model_used": resp.model_used,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
    }

    return {
        "total_elapsed_ms": int((time.monotonic() - pipeline_start) * 1000),
        "steps": steps,
    }
