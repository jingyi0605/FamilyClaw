"""create qa reminder and scene tables

Revision ID: 20260310_0004
Revises: 20260310_0003
Create Date: 2026-03-10 12:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260310_0004"
down_revision = "20260310_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_query_logs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("requester_member_id", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(length=50), nullable=False),
        sa.Column("answer_summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("degraded", sa.Boolean(), nullable=False),
        sa.Column("facts_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_member_id"], ["members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_qa_query_logs_household_created_at",
        "qa_query_logs",
        ["household_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_qa_query_logs_requester_member_id",
        "qa_query_logs",
        ["requester_member_id"],
        unique=False,
    )

    op.create_table(
        "reminder_tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("owner_member_id", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reminder_type", sa.String(length=30), nullable=False),
        sa.Column("target_member_ids_json", sa.Text(), nullable=False),
        sa.Column("preferred_room_ids_json", sa.Text(), nullable=False),
        sa.Column("schedule_kind", sa.String(length=30), nullable=False),
        sa.Column("schedule_rule_json", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("delivery_channels_json", sa.Text(), nullable=False),
        sa.Column("ack_required", sa.Boolean(), nullable=False),
        sa.Column("escalation_policy_json", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_member_id"], ["members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_reminder_tasks_household_enabled_updated_at",
        "reminder_tasks",
        ["household_id", "enabled", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_reminder_tasks_owner_member_id",
        "reminder_tasks",
        ["owner_member_id"],
        unique=False,
    )

    op.create_table(
        "reminder_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("schedule_slot_key", sa.String(length=100), nullable=False),
        sa.Column("trigger_reason", sa.String(length=50), nullable=False),
        sa.Column("planned_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("context_snapshot_json", sa.Text(), nullable=True),
        sa.Column("result_summary_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["reminder_tasks.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("task_id", "schedule_slot_key", name="uq_reminder_runs_task_slot"),
    )
    op.create_index(
        "idx_reminder_runs_household_status_planned_at",
        "reminder_runs",
        ["household_id", "status", "planned_at"],
        unique=False,
    )

    op.create_table(
        "reminder_delivery_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("target_member_id", sa.Text(), nullable=True),
        sa.Column("target_room_id", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("planned_at", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_result_json", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["reminder_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "run_id",
            "channel",
            "attempt_index",
            name="uq_reminder_delivery_attempts_run_channel_attempt",
        ),
    )
    op.create_index(
        "idx_reminder_delivery_attempts_run_status",
        "reminder_delivery_attempts",
        ["run_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_reminder_delivery_attempts_target_member_id",
        "reminder_delivery_attempts",
        ["target_member_id"],
        unique=False,
    )

    op.create_table(
        "reminder_ack_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["reminder_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_reminder_ack_events_run_created_at",
        "reminder_ack_events",
        ["run_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_reminder_ack_events_member_id",
        "reminder_ack_events",
        ["member_id"],
        unique=False,
    )

    op.create_table(
        "scene_templates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("template_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("trigger_json", sa.Text(), nullable=False),
        sa.Column("conditions_json", sa.Text(), nullable=False),
        sa.Column("guards_json", sa.Text(), nullable=False),
        sa.Column("actions_json", sa.Text(), nullable=False),
        sa.Column("rollout_policy_json", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "template_code", name="uq_scene_templates_household_code"),
    )
    op.create_index(
        "idx_scene_templates_household_enabled_priority",
        "scene_templates",
        ["household_id", "enabled", "priority"],
        unique=False,
    )

    op.create_table(
        "scene_executions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("trigger_key", sa.String(length=100), nullable=False),
        sa.Column("trigger_source", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("guard_result_json", sa.Text(), nullable=True),
        sa.Column("conflict_result_json", sa.Text(), nullable=True),
        sa.Column("context_snapshot_json", sa.Text(), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["scene_templates.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "idx_scene_executions_household_status_started_at",
        "scene_executions",
        ["household_id", "status", "started_at"],
        unique=False,
    )
    op.create_index(
        "idx_scene_executions_template_trigger_key",
        "scene_executions",
        ["template_id", "trigger_key"],
        unique=False,
    )

    op.create_table(
        "scene_execution_steps",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("execution_id", sa.Text(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=30), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=True),
        sa.Column("request_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["scene_executions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("execution_id", "step_index", name="uq_scene_execution_steps_execution_step"),
    )
    op.create_index(
        "idx_scene_execution_steps_execution_status",
        "scene_execution_steps",
        ["execution_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_scene_execution_steps_execution_status", table_name="scene_execution_steps")
    op.drop_table("scene_execution_steps")
    op.drop_index("idx_scene_executions_template_trigger_key", table_name="scene_executions")
    op.drop_index("idx_scene_executions_household_status_started_at", table_name="scene_executions")
    op.drop_table("scene_executions")
    op.drop_index("idx_scene_templates_household_enabled_priority", table_name="scene_templates")
    op.drop_table("scene_templates")
    op.drop_index("idx_reminder_ack_events_member_id", table_name="reminder_ack_events")
    op.drop_index("idx_reminder_ack_events_run_created_at", table_name="reminder_ack_events")
    op.drop_table("reminder_ack_events")
    op.drop_index("idx_reminder_delivery_attempts_target_member_id", table_name="reminder_delivery_attempts")
    op.drop_index("idx_reminder_delivery_attempts_run_status", table_name="reminder_delivery_attempts")
    op.drop_table("reminder_delivery_attempts")
    op.drop_index("idx_reminder_runs_household_status_planned_at", table_name="reminder_runs")
    op.drop_table("reminder_runs")
    op.drop_index("idx_reminder_tasks_owner_member_id", table_name="reminder_tasks")
    op.drop_index("idx_reminder_tasks_household_enabled_updated_at", table_name="reminder_tasks")
    op.drop_table("reminder_tasks")
    op.drop_index("idx_qa_query_logs_requester_member_id", table_name="qa_query_logs")
    op.drop_index("idx_qa_query_logs_household_created_at", table_name="qa_query_logs")
    op.drop_table("qa_query_logs")
