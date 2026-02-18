"""Add daily_moods table

Revision ID: 004
Revises: 003
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_moods',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('filled_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_moods_user_id', 'daily_moods', ['user_id'])
    op.create_index('ix_daily_moods_date', 'daily_moods', ['date'])
    op.create_unique_constraint('uq_daily_moods_user_date', 'daily_moods', ['user_id', 'date'])


def downgrade() -> None:
    op.drop_constraint('uq_daily_moods_user_date', 'daily_moods')
    op.drop_index('ix_daily_moods_date', table_name='daily_moods')
    op.drop_index('ix_daily_moods_user_id', table_name='daily_moods')
    op.drop_table('daily_moods')
