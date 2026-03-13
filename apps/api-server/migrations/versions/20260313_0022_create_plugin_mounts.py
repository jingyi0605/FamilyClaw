"""create plugin mounts

Revision ID: 20260313_0022
Revises: 20260313_0021
Create Date: 2026-03-13 23:55:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0022"
down_revision: str = "20260313_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_mounts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("execution_backend", sa.String(length=30), nullable=False, server_default="subprocess_runner"),
        sa.Column("manifest_path", sa.Text(), nullable=False),
        sa.Column("plugin_root", sa.Text(), nullable=False),
        sa.Column("python_path", sa.Text(), nullable=False),
        sa.Column("working_dir", sa.Text(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("stdout_limit_bytes", sa.Integer(), nullable=False, server_default="65536"),
        sa.Column("stderr_limit_bytes", sa.Integer(), nullable=False, server_default="65536"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "plugin_id", name="uq_plugin_mounts_household_plugin"),
    )
    op.create_index("idx_plugin_mounts_household_id", "plugin_mounts", ["household_id"], unique=False)
    op.create_index("idx_plugin_mounts_plugin_id", "plugin_mounts", ["plugin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_mounts_plugin_id", table_name="plugin_mounts")
    op.drop_index("idx_plugin_mounts_household_id", table_name="plugin_mounts")
    op.drop_table("plugin_mounts")
