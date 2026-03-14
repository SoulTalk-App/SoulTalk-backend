import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, SmallInteger, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from typing import Optional, List, TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.journal_entry import JournalEntry


class EntryTags(Base):
    __tablename__ = "entry_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    schema_version: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="v1"
    )
    tags: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    embedding = mapped_column(
        Vector(512),
        nullable=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    # Extracted indexed columns for fast aggregation queries
    emotion_primary: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        index=True
    )
    emotion_secondary: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True
    )
    emotion_intensity: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True
    )
    emotion_valence: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True
    )
    nervous_system_state: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True
    )
    topics: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True
    )
    coping_mechanisms: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True
    )
    self_talk_style: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True
    )
    self_talk_harshness: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True
    )
    crisis_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    confidence_overall: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    insight_overload_risk: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True
    )
    continuity_fear_present: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry",
        back_populates="entry_tags"
    )
