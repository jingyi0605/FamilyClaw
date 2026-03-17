"""create device entity favorites

Revision ID: 20260317_0045
Revises: 20260316_0044
Create Date: 2026-03-17 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0045"
down_revision = "20260316_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_entity_favorites",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "device_id",
            "entity_id",
            name="uq_device_entity_favorites_household_device_entity",
        ),
    )
    op.create_index(
        "ix_device_entity_favorites_household_id",
        "device_entity_favorites",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_device_entity_favorites_device_id",
        "device_entity_favorites",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_device_entity_favorites_device_id", table_name="device_entity_favorites")
    op.drop_index("ix_device_entity_favorites_household_id", table_name="device_entity_favorites")
    op.drop_table("device_entity_favorites")
