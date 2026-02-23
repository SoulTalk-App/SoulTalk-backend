"""Add user_streaks, soul_bars tables and is_draft column to journal_entries

Revision ID: 005
Revises: 004
Create Date: 2026-02-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_streaks table (IF NOT EXISTS for idempotency)
    op.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS user_streaks ("
        "id UUID PRIMARY KEY, "
        "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
        "current_streak INTEGER NOT NULL DEFAULT 0, "
        "longest_streak INTEGER NOT NULL DEFAULT 0, "
        "last_journal_date DATE, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())"
    ))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_streaks_user_id ON user_streaks (user_id)"))
    op.execute(sa.text(
        "DO $body$ BEGIN "
        "ALTER TABLE user_streaks ADD CONSTRAINT uq_user_streaks_user_id UNIQUE (user_id); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $body$"
    ))

    # Create soul_bars table (IF NOT EXISTS for idempotency)
    op.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS soul_bars ("
        "id UUID PRIMARY KEY, "
        "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
        "points INTEGER NOT NULL DEFAULT 0, "
        "total_filled INTEGER NOT NULL DEFAULT 0, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())"
    ))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_soul_bars_user_id ON soul_bars (user_id)"))
    op.execute(sa.text(
        "DO $body$ BEGIN "
        "ALTER TABLE soul_bars ADD CONSTRAINT uq_soul_bars_user_id UNIQUE (user_id); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $body$"
    ))

    # Add is_draft column to journal_entries (IF NOT EXISTS)
    op.execute(sa.text(
        "DO $body$ BEGIN "
        "ALTER TABLE journal_entries ADD COLUMN is_draft BOOLEAN NOT NULL DEFAULT false; "
        "EXCEPTION WHEN duplicate_column THEN NULL; "
        "END $body$"
    ))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_journal_entries_is_draft ON journal_entries (is_draft)"))


def downgrade() -> None:
    op.drop_index('ix_journal_entries_is_draft', table_name='journal_entries')
    op.drop_column('journal_entries', 'is_draft')

    op.drop_constraint('uq_soul_bars_user_id', 'soul_bars')
    op.drop_index('ix_soul_bars_user_id', table_name='soul_bars')
    op.drop_table('soul_bars')

    op.drop_constraint('uq_user_streaks_user_id', 'user_streaks')
    op.drop_index('ix_user_streaks_user_id', table_name='user_streaks')
    op.drop_table('user_streaks')
