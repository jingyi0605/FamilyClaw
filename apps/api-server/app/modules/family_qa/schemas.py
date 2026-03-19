from typing import Any

from app.modules.context.schemas import (
    ContextOverviewActiveMember,
    ContextOverviewDeviceSummary,
    ContextOverviewMemberState,
    ContextOverviewRoomOccupancy,
)

from pydantic import BaseModel, Field


class QaFactReference(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    occurred_at: str | None = None
    visibility: str = Field(default="family", min_length=1, max_length=30)
    inferred: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class QaQueryLogCreate(BaseModel):
    household_id: str = Field(min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    question: str = Field(min_length=1, max_length=500)
    answer_type: str = Field(min_length=1, max_length=50)
    answer_summary: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0, ge=0, le=1)
    degraded: bool = False
    facts: list[QaFactReference] = Field(default_factory=list)


class QaQueryLogRead(QaQueryLogCreate):
    id: str
    created_at: str


class QaFactDeviceState(BaseModel):
    device_id: str
    name: str
    device_type: str
    room_id: str | None = None
    room_name: str | None = None
    status: str
    controllable: bool


class QaReminderFactItem(BaseModel):
    task_id: str
    title: str
    reminder_type: str
    target_member_ids: list[str] = Field(default_factory=list)
    enabled: bool
    last_run_status: str | None = None
    last_run_planned_at: str | None = None
    last_ack_action: str | None = None


class QaReminderSummary(BaseModel):
    total_tasks: int = Field(ge=0)
    enabled_tasks: int = Field(ge=0)
    pending_runs: int = Field(ge=0)
    recent_items: list[QaReminderFactItem] = Field(default_factory=list)


class QaSceneFactItem(BaseModel):
    template_id: str
    template_code: str
    name: str
    enabled: bool
    last_execution_status: str | None = None
    last_execution_started_at: str | None = None


class QaSceneSummary(BaseModel):
    total_templates: int = Field(ge=0)
    enabled_templates: int = Field(ge=0)
    running_executions: int = Field(ge=0)
    recent_items: list[QaSceneFactItem] = Field(default_factory=list)


class QaMemorySummary(BaseModel):
    status: str = "unavailable"
    summary: str = "记忆中心暂未接入，当前只使用上下文、提醒和场景数据回答。"
    last_updated_at: str | None = None
    query: str | None = None
    items: list[QaFactReference] = Field(default_factory=list)
    degraded: bool = False


class QaFactMemberRelationship(BaseModel):
    target_member_id: str
    target_member_name: str
    relation_type: str
    relation_label: str


class QaFactMemberProfile(BaseModel):
    member_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str
    gender: str | None = None
    age_group: str | None = None
    age_group_label: str | None = None
    birthday: str | None = None
    age_years: int | None = None
    preferred_name: str | None = None
    guardian_member_id: str | None = None
    guardian_name: str | None = None
    relationships: list[QaFactMemberRelationship] = Field(default_factory=list)


class QaPermissionScope(BaseModel):
    requester_member_id: str | None = None
    requester_role: str = "guest"
    can_view_member_details: bool = False
    can_view_device_states: bool = False
    can_view_private_reminders: bool = False
    can_view_scene_details: bool = False
    visible_member_ids: list[str] = Field(default_factory=list)
    visible_room_ids: list[str] = Field(default_factory=list)
    masked_sections: list[str] = Field(default_factory=list)


class QaFactViewRead(BaseModel):
    household_id: str
    generated_at: str
    requester_member_id: str | None = None
    active_member: ContextOverviewActiveMember | None = None
    member_states: list[ContextOverviewMemberState] = Field(default_factory=list)
    member_profiles: list[QaFactMemberProfile] = Field(default_factory=list)
    room_occupancy: list[ContextOverviewRoomOccupancy] = Field(default_factory=list)
    device_summary: ContextOverviewDeviceSummary
    device_states: list[QaFactDeviceState] = Field(default_factory=list)
    reminder_summary: QaReminderSummary
    scene_summary: QaSceneSummary
    memory_summary: QaMemorySummary
    permission_scope: QaPermissionScope


class FamilyQaQueryRequest(BaseModel):
    household_id: str = Field(min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    agent_id: str | None = Field(default=None, min_length=1)
    question: str = Field(min_length=1, max_length=500)
    channel: str = Field(default="admin_web", min_length=1, max_length=30)
    context: dict[str, Any] = Field(default_factory=dict)


class FamilyQaQueryResponse(BaseModel):
    answer_type: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    facts: list[QaFactReference] = Field(default_factory=list)
    degraded: bool = False
    suggestions: list[str] = Field(default_factory=list)
    effective_agent_id: str | None = None
    effective_agent_type: str | None = None
    effective_agent_name: str | None = None
    ai_trace_id: str | None = None
    ai_provider_code: str | None = None
    ai_degraded: bool = False


class FamilyQaSuggestionItem(BaseModel):
    question: str
    answer_type: str
    reason: str


class FamilyQaSuggestionsResponse(BaseModel):
    household_id: str
    effective_agent_id: str | None = None
    effective_agent_type: str | None = None
    effective_agent_name: str | None = None
    items: list[FamilyQaSuggestionItem] = Field(default_factory=list)
