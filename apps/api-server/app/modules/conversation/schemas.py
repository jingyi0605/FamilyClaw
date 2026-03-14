from typing import Any, Literal

from pydantic import BaseModel, Field


ConversationSessionMode = Literal["family_chat", "agent_bootstrap", "agent_config"]
ConversationSessionStatus = Literal["active", "archived", "failed"]
ConversationMessageRole = Literal["user", "assistant", "system"]
ConversationMessageType = Literal["text", "error", "memory_candidate_notice"]
ConversationMessageStatus = Literal["pending", "streaming", "completed", "failed"]
ConversationCandidateStatus = Literal["pending_review", "confirmed", "dismissed"]
ConversationActionCategory = Literal["memory", "config", "action"]
ConversationActionPolicyMode = Literal["ask", "notify", "auto"]
ConversationActionStatus = Literal["pending_confirmation", "completed", "failed", "dismissed", "undone", "undo_failed"]
ConversationDebugLogLevel = Literal["info", "warning", "error"]


class ConversationSessionCreate(BaseModel):
    household_id: str = Field(min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    active_agent_id: str | None = Field(default=None, min_length=1)
    session_mode: ConversationSessionMode = "family_chat"
    title: str | None = Field(default=None, min_length=1, max_length=200)


class ConversationTurnCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    agent_id: str | None = Field(default=None, min_length=1)
    channel: str = Field(default="user_web", min_length=1, max_length=30)


class ConversationMessageRead(BaseModel):
    id: str
    session_id: str
    request_id: str | None = None
    seq: int = Field(ge=1)
    role: ConversationMessageRole
    message_type: ConversationMessageType
    content: str
    status: ConversationMessageStatus
    effective_agent_id: str | None = None
    ai_provider_code: str | None = None
    ai_trace_id: str | None = None
    degraded: bool = False
    error_code: str | None = None
    facts: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ConversationMemoryCandidateRead(BaseModel):
    id: str
    session_id: str
    source_message_id: str | None = None
    requester_member_id: str | None = None
    status: ConversationCandidateStatus
    memory_type: str
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    created_at: str
    updated_at: str


class ConversationActionRecordRead(BaseModel):
    id: str
    session_id: str
    request_id: str | None = None
    trigger_message_id: str | None = None
    source_message_id: str | None = None
    intent: str
    action_category: ConversationActionCategory
    action_name: str
    policy_mode: ConversationActionPolicyMode
    status: ConversationActionStatus
    title: str
    summary: str | None = None
    target_ref: str | None = None
    plan_payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    undo_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    executed_at: str | None = None
    undone_at: str | None = None
    updated_at: str


class ConversationSessionRead(BaseModel):
    id: str
    household_id: str
    requester_member_id: str | None = None
    session_mode: ConversationSessionMode
    active_agent_id: str | None = None
    active_agent_name: str | None = None
    active_agent_type: str | None = None
    title: str
    status: ConversationSessionStatus
    last_message_at: str
    created_at: str
    updated_at: str
    message_count: int = Field(default=0, ge=0)
    latest_message_preview: str | None = None


class ConversationSessionDetailRead(ConversationSessionRead):
    messages: list[ConversationMessageRead] = Field(default_factory=list)
    memory_candidates: list[ConversationMemoryCandidateRead] = Field(default_factory=list)
    action_records: list[ConversationActionRecordRead] = Field(default_factory=list)


class ConversationSessionListResponse(BaseModel):
    household_id: str
    requester_member_id: str | None = None
    items: list[ConversationSessionRead] = Field(default_factory=list)


class ConversationTurnRead(BaseModel):
    request_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    outcome: Literal["completed", "failed"]
    error_message: str | None = None
    session: ConversationSessionDetailRead


class ConversationMemoryCandidateActionRead(BaseModel):
    candidate: ConversationMemoryCandidateRead
    memory_card_id: str | None = None


class ConversationActionExecutionRead(BaseModel):
    action: ConversationActionRecordRead


class ConversationDebugLogRead(BaseModel):
    id: str
    session_id: str
    request_id: str | None = None
    stage: str
    source: str
    level: ConversationDebugLogLevel
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ConversationDebugLogListRead(BaseModel):
    session_id: str
    debug_enabled: bool
    request_id: str | None = None
    items: list[ConversationDebugLogRead] = Field(default_factory=list)
