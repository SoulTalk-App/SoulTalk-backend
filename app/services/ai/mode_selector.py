"""Mode selector — deterministic rules engine using tags.

Selects a response mode and optional hints based on extracted tags.
Priority order: CRISIS_OVERRIDE > SOFT_LANDING > NO_MORE_HOMEWORK >
CONTINUITY_KEEPER > INTEGRATION > CLEAN_MIRROR > DEFAULT_REFLECT.
"""

from dataclasses import dataclass, field

from app.services.ai_schemas.tags_v1 import TagsV1


@dataclass
class ModeResult:
    mode: str
    hints: list[str] = field(default_factory=list)


def select_mode(tags: TagsV1, tone_preference: str = "balanced") -> ModeResult:
    """Select response mode and hints from tags.

    Args:
        tags: Validated TagsV1 from tagging service.
        tone_preference: User's tone preference (softer/balanced/direct).

    Returns:
        ModeResult with mode string and list of hint strings.
    """
    mode = _select_primary_mode(tags, tone_preference)
    hints = _compute_hints(tags)
    return ModeResult(mode=mode, hints=hints)


def _select_primary_mode(tags: TagsV1, tone_preference: str) -> str:
    """First matching mode wins (priority order)."""

    risk = tags.risk
    emotions = tags.emotions
    ns = tags.nervous_system
    load = tags.load
    continuity = tags.continuity

    # 1. CRISIS_OVERRIDE
    if risk.crisis_flag:
        return "CRISIS_OVERRIDE"
    if any(level in ("possible", "likely") for level in [
        risk.self_harm_risk,
        risk.harm_to_others_risk,
        risk.severe_disorientation_risk,
    ]):
        return "CRISIS_OVERRIDE"

    # 2. SOFT_LANDING
    if ns.state in ("collapsed", "dissociated"):
        return "SOFT_LANDING"
    if ns.state == "highly_activated" and (emotions.intensity or 0) >= 5:
        return "SOFT_LANDING"
    if emotions.primary in ("overwhelm", "dread") and (emotions.intensity or 0) >= 5:
        return "SOFT_LANDING"

    # 3. NO_MORE_HOMEWORK — require 2+ load signals to avoid over-triggering
    nmh_signals = 0
    if load.insight_overload_risk == "high":
        nmh_signals += 1
    if load.self_fixing_pressure == "high":
        nmh_signals += 1
    if load.self_surveillance_present and load.internal_performance_review in ("medium", "high"):
        nmh_signals += 1
    if nmh_signals >= 2:
        return "NO_MORE_HOMEWORK"

    # 4. CONTINUITY_KEEPER — require 2+ signals to avoid over-triggering
    ck_signals = 0
    if continuity.continuity_fear_present:
        ck_signals += 1
    if continuity.external_container_needed:
        ck_signals += 1
    if continuity.momentum_dependence == "high":
        ck_signals += 1
    if continuity.fear_of_forgetting_ideas:
        ck_signals += 1
    if ck_signals >= 2:
        return "CONTINUITY_KEEPER"

    # 5. INTEGRATION — require negative/mixed valence to avoid stealing from DEFAULT_REFLECT
    topics = tags.topics or []
    if "spirituality_integration" in topics and emotions.valence in ("negative", "mixed"):
        return "INTEGRATION"
    if "travel_change" in topics and emotions.primary in ("overwhelm", "sadness", "anxiety"):
        return "INTEGRATION"

    # 6. CLEAN_MIRROR
    if tone_preference == "direct":
        return "CLEAN_MIRROR"
    if (tags.self_talk.style in ("inner_critic", "perfectionistic", "catastrophizing")
            and tags.orientation.agency_level in ("medium", "high")):
        return "CLEAN_MIRROR"
    if (any(d in ("catastrophizing", "all_or_nothing") for d in (tags.cognition.distortions or []))
            and ns.state in ("regulated", "mildly_activated")):
        return "CLEAN_MIRROR"

    # 7. DEFAULT_REFLECT
    return "DEFAULT_REFLECT"


def _compute_hints(tags: TagsV1) -> list[str]:
    """Compute secondary hints that alter response shape."""
    hints = []

    coping = tags.coping
    if any(m in ("cannabis", "food", "doomscrolling") for m in (coping.mechanisms or [])):
        if coping.cost_signal in ("medium", "high"):
            hints.append("REPAIR_NOT_PUNISHMENT")

    if ("should_statements" in (tags.cognition.distortions or [])
            and (tags.self_talk.harshness_level or 0) >= 4):
        hints.append("CRITIC_SOFTENING")

    topics = tags.topics or []
    if "romantic_relationship" in topics and tags.emotions.primary in ("anxiety", "dread"):
        hints.append("ATTACHMENT_LOOP")

    if "money_stability" in topics and tags.emotions.primary in ("fear", "anxiety"):
        hints.append("SCARCITY_SPIRAL")

    return hints
