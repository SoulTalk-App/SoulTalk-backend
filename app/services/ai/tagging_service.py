"""Tagging service — structured extraction via Haiku."""

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.ai_schemas.tags_v1 import TagsV1
from app.services.ai.safety import validate_tags
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
            logger.debug(f"[Tagging] Raw content: {content[:500]}")
            return None
        except Exception as e:
            logger.error(f"[Tagging] Validation error: {type(e).__name__}: {e}")
            logger.info(f"[Tagging] Failed JSON keys: {list(data.keys()) if 'data' in dir() else 'N/A'}")
            return None

    @staticmethod
    def _normalize(data: dict) -> dict:
        """Fix common Haiku output quirks before Pydantic validation.

        Haiku consistently:
        - Returns schema_version as the schema name instead of "v1"
        - Returns lists for single-value fields (secondary, coping.function)
        - Puts somatic cues in the emotion blend list
        - Returns invalid emotion values (relief, exhaustion, hopelessness, etc.)
        """
        # Force schema_version
        data["schema_version"] = "v1"

        # Valid emotion values for filtering
        valid_emotions = {
            "joy", "calm", "contentment", "gratitude", "hope", "curiosity",
            "inspiration", "sadness", "grief", "loneliness", "fear", "anxiety",
            "dread", "anger", "frustration", "resentment", "shame", "guilt",
            "unworthiness", "numbness", "emptiness", "overwhelm",
        }

        # Map common invalid emotions Haiku produces to valid ones
        emotion_aliases = {
            "relief": "calm",
            "exhaustion": "numbness",
            "hopelessness": "dread",
            "despair": "grief",
            "confusion": "overwhelm",
            "disappointment": "sadness",
            "irritation": "frustration",
            "nervousness": "anxiety",
            "panic": "dread",
            "boredom": "emptiness",
            "excitement": "joy",
            "love": "gratitude",
            "compassion": "contentment",
            "pride": "joy",
            "nostalgia": "sadness",
            "regret": "guilt",
            "jealousy": "resentment",
            "envy": "resentment",
            "stress": "anxiety",
            "tension": "anxiety",
            "worry": "anxiety",
            "melancholy": "sadness",
            "apathy": "numbness",
            "resignation": "numbness",
            "ambivalence": "numbness",
            "determination": "hope",
            "acceptance": "calm",
            "peace": "calm",
            "satisfaction": "contentment",
            "awe": "inspiration",
            "wonder": "curiosity",
        }

        def _fix_emotion(val: str) -> str | None:
            if val in valid_emotions:
                return val
            return emotion_aliases.get(val)

        emotions = data.get("emotions", {})

        # primary: fix invalid values
        if emotions.get("primary") and emotions["primary"] not in valid_emotions:
            emotions["primary"] = _fix_emotion(emotions["primary"])

        # secondary: list -> first valid item, or fix invalid string
        if isinstance(emotions.get("secondary"), list):
            mapped = [_fix_emotion(e) for e in emotions["secondary"]]
            valid = [e for e in mapped if e]
            emotions["secondary"] = valid[0] if valid else None
        elif emotions.get("secondary") and emotions["secondary"] not in valid_emotions:
            emotions["secondary"] = _fix_emotion(emotions["secondary"])

        # blend: filter to valid emotions only (with alias mapping)
        if isinstance(emotions.get("blend"), list):
            mapped = [_fix_emotion(e) for e in emotions["blend"]]
            emotions["blend"] = [e for e in mapped if e]

        # coping.function: list -> first item
        coping = data.get("coping", {})
        if isinstance(coping.get("function"), list):
            coping["function"] = coping["function"][0] if coping["function"] else None

        # coping.mechanisms: ensure it's a list
        if isinstance(coping.get("mechanisms"), str):
            coping["mechanisms"] = [coping["mechanisms"]]

        # self_talk.style: list -> first item
        self_talk = data.get("self_talk", {})
        if isinstance(self_talk.get("style"), list):
            self_talk["style"] = self_talk["style"][0] if self_talk["style"] else "mixed"

        # topics: ensure it's a list
        if isinstance(data.get("topics"), str):
            data["topics"] = [data["topics"]]

        return data


tagging_service = TaggingService()
