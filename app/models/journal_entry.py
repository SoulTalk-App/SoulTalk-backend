import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSON
from typing import Optional, List, TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class JournalEntry(Base):
    __tablename__ = "journal_entries"

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
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    mood: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    emotion_primary: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    emotion_secondary: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    emotion_intensity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    nervous_system_state: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    topics: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True
    )
    coping_mechanisms: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True
    )
    self_talk_style: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    time_focus: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    ai_response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    is_ai_processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False
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

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="journal_entries"
    )
