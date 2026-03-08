"""Create daily_aggregates table

Revision ID: 013
Revises: 012
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_aggregates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('entry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('emotion_distribution', JSONB, server_default='{}'),
        sa.Column('avg_emotion_intensity', sa.Float, nullable=True),
        sa.Column('nervous_system_distribution', JSONB, server_default='{}'),
        sa.Column('topic_counts', JSONB, server_default='{}'),
        sa.Column('coping_counts', JSONB, server_default='{}'),
        sa.Column('self_talk_distribution', JSONB, server_default='{}'),
        sa.Column('distortion_counts', JSONB, server_default='{}'),
        sa.Column('loop_counts', JSONB, server_default='{}'),
        sa.Column('narrative_cache', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_unique_constraint('uq_daily_aggregates_user_id_date', 'daily_aggregates', ['user_id', 'date'])
    op.create_index('ix_daily_aggregates_user_date', 'daily_aggregates', ['user_id', 'date'])


def downgrade() -> None:
    op.drop_table('daily_aggregates')
