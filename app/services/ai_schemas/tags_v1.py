"""SoulTalkJournalEntryTagsV1 — Pydantic models for structured journal tag extraction.

Mirrors the JSON schema from the Dec 2025 training doc exactly.
All enums use Literal types for strict validation.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ── Enum literals ──

EmotionEnum = Literal[
    "joy", "calm", "contentment", "gratitude", "hope", "curiosity", "inspiration",
    "sadness", "grief", "loneliness",
    "fear", "anxiety", "dread",
    "anger", "frustration", "resentment",
    "shame", "guilt", "unworthiness",
    "numbness", "emptiness", "overwhelm",
]

NervousSystemState = Literal[
    "regulated", "mildly_activated", "highly_activated", "collapsed", "dissociated",
]

SomaticCue = Literal[
    "tight_chest", "jaw_tension", "racing_heart", "shallow_breath",
    "restlessness", "fatigue", "heaviness", "numb", "buzzing",
    "stomach_drop", "headache", "tearful", "insomnia", "body_ache",
    "warmth", "ease",
]

TopicEnum = Literal[
    "work_career", "money_stability", "romantic_relationship", "family_origin",
    "friends_community", "health_body", "spirituality_integration",
    "creativity_expression", "purpose_direction", "self_image_identity",
    "home_environment", "habits_routines", "technology_screens",
    "travel_change", "other",
]

CopingMechanism = Literal[
    "food", "cannabis", "alcohol", "nicotine", "scrolling",
    "overworking", "overscheduling", "isolation", "people_pleasing",
    "control_planning", "shopping_spending", "sex_dating", "doomscrolling",
    "avoidance_procrastination",
    "breathwork", "movement", "sleep", "meditation", "social_support",
    "other",
]

CopingFunction = Literal[
    "soothe", "escape", "numb", "control", "seek_reward",
    "seek_connection", "reduce_overwhelm", "avoid_conflict", "unknown",
]

SelfTalkStyle = Literal[
    "inner_critic", "perfectionistic", "people_pleasing", "hyper_independent",
    "catastrophizing", "hopeless", "compassionate_observer", "grounded_leader",
    "mixed",
]

CognitiveDistortion = Literal[
    "all_or_nothing", "mind_reading", "catastrophizing", "overgeneralizing",
    "should_statements", "personalization", "emotional_reasoning",
    "fortune_telling", "filtering_disqualifying_positive", "labeling",
    "none_detected",
]

BehavioralLoop = Literal[
    "anxiety_overwork_crash_shame",
    "overwhelm_numb_guilt_overwhelm",
    "people_please_resent_withdraw",
    "scroll_compare_shame_scroll",
    "control_tighten_exhaust_collapse",
    "ruminate_delay_panic_ruminate",
    "none_detected",
]

Valence = Literal["positive", "negative", "mixed", "neutral"]
TimeFocus = Literal["past", "present", "future", "mixed"]
AgencyLevel = Literal["low", "medium", "high"]
LevelEnum = Literal["low", "medium", "high"]
CostSignal = Literal["low", "medium", "high", "unknown"]
RiskLevel = Literal["none", "possible", "likely"]


# ── Sub-models ──

class Emotions(BaseModel):
    primary: Optional[EmotionEnum] = None
    secondary: Optional[EmotionEnum] = None
    valence: Optional[Valence] = None
    intensity: Optional[int] = Field(None, ge=1, le=5)
    blend: list[EmotionEnum] = Field(default_factory=list, max_length=5)
    notes: Optional[str] = None


class NervousSystem(BaseModel):
    state: Optional[NervousSystemState] = None
    somatic_cues: list[SomaticCue] = Field(default_factory=list)
    arousal_level: Optional[int] = Field(None, ge=1, le=5)


class Coping(BaseModel):
    mechanisms: list[CopingMechanism] = Field(default_factory=list)
    urges_present: Optional[bool] = None
    function: Optional[CopingFunction] = None
    cost_signal: Optional[CostSignal] = None


class SelfTalk(BaseModel):
    style: Optional[SelfTalkStyle] = None
    harshness_level: Optional[int] = Field(None, ge=1, le=5)


class Cognition(BaseModel):
    distortions: list[CognitiveDistortion] = Field(default_factory=list)
    loops: list[BehavioralLoop] = Field(default_factory=list)


class Orientation(BaseModel):
    time_focus: Optional[TimeFocus] = None
    agency_level: Optional[AgencyLevel] = None
    desire_present: Optional[bool] = None
    fear_present: Optional[bool] = None


class Continuity(BaseModel):
    continuity_fear_present: Optional[bool] = None
    fear_of_forgetting_ideas: Optional[bool] = None
    momentum_dependence: Optional[LevelEnum] = None
    external_container_needed: Optional[bool] = None


class IntensityPattern(BaseModel):
    intensity_seeking: Optional[LevelEnum] = None
    intensity_as_regulation: Optional[bool] = None
    intensity_as_avoidance: Optional[bool] = None
    planned_landing_needed: Optional[bool] = None


class Load(BaseModel):
    self_surveillance_present: Optional[bool] = None
    internal_performance_review: Optional[LevelEnum] = None
    self_fixing_pressure: Optional[LevelEnum] = None
    insight_overload_risk: Optional[LevelEnum] = None
    needs_container: Optional[bool] = None
    binary_thinking_present: Optional[bool] = None


class Risk(BaseModel):
    crisis_flag: bool = False
    self_harm_risk: Optional[RiskLevel] = None
    harm_to_others_risk: Optional[RiskLevel] = None
    severe_disorientation_risk: Optional[RiskLevel] = None
    medical_advice_request: Optional[bool] = None


class Confidence(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    emotion: float = Field(ge=0.0, le=1.0)
    nervous_system: float = Field(ge=0.0, le=1.0)
    topics: float = Field(ge=0.0, le=1.0)
    coping: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)


# ── Root model ──

class TagsV1(BaseModel):
    """Full tag payload for a single journal entry.

    Fields entry_id, user_id, created_at, and language are metadata
    injected by the tagging service before sending to the LLM.
    The LLM echoes them back; they are not extracted from the entry.
    """

    schema_version: Literal["v1"] = "v1"
    entry_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    language: str = "en"

    emotions: Emotions
    nervous_system: NervousSystem
    topics: list[TopicEnum] = Field(default_factory=list, max_length=6)
    coping: Coping
    self_talk: SelfTalk
    cognition: Cognition
    orientation: Orientation
    continuity: Continuity
    intensity_pattern: IntensityPattern
    load: Load
    risk: Risk
    confidence: Confidence

    @model_validator(mode="after")
    def enforce_crisis_flag(self) -> "TagsV1":
        """Safety enforcement: force crisis_flag if any high-risk signal is 'likely'."""
        risk = self.risk
        if any(level == "likely" for level in [
            risk.self_harm_risk,
            risk.harm_to_others_risk,
            risk.severe_disorientation_risk,
        ]):
            risk.crisis_flag = True
        return self
