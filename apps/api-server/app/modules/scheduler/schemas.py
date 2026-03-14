from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

OwnerScope = Literal["household", "member"]
TriggerType = Literal["schedule", "heartbeat"]
ScheduleType = Literal["daily", "interval", "cron"]
TargetType = Literal["plugin_job", "agent_reminder", "system_notice"]
RuleType = Literal["none", "context_insight", "presence", "device_summary"]
TaskStatus = Literal["active", "paused", "error", "invalid_dependency"]
RunStatus = Literal["queued", "dispatching", "succeeded", "failed", "skipped", "suppressed"]
TriggerSource = Literal["schedule", "heartbeat", "manual_retry"]


class ScheduledTaskDefinitionBase(BaseModel):
    household_id: str = Field(min_length=1)
    owner_scope: OwnerScope
    owner_member_id: str | None = Field(default=None, min_length=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    trigger_type: TriggerType
    schedule_type: ScheduleType | None = None
    schedule_expr: str | None = Field(default=None, min_length=1, max_length=128)
    heartbeat_interval_seconds: int | None = Field(default=None, ge=1, le=31_536_000)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    target_type: TargetType
    target_ref_id: str | None = Field(default=None, min_length=1, max_length=100)
    rule_type: RuleType = "none"
    rule_config: dict[str, Any] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=0, ge=0, le=31_536_000)
    quiet_hours_policy: Literal["allow", "suppress", "delay"] = "suppress"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_trigger_fields(self) -> "ScheduledTaskDefinitionBase":
        if self.owner_scope == "member" and not self.owner_member_id:
            raise ValueError("member scope requires owner_member_id")
        if self.owner_scope == "household" and self.owner_member_id is not None:
            raise ValueError("household scope does not allow owner_member_id")
        if self.trigger_type == "schedule":
            if self.schedule_type is None or self.schedule_expr is None:
                raise ValueError("schedule trigger requires schedule_type and schedule_expr")
            if self.heartbeat_interval_seconds is not None:
                raise ValueError("schedule trigger does not allow heartbeat_interval_seconds")
        else:
            if self.heartbeat_interval_seconds is None:
                raise ValueError("heartbeat trigger requires heartbeat_interval_seconds")
            if self.schedule_type is not None or self.schedule_expr is not None:
                raise ValueError("heartbeat trigger does not allow schedule fields")
        return self


class ScheduledTaskDefinitionCreate(ScheduledTaskDefinitionBase):
    pass


class ScheduledTaskDefinitionUpdate(BaseModel):
    owner_scope: OwnerScope | None = None
    owner_member_id: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    schedule_type: ScheduleType | None = None
    schedule_expr: str | None = Field(default=None, min_length=1, max_length=128)
    heartbeat_interval_seconds: int | None = Field(default=None, ge=1, le=31_536_000)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    target_type: TargetType | None = None
    target_ref_id: str | None = Field(default=None, min_length=1, max_length=100)
    rule_type: RuleType | None = None
    rule_config: dict[str, Any] | None = None
    payload_template: dict[str, Any] | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=31_536_000)
    quiet_hours_policy: Literal["allow", "suppress", "delay"] | None = None
    enabled: bool | None = None
    status: TaskStatus | None = None


class ScheduledTaskDefinitionRead(BaseModel):
    id: str
    household_id: str
    owner_scope: OwnerScope
    owner_member_id: str | None = None
    created_by_account_id: str
    last_modified_by_account_id: str
    code: str
    name: str
    description: str | None = None
    trigger_type: TriggerType
    schedule_type: ScheduleType | None = None
    schedule_expr: str | None = None
    heartbeat_interval_seconds: int | None = None
    timezone: str
    target_type: TargetType
    target_ref_id: str | None = None
    rule_type: RuleType
    rule_config: dict[str, Any] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int
    quiet_hours_policy: Literal["allow", "suppress", "delay"]
    enabled: bool
    status: TaskStatus
    last_run_at: str | None = None
    last_result: str | None = None
    consecutive_failures: int
    next_run_at: str | None = None
    next_heartbeat_at: str | None = None
    created_at: str
    updated_at: str


class ScheduledTaskRunCreate(BaseModel):
    task_definition_id: str = Field(min_length=1)
    trigger_source: TriggerSource
    scheduled_for: str | None = None
    status: RunStatus = "queued"
    evaluation_snapshot: dict[str, Any] = Field(default_factory=dict)
    dispatch_payload: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=255)
    started_at: str | None = None
    finished_at: str | None = None


class ScheduledTaskRunRead(BaseModel):
    id: str
    task_definition_id: str
    household_id: str
    owner_scope: OwnerScope
    owner_member_id: str | None = None
    trigger_source: TriggerSource
    scheduled_for: str | None = None
    status: RunStatus
    idempotency_key: str
    evaluation_snapshot: dict[str, Any] = Field(default_factory=dict)
    dispatch_payload: dict[str, Any] = Field(default_factory=dict)
    target_type: TargetType
    target_ref_id: str | None = None
    target_run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str


class ScheduledTaskDeliveryRead(BaseModel):
    id: str
    task_run_id: str
    channel: str
    recipient_type: str
    recipient_ref: str | None = None
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    delivered_at: str | None = None
    error_message: str | None = None


class ScheduledTaskDraftFromConversationRequest(BaseModel):
    household_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4000)
    draft_id: str | None = None


class ScheduledTaskDraftConfirmRequest(BaseModel):
    text: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    schedule_expr: str | None = Field(default=None, min_length=1, max_length=128)
    target_ref_id: str | None = Field(default=None, min_length=1, max_length=100)


class ScheduledTaskDraftRead(BaseModel):
    draft_id: str
    household_id: str
    creator_account_id: str
    owner_scope: OwnerScope | None = None
    owner_member_id: str | None = None
    intent_summary: str
    missing_fields: list[str] = Field(default_factory=list)
    draft_payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["drafting", "awaiting_confirm", "confirmed", "cancelled"]
    can_confirm: bool = False
