"""Response service — coaching response generation via Sonnet."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.ai_schemas.tags_v1 import TagsV1
from app.services.ai.mode_selector import ModeResult
from app.services.ai.safety import is_crisis, generate_safety_redirect
from app.services.ai.usage_tracker import record_usage
from app.services.ai_prompts.response import (
    RESPONSE_SYSTEM_PROMPT,
    RESPONSE_DEVELOPER_MESSAGE,
    RESPONSE_USER_TEMPLATE,
    MODE_INSTRUCTIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class ResponseResult:
    text: str
    model_used: str
    input_tokens: int
    output_tokens: int
    generation_time_ms: int


class ResponseService:
    def __init__(self):
        self._client: Optional[AsyncAnthropic] = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured")
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def generate_response(
        self,
        raw_text: str,
        tags: TagsV1,
        mode_result: ModeResult,
        scenarios: list[str],
        recent_context: str,
        main_focus: str = "",
        tone_preference: str = "balanced",
    ) -> ResponseResult:
        """Generate a coaching response for a journal entry.

        If the entry is a crisis, returns the safety redirect without
        calling the LLM.
        """
        # Crisis override — no LLM call
        if mode_result.mode == "CRISIS_OVERRIDE" or is_crisis(tags):
            return ResponseResult(
                text=generate_safety_redirect(),
                model_used="safety_redirect",
                input_tokens=0,
                output_tokens=0,
                generation_time_ms=0,
            )

        # Build the prompt
        mode_instructions = MODE_INSTRUCTIONS.get(mode_result.mode, "")
        scenario_guidance = "\n\n---\n\n".join(scenarios) if scenarios else "No specific scenario guidance."

        user_message = RESPONSE_USER_TEMPLATE.format(
            main_focus=main_focus or "not specified",
            tone_preference=tone_preference,
            recent_context=recent_context or "No recent context available.",
            scenario_guidance=scenario_guidance,
            raw_text=raw_text,
            tags_json=tags.model_dump_json(indent=2),
            mode=mode_result.mode,
            hints=", ".join(mode_result.hints) if mode_result.hints else "none",
            mode_instructions=mode_instructions,
        )

        messages = [
            {"role": "user", "content": f"{RESPONSE_DEVELOPER_MESSAGE}\n\n{user_message}"},
        ]

        start = time.monotonic()
        response = await self.client.messages.create(
            model=settings.ANTHROPIC_RESPONSE_MODEL,
            max_tokens=500,
            system=RESPONSE_SYSTEM_PROMPT,
            messages=messages,
            temperature=0.7,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        await record_usage(
            model=settings.ANTHROPIC_RESPONSE_MODEL,
            service="response",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        if not response.content:
            raise ValueError("Anthropic returned no content for response generation")

        text = response.content[0].text.strip()

        return ResponseResult(
            text=text,
            model_used=settings.ANTHROPIC_RESPONSE_MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            generation_time_ms=elapsed_ms,
        )


response_service = ResponseService()
