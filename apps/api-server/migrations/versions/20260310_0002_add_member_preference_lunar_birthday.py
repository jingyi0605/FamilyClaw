"""add lunar birthday flag to member preferences

Revision ID: 20260310_0002
Revises: 20260311_0008
Create Date: 2026-03-10 00:02:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260310_0002"
down_revision = "20260311_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("member_preferences")}
    if "birthday_is_lunar" not in columns:
        op.add_column(
            "member_preferences",
            sa.Column("birthday_is_lunar", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("member_preferences", "birthday_is_lunar")
