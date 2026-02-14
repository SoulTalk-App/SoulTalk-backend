"""Add journal_entries table

Revision ID: 002
Revises: 001
Create Date: 2026-02-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'journal_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('mood', sa.String(length=20), nullable=True),
        sa.Column('emotion_primary', sa.String(length=50), nullable=True),
        sa.Column('emotion_secondary', sa.String(length=50), nullable=True),
        sa.Column('emotion_intensity', sa.Integer(), nullable=True),
        sa.Column('nervous_system_state', sa.String(length=50), nullable=True),
        sa.Column('topics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('coping_mechanisms', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('self_talk_style', sa.String(length=50), nullable=True),
        sa.Column('time_focus', sa.String(length=20), nullable=True),
        sa.Column('ai_response', sa.Text(), nullable=True),
        sa.Column('is_ai_processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_journal_entries_user_id_users', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_journal_entries'),
    )
    op.create_index('ix_journal_entries_user_id', 'journal_entries', ['user_id'])
    op.create_index('ix_journal_entries_created_at', 'journal_entries', ['created_at'])


def downgrade() -> None:
    op.drop_table('journal_entries')
