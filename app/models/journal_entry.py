import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional, TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.entry_tags import EntryTags
    from app.models.ai_response import AIResponse


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
    ai_processing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="none"
    )
    ai_processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    ai_processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    is_draft: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True
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
    entry_tags: Mapped[Optional["EntryTags"]] = relationship(
        "EntryTags",
        back_populates="journal_entry",
        uselist=False,
        cascade="all, delete-orphan"
    )
    ai_response: Mapped[Optional["AIResponse"]] = relationship(
        "AIResponse",
        back_populates="journal_entry",
        uselist=False,
        cascade="all, delete-orphan"
    )
