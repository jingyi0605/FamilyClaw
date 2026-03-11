from typing import Any, Literal

from pydantic import BaseModel, Field

AgentType = Literal["butler", "nutritionist", "fitness_coach", "study_coach", "custom"]
AgentStatus = Literal["draft", "active", "inactive"]


class AgentSoulProfileRead(BaseModel):
    id: str
    agent_id: str
    version: int
    self_identity: str
    role_summary: str
    intro_message: str | None
    speaking_style: str | None
    personality_traits: list[str] = Field(default_factory=list)
    service_focus: list[str] = Field(default_factory=list)
    service_boundaries: dict[str, Any] | None = None
    is_active: bool
    created_by: str
    created_at: str


class AgentMemberCognitionRead(BaseModel):
    id: str
    agent_id: str
    member_id: str
    display_address: str | None
    closeness_level: int
    service_priority: int
    communication_style: str | None
    care_notes: dict[str, Any] | None = None
    prompt_notes: str | None
    version: int
    updated_at: str


class AgentRuntimePolicyRead(BaseModel):
    agent_id: str
    conversation_enabled: bool
    default_entry: bool
    routing_tags: list[str] = Field(default_factory=list)
    memory_scope: dict[str, Any] | None = None
    updated_at: str


class AgentSummaryRead(BaseModel):
    id: str
    household_id: str
    code: str
    agent_type: AgentType
    display_name: str
    status: AgentStatus
    is_primary: bool
    sort_order: int
    summary: str | None = None
    conversation_enabled: bool = True
    default_entry: bool = False
    updated_at: str


class AgentDetailRead(BaseModel):
    id: str
    household_id: str
    code: str
    agent_type: AgentType
    display_name: str
    status: AgentStatus
    is_primary: bool
    sort_order: int
    created_at: str
    updated_at: str
    soul: AgentSoulProfileRead | None = None
    member_cognitions: list[AgentMemberCognitionRead] = Field(default_factory=list)
    runtime_policy: AgentRuntimePolicyRead | None = None


class AgentListResponse(BaseModel):
    household_id: str
    items: list[AgentSummaryRead] = Field(default_factory=list)


class AgentSoulProfileUpsert(BaseModel):
    self_identity: str = Field(min_length=1, max_length=4000)
    role_summary: str = Field(min_length=1, max_length=2000)
    intro_message: str | None = Field(default=None, max_length=4000)
    speaking_style: str | None = Field(default=None, max_length=2000)
    personality_traits: list[str] = Field(default_factory=list, max_length=20)
    service_focus: list[str] = Field(default_factory=list, max_length=20)
    service_boundaries: dict[str, Any] | None = None
    created_by: str = Field(default="admin", min_length=1, max_length=30)


class AgentMemberCognitionUpsertItem(BaseModel):
    member_id: str = Field(min_length=1)
    display_address: str | None = Field(default=None, max_length=100)
    closeness_level: int = Field(default=3, ge=1, le=5)
    service_priority: int = Field(default=3, ge=1, le=5)
    communication_style: str | None = Field(default=None, max_length=2000)
    care_notes: dict[str, Any] | None = None
    prompt_notes: str | None = Field(default=None, max_length=4000)


class AgentMemberCognitionsUpsert(BaseModel):
    items: list[AgentMemberCognitionUpsertItem] = Field(default_factory=list)


class AgentRuntimePolicyUpsert(BaseModel):
    conversation_enabled: bool = True
    default_entry: bool = False
    routing_tags: list[str] = Field(default_factory=list, max_length=20)
    memory_scope: dict[str, Any] | None = None
