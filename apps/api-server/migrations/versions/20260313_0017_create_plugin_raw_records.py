"""create plugin raw records

Revision ID: 20260313_0017
Revises: 20260312_0016
Create Date: 2026-03-13 10:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0017"
down_revision: str = "20260312_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_raw_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_plugin_raw_records_household_id",
        "plugin_raw_records",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_raw_records_plugin_id",
        "plugin_raw_records",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_raw_records_run_id",
        "plugin_raw_records",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_raw_records_record_type",
        "plugin_raw_records",
        ["record_type"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_raw_records_household_plugin_run",
        "plugin_raw_records",
        ["household_id", "plugin_id", "run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_plugin_raw_records_household_plugin_run", table_name="plugin_raw_records")
    op.drop_index("idx_plugin_raw_records_record_type", table_name="plugin_raw_records")
    op.drop_index("idx_plugin_raw_records_run_id", table_name="plugin_raw_records")
    op.drop_index("idx_plugin_raw_records_plugin_id", table_name="plugin_raw_records")
    op.drop_index("idx_plugin_raw_records_household_id", table_name="plugin_raw_records")
    op.drop_table("plugin_raw_records")
