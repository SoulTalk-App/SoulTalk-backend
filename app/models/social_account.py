import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSON
from typing import TYPE_CHECKING, Any

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ProviderEnum(str, Enum):
    GOOGLE = "google"
    FACEBOOK = "facebook"
    EMAIL = "email"


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_social_accounts_provider_user"),
    )

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
    provider: Mapped[ProviderEnum] = mapped_column(
        SQLEnum(ProviderEnum, name="provider_enum"),
        nullable=False
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    provider_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    profile_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="social_accounts"
    )
