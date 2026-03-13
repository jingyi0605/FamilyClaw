"""create plugin runs

Revision ID: 20260313_0019
Revises: 20260313_0018
Create Date: 2026-03-13 12:05:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0019"
down_revision: str = "20260313_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("plugin_type", sa.String(length=30), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_card_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_plugin_runs_household_id", "plugin_runs", ["household_id"], unique=False)
    op.create_index("idx_plugin_runs_plugin_id", "plugin_runs", ["plugin_id"], unique=False)
    op.create_index("idx_plugin_runs_status", "plugin_runs", ["status"], unique=False)
    op.create_index("idx_plugin_runs_household_plugin", "plugin_runs", ["household_id", "plugin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_runs_household_plugin", table_name="plugin_runs")
    op.drop_index("idx_plugin_runs_status", table_name="plugin_runs")
    op.drop_index("idx_plugin_runs_plugin_id", table_name="plugin_runs")
    op.drop_index("idx_plugin_runs_household_id", table_name="plugin_runs")
    op.drop_table("plugin_runs")
