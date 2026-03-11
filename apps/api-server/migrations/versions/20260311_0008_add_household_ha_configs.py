"""add household ha configs

Revision ID: 20260311_0008
Revises: 20260311_0007
Create Date: 2026-03-11 15:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0008"
down_revision: str = "20260311_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_ha_configs",
        sa.Column("household_id", sa.Text(), primary_key=True),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("sync_rooms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_device_sync_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("household_ha_configs")
