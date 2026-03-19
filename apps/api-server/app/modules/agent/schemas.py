from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.ai_gateway.schemas import AiCapability

AgentType = Literal["butler", "nutritionist", "fitness_coach", "study_coach", "custom"]
AgentStatus = Literal["draft", "active", "inactive"]
ButlerBootstrapStatus = Literal["collecting", "reviewing", "completed", "cancelled"]
AgentAutonomousActionLevel = Literal["ask", "notify", "auto"]
ButlerBootstrapField = Literal[
    "display_name",
    "speaking_style",
    "personality_traits",
]


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


class AgentAutonomousActionPolicy(BaseModel):
    memory: AgentAutonomousActionLevel = "ask"
    config: AgentAutonomousActionLevel = "ask"
    action: AgentAutonomousActionLevel = "ask"


class AgentModelBindingRead(BaseModel):
    capability: AiCapability
    provider_profile_id: str


class AgentSkillModelBindingRead(BaseModel):
    plugin_id: str
    capability: AiCapability
    provider_profile_id: str


class AgentRuntimePolicyRead(BaseModel):
    agent_id: str
    conversation_enabled: bool
    default_entry: bool
    routing_tags: list[str] = Field(default_factory=list)
    memory_scope: dict[str, Any] | None = None
    autonomous_action_policy: AgentAutonomousActionPolicy = Field(default_factory=AgentAutonomousActionPolicy)
    model_bindings: list[AgentModelBindingRead] = Field(default_factory=list)
    agent_skill_model_bindings: list[AgentSkillModelBindingRead] = Field(default_factory=list)
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


class AgentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    agent_type: AgentType = "butler"
    self_identity: str = Field(min_length=1, max_length=4000)
    role_summary: str = Field(min_length=1, max_length=2000)
    intro_message: str | None = Field(default=None, max_length=4000)
    speaking_style: str | None = Field(default=None, max_length=2000)
    personality_traits: list[str] = Field(default_factory=list, max_length=20)
    service_focus: list[str] = Field(default_factory=list, max_length=20)
    service_boundaries: dict[str, Any] | None = None
    conversation_enabled: bool = True
    default_entry: bool = True
    created_by: str = Field(default="user-app", min_length=1, max_length=30)


class ButlerBootstrapDraft(BaseModel):
    """管家引导草稿（简化版，只收集称呼、性格、说话风格）"""
    household_id: str = Field(min_length=1)
    display_name: str = Field(default="", max_length=100)
    speaking_style: str = Field(default="", max_length=2000)
    personality_traits: list[str] = Field(default_factory=list, max_length=20)


class ButlerBootstrapMessageRead(BaseModel):
    id: str = Field(min_length=1)
    request_id: str | None = None
    role: Literal["assistant", "user"]
    content: str = Field(min_length=1)
    seq: int = Field(ge=1)
    created_at: str = Field(min_length=1)


class ButlerBootstrapSessionRead(BaseModel):
    session_id: str = Field(min_length=1)
    status: ButlerBootstrapStatus
    pending_field: ButlerBootstrapField | None = None
    draft: ButlerBootstrapDraft
    assistant_message: str = Field(min_length=1)
    messages: list[ButlerBootstrapMessageRead] = Field(default_factory=list)
    can_confirm: bool = False
    current_request_id: str | None = None
    last_event_seq: int = Field(default=0, ge=0)


class ButlerBootstrapMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ButlerBootstrapConfirm(BaseModel):
    draft: ButlerBootstrapDraft
    created_by: str = Field(default="user-app", min_length=1, max_length=30)


class AgentUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: AgentStatus | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class AgentSoulProfileUpsert(BaseModel):
    # self_identity 作为派生/高级字段，普通配置更新链路不再要求传入。
    self_identity: str | None = Field(default=None, max_length=4000)
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
    autonomous_action_policy: AgentAutonomousActionPolicy = Field(default_factory=AgentAutonomousActionPolicy)
    model_bindings: list[AgentModelBindingRead] = Field(default_factory=list)
    agent_skill_model_bindings: list[AgentSkillModelBindingRead] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_model_bindings(self) -> "AgentRuntimePolicyUpsert":
        seen_capabilities: set[str] = set()
        normalized_model_bindings: list[AgentModelBindingRead] = []
        for item in self.model_bindings:
            if item.capability in seen_capabilities:
                raise ValueError("同一个 Agent 不能重复绑定同一项模型能力")
            seen_capabilities.add(item.capability)
            normalized_model_bindings.append(item)

        seen_skill_bindings: set[tuple[str, str]] = set()
        normalized_skill_bindings: list[AgentSkillModelBindingRead] = []
        for item in self.agent_skill_model_bindings:
            binding_key = (item.plugin_id.strip(), item.capability)
            if not binding_key[0]:
                raise ValueError("agent-skill 模型绑定缺少 plugin_id")
            if binding_key in seen_skill_bindings:
                raise ValueError("同一个 agent-skill 不能重复绑定同一项模型能力")
            seen_skill_bindings.add(binding_key)
            normalized_skill_bindings.append(
                AgentSkillModelBindingRead(
                    plugin_id=binding_key[0],
                    capability=item.capability,
                    provider_profile_id=item.provider_profile_id,
                )
            )

        self.model_bindings = normalized_model_bindings
        self.agent_skill_model_bindings = normalized_skill_bindings
        return self


class AgentMemoryInsightFact(BaseModel):
    memory_id: str
    source_plugin_id: str
    category: str
    summary: str
    observed_at: str | None = None


class AgentMemoryInsightRead(BaseModel):
    agent_id: str
    agent_name: str
    household_id: str
    summary: str
    suggestions: list[str] = Field(default_factory=list)
    used_plugins: list[str] = Field(default_factory=list)
    facts: list[AgentMemoryInsightFact] = Field(default_factory=list)


class AgentPluginMemoryCheckpointRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="agent-checkpoint", min_length=1, max_length=50)


class AgentPluginMemoryCheckpointRead(BaseModel):
    agent_id: str
    agent_name: str
    household_id: str
    plugin_id: str
    trigger: str
    pipeline_run_id: str | None = None
    pipeline_success: bool | None = None
    raw_record_count: int = Field(ge=0)
    memory_card_count: int = Field(ge=0)
    degraded: bool = False
    insight: AgentMemoryInsightRead
    queued: bool = False
    job_id: str | None = None
    job_status: str | None = None
