"""Change soul_bars.points from INTEGER to FLOAT for fractional points

Revision ID: 007
Revises: 006
Create Date: 2026-02-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'soul_bars',
        'points',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )


def downgrade() -> None:
    op.alter_column(
        'soul_bars',
        'points',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )
