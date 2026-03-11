"""Add api_usage_log table

Revision ID: 018
Revises: 017
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_usage_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model", sa.String(100), nullable=False, index=True),
        sa.Column("service", sa.String(50), nullable=False, index=True),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("estimated_cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("api_usage_log")
