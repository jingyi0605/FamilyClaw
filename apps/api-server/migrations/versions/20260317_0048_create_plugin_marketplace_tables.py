"""create plugin marketplace tables

Revision ID: 20260317_0048
Revises: 20260317_0047
Create Date: 2026-03-17 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0048"
down_revision = "20260317_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_marketplace_sources",
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("market_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("branch", sa.String(length=100), nullable=False),
        sa.Column("entry_root", sa.String(length=255), nullable=False),
        sa.Column("trusted_level", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_status", sa.String(length=20), nullable=True),
        sa.Column("last_sync_error_json", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_plugin_marketplace_sources_market_id", "plugin_marketplace_sources", ["market_id"], unique=False)

    op.create_table(
        "plugin_marketplace_entry_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_repo", sa.Text(), nullable=False),
        sa.Column("manifest_path", sa.Text(), nullable=False),
        sa.Column("readme_url", sa.Text(), nullable=False),
        sa.Column("publisher_json", sa.Text(), nullable=False),
        sa.Column("categories_json", sa.Text(), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=False),
        sa.Column("maintainers_json", sa.Text(), nullable=False),
        sa.Column("versions_json", sa.Text(), nullable=False),
        sa.Column("install_json", sa.Text(), nullable=False),
        sa.Column("repository_metrics_json", sa.Text(), nullable=True),
        sa.Column("raw_entry_json", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("latest_version", sa.String(length=50), nullable=False),
        sa.Column("manifest_digest", sa.String(length=128), nullable=True),
        sa.Column("sync_status", sa.String(length=20), nullable=False),
        sa.Column("sync_error_json", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "plugin_id",
            name="uq_plugin_marketplace_entry_snapshots_source_plugin",
        ),
    )
    op.create_index(
        "ix_plugin_marketplace_entry_snapshots_source_id",
        "plugin_marketplace_entry_snapshots",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_entry_snapshots_plugin_id",
        "plugin_marketplace_entry_snapshots",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_entry_snapshots_sync_status",
        "plugin_marketplace_entry_snapshots",
        ["sync_status"],
        unique=False,
    )

    op.create_table(
        "plugin_marketplace_install_tasks",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("requested_version", sa.String(length=50), nullable=True),
        sa.Column("installed_version", sa.String(length=50), nullable=True),
        sa.Column("install_status", sa.String(length=30), nullable=False),
        sa.Column("failure_stage", sa.String(length=50), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_repo", sa.Text(), nullable=True),
        sa.Column("market_repo", sa.Text(), nullable=True),
        sa.Column("artifact_url", sa.Text(), nullable=True),
        sa.Column("plugin_root", sa.Text(), nullable=True),
        sa.Column("manifest_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plugin_marketplace_install_tasks_household_id",
        "plugin_marketplace_install_tasks",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_install_tasks_source_id",
        "plugin_marketplace_install_tasks",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_install_tasks_plugin_id",
        "plugin_marketplace_install_tasks",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_install_tasks_install_status",
        "plugin_marketplace_install_tasks",
        ["install_status"],
        unique=False,
    )

    op.create_table(
        "plugin_marketplace_instances",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("installed_version", sa.String(length=50), nullable=False),
        sa.Column("install_status", sa.String(length=30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config_status", sa.String(length=20), nullable=False, server_default="unconfigured"),
        sa.Column("source_repo", sa.Text(), nullable=False),
        sa.Column("market_repo", sa.Text(), nullable=False),
        sa.Column("plugin_root", sa.Text(), nullable=False),
        sa.Column("manifest_path", sa.Text(), nullable=False),
        sa.Column("python_path", sa.Text(), nullable=False),
        sa.Column("working_dir", sa.Text(), nullable=True),
        sa.Column("installed_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "plugin_id",
            name="uq_plugin_marketplace_instances_household_plugin",
        ),
    )
    op.create_index(
        "ix_plugin_marketplace_instances_household_id",
        "plugin_marketplace_instances",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_instances_source_id",
        "plugin_marketplace_instances",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_instances_plugin_id",
        "plugin_marketplace_instances",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "ix_plugin_marketplace_instances_install_status",
        "plugin_marketplace_instances",
        ["install_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_plugin_marketplace_instances_install_status", table_name="plugin_marketplace_instances")
    op.drop_index("ix_plugin_marketplace_instances_plugin_id", table_name="plugin_marketplace_instances")
    op.drop_index("ix_plugin_marketplace_instances_source_id", table_name="plugin_marketplace_instances")
    op.drop_index("ix_plugin_marketplace_instances_household_id", table_name="plugin_marketplace_instances")
    op.drop_table("plugin_marketplace_instances")

    op.drop_index("ix_plugin_marketplace_install_tasks_install_status", table_name="plugin_marketplace_install_tasks")
    op.drop_index("ix_plugin_marketplace_install_tasks_plugin_id", table_name="plugin_marketplace_install_tasks")
    op.drop_index("ix_plugin_marketplace_install_tasks_source_id", table_name="plugin_marketplace_install_tasks")
    op.drop_index("ix_plugin_marketplace_install_tasks_household_id", table_name="plugin_marketplace_install_tasks")
    op.drop_table("plugin_marketplace_install_tasks")

    op.drop_index(
        "ix_plugin_marketplace_entry_snapshots_sync_status",
        table_name="plugin_marketplace_entry_snapshots",
    )
    op.drop_index(
        "ix_plugin_marketplace_entry_snapshots_plugin_id",
        table_name="plugin_marketplace_entry_snapshots",
    )
    op.drop_index(
        "ix_plugin_marketplace_entry_snapshots_source_id",
        table_name="plugin_marketplace_entry_snapshots",
    )
    op.drop_table("plugin_marketplace_entry_snapshots")

    op.drop_index("ix_plugin_marketplace_sources_market_id", table_name="plugin_marketplace_sources")
    op.drop_table("plugin_marketplace_sources")
