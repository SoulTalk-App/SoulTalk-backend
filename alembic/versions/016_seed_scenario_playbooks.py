"""Seed scenario_playbooks table with 20 coaching scenarios

Revision ID: 016
Revises: 015
Create Date: 2026-03-08
"""
import json
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLAYBOOKS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'app', 'services', 'ai_data', 'scenario_playbooks.json'
)


def upgrade() -> None:
    with open(PLAYBOOKS_PATH, 'r') as f:
        playbooks = json.load(f)

    scenario_table = sa.table(
        'scenario_playbooks',
        sa.column('id', sa.String),
        sa.column('title', sa.String),
        sa.column('retrieval_tags', sa.ARRAY(sa.Text)),
        sa.column('signals', sa.Text),
        sa.column('coaching_moves', sa.Text),
        sa.column('avoid_list', sa.Text),
        sa.column('micro_actions', sa.Text),
        sa.column('example_lines', sa.Text),
        sa.column('priority', sa.Integer),
        sa.column('is_active', sa.Boolean),
    )

    op.bulk_insert(scenario_table, [
        {
            'id': p['id'],
            'title': p['title'],
            'retrieval_tags': p['retrieval_tags'],
            'signals': p['signals'],
            'coaching_moves': p['coaching_moves'],
            'avoid_list': p['avoid_list'],
            'micro_actions': p['micro_actions'],
            'example_lines': p['example_lines'],
            'priority': p['priority'],
            'is_active': True,
        }
        for p in playbooks
    ])


def downgrade() -> None:
    op.execute("DELETE FROM scenario_playbooks WHERE id LIKE 'ST-SCEN-%'")
