import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Integer, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional, TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserStreak(Base):
    __tablename__ = "user_streaks"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_streaks_user_id"),
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
    current_streak: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    longest_streak: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    last_journal_date: Mapped[Optional[date]] = mapped_column(
        Date,
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

    user: Mapped["User"] = relationship("User")
