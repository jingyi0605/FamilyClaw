"""simplify plugin source and install model

Revision ID: 20260320_0062
Revises: 20260319_0061
Create Date: 2026-03-20 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0062"
down_revision = "20260319_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    plugin_mount_columns = {column["name"] for column in inspector.get_columns("plugin_mounts")}
    if "install_method" not in plugin_mount_columns:
        op.add_column("plugin_mounts", sa.Column("install_method", sa.String(length=20), nullable=True))

    marketplace_source_columns = {column["name"] for column in inspector.get_columns("plugin_marketplace_sources")}
    if "is_system" not in marketplace_source_columns:
        op.add_column(
            "plugin_marketplace_sources",
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    op.execute(
        sa.text(
            """
            UPDATE plugin_mounts
            SET source_type = 'third_party'
            WHERE source_type = 'official'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE plugin_state_overrides
            SET source_type = 'third_party'
            WHERE source_type = 'official'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE plugin_mounts
            SET install_method = 'local'
            WHERE source_type = 'third_party'
              AND install_method IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE plugin_mounts AS mounts
            SET install_method = 'marketplace'
            FROM plugin_marketplace_instances AS instances
            WHERE mounts.household_id = instances.household_id
              AND mounts.plugin_id = instances.plugin_id
            """
        )
    )
    op.execute(
        sa.text(
            r"""
            UPDATE plugin_mounts
            SET install_method = 'marketplace'
            WHERE install_method IS NULL
              AND (
                LOWER(plugin_root) LIKE '%/third_party/marketplace/%'
                OR LOWER(plugin_root) LIKE '%\\third_party\\marketplace\\%'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE plugin_mounts
            SET install_method = 'local'
            WHERE install_method IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE plugin_marketplace_sources
            SET is_system = CASE WHEN trusted_level = 'official' THEN TRUE ELSE FALSE END
            """
        )
    )

    if "trusted_level" in marketplace_source_columns:
        op.drop_column("plugin_marketplace_sources", "trusted_level")

    op.alter_column("plugin_mounts", "install_method", nullable=False)
    op.alter_column("plugin_mounts", "install_method", server_default=None)
    op.alter_column("plugin_marketplace_sources", "is_system", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    marketplace_source_columns = {column["name"] for column in inspector.get_columns("plugin_marketplace_sources")}

    if "trusted_level" not in marketplace_source_columns:
        op.add_column("plugin_marketplace_sources", sa.Column("trusted_level", sa.String(length=20), nullable=True))
        op.execute(
            sa.text(
                """
                UPDATE plugin_marketplace_sources
                SET trusted_level = CASE WHEN is_system THEN 'official' ELSE 'third_party' END
                """
            )
        )
        op.alter_column("plugin_marketplace_sources", "trusted_level", nullable=False)

    plugin_mount_columns = {column["name"] for column in inspector.get_columns("plugin_mounts")}
    if "install_method" in plugin_mount_columns:
        op.drop_column("plugin_mounts", "install_method")

    if "is_system" in marketplace_source_columns:
        op.drop_column("plugin_marketplace_sources", "is_system")
