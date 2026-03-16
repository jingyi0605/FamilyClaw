"""create plugin config instances

Revision ID: 20260316_0039
Revises: 20260316_0038
Create Date: 2026-03-16 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0039"
down_revision = "20260316_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_config_instances",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("secret_data_encrypted", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "plugin_id",
            "scope_type",
            "scope_key",
            name="uq_plugin_config_instances_household_plugin_scope",
        ),
    )
    op.create_index(
        "idx_plugin_config_instances_household_id",
        "plugin_config_instances",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_config_instances_plugin_id",
        "plugin_config_instances",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_config_instances_scope_type",
        "plugin_config_instances",
        ["scope_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_plugin_config_instances_scope_type", table_name="plugin_config_instances")
    op.drop_index("idx_plugin_config_instances_plugin_id", table_name="plugin_config_instances")
    op.drop_index("idx_plugin_config_instances_household_id", table_name="plugin_config_instances")
    op.drop_table("plugin_config_instances")
