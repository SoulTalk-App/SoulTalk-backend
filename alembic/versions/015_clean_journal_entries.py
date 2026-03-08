"""Remove legacy AI columns from journal_entries, add processing status

Revision ID: 015
Revises: 014
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy AI columns
    op.drop_column('journal_entries', 'emotion_primary')
    op.drop_column('journal_entries', 'emotion_secondary')
    op.drop_column('journal_entries', 'emotion_intensity')
    op.drop_column('journal_entries', 'nervous_system_state')
    op.drop_column('journal_entries', 'topics')
    op.drop_column('journal_entries', 'coping_mechanisms')
    op.drop_column('journal_entries', 'self_talk_style')
    op.drop_column('journal_entries', 'time_focus')
    op.drop_column('journal_entries', 'ai_response')
    op.drop_column('journal_entries', 'is_ai_processed')

    # Add new processing status columns
    op.add_column('journal_entries', sa.Column(
        'ai_processing_status', sa.String(20), nullable=False, server_default='none'
    ))
    op.add_column('journal_entries', sa.Column(
        'ai_processing_error', sa.Text, nullable=True
    ))
    op.add_column('journal_entries', sa.Column(
        'ai_processing_started_at', sa.DateTime(timezone=True), nullable=True
    ))


def downgrade() -> None:
    # Remove new columns
    op.drop_column('journal_entries', 'ai_processing_status')
    op.drop_column('journal_entries', 'ai_processing_error')
    op.drop_column('journal_entries', 'ai_processing_started_at')

    # Restore legacy columns
    op.add_column('journal_entries', sa.Column('emotion_primary', sa.String(50), nullable=True))
    op.add_column('journal_entries', sa.Column('emotion_secondary', sa.String(50), nullable=True))
    op.add_column('journal_entries', sa.Column('emotion_intensity', sa.Integer, nullable=True))
    op.add_column('journal_entries', sa.Column('nervous_system_state', sa.String(50), nullable=True))
    op.add_column('journal_entries', sa.Column('topics', sa.JSON, nullable=True))
    op.add_column('journal_entries', sa.Column('coping_mechanisms', sa.JSON, nullable=True))
    op.add_column('journal_entries', sa.Column('self_talk_style', sa.String(50), nullable=True))
    op.add_column('journal_entries', sa.Column('time_focus', sa.String(20), nullable=True))
    op.add_column('journal_entries', sa.Column('ai_response', sa.Text, nullable=True))
    op.add_column('journal_entries', sa.Column('is_ai_processed', sa.Boolean, server_default=sa.text('FALSE')))
