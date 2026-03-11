"""Persistent API usage tracker — logs every Anthropic call to the DB."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Approximate per-token pricing (USD per 1M tokens)
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6-20250725": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = MODEL_PRICING.get(model, {"input": 3.00, "output": 15.00})
    return round(
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"],
        6,
    )


async def record_usage(model: str, service: str, input_tokens: int, output_tokens: int):
    """Write a usage log entry to the DB. Fire-and-forget — errors are logged, not raised."""
    try:
        from app.db.session import async_session_maker
        from app.models.api_usage_log import APIUsageLog

        cost = estimate_cost(model, input_tokens, output_tokens)

        async with async_session_maker() as session:
            session.add(APIUsageLog(
                model=model,
                service=service,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
            ))
            await session.commit()
    except Exception as e:
        logger.warning(f"[UsageTracker] Failed to log usage: {e}")
