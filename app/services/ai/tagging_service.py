"""Tagging service — structured extraction via Haiku."""

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.ai_schemas.tags_v1 import TagsV1
from app.services.ai.safety import validate_tags
from app.services.ai.config_service import ALL_DEFAULTS
from app.services.ai_prompts.tagging import (
    TAGGING_SYSTEM_PROMPT,
    TAGGING_DEVELOPER_MESSAGE,
    TAGGING_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)


class TaggingService:
    def __init__(self):
        self._client: Optional[AsyncAnthropic] = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured")
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def tag_entry(
        self,
        raw_text: str,
        entry_id: str,
        user_id: str,
        created_at: str,
        language: str = "en",
    ) -> TagsV1:
        """Extract structured tags from a journal entry using Haiku.

        Returns a validated TagsV1 object with safety enforcement applied.
        Retries once if JSON parsing fails.
        """
        user_message = TAGGING_USER_TEMPLATE.format(
            entry_id=entry_id,
            user_id=user_id,
            created_at=created_at,
            language=language,
            raw_text=raw_text,
        )

        messages = [
            {"role": "user", "content": f"{TAGGING_DEVELOPER_MESSAGE}\n\n{user_message}"},
        ]

        tags = await self._call_and_parse(messages)
        if tags is None:
            # Retry once with error context
            logger.warning(f"[Tagging] First attempt failed for entry {entry_id}, retrying")
            messages.append({"role": "assistant", "content": "I'll fix the JSON and try again."})
            messages.append({
                "role": "user",
                "content": "The previous response was not valid JSON. Please return only a single valid JSON object matching the schema exactly. No markdown, no commentary.",
            })
            tags = await self._call_and_parse(messages)
            if tags is None:
                raise ValueError(f"Tagging failed after retry for entry {entry_id}")

        # Inject metadata the LLM may have echoed incorrectly
        tags.entry_id = entry_id
        tags.user_id = user_id
        tags.created_at = created_at
        tags.language = language

        # Safety enforcement
        tags = validate_tags(tags)

        return tags

    async def _call_and_parse(self, messages: list) -> Optional[TagsV1]:
        """Call Haiku and attempt to parse the response as TagsV1."""
        try:
            response = await self.client.messages.create(
                model=settings.ANTHROPIC_TAGGING_MODEL,
                max_tokens=1500,
                system=TAGGING_SYSTEM_PROMPT,
                messages=messages,
                temperature=0.0,
            )

            if not response.content:
                logger.error("[Tagging] Anthropic returned no content")
                return None

            content = response.content[0].text.strip()

            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3].strip()

            data = json.loads(content)
            data = self._normalize(data)
            return TagsV1.model_validate(data)

        except json.JSONDecodeError as e:
            logger.error(f"[Tagging] JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"[Tagging] Validation error: {type(e).__name__}: {e}")
            return None


    # ── Valid enum values for normalization ──
    _VALID_EMOTIONS = {
        "joy", "calm", "contentment", "gratitude", "hope", "curiosity", "inspiration",
        "sadness", "grief", "loneliness", "fear", "anxiety", "dread",
        "anger", "frustration", "resentment", "shame", "guilt", "unworthiness",
        "numbness", "emptiness", "overwhelm",
    }

    def _normalize(self, data: dict) -> dict:
        """Fix common Haiku output issues before Pydantic validation."""

        # Fix schema_version
        if data.get("schema_version") != "v1":
            data["schema_version"] = "v1"

        # Load emotion aliases
        try:
            from app.services.ai.config_service import config_service
            alias_json = config_service.get("alias", "emotion_aliases")
            aliases = json.loads(alias_json) if alias_json else {}
        except Exception:
            aliases = json.loads(ALL_DEFAULTS.get("alias", {}).get("emotion_aliases", "{}"))

        def normalize_emotion(val):
            if not val or not isinstance(val, str):
                return val
            val = val.lower().strip()
            if val in self._VALID_EMOTIONS:
                return val
            return aliases.get(val, None)

        # Emotions
        emotions = data.get("emotions", {})
        if isinstance(emotions, dict):
            # secondary: list → first valid string
            if isinstance(emotions.get("secondary"), list):
                for item in emotions["secondary"]:
                    normed = normalize_emotion(item)
                    if normed:
                        emotions["secondary"] = normed
                        break
                else:
                    emotions["secondary"] = None
                if isinstance(emotions.get("secondary"), list):
                    emotions["secondary"] = None

            # Normalize primary/secondary through aliases
            emotions["primary"] = normalize_emotion(emotions.get("primary"))
            if isinstance(emotions.get("secondary"), str):
                emotions["secondary"] = normalize_emotion(emotions.get("secondary"))

            # blend: filter invalid values, apply aliases
            if isinstance(emotions.get("blend"), list):
                normed_blend = []
                for item in emotions["blend"]:
                    n = normalize_emotion(item)
                    if n and n not in normed_blend:
                        normed_blend.append(n)
                emotions["blend"] = normed_blend[:5]

        # Coping function: list → first string
        coping = data.get("coping", {})
        if isinstance(coping, dict):
            if isinstance(coping.get("function"), list):
                coping["function"] = coping["function"][0] if coping["function"] else "unknown"
            # mechanisms: string → list
            if isinstance(coping.get("mechanisms"), str):
                coping["mechanisms"] = [coping["mechanisms"]]

        # Self-talk style: list → first string
        self_talk = data.get("self_talk", {})
        if isinstance(self_talk, dict):
            if isinstance(self_talk.get("style"), list):
                self_talk["style"] = self_talk["style"][0] if self_talk["style"] else "mixed"

        # Topics: string → list
        if isinstance(data.get("topics"), str):
            data["topics"] = [data["topics"]]

        return data


tagging_service = TaggingService()
