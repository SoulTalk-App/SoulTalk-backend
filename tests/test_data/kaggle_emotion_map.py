"""Mapping between Kaggle 'Journal Entries with Labelled Emotions' labels and our TagsV1 enums.

Kaggle dataset: 18 emotion booleans, 11 topic booleans.
Our schema: 22 EmotionEnum values, 15 TopicEnum values.

Each Kaggle label maps to one or more TagsV1 values that would indicate agreement.
"""

# Kaggle emotion label -> list of TagsV1 EmotionEnum values considered a match
EMOTION_MAP: dict[str, list[str]] = {
    "happy": ["joy", "contentment", "gratitude", "hope", "inspiration"],
    "satisfied": ["contentment", "calm", "gratitude"],
    "calm": ["calm", "contentment"],
    "proud": ["joy", "hope", "inspiration"],
    "excited": ["joy", "curiosity", "inspiration", "hope"],
    "frustrated": ["frustration", "anger", "resentment"],
    "anxious": ["anxiety", "fear", "dread", "overwhelm"],
    "surprised": ["curiosity"],
    "nostalgic": ["sadness", "grief", "calm", "joy"],  # can be positive or negative
    "bored": ["numbness", "emptiness"],
    "sad": ["sadness", "grief", "loneliness"],
    "angry": ["anger", "frustration", "resentment"],
    "confused": ["overwhelm", "anxiety"],
    "disgusted": ["anger", "resentment"],
    "afraid": ["fear", "anxiety", "dread"],
    "ashamed": ["shame", "guilt", "unworthiness"],
    "awkward": ["shame", "anxiety"],
    "jealous": ["resentment", "anger", "anxiety"],
}

# Kaggle topic label -> list of TagsV1 TopicEnum values considered a match
TOPIC_MAP: dict[str, list[str]] = {
    "family": ["family_origin"],
    "work": ["work_career"],
    "food": ["habits_routines", "health_body"],
    "sleep": ["health_body", "habits_routines"],
    "friends": ["friends_community"],
    "health": ["health_body"],
    "recreation": ["creativity_expression", "habits_routines"],
    "god": ["spirituality_integration"],
    "love": ["romantic_relationship"],
    "school": ["work_career"],
    "exercise": ["health_body", "habits_routines"],
}


def check_emotion_agreement(
    kaggle_emotions: dict[str, bool],
    haiku_primary: str | None,
    haiku_secondary: str | None,
    haiku_blend: list[str],
) -> dict:
    """Check agreement between Kaggle emotion labels and Haiku's tagged emotions.

    Args:
        kaggle_emotions: dict of {emotion_name: True/False} from the dataset
        haiku_primary: emotions.primary from TagsV1
        haiku_secondary: emotions.secondary from TagsV1
        haiku_blend: emotions.blend from TagsV1

    Returns:
        dict with 'matches', 'misses', 'false_positives', 'agreement_rate'
    """
    haiku_all = set()
    if haiku_primary:
        haiku_all.add(haiku_primary)
    if haiku_secondary:
        haiku_all.add(haiku_secondary)
    haiku_all.update(haiku_blend)

    matches = 0
    misses = 0
    total_active = 0

    for emotion, is_active in kaggle_emotions.items():
        if not is_active:
            continue
        total_active += 1

        acceptable = set(EMOTION_MAP.get(emotion.lower(), []))
        if haiku_all & acceptable:
            matches += 1
        else:
            misses += 1

    agreement_rate = matches / total_active if total_active > 0 else 1.0

    return {
        "matches": matches,
        "misses": misses,
        "total_active": total_active,
        "agreement_rate": agreement_rate,
    }


def check_topic_agreement(
    kaggle_topics: dict[str, bool],
    haiku_topics: list[str],
) -> dict:
    """Check agreement between Kaggle topic labels and Haiku's tagged topics.

    Args:
        kaggle_topics: dict of {topic_name: True/False} from the dataset
        haiku_topics: topics list from TagsV1

    Returns:
        dict with 'matches', 'misses', 'agreement_rate'
    """
    haiku_set = set(haiku_topics)

    matches = 0
    misses = 0
    total_active = 0

    for topic, is_active in kaggle_topics.items():
        if not is_active:
            continue
        total_active += 1

        acceptable = set(TOPIC_MAP.get(topic.lower(), []))
        if haiku_set & acceptable:
            matches += 1
        else:
            misses += 1

    agreement_rate = matches / total_active if total_active > 0 else 1.0

    return {
        "matches": matches,
        "misses": misses,
        "total_active": total_active,
        "agreement_rate": agreement_rate,
    }
