import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from typing import Optional, List, TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.journal_entry import JournalEntry


class AIResponse(Base):
    __tablename__ = "ai_responses"

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
    response_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    hints: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        default=list
    )
    model_used: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    input_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    output_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    generation_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry",
        back_populates="ai_response"
    )
