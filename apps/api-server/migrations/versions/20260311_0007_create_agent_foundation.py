"""create agent foundation tables

Revision ID: 20260311_0007
Revises: 20260310_0006
Create Date: 2026-03-11 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0007"
down_revision: str = "20260310_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_agents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_family_agents_household_id", "family_agents", ["household_id"], unique=False)
    op.create_index("idx_family_agents_agent_type", "family_agents", ["agent_type"], unique=False)
    op.create_index("idx_family_agents_status", "family_agents", ["status"], unique=False)
    op.create_index(
        "uq_family_agents_household_code",
        "family_agents",
        ["household_id", "code"],
        unique=True,
    )
    op.create_index(
        "uq_family_agents_household_primary",
        "family_agents",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "family_agent_soul_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("self_identity", sa.Text(), nullable=False),
        sa.Column("role_summary", sa.Text(), nullable=False),
        sa.Column("intro_message", sa.Text(), nullable=True),
        sa.Column("speaking_style", sa.Text(), nullable=True),
        sa.Column("personality_traits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("service_focus_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("service_boundaries_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=30), nullable=False, server_default="system"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["family_agents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "version", name="uq_family_agent_soul_profiles_agent_version"),
    )
    op.create_index(
        "idx_family_agent_soul_profiles_agent_id",
        "family_agent_soul_profiles",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "idx_family_agent_soul_profiles_is_active",
        "family_agent_soul_profiles",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "uq_family_agent_soul_profiles_agent_active",
        "family_agent_soul_profiles",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "family_agent_member_cognitions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("display_address", sa.String(length=100), nullable=True),
        sa.Column("closeness_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("service_priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("communication_style", sa.Text(), nullable=True),
        sa.Column("care_notes_json", sa.Text(), nullable=True),
        sa.Column("prompt_notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["family_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "member_id", name="uq_family_agent_member_cognitions_agent_member"),
    )
    op.create_index(
        "idx_family_agent_member_cognitions_agent_id",
        "family_agent_member_cognitions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "idx_family_agent_member_cognitions_member_id",
        "family_agent_member_cognitions",
        ["member_id"],
        unique=False,
    )

    op.create_table(
        "family_agent_runtime_policies",
        sa.Column("agent_id", sa.Text(), primary_key=True),
        sa.Column("conversation_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("default_entry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("routing_tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("memory_scope_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["family_agents.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("family_agent_runtime_policies")

    op.drop_index(
        "idx_family_agent_member_cognitions_member_id",
        table_name="family_agent_member_cognitions",
    )
    op.drop_index(
        "idx_family_agent_member_cognitions_agent_id",
        table_name="family_agent_member_cognitions",
    )
    op.drop_table("family_agent_member_cognitions")

    op.drop_index(
        "uq_family_agent_soul_profiles_agent_active",
        table_name="family_agent_soul_profiles",
    )
    op.drop_index(
        "idx_family_agent_soul_profiles_is_active",
        table_name="family_agent_soul_profiles",
    )
    op.drop_index(
        "idx_family_agent_soul_profiles_agent_id",
        table_name="family_agent_soul_profiles",
    )
    op.drop_table("family_agent_soul_profiles")

    op.drop_index("uq_family_agents_household_primary", table_name="family_agents")
    op.drop_index("uq_family_agents_household_code", table_name="family_agents")
    op.drop_index("idx_family_agents_status", table_name="family_agents")
    op.drop_index("idx_family_agents_agent_type", table_name="family_agents")
    op.drop_index("idx_family_agents_household_id", table_name="family_agents")
    op.drop_table("family_agents")
