import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Integer, Float, Text, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Optional

from app.db.base import Base


class DailyAggregate(Base):
    __tablename__ = "daily_aggregates"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_aggregates_user_id_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    entry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    emotion_distribution: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    avg_emotion_intensity: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    nervous_system_distribution: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    topic_counts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    coping_counts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    self_talk_distribution: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    distortion_counts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    loop_counts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )
    narrative_cache: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
