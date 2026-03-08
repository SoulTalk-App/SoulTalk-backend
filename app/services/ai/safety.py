"""Safety module — tag validation and crisis detection."""

from app.services.ai_schemas.tags_v1 import TagsV1


def validate_tags(tags: TagsV1) -> TagsV1:
    """Enforce safety invariants on extracted tags.

    Forces crisis_flag=True if any high-risk signal is 'likely'.
    This duplicates the Pydantic model_validator as a defense-in-depth measure.
    """
    risk = tags.risk
    if any(level == "likely" for level in [
        risk.self_harm_risk,
        risk.harm_to_others_risk,
        risk.severe_disorientation_risk,
    ]):
        risk.crisis_flag = True
    return tags


def is_crisis(tags: TagsV1) -> bool:
    """Check if tags indicate a crisis that should override coaching."""
    risk = tags.risk
    if risk.crisis_flag:
        return True
    if any(level in ("possible", "likely") for level in [
        risk.self_harm_risk,
        risk.harm_to_others_risk,
        risk.severe_disorientation_risk,
    ]):
        return True
    return False


SAFETY_REDIRECT = (
    "I'm really glad you shared this. What you're feeling matters, and you deserve "
    "real support right now — more than I can offer as an AI.\n\n"
    "If you're in immediate danger, please contact your local emergency services now. "
    "If you can, reach out to someone you trust and tell them you need support.\n\n"
    "You don't have to carry this alone."
)


def generate_safety_redirect() -> str:
    """Return the compassionate safety redirect message for crisis situations."""
    return SAFETY_REDIRECT
