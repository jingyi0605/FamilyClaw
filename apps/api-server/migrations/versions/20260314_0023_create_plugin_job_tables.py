"""create plugin job tables

Revision ID: 20260314_0023
Revises: 20260313_0022
Create Date: 2026-03-14 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260314_0023"
down_revision: str = "20260313_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("plugin_type", sa.String(length=30), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("request_payload_json", sa.Text(), nullable=False),
        sa.Column("payload_summary_json", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("current_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("response_deadline_at", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "idempotency_key", name="uq_plugin_jobs_household_idempotency_key"),
    )
    op.create_index("idx_plugin_jobs_household_id", "plugin_jobs", ["household_id"], unique=False)
    op.create_index("idx_plugin_jobs_plugin_id", "plugin_jobs", ["plugin_id"], unique=False)
    op.create_index("idx_plugin_jobs_status", "plugin_jobs", ["status"], unique=False)

    op.create_table(
        "plugin_job_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output_summary_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["plugin_jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_plugin_job_attempts_job_attempt_no"),
    )
    op.create_index("idx_plugin_job_attempts_job_id", "plugin_job_attempts", ["job_id"], unique=False)
    op.create_index("idx_plugin_job_attempts_status", "plugin_job_attempts", ["status"], unique=False)

    op.create_table(
        "plugin_job_notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(length=30), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("delivered_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["plugin_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_plugin_job_notifications_job_id", "plugin_job_notifications", ["job_id"], unique=False)
    op.create_index(
        "idx_plugin_job_notifications_type",
        "plugin_job_notifications",
        ["notification_type"],
        unique=False,
    )

    op.create_table(
        "plugin_job_responses",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["plugin_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_plugin_job_responses_job_id", "plugin_job_responses", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plugin_job_responses_job_id", table_name="plugin_job_responses")
    op.drop_table("plugin_job_responses")

    op.drop_index("idx_plugin_job_notifications_type", table_name="plugin_job_notifications")
    op.drop_index("idx_plugin_job_notifications_job_id", table_name="plugin_job_notifications")
    op.drop_table("plugin_job_notifications")

    op.drop_index("idx_plugin_job_attempts_status", table_name="plugin_job_attempts")
    op.drop_index("idx_plugin_job_attempts_job_id", table_name="plugin_job_attempts")
    op.drop_table("plugin_job_attempts")

    op.drop_index("idx_plugin_jobs_status", table_name="plugin_jobs")
    op.drop_index("idx_plugin_jobs_plugin_id", table_name="plugin_jobs")
    op.drop_index("idx_plugin_jobs_household_id", table_name="plugin_jobs")
    op.drop_table("plugin_jobs")
