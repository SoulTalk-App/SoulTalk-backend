"""add display_first_name column

Revision ID: 006
Revises: 005
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_first_name", sa.String(100), nullable=True))
    # Backfill: set display_first_name = first_name for existing users
    op.execute("UPDATE users SET display_first_name = first_name WHERE display_first_name IS NULL")


def downgrade() -> None:
    op.drop_column("users", "display_first_name")
