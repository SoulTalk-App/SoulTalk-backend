"""Create scenario_playbooks table

Revision ID: 012
Revises: 011
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scenario_playbooks',
        sa.Column('id', sa.String(20), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('retrieval_tags', ARRAY(sa.Text), nullable=False),
        sa.Column('signals', sa.Text, nullable=False),
        sa.Column('coaching_moves', sa.Text, nullable=False),
        sa.Column('avoid_list', sa.Text, nullable=False),
        sa.Column('micro_actions', sa.Text, nullable=False),
        sa.Column('example_lines', sa.Text, nullable=False),
        sa.Column('priority', sa.Integer, nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('TRUE')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.execute("CREATE INDEX ix_scenario_playbooks_tags ON scenario_playbooks USING GIN(retrieval_tags)")


def downgrade() -> None:
    op.drop_table('scenario_playbooks')
