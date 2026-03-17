"""create integration discoveries

Revision ID: 20260317_0046
Revises: 20260317_0045
Create Date: 2026-03-17 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0046"
down_revision = "20260317_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_discoveries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("integration_instance_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("discovery_key", sa.String(length=255), nullable=False),
        sa.Column("discovery_type", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False, server_default="device"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("external_device_id", sa.String(length=255), nullable=True),
        sa.Column("external_entity_id", sa.String(length=255), nullable=True),
        sa.Column("adapter_type", sa.String(length=64), nullable=True),
        sa.Column("capability_tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("claimed_device_id", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_instance_id"], ["integration_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claimed_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("plugin_id", "integration_instance_id", "discovery_key", name="uq_integration_discoveries_instance_key"),
    )
    op.create_index("ix_integration_discoveries_household_id", "integration_discoveries", ["household_id"], unique=False)
    op.create_index(
        "ix_integration_discoveries_integration_instance_id",
        "integration_discoveries",
        ["integration_instance_id"],
        unique=False,
    )
    op.create_index("ix_integration_discoveries_plugin_id", "integration_discoveries", ["plugin_id"], unique=False)
    op.create_index("ix_integration_discoveries_status", "integration_discoveries", ["status"], unique=False)
    op.create_index("ix_integration_discoveries_claimed_device_id", "integration_discoveries", ["claimed_device_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_discoveries_claimed_device_id", table_name="integration_discoveries")
    op.drop_index("ix_integration_discoveries_status", table_name="integration_discoveries")
    op.drop_index("ix_integration_discoveries_plugin_id", table_name="integration_discoveries")
    op.drop_index("ix_integration_discoveries_integration_instance_id", table_name="integration_discoveries")
    op.drop_index("ix_integration_discoveries_household_id", table_name="integration_discoveries")
    op.drop_table("integration_discoveries")
