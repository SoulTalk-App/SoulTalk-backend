"""Add profile fields to users table

Revision ID: 003
Revises: 002
Create Date: 2026-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('username', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('pronoun', sa.String(length=30), nullable=True))
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_column('users', 'pronoun')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'username')
    op.drop_column('users', 'display_name')
