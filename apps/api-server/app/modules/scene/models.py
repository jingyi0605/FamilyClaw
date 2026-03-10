from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class SceneTemplate(Base):
    __tablename__ = "scene_templates"
    __table_args__ = (
        UniqueConstraint("household_id", "template_code", name="uq_scene_templates_household_code"),
        Index("idx_scene_templates_household_enabled_priority", "household_id", "enabled", "priority"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trigger_json: Mapped[str] = mapped_column(Text, nullable=False)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    guards_json: Mapped[str] = mapped_column(Text, nullable=False)
    actions_json: Mapped[str] = mapped_column(Text, nullable=False)
    rollout_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class SceneExecution(Base):
    __tablename__ = "scene_executions"
    __table_args__ = (
        Index("idx_scene_executions_household_status_started_at", "household_id", "status", "started_at"),
        Index("idx_scene_executions_template_trigger_key", "template_id", "trigger_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    template_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("scene_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_key: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    guard_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SceneExecutionStep(Base):
    __tablename__ = "scene_execution_steps"
    __table_args__ = (
        UniqueConstraint("execution_id", "step_index", name="uq_scene_execution_steps_execution_step"),
        Index("idx_scene_execution_steps_execution_status", "execution_id", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("scene_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
