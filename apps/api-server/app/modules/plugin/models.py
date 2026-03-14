from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class PluginRun(Base):
    __tablename__ = "plugin_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plugin_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    raw_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    memory_card_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class PluginRawRecord(Base):
    __tablename__ = "plugin_raw_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class PluginMount(Base):
    __tablename__ = "plugin_mounts"
    __table_args__ = (
        UniqueConstraint("household_id", "plugin_id", name="uq_plugin_mounts_household_plugin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_backend: Mapped[str] = mapped_column(String(30), nullable=False, default="subprocess_runner")
    manifest_path: Mapped[str] = mapped_column(Text, nullable=False)
    plugin_root: Mapped[str] = mapped_column(Text, nullable=False)
    python_path: Mapped[str] = mapped_column(Text, nullable=False)
    working_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=30)
    stdout_limit_bytes: Mapped[int] = mapped_column(nullable=False, default=65536)
    stderr_limit_bytes: Mapped[int] = mapped_column(nullable=False, default=65536)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class PluginJob(Base):
    __tablename__ = "plugin_jobs"
    __table_args__ = (
        UniqueConstraint("household_id", "idempotency_key", name="uq_plugin_jobs_household_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plugin_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    request_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_task_definition_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    source_task_run_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    current_attempt: Mapped[int] = mapped_column(nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=1)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_after_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_deadline_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class PluginJobAttempt(Base):
    __tablename__ = "plugin_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no", name="uq_plugin_job_attempts_job_attempt_no"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("plugin_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_no: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class PluginJobNotification(Base):
    __tablename__ = "plugin_job_notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("plugin_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class PluginJobResponse(Base):
    __tablename__ = "plugin_job_responses"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("plugin_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
