"""Create soulsights table

Revision ID: 011
Revises: 010
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'soulsights',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('window_start', sa.Date, nullable=False),
        sa.Column('window_end', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('aggregate_stats', JSONB, nullable=True),
        sa.Column('entry_count', sa.Integer, nullable=True),
        sa.Column('active_days', sa.Integer, nullable=True),
        sa.Column('model_used', sa.String(50), nullable=True),
        sa.Column('input_tokens', sa.Integer, nullable=True),
        sa.Column('output_tokens', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_index('ix_soulsights_user_id', 'soulsights', ['user_id'])
    op.create_index('ix_soulsights_status', 'soulsights', ['status'])
    op.create_index('ix_soulsights_user_window', 'soulsights', ['user_id', 'window_end'], unique=False)


def downgrade() -> None:
    op.drop_table('soulsights')
