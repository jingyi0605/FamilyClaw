from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class ReminderTask(Base):
    __tablename__ = "reminder_tasks"
    __table_args__ = (
        Index("idx_reminder_tasks_household_enabled_updated_at", "household_id", "enabled", "updated_at"),
        Index("idx_reminder_tasks_owner_member_id", "owner_member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_member_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_room_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    schedule_rule_json: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_channels_json: Mapped[str] = mapped_column(Text, nullable=False)
    ack_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class ReminderRun(Base):
    __tablename__ = "reminder_runs"
    __table_args__ = (
        UniqueConstraint("task_id", "schedule_slot_key", name="uq_reminder_runs_task_slot"),
        Index("idx_reminder_runs_household_status_planned_at", "household_id", "status", "planned_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("reminder_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_slot_key: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    planned_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    context_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReminderDeliveryAttempt(Base):
    __tablename__ = "reminder_delivery_attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "channel", "attempt_index", name="uq_reminder_delivery_attempts_run_channel_attempt"),
        Index("idx_reminder_delivery_attempts_run_status", "run_id", "status"),
        Index("idx_reminder_delivery_attempts_target_member_id", "target_member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("reminder_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_room_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_at: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReminderAckEvent(Base):
    __tablename__ = "reminder_ack_events"
    __table_args__ = (
        Index("idx_reminder_ack_events_run_created_at", "run_id", "created_at"),
        Index("idx_reminder_ack_events_member_id", "member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("reminder_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
