"""add agent model bindings

Revision ID: 20260318_0052
Revises: 20260317_0051
Create Date: 2026-03-18 13:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0052"
down_revision = "20260317_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "family_agent_runtime_policies",
        sa.Column("model_bindings_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "family_agent_runtime_policies",
        sa.Column("agent_skill_model_bindings_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.alter_column("family_agent_runtime_policies", "model_bindings_json", server_default=None)
    op.alter_column("family_agent_runtime_policies", "agent_skill_model_bindings_json", server_default=None)


def downgrade() -> None:
    op.drop_column("family_agent_runtime_policies", "agent_skill_model_bindings_json")
    op.drop_column("family_agent_runtime_policies", "model_bindings_json")
