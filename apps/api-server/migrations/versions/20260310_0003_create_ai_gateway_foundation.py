"""create ai gateway foundation tables

Revision ID: 20260310_0003
Revises: 20260309_0002
Create Date: 2026-03-10 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260310_0003"
down_revision = "20260309_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider_code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("transport_type", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("api_version", sa.String(length=50), nullable=True),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("supported_capabilities_json", sa.Text(), nullable=False),
        sa.Column("privacy_level", sa.String(length=30), nullable=False),
        sa.Column("latency_budget_ms", sa.Integer(), nullable=True),
        sa.Column("cost_policy_json", sa.Text(), nullable=True),
        sa.Column("extra_config_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "uq_ai_provider_profiles_provider_code",
        "ai_provider_profiles",
        ["provider_code"],
        unique=True,
    )
    op.create_index(
        "idx_ai_provider_profiles_enabled",
        "ai_provider_profiles",
        ["enabled"],
        unique=False,
    )

    op.create_table(
        "ai_capability_routes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=True),
        sa.Column("primary_provider_profile_id", sa.Text(), nullable=True),
        sa.Column("fallback_provider_profile_ids_json", sa.Text(), nullable=False),
        sa.Column("routing_mode", sa.String(length=40), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_retry_count", sa.Integer(), nullable=False),
        sa.Column("allow_remote", sa.Boolean(), nullable=False),
        sa.Column("prompt_policy_json", sa.Text(), nullable=True),
        sa.Column("response_policy_json", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["primary_provider_profile_id"],
            ["ai_provider_profiles.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "idx_ai_capability_routes_capability",
        "ai_capability_routes",
        ["capability"],
        unique=False,
    )
    op.create_index(
        "idx_ai_capability_routes_household_id",
        "ai_capability_routes",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "uq_ai_capability_routes_global_capability",
        "ai_capability_routes",
        ["capability"],
        unique=True,
        postgresql_where=sa.text("household_id IS NULL"),
    )
    op.create_index(
        "uq_ai_capability_routes_household_capability",
        "ai_capability_routes",
        ["household_id", "capability"],
        unique=True,
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )

    op.create_table(
        "ai_model_call_logs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("provider_code", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=True),
        sa.Column("requester_member_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=False),
        sa.Column("input_policy", sa.String(length=50), nullable=False),
        sa.Column("masked_fields_json", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_member_id"], ["members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_ai_model_call_logs_trace_id",
        "ai_model_call_logs",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        "idx_ai_model_call_logs_household_created_at",
        "ai_model_call_logs",
        ["household_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_ai_model_call_logs_capability_created_at",
        "ai_model_call_logs",
        ["capability", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_ai_model_call_logs_capability_created_at", table_name="ai_model_call_logs")
    op.drop_index("idx_ai_model_call_logs_household_created_at", table_name="ai_model_call_logs")
    op.drop_index("idx_ai_model_call_logs_trace_id", table_name="ai_model_call_logs")
    op.drop_table("ai_model_call_logs")
    op.drop_index("uq_ai_capability_routes_household_capability", table_name="ai_capability_routes")
    op.drop_index("uq_ai_capability_routes_global_capability", table_name="ai_capability_routes")
    op.drop_index("idx_ai_capability_routes_household_id", table_name="ai_capability_routes")
    op.drop_index("idx_ai_capability_routes_capability", table_name="ai_capability_routes")
    op.drop_table("ai_capability_routes")
    op.drop_index("idx_ai_provider_profiles_enabled", table_name="ai_provider_profiles")
    op.drop_index("uq_ai_provider_profiles_provider_code", table_name="ai_provider_profiles")
    op.drop_table("ai_provider_profiles")
