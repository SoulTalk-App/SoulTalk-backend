import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Optional

from app.db.base import Base


class UserAIProfile(Base):
    __tablename__ = "user_ai_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    main_focus: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    tone_preference: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="balanced"
    )
    spiritual_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )
    soulpal_name: Mapped[Optional[str]] = mapped_column(
        String(50),
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
