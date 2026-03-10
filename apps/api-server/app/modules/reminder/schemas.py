from typing import Any, Literal

from pydantic import BaseModel, Field

ReminderType = Literal["personal", "family", "medication", "course", "announcement"]
ReminderScheduleKind = Literal["once", "recurring", "contextual"]
ReminderPriority = Literal["low", "normal", "high", "urgent"]
ReminderRunStatus = Literal["pending", "delivering", "acked", "expired", "cancelled", "failed"]
ReminderDeliveryStatus = Literal["queued", "sent", "heard", "failed", "skipped"]
ReminderAckAction = Literal["heard", "done", "dismissed", "delegated"]


class ReminderTaskBase(BaseModel):
    household_id: str = Field(min_length=1)
    owner_member_id: str | None = Field(default=None, min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    reminder_type: ReminderType
    target_member_ids: list[str] = Field(default_factory=list)
    preferred_room_ids: list[str] = Field(default_factory=list)
    schedule_kind: ReminderScheduleKind
    schedule_rule: dict[str, Any] = Field(default_factory=dict)
    priority: ReminderPriority = "normal"
    delivery_channels: list[str] = Field(default_factory=list)
    ack_required: bool = False
    escalation_policy: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ReminderTaskCreate(ReminderTaskBase):
    updated_by: str | None = Field(default=None, min_length=1)


class ReminderTaskUpdate(BaseModel):
    owner_member_id: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    reminder_type: ReminderType | None = None
    target_member_ids: list[str] | None = None
    preferred_room_ids: list[str] | None = None
    schedule_kind: ReminderScheduleKind | None = None
    schedule_rule: dict[str, Any] | None = None
    priority: ReminderPriority | None = None
    delivery_channels: list[str] | None = None
    ack_required: bool | None = None
    escalation_policy: dict[str, Any] | None = None
    enabled: bool | None = None
    updated_by: str | None = Field(default=None, min_length=1)


class ReminderTaskRead(ReminderTaskBase):
    id: str
    version: int
    updated_by: str | None = None
    updated_at: str


class ReminderRunCreate(BaseModel):
    task_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    schedule_slot_key: str = Field(min_length=1, max_length=100)
    trigger_reason: str = Field(min_length=1, max_length=50)
    planned_at: str = Field(min_length=1)
    started_at: str | None = None
    finished_at: str | None = None
    status: ReminderRunStatus = "pending"
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)


class ReminderRunRead(ReminderRunCreate):
    id: str


class ReminderDeliveryAttemptCreate(BaseModel):
    run_id: str = Field(min_length=1)
    target_member_id: str | None = Field(default=None, min_length=1)
    target_room_id: str | None = Field(default=None, min_length=1)
    channel: str = Field(min_length=1, max_length=30)
    attempt_index: int = Field(ge=0, le=100)
    planned_at: str = Field(min_length=1)
    sent_at: str | None = None
    status: ReminderDeliveryStatus = "queued"
    provider_result: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = Field(default=None, max_length=500)


class ReminderDeliveryAttemptRead(ReminderDeliveryAttemptCreate):
    id: str


class ReminderAckEventCreate(BaseModel):
    run_id: str = Field(min_length=1)
    member_id: str | None = Field(default=None, min_length=1)
    action: ReminderAckAction
    note: str | None = Field(default=None, max_length=500)


class ReminderAckEventRead(ReminderAckEventCreate):
    id: str
    created_at: str
