from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryEventProcessingStatus = Literal["pending", "processed", "failed", "ignored"]
MemoryType = Literal["fact", "event", "preference", "relation", "growth"]
MemoryStatus = Literal["active", "pending_review", "invalidated", "deleted"]
MemoryVisibility = Literal["public", "family", "private", "sensitive"]
MemoryRelationRole = Literal["subject", "participant", "mentioned", "owner"]


class EventRecordCreate(BaseModel):
    household_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1, max_length=50)
    source_type: str = Field(min_length=1, max_length=30)
    source_ref: str | None = Field(default=None, max_length=255)
    subject_member_id: str | None = Field(default=None, min_length=1)
    room_id: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str | None = Field(default=None, min_length=1, max_length=255)
    generate_memory_card: bool = True
    occurred_at: str | None = None


class EventRecordRead(BaseModel):
    id: str
    household_id: str
    event_type: str
    source_type: str
    source_ref: str | None
    subject_member_id: str | None
    room_id: str | None
    payload: Any | None = None
    dedupe_key: str | None
    processing_status: MemoryEventProcessingStatus
    generate_memory_card: bool
    failure_reason: str | None
    occurred_at: str
    created_at: str
    processed_at: str | None


class EventRecordWriteResponse(BaseModel):
    event_id: str
    accepted: bool
    duplicate_detected: bool
    processing_status: MemoryEventProcessingStatus


class EventRecordListResponse(BaseModel):
    items: list[EventRecordRead]
    page: int
    page_size: int
    total: int


class MemoryCardMemberLink(BaseModel):
    member_id: str = Field(min_length=1)
    relation_role: MemoryRelationRole = "participant"


class MemoryCardManualCreate(BaseModel):
    household_id: str = Field(min_length=1)
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    content: dict[str, Any] = Field(default_factory=dict)
    status: MemoryStatus = "active"
    visibility: MemoryVisibility = "family"
    importance: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=0.85, ge=0, le=1)
    subject_member_id: str | None = Field(default=None, min_length=1)
    source_event_id: str | None = Field(default=None, min_length=1)
    dedupe_key: str | None = Field(default=None, min_length=1, max_length=255)
    effective_at: str | None = None
    last_observed_at: str | None = None
    related_members: list[MemoryCardMemberLink] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=500)


class MemoryCardMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: str
    member_id: str
    relation_role: str


class MemoryCardRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    memory_id: str
    revision_no: int
    action: str
    before_json: str | None
    after_json: str | None
    reason: str | None
    actor_type: str
    actor_id: str | None
    created_at: str


class MemoryCardRevisionListResponse(BaseModel):
    items: list[MemoryCardRevisionRead]


class MemoryCardRead(BaseModel):
    id: str
    household_id: str
    memory_type: MemoryType
    title: str
    summary: str
    normalized_text: str | None
    content: Any | None = None
    status: MemoryStatus
    visibility: MemoryVisibility
    importance: int
    confidence: float
    subject_member_id: str | None
    source_event_id: str | None
    dedupe_key: str | None
    effective_at: str | None
    last_observed_at: str | None
    created_by: str
    created_at: str
    updated_at: str
    invalidated_at: str | None
    related_members: list[MemoryCardMemberRead] = Field(default_factory=list)


class MemoryCardListResponse(BaseModel):
    items: list[MemoryCardRead]
    page: int
    page_size: int
    total: int


class MemoryQueryRequest(BaseModel):
    household_id: str = Field(min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    member_id: str | None = Field(default=None, min_length=1)
    memory_type: MemoryType | None = None
    status: MemoryStatus | None = None
    visibility: MemoryVisibility | None = None
    query: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class MemoryQueryHit(BaseModel):
    card: MemoryCardRead
    score: int = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)


class MemoryQueryResponse(BaseModel):
    household_id: str
    requester_member_id: str | None = None
    total: int
    query: str | None = None
    items: list[MemoryQueryHit] = Field(default_factory=list)


class MemoryHotSummaryItem(BaseModel):
    title: str
    memory_id: str
    memory_type: str
    summary: str
    updated_at: str


class MemoryHotSummaryRead(BaseModel):
    household_id: str
    requester_member_id: str | None = None
    generated_at: str
    total_visible_cards: int = Field(ge=0)
    top_memories: list[MemoryHotSummaryItem] = Field(default_factory=list)
    preference_highlights: list[str] = Field(default_factory=list)
    recent_event_highlights: list[str] = Field(default_factory=list)


class MemoryDebugOverviewRead(BaseModel):
    household_id: str
    total_events: int
    pending_events: int
    processed_events: int
    failed_events: int
    ignored_events: int
    total_cards: int
    active_cards: int
    pending_cards: int
    invalidated_cards: int
    deleted_cards: int
    latest_event_at: str | None = None
    latest_card_at: str | None = None


class MemoryCardCorrectionPayload(BaseModel):
    action: Literal["correct", "invalidate", "delete"]
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, min_length=1, max_length=4000)
    content: dict[str, Any] | None = None
    visibility: MemoryVisibility | None = None
    status: MemoryStatus | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=500)
