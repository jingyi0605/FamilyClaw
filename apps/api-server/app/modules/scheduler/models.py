from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class ScheduledTaskDefinition(Base):
    __tablename__ = "scheduled_task_definitions"
    __table_args__ = (
        UniqueConstraint("household_id", "code", name="uq_scheduled_task_definitions_household_code"),
        CheckConstraint(
            "(owner_scope = 'member' AND owner_member_id IS NOT NULL) OR "
            "(owner_scope = 'household' AND owner_member_id IS NULL)",
            name="ck_scheduled_task_definitions_owner_scope",
        ),
        CheckConstraint(
            "(trigger_type = 'schedule' AND schedule_type IS NOT NULL AND schedule_expr IS NOT NULL "
            "AND heartbeat_interval_seconds IS NULL) OR "
            "(trigger_type = 'heartbeat' AND schedule_type IS NULL AND schedule_expr IS NULL "
            "AND heartbeat_interval_seconds IS NOT NULL)",
            name="ck_scheduled_task_definitions_trigger_fields",
        ),
        Index(
            "idx_scheduled_task_definitions_schedule_due",
            "enabled",
            "status",
            "trigger_type",
            "next_run_at",
        ),
        Index(
            "idx_scheduled_task_definitions_heartbeat_due",
            "enabled",
            "status",
            "trigger_type",
            "next_heartbeat_at",
        ),
        Index("idx_scheduled_task_definitions_household_owner", "household_id", "owner_scope", "owner_member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(Text, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    owner_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_member_id: Mapped[str | None] = mapped_column(Text, ForeignKey("members.id", ondelete="RESTRICT"), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(Text, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    last_modified_by_account_id: Mapped[str] = mapped_column(Text, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    schedule_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schedule_expr: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heartbeat_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_template_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiet_hours_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="suppress")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_run_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_heartbeat_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class ScheduledTaskRun(Base):
    __tablename__ = "scheduled_task_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_scheduled_task_runs_idempotency_key"),
        Index("idx_scheduled_task_runs_household_status_scheduled_for", "household_id", "status", "scheduled_for"),
        Index("idx_scheduled_task_runs_task_definition_created", "task_definition_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_definition_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("scheduled_task_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    household_id: Mapped[str] = mapped_column(Text, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    owner_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_member_id: Mapped[str | None] = mapped_column(Text, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    evaluation_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ScheduledTaskDelivery(Base):
    __tablename__ = "scheduled_task_deliveries"
    __table_args__ = (
        Index("idx_scheduled_task_deliveries_run_status", "task_run_id", "status"),
        Index("idx_scheduled_task_deliveries_recipient", "recipient_type", "recipient_ref"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_run_id: Mapped[str] = mapped_column(Text, ForeignKey("scheduled_task_runs.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
