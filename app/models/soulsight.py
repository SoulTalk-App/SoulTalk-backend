import uuid
from datetime import date, datetime, timezone
from sqlalchemy import String, Integer, Float, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Optional

from app.db.base import Base


class Soulsight(Base):
    __tablename__ = "soulsights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    window_start: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    window_end: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    aggregate_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )
    entry_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    active_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    model_used: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    input_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    output_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
