"""Create ai_responses table

Revision ID: 010
Revises: 009
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_responses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('response_text', sa.Text, nullable=False),
        sa.Column('mode', sa.String(30), nullable=False),
        sa.Column('hints', ARRAY(sa.Text), server_default='{}'),
        sa.Column('model_used', sa.String(50), nullable=False),
        sa.Column('input_tokens', sa.Integer, nullable=True),
        sa.Column('output_tokens', sa.Integer, nullable=True),
        sa.Column('generation_time_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_unique_constraint('uq_ai_responses_entry_id', 'ai_responses', ['entry_id'])
    op.create_index('ix_ai_responses_user_id', 'ai_responses', ['user_id'])


def downgrade() -> None:
    op.drop_table('ai_responses')
