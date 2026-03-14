"""add plugin job schedule sources

Revision ID: 20260314_0028
Revises: 20260314_0027
Create Date: 2026-03-14 19:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0028"
down_revision = "20260314_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plugin_jobs", sa.Column("source_task_definition_id", sa.Text(), nullable=True))
    op.add_column("plugin_jobs", sa.Column("source_task_run_id", sa.Text(), nullable=True))
    op.create_index("idx_plugin_jobs_source_task_definition_id", "plugin_jobs", ["source_task_definition_id"], unique=False)
    op.create_index("idx_plugin_jobs_source_task_run_id", "plugin_jobs", ["source_task_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_jobs_source_task_run_id", table_name="plugin_jobs")
    op.drop_index("idx_plugin_jobs_source_task_definition_id", table_name="plugin_jobs")
    op.drop_column("plugin_jobs", "source_task_run_id")
    op.drop_column("plugin_jobs", "source_task_definition_id")
