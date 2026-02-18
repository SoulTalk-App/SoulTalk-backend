import json
import logging
from typing import Optional, List

from pydantic import BaseModel, Field
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SoulPal, a warm and empathetic AI companion for the SoulTalk journaling app.

When given a journal entry, analyze it and return a JSON object with these fields:

- "emotion_primary": The dominant emotion (e.g. "Joy", "Sadness", "Anger", "Fear", "Anxiety", "Gratitude", "Loneliness", "Hope", "Frustration", "Contentment")
- "emotion_secondary": A secondary emotion present (same options, or null if none)
- "emotion_intensity": Intensity of the primary emotion from 1 (mild) to 10 (overwhelming)
- "nervous_system_state": One of "Regulated", "Sympathetic" (fight/flight), "Dorsal Vagal" (shutdown/freeze), "Mixed"
- "topics": An array of 1-4 key topics/themes (e.g. ["work stress", "relationships", "self-worth"])
- "coping_mechanisms": An array of 0-3 coping mechanisms observed (e.g. ["journaling", "avoidance", "social support"])
- "self_talk_style": One of "Compassionate", "Critical", "Neutral", "Mixed"
- "time_focus": One of "Past", "Present", "Future", "Mixed"
- "ai_response": A warm, supportive 2-4 sentence reflection from you (SoulPal). Acknowledge the writer's feelings, offer a gentle insight, and end with encouragement. Do NOT give advice unless they explicitly ask. Be authentic, not generic.

Return ONLY valid JSON. No markdown, no code fences."""


class JournalAnalysis(BaseModel):
    emotion_primary: str
    emotion_secondary: Optional[str] = None
    emotion_intensity: int = Field(ge=1, le=10)
    nervous_system_state: str
    topics: List[str] = Field(default_factory=list)
    coping_mechanisms: List[str] = Field(default_factory=list)
    self_talk_style: str
    time_focus: str
    ai_response: str


class AIService:
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def analyze_journal_entry(self, raw_text: str) -> JournalAnalysis:
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.7,
            max_tokens=600,
        )

        content = response.choices[0].message.content
        logger.info(f"[AI] Raw OpenAI response length: {len(content) if content else 0}")
        data = json.loads(content)
        return JournalAnalysis(**data)


ai_service = AIService()
