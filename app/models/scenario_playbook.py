from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List

from app.db.base import Base


class ScenarioPlaybook(Base):
    __tablename__ = "scenario_playbooks"

    id: Mapped[str] = mapped_column(
        String(20),
        primary_key=True
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    retrieval_tags: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False
    )
    signals: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    coaching_moves: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    avoid_list: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    micro_actions: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    example_lines: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
