"""create scheduler foundation

Revision ID: 20260314_0027
Revises: 20260314_0026
Create Date: 2026-03-14 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0027"
down_revision = "20260314_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_task_definitions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("owner_scope", sa.String(length=32), nullable=False),
        sa.Column("owner_member_id", sa.Text(), nullable=True),
        sa.Column("created_by_account_id", sa.Text(), nullable=False),
        sa.Column("last_modified_by_account_id", sa.Text(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("schedule_type", sa.String(length=32), nullable=True),
        sa.Column("schedule_expr", sa.String(length=128), nullable=True),
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_ref_id", sa.String(length=100), nullable=True),
        sa.Column("rule_type", sa.String(length=32), nullable=True),
        sa.Column("rule_config_json", sa.Text(), nullable=True),
        sa.Column("payload_template_json", sa.Text(), nullable=True),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("quiet_hours_policy", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_run_at", sa.Text(), nullable=True),
        sa.Column("last_result", sa.String(length=32), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.Text(), nullable=True),
        sa.Column("next_heartbeat_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_member_id"], ["members.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_modified_by_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("household_id", "code", name="uq_scheduled_task_definitions_household_code"),
        sa.CheckConstraint(
            "(owner_scope = 'member' AND owner_member_id IS NOT NULL) OR "
            "(owner_scope = 'household' AND owner_member_id IS NULL)",
            name="ck_scheduled_task_definitions_owner_scope",
        ),
        sa.CheckConstraint(
            "(trigger_type = 'schedule' AND schedule_type IS NOT NULL AND schedule_expr IS NOT NULL "
            "AND heartbeat_interval_seconds IS NULL) OR "
            "(trigger_type = 'heartbeat' AND schedule_type IS NULL AND schedule_expr IS NULL "
            "AND heartbeat_interval_seconds IS NOT NULL)",
            name="ck_scheduled_task_definitions_trigger_fields",
        ),
    )
    op.create_index(
        "idx_scheduled_task_definitions_schedule_due",
        "scheduled_task_definitions",
        ["enabled", "status", "trigger_type", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "idx_scheduled_task_definitions_heartbeat_due",
        "scheduled_task_definitions",
        ["enabled", "status", "trigger_type", "next_heartbeat_at"],
        unique=False,
    )
    op.create_index(
        "idx_scheduled_task_definitions_household_owner",
        "scheduled_task_definitions",
        ["household_id", "owner_scope", "owner_member_id"],
        unique=False,
    )

    op.create_table(
        "scheduled_task_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("task_definition_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("owner_scope", sa.String(length=32), nullable=False),
        sa.Column("owner_member_id", sa.Text(), nullable=True),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("scheduled_for", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("evaluation_snapshot_json", sa.Text(), nullable=True),
        sa.Column("dispatch_payload_json", sa.Text(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_ref_id", sa.String(length=100), nullable=True),
        sa.Column("target_run_id", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_definition_id"], ["scheduled_task_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("idempotency_key", name="uq_scheduled_task_runs_idempotency_key"),
    )
    op.create_index(
        "idx_scheduled_task_runs_household_status_scheduled_for",
        "scheduled_task_runs",
        ["household_id", "status", "scheduled_for"],
        unique=False,
    )
    op.create_index(
        "idx_scheduled_task_runs_task_definition_created",
        "scheduled_task_runs",
        ["task_definition_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "scheduled_task_deliveries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("task_run_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_type", sa.String(length=32), nullable=False),
        sa.Column("recipient_ref", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["task_run_id"], ["scheduled_task_runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_scheduled_task_deliveries_run_status",
        "scheduled_task_deliveries",
        ["task_run_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_scheduled_task_deliveries_recipient",
        "scheduled_task_deliveries",
        ["recipient_type", "recipient_ref"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_scheduled_task_deliveries_recipient", table_name="scheduled_task_deliveries")
    op.drop_index("idx_scheduled_task_deliveries_run_status", table_name="scheduled_task_deliveries")
    op.drop_table("scheduled_task_deliveries")
    op.drop_index("idx_scheduled_task_runs_task_definition_created", table_name="scheduled_task_runs")
    op.drop_index("idx_scheduled_task_runs_household_status_scheduled_for", table_name="scheduled_task_runs")
    op.drop_table("scheduled_task_runs")
    op.drop_index("idx_scheduled_task_definitions_household_owner", table_name="scheduled_task_definitions")
    op.drop_index("idx_scheduled_task_definitions_heartbeat_due", table_name="scheduled_task_definitions")
    op.drop_index("idx_scheduled_task_definitions_schedule_due", table_name="scheduled_task_definitions")
    op.drop_table("scheduled_task_definitions")
