"""Retrieval service — scenario matching, similar entries, and recent context."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scenario_playbook import ScenarioPlaybook
from app.models.entry_tags import EntryTags
from app.models.journal_entry import JournalEntry
from app.services.ai_schemas.tags_v1 import TagsV1

logger = logging.getLogger(__name__)


class RetrievalService:

    async def retrieve_scenarios(
        self,
        tags: TagsV1,
        db: AsyncSession,
        limit: int = 2,
    ) -> list[str]:
        """Find matching scenario playbooks by tag overlap.

        Matches entry tags against scenario retrieval_tags using
        PostgreSQL array overlap (&&). Orders by overlap count DESC,
        priority ASC. Returns formatted scenario text blocks.
        """
        # Build a list of relevant tag strings from the entry
        entry_tags = self._extract_retrieval_tags(tags)
        if not entry_tags:
            return []

        # Query: find scenarios whose retrieval_tags overlap with entry_tags
        # Order by overlap count (more matches = more relevant), then priority
        stmt = (
            select(ScenarioPlaybook)
            .where(
                ScenarioPlaybook.is_active == True,
                ScenarioPlaybook.retrieval_tags.overlap(entry_tags),
            )
            .order_by(
                # Count of overlapping tags (descending)
                desc(func.cardinality(
                    func.array(
                        select(func.unnest(ScenarioPlaybook.retrieval_tags))
                        .where(func.unnest(ScenarioPlaybook.retrieval_tags).in_(entry_tags))
                        .correlate(ScenarioPlaybook)
                        .scalar_subquery()
                    )
                )),
                ScenarioPlaybook.priority.asc(),
            )
            .limit(limit)
        )

        # Simpler approach: use raw SQL for the overlap + ordering
        # since the nested array subquery is complex in SQLAlchemy
        raw_sql = text("""
            SELECT id, title, signals, coaching_moves, avoid_list, micro_actions, example_lines
            FROM scenario_playbooks
            WHERE is_active = true
              AND retrieval_tags && :entry_tags
            ORDER BY
              cardinality(ARRAY(
                SELECT unnest(retrieval_tags) INTERSECT SELECT unnest(:entry_tags_2)
              )) DESC,
              priority ASC
            LIMIT :limit
        """)

        result = await db.execute(raw_sql, {
            "entry_tags": entry_tags,
            "entry_tags_2": entry_tags,
            "limit": limit,
        })

        scenarios = []
        for row in result:
            block = (
                f"Scenario: {row.title}\n"
                f"Signals: {row.signals}\n"
                f"Coaching moves: {row.coaching_moves}\n"
                f"Avoid: {row.avoid_list}\n"
                f"Micro-actions: {row.micro_actions}\n"
                f"Example lines: {row.example_lines}"
            )
            scenarios.append(block)

        logger.info(f"[Retrieval] Found {len(scenarios)} matching scenarios")
        return scenarios

    async def retrieve_similar_entries(
        self,
        embedding: list[float],
        user_id: str,
        current_entry_id: str,
        db: AsyncSession,
        limit: int = 5,
        days: int = 90,
    ) -> list[dict]:
        """Find similar past entries using vector cosine similarity.

        Returns entries from the same user within the last N days,
        excluding the current entry. Each result includes a text excerpt,
        tags summary, and created_at.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        raw_sql = text("""
            SELECT
                et.entry_id,
                je.raw_text,
                et.emotion_primary,
                et.nervous_system_state,
                et.topics,
                et.created_at,
                et.embedding <=> :embedding AS distance
            FROM entry_tags et
            JOIN journal_entries je ON je.id = et.entry_id
            WHERE et.user_id = :user_id
              AND et.entry_id != :current_entry_id
              AND et.embedding IS NOT NULL
              AND et.created_at >= :cutoff
            ORDER BY et.embedding <=> :embedding
            LIMIT :limit
        """)

        result = await db.execute(raw_sql, {
            "embedding": embedding_str,
            "user_id": user_id,
            "current_entry_id": current_entry_id,
            "cutoff": cutoff,
            "limit": limit,
        })

        entries = []
        for row in result:
            excerpt = row.raw_text[:200] + "..." if len(row.raw_text) > 200 else row.raw_text
            entries.append({
                "entry_id": str(row.entry_id),
                "raw_text_excerpt": excerpt,
                "emotion_primary": row.emotion_primary,
                "nervous_system_state": row.nervous_system_state,
                "topics": row.topics or [],
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "distance": float(row.distance) if row.distance else None,
            })

        logger.info(f"[Retrieval] Found {len(entries)} similar entries")
        return entries

    async def build_recent_context(
        self,
        user_id: str,
        db: AsyncSession,
        limit: int = 7,
    ) -> str:
        """Build a compact text summary of recent entry tags.

        Fetches the last N entry_tags rows and formats dominant
        emotions, recurring topics, NS trend, and coping patterns.
        No LLM call — pure SQL + Python formatting.
        """
        stmt = (
            select(EntryTags)
            .where(EntryTags.user_id == user_id)
            .order_by(EntryTags.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        recent_tags = list(result.scalars().all())

        if not recent_tags:
            return "No recent entries."

        # Aggregate
        emotions = []
        ns_states = []
        all_topics = []
        coping = []

        for et in recent_tags:
            if et.emotion_primary:
                emotions.append(et.emotion_primary)
            if et.nervous_system_state:
                ns_states.append(et.nervous_system_state)
            if et.topics:
                all_topics.extend(et.topics)
            if et.coping_mechanisms:
                coping.extend(et.coping_mechanisms)

        def top_n(items: list, n: int = 3) -> list:
            counts = {}
            for item in items:
                counts[item] = counts.get(item, 0) + 1
            return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:n]]

        parts = [f"Based on the last {len(recent_tags)} entries:"]

        if emotions:
            parts.append(f"Dominant emotions: {', '.join(top_n(emotions))}")
        if ns_states:
            parts.append(f"Nervous system trend: {', '.join(top_n(ns_states))}")
        if all_topics:
            parts.append(f"Recurring topics: {', '.join(top_n(all_topics, 4))}")
        if coping:
            parts.append(f"Coping patterns: {', '.join(top_n(coping))}")

        return "\n".join(parts)

    def _extract_retrieval_tags(self, tags: TagsV1) -> list[str]:
        """Extract a flat list of tag strings for scenario matching."""
        result = []

        # From load
        if tags.load.self_surveillance_present:
            result.append("self_surveillance")
        if tags.load.internal_performance_review in ("medium", "high"):
            result.append("internal_performance_review")
        if tags.load.insight_overload_risk in ("medium", "high"):
            result.append("insight_overload")
        if tags.load.self_fixing_pressure in ("medium", "high"):
            result.append("self_fixing_pressure")
        if tags.load.binary_thinking_present:
            result.append("binary_thinking")

        # From continuity
        if tags.continuity.continuity_fear_present:
            result.append("continuity_fear")
        if tags.continuity.momentum_dependence in ("medium", "high"):
            result.append("momentum_dependence")
        if tags.continuity.external_container_needed:
            result.append("external_containers")
            result.append("neurodivergent_support")

        # From intensity_pattern
        if tags.intensity_pattern.intensity_seeking in ("medium", "high"):
            result.append("intensity_seeking")
        if tags.intensity_pattern.planned_landing_needed:
            result.append("planned_landing_needed")

        # From emotions
        if tags.emotions.primary == "shame":
            result.append("shame_loop")
        if tags.emotions.primary == "guilt":
            result.append("shame_loop")
        if tags.emotions.primary == "grief":
            result.append("grief")
            result.append("loss")
            result.append("emotional_validity")
        if tags.emotions.primary == "anger":
            result.append("anger")
            result.append("boundary_signal")
            result.append("protection")
        if tags.emotions.primary == "overwhelm":
            result.append("overwhelm_mode")

        # From coping
        for mech in (tags.coping.mechanisms or []):
            if mech in ("scrolling", "doomscrolling"):
                result.append("comparison")
                result.append("algorithm_effect")
            if mech == "overworking":
                result.append("burnout")
                result.append("overworking")
                result.append("survival_mode")
            if mech == "people_pleasing":
                result.append("people_pleasing")
                result.append("boundary_guilt")
            if mech in ("avoidance_procrastination",):
                result.append("avoidance")
                result.append("procrastination")
            if mech in ("cannabis", "food", "alcohol"):
                result.append("numbing")
                result.append("repair")

        # From self_talk
        if tags.self_talk.style == "perfectionistic":
            result.append("perfectionism")
        if tags.self_talk.style == "inner_critic" and (tags.self_talk.harshness_level or 0) >= 3:
            result.append("perfectionism")
            result.append("breakdown")

        # From cognition
        for loop in (tags.cognition.loops or []):
            if loop == "scroll_compare_shame_scroll":
                result.append("comparison")
                result.append("worthiness")
            if loop == "people_please_resent_withdraw":
                result.append("conflict_avoidance")
                result.append("resentment")
                result.append("indirect_needs")

        # From risk
        if tags.risk.crisis_flag:
            result.append("crisis_flag")
        if tags.risk.self_harm_risk in ("possible", "likely"):
            result.append("self_harm_risk")
            result.append("imminent_danger")

        # From topics
        for topic in (tags.topics or []):
            if topic == "romantic_relationship":
                if tags.emotions.primary in ("anxiety", "dread", "fear"):
                    result.append("anxious_attachment")
                    result.append("reassurance_seeking")
                    result.append("relational_loop")
            if topic == "spirituality_integration":
                result.append("spiritual_crisis")
                result.append("meaning")
            if topic == "self_image_identity":
                result.append("identity_shift")
                result.append("integration")
                result.append("worthiness")
                result.append("self_sabotage")
            if topic == "money_stability":
                result.append("scarcity_spiral")

        # Deduplicate
        return list(set(result))


retrieval_service = RetrievalService()
