"""add plugin job retry after

Revision ID: 20260314_0024
Revises: 20260314_0023
Create Date: 2026-03-14 12:10:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260314_0024"
down_revision: str = "20260314_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plugin_jobs", sa.Column("retry_after_at", sa.Text(), nullable=True))
    op.create_index("idx_plugin_jobs_retry_after_at", "plugin_jobs", ["retry_after_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_jobs_retry_after_at", table_name="plugin_jobs")
    op.drop_column("plugin_jobs", "retry_after_at")
