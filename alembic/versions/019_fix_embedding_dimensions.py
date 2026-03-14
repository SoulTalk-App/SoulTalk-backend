"""Fix embedding column from 1024 to 512 dimensions for voyage-3-lite

Revision ID: 019
Revises: 018
Create Date: 2026-03-14
"""
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE entry_tags DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entry_tags ADD COLUMN embedding vector(512)")


def downgrade() -> None:
    op.execute("ALTER TABLE entry_tags DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entry_tags ADD COLUMN embedding vector(1024)")
