"""Create entry_tags table

Revision ID: 009
Revises: 008
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'entry_tags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('schema_version', sa.String(10), nullable=False, server_default='v1'),
        sa.Column('tags', JSONB, nullable=False),
        sa.Column('embedding_model', sa.String(50), nullable=True),
        sa.Column('emotion_primary', sa.String(30), nullable=True),
        sa.Column('emotion_secondary', sa.String(30), nullable=True),
        sa.Column('emotion_intensity', sa.SmallInteger, nullable=True),
        sa.Column('emotion_valence', sa.String(10), nullable=True),
        sa.Column('nervous_system_state', sa.String(30), nullable=True),
        sa.Column('topics', ARRAY(sa.Text), nullable=True),
        sa.Column('coping_mechanisms', ARRAY(sa.Text), nullable=True),
        sa.Column('self_talk_style', sa.String(30), nullable=True),
        sa.Column('self_talk_harshness', sa.SmallInteger, nullable=True),
        sa.Column('crisis_flag', sa.Boolean, nullable=False, server_default=sa.text('FALSE')),
        sa.Column('confidence_overall', sa.Float, nullable=True),
        sa.Column('insight_overload_risk', sa.String(10), nullable=True),
        sa.Column('continuity_fear_present', sa.Boolean, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # Add vector column separately (pgvector type)
    op.execute("ALTER TABLE entry_tags ADD COLUMN embedding vector(1024)")

    # Unique constraint
    op.create_unique_constraint('uq_entry_tags_entry_id', 'entry_tags', ['entry_id'])

    # Indexes
    op.create_index('ix_entry_tags_user_id', 'entry_tags', ['user_id'])
    op.create_index('ix_entry_tags_created_at', 'entry_tags', ['created_at'])
    op.create_index('ix_entry_tags_emotion_primary', 'entry_tags', ['emotion_primary'])
    op.execute("CREATE INDEX ix_entry_tags_topics ON entry_tags USING GIN(topics)")
    op.execute("CREATE INDEX ix_entry_tags_crisis_flag ON entry_tags(crisis_flag) WHERE crisis_flag = TRUE")

    # HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX ix_entry_tags_embedding ON entry_tags
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_table('entry_tags')
