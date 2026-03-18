"""add device scope to plugin config instances

Revision ID: 20260317_0050
Revises: 20260317_0049
Create Date: 2026-03-17 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0050"
down_revision = "20260317_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plugin_config_instances",
        sa.Column("device_id", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_plugin_config_instances_device_id_devices",
        "plugin_config_instances",
        "devices",
        ["device_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_plugin_config_instances_device_id",
        "plugin_config_instances",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_plugin_config_instances_device_id", table_name="plugin_config_instances")
    op.drop_constraint(
        "fk_plugin_config_instances_device_id_devices",
        "plugin_config_instances",
        type_="foreignkey",
    )
    op.drop_column("plugin_config_instances", "device_id")
