"""Kaggle emotion-labeled journal entries — tagger validation.

Downloads and processes the Kaggle 'Journal Entries with Labelled Emotions'
dataset, runs each entry through Haiku tagging, and computes agreement rates
between Kaggle's ground truth emotion/topic labels and Haiku's TagsV1 output.

Usage:
    # First, download the dataset CSV from Kaggle and place it at:
    # tests/test_data/kaggle_journal_emotions.csv
    #
    # Then run:
    python -m tests.test_kaggle_validation [--limit 50] [--output results.json]

The CSV should have columns:
    - Answer: the journal text
    - Answer.f1.happy.raw, Answer.f1.sad.raw, ... (18 emotion booleans)
    - Answer.t1.work.raw, Answer.t1.family.raw, ... (11 topic booleans)
"""

import asyncio
import argparse
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.tagging_service import tagging_service
from tests.test_data.kaggle_emotion_map import check_emotion_agreement, check_topic_agreement

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent / "test_data" / "kaggle_journal_emotions.csv"

# Column name patterns in the Kaggle CSV
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


def parse_bool(value: str) -> bool:
    """Parse various boolean representations from CSV."""
    return value.strip().lower() in ("true", "1", "yes", "t")


def load_kaggle_data(limit: int | None = None) -> list[dict]:
    """Load entries from the Kaggle CSV."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Kaggle CSV not found at {CSV_PATH}\n"
            "Download from: https://www.kaggle.com/datasets/madhavmalhotra/journal-entries-with-labelled-emotions\n"
            "Place the CSV at: tests/test_data/kaggle_journal_emotions.csv"
        )

    entries = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []

        # Detect column naming pattern
        # Could be "Answer.f1.happy.raw" or "happy" etc.
        emotion_cols = {}
        topic_cols = {}

        for col in columns:
            col_lower = col.lower()
            for emotion in EMOTION_LABELS:
                if emotion in col_lower and ("f1" in col_lower or emotion == col_lower):
                    emotion_cols[emotion] = col
                    break
            for topic in TOPIC_LABELS:
                if topic in col_lower and ("t1" in col_lower or topic == col_lower):
                    topic_cols[topic] = col
                    break

        # Find the text column
        text_col = None
        for col in columns:
            if col.lower() in ("answer", "text", "entry", "journal_entry"):
                text_col = col
                break
        if not text_col:
            # Fall back to first column
            text_col = columns[0]

        logger.info(f"Text column: {text_col}")
        logger.info(f"Emotion columns found: {len(emotion_cols)}/{len(EMOTION_LABELS)}")
        logger.info(f"Topic columns found: {len(topic_cols)}/{len(TOPIC_LABELS)}")

        for i, row in enumerate(reader):
            if limit and i >= limit:
                break

            text = row.get(text_col, "").strip()
            if not text or len(text) < 20:
                continue

            emotions = {}
            for emotion, col in emotion_cols.items():
                emotions[emotion] = parse_bool(row.get(col, "false"))

            topics = {}
            for topic, col in topic_cols.items():
                topics[topic] = parse_bool(row.get(col, "false"))

            entries.append({
                "index": i,
                "text": text,
                "kaggle_emotions": emotions,
                "kaggle_topics": topics,
            })

    logger.info(f"Loaded {len(entries)} valid entries from Kaggle CSV")
    return entries


async def validate_entry(entry: dict, entry_num: int, total: int) -> dict:
    """Run a single entry through the tagger and compare."""
    logger.info(f"  [{entry_num}/{total}] Processing entry {entry['index']} ({len(entry['text'])} chars)")

    result = {
        "index": entry["index"],
        "text_preview": entry["text"][:100] + "...",
        "kaggle_emotions": {k: v for k, v in entry["kaggle_emotions"].items() if v},
        "kaggle_topics": {k: v for k, v in entry["kaggle_topics"].items() if v},
        "haiku_tags": None,
        "emotion_agreement": None,
        "topic_agreement": None,
        "error": None,
    }

    try:
        tags = await tagging_service.tag_entry(
            raw_text=entry["text"],
            entry_id=f"kaggle-{entry['index']}",
            user_id="kaggle-validation",
            created_at="2024-01-01T00:00:00",
        )

        result["haiku_tags"] = {
            "emotion_primary": tags.emotions.primary,
            "emotion_secondary": tags.emotions.secondary,
            "emotion_blend": tags.emotions.blend,
            "topics": list(tags.topics),
        }

        result["emotion_agreement"] = check_emotion_agreement(
            kaggle_emotions=entry["kaggle_emotions"],
            haiku_primary=tags.emotions.primary,
            haiku_secondary=tags.emotions.secondary,
            haiku_blend=tags.emotions.blend,
        )

        result["topic_agreement"] = check_topic_agreement(
            kaggle_topics=entry["kaggle_topics"],
            haiku_topics=list(tags.topics),
        )

        logger.info(f"    Haiku: {tags.emotions.primary} | Kaggle active: {list(result['kaggle_emotions'].keys())}")
        logger.info(f"    Emotion agreement: {result['emotion_agreement']['agreement_rate']:.0%}")
        logger.info(f"    Topic agreement: {result['topic_agreement']['agreement_rate']:.0%}")

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.error(f"    Error: {result['error']}")

    return result


async def main():
    parser = argparse.ArgumentParser(description="Validate Haiku tagger against Kaggle labeled journal entries")
    parser.add_argument("--limit", type=int, default=50, help="Max entries to process (default: 50)")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--batch-delay", type=float, default=0.5, help="Seconds between API calls (rate limiting)")
    args = parser.parse_args()

    entries = load_kaggle_data(limit=args.limit)

    results = []
    for i, entry in enumerate(entries):
        result = await validate_entry(entry, i + 1, len(entries))
        results.append(result)

        if args.batch_delay and i < len(entries) - 1:
            await asyncio.sleep(args.batch_delay)

    # Aggregate results
    valid_results = [r for r in results if r["error"] is None]
    errors = [r for r in results if r["error"] is not None]

    emotion_rates = [r["emotion_agreement"]["agreement_rate"] for r in valid_results if r["emotion_agreement"]]
    topic_rates = [r["topic_agreement"]["agreement_rate"] for r in valid_results if r["topic_agreement"]]

    logger.info(f"\n{'='*60}")
    logger.info("KAGGLE VALIDATION RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total entries: {len(entries)}")
    logger.info(f"Successful: {len(valid_results)}")
    logger.info(f"Errors: {len(errors)}")

    if emotion_rates:
        avg_emotion = sum(emotion_rates) / len(emotion_rates)
        logger.info(f"\nEmotion agreement: {avg_emotion:.1%} average across {len(emotion_rates)} entries")
        logger.info(f"  Perfect matches: {sum(1 for r in emotion_rates if r == 1.0)}/{len(emotion_rates)}")
        logger.info(f"  Zero matches: {sum(1 for r in emotion_rates if r == 0.0)}/{len(emotion_rates)}")

    if topic_rates:
        avg_topic = sum(topic_rates) / len(topic_rates)
        logger.info(f"\nTopic agreement: {avg_topic:.1%} average across {len(topic_rates)} entries")
        logger.info(f"  Perfect matches: {sum(1 for r in topic_rates if r == 1.0)}/{len(topic_rates)}")
        logger.info(f"  Zero matches: {sum(1 for r in topic_rates if r == 0.0)}/{len(topic_rates)}")

    # Most common Haiku emotions
    haiku_primaries: dict[str, int] = {}
    for r in valid_results:
        if r["haiku_tags"] and r["haiku_tags"]["emotion_primary"]:
            e = r["haiku_tags"]["emotion_primary"]
            haiku_primaries[e] = haiku_primaries.get(e, 0) + 1

    if haiku_primaries:
        logger.info(f"\nHaiku emotion distribution:")
        for emotion, count in sorted(haiku_primaries.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {emotion}: {count}")

    if args.output:
        output_data = {
            "summary": {
                "total": len(entries),
                "successful": len(valid_results),
                "errors": len(errors),
                "avg_emotion_agreement": sum(emotion_rates) / len(emotion_rates) if emotion_rates else None,
                "avg_topic_agreement": sum(topic_rates) / len(topic_rates) if topic_rates else None,
            },
            "entries": results,
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        logger.info(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
