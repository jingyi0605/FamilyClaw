"""add repo access fields to plugin marketplace sources

Revision ID: 20260317_0051
Revises: 20260317_0050
Create Date: 2026-03-17 23:58:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0051"
down_revision = "20260317_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plugin_marketplace_sources", sa.Column("owner", sa.String(length=100), nullable=True))
    op.add_column(
        "plugin_marketplace_sources",
        sa.Column("repo_provider", sa.String(length=20), nullable=False, server_default="github"),
    )
    op.add_column("plugin_marketplace_sources", sa.Column("api_base_url", sa.Text(), nullable=True))
    op.add_column("plugin_marketplace_sources", sa.Column("mirror_repo_url", sa.Text(), nullable=True))
    op.add_column("plugin_marketplace_sources", sa.Column("mirror_repo_provider", sa.String(length=20), nullable=True))
    op.add_column("plugin_marketplace_sources", sa.Column("mirror_api_base_url", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE plugin_marketplace_sources
        SET repo_provider = 'github'
        WHERE repo_provider IS NULL OR repo_provider = ''
        """
    )
    op.alter_column("plugin_marketplace_sources", "repo_provider", server_default=None)


def downgrade() -> None:
    op.drop_column("plugin_marketplace_sources", "mirror_api_base_url")
    op.drop_column("plugin_marketplace_sources", "mirror_repo_provider")
    op.drop_column("plugin_marketplace_sources", "mirror_repo_url")
    op.drop_column("plugin_marketplace_sources", "api_base_url")
    op.drop_column("plugin_marketplace_sources", "repo_provider")
    op.drop_column("plugin_marketplace_sources", "owner")
