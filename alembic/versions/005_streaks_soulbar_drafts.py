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
    # Create user_streaks table
    op.create_table(
        'user_streaks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_journal_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_user_streaks_user_id', 'user_streaks', ['user_id'])
    op.create_unique_constraint('uq_user_streaks_user_id', 'user_streaks', ['user_id'])

    # Create soul_bars table
    op.create_table(
        'soul_bars',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_filled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_soul_bars_user_id', 'soul_bars', ['user_id'])
    op.create_unique_constraint('uq_soul_bars_user_id', 'soul_bars', ['user_id'])

    # Add is_draft column to journal_entries
    op.add_column('journal_entries', sa.Column('is_draft', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index('ix_journal_entries_is_draft', 'journal_entries', ['is_draft'])


def downgrade() -> None:
    op.drop_index('ix_journal_entries_is_draft', table_name='journal_entries')
    op.drop_column('journal_entries', 'is_draft')

    op.drop_constraint('uq_soul_bars_user_id', 'soul_bars')
    op.drop_index('ix_soul_bars_user_id', table_name='soul_bars')
    op.drop_table('soul_bars')

    op.drop_constraint('uq_user_streaks_user_id', 'user_streaks')
    op.drop_index('ix_user_streaks_user_id', table_name='user_streaks')
    op.drop_table('user_streaks')
