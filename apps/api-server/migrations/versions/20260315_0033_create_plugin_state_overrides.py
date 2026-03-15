"""create plugin state overrides

Revision ID: 20260315_0033
Revises: 20260314_0032
Create Date: 2026-03-15 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0033"
down_revision: str = "20260314_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_state_overrides",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "plugin_id", name="uq_plugin_state_overrides_household_plugin"),
    )
    op.create_index("idx_plugin_state_overrides_household_id", "plugin_state_overrides", ["household_id"], unique=False)
    op.create_index("idx_plugin_state_overrides_plugin_id", "plugin_state_overrides", ["plugin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_state_overrides_plugin_id", table_name="plugin_state_overrides")
    op.drop_index("idx_plugin_state_overrides_household_id", table_name="plugin_state_overrides")
    op.drop_table("plugin_state_overrides")
