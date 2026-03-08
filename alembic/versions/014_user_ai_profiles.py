"""Create user_ai_profiles table

Revision ID: 014
Revises: 013
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_ai_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('main_focus', sa.Text, nullable=True),
        sa.Column('tone_preference', sa.String(20), nullable=False, server_default='balanced'),
        sa.Column('spiritual_metadata', JSONB, nullable=True),
        sa.Column('soulpal_name', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_unique_constraint('uq_user_ai_profiles_user_id', 'user_ai_profiles', ['user_id'])


def downgrade() -> None:
    op.drop_table('user_ai_profiles')
