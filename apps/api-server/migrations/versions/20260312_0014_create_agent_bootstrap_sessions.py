"""create agent bootstrap sessions table

Revision ID: 20260312_0014
Revises: 20260311_0013
Create Date: 2026-03-12 11:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260312_0014"
down_revision: str = "20260311_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_agent_bootstrap_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="collecting"),
        sa.Column("pending_field", sa.String(length=50), nullable=True),
        sa.Column("draft_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("transcript_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_family_agent_bootstrap_sessions_household_id",
        "family_agent_bootstrap_sessions",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_family_agent_bootstrap_sessions_status",
        "family_agent_bootstrap_sessions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_family_agent_bootstrap_sessions_status",
        table_name="family_agent_bootstrap_sessions",
    )
    op.drop_index(
        "idx_family_agent_bootstrap_sessions_household_id",
        table_name="family_agent_bootstrap_sessions",
    )
    op.drop_table("family_agent_bootstrap_sessions")
