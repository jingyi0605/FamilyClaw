from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AiCapability = Literal[
    "text",
    "intent_recognition",
    "vision",
    "audio_generation",
    "audio_recognition",
    "image_generation",
]
AiProviderModelType = Literal["llm", "embedding", "vision", "speech", "image"]
AiTransportType = Literal["openai_compatible", "native_sdk", "local_gateway"]
AiApiFamily = str
AiPrivacyLevel = Literal["local_only", "private_cloud", "public_cloud"]
AiRoutingMode = Literal[
    "template_only",
    "primary_then_fallback",
    "local_only",
    "local_preferred_then_cloud",
]
AiModelCallStatus = Literal[
    "success",
    "fallback_success",
    "blocked",
    "failed",
    "timeout",
    "rate_limited",
    "validation_error",
]
AiProviderFieldType = Literal["text", "secret", "number", "select", "boolean"]


class AiProviderFieldOptionRead(BaseModel):
    label: str
    value: str


class AiProviderFieldRead(BaseModel):
    key: str
    label: str
    field_type: AiProviderFieldType
    required: bool
    placeholder: str | None = None
    help_text: str | None = None
    default_value: str | int | bool | None = None
    options: list[AiProviderFieldOptionRead] = Field(default_factory=list)


class AiProviderBrandingRead(BaseModel):
    logo_url: str | None = None
    logo_dark_url: str | None = None
    description_locales: dict[str, str] = Field(default_factory=dict)


class AiProviderConfigVisibilityRuleRead(BaseModel):
    field: str
    operator: Literal["equals", "not_equals", "in", "truthy"] = "equals"
    value: Any | None = None


class AiProviderConfigFieldUiRead(BaseModel):
    help_text: str | None = None
    hidden_when: list[AiProviderConfigVisibilityRuleRead] = Field(default_factory=list)


class AiProviderConfigActionRead(BaseModel):
    key: str
    label: str
    description: str | None = None
    kind: Literal["model_discovery"] = "model_discovery"
    placement: Literal["field"] = "field"
    field_key: str


class AiProviderConfigSectionRead(BaseModel):
    key: str
    title: str
    description: str | None = None
    fields: list[str] = Field(default_factory=list)


class AiProviderConfigUiRead(BaseModel):
    field_order: list[str] = Field(default_factory=list)
    hidden_fields: list[str] = Field(default_factory=list)
    sections: list[AiProviderConfigSectionRead] = Field(default_factory=list)
    field_ui: dict[str, AiProviderConfigFieldUiRead] = Field(default_factory=dict)
    actions: list[AiProviderConfigActionRead] = Field(default_factory=list)


class AiProviderModelDiscoveryConfigRead(BaseModel):
    enabled: bool = False
    action_key: str | None = None
    depends_on_fields: list[str] = Field(default_factory=list)
    target_field: str | None = None
    debounce_ms: int = 500
    empty_state_text: str | None = None
    discovery_hint_text: str | None = None
    discovering_text: str | None = None
    discovered_text_template: str | None = None


class AiProviderAdapterRead(BaseModel):
    plugin_id: str
    plugin_name: str
    adapter_code: str
    display_name: str
    description: str
    branding: AiProviderBrandingRead
    transport_type: AiTransportType
    api_family: AiApiFamily
    default_privacy_level: AiPrivacyLevel
    default_supported_capabilities: list[AiCapability] = Field(default_factory=list)
    supported_model_types: list[AiProviderModelType] = Field(default_factory=list)
    llm_workflow: str = "openai_chat_completions"
    supports_model_discovery: bool = False
    field_schema: list[AiProviderFieldRead] = Field(default_factory=list)
    config_ui: AiProviderConfigUiRead
    model_discovery: AiProviderModelDiscoveryConfigRead


class AiProviderDiscoveredModelRead(BaseModel):
    id: str
    label: str


class AiProviderModelDiscoveryRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class AiProviderModelDiscoveryRead(BaseModel):
    adapter_code: str
    models: list[AiProviderDiscoveredModelRead] = Field(default_factory=list)


class AiProviderProfileConfigBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    transport_type: AiTransportType
    api_family: AiApiFamily
    base_url: str | None = Field(default=None, max_length=500)
    api_version: str | None = Field(default=None, max_length=50)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool = True
    supported_capabilities: list[AiCapability] = Field(default_factory=list)
    privacy_level: AiPrivacyLevel
    latency_budget_ms: int | None = Field(default=None, ge=100, le=120000)
    cost_policy: dict[str, Any] = Field(default_factory=dict)
    extra_config: dict[str, Any] = Field(default_factory=dict)


class AiProviderProfileCreate(AiProviderProfileConfigBase):
    provider_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_.-]+$",
    )


class AiProviderProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    transport_type: AiTransportType | None = None
    base_url: str | None = Field(default=None, max_length=500)
    api_version: str | None = Field(default=None, max_length=50)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    supported_capabilities: list[AiCapability] | None = None
    privacy_level: AiPrivacyLevel | None = None
    latency_budget_ms: int | None = Field(default=None, ge=100, le=120000)
    cost_policy: dict[str, Any] | None = None
    extra_config: dict[str, Any] | None = None


class AiProviderProfileRead(AiProviderProfileConfigBase):
    id: str
    provider_code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.-]+$")
    plugin_id: str | None = None
    plugin_enabled: bool | None = None
    plugin_disabled_reason: str | None = None
    updated_at: str


class AiCapabilityRouteUpsert(BaseModel):
    capability: AiCapability
    household_id: str | None = Field(default=None, min_length=1)
    primary_provider_profile_id: str | None = Field(default=None, min_length=1)
    fallback_provider_profile_ids: list[str] = Field(default_factory=list)
    routing_mode: AiRoutingMode = "primary_then_fallback"
    timeout_ms: int = Field(default=15000, ge=100, le=120000)
    max_retry_count: int = Field(default=0, ge=0, le=5)
    allow_remote: bool = True
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    response_policy: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_provider_binding(self) -> "AiCapabilityRouteUpsert":
        if self.routing_mode == "template_only":
            if self.primary_provider_profile_id is not None:
                raise ValueError("template_only 路由不能绑定主供应商")
            if self.fallback_provider_profile_ids:
                raise ValueError("template_only 路由不能绑定备用供应商")
            return self

        if self.primary_provider_profile_id is None:
            raise ValueError("非 template_only 路由必须绑定主供应商")

        fallback_ids = list(dict.fromkeys(self.fallback_provider_profile_ids))
        if self.primary_provider_profile_id in fallback_ids:
            raise ValueError("备用供应商列表不能重复包含主供应商")

        self.fallback_provider_profile_ids = fallback_ids
        return self


class AiCapabilityRouteRead(AiCapabilityRouteUpsert):
    id: str
    updated_at: str


class AiModelCallLogCreate(BaseModel):
    capability: AiCapability
    provider_code: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    household_id: str | None = Field(default=None, min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    trace_id: str = Field(min_length=1, max_length=100)
    input_policy: str = Field(default="default", min_length=1, max_length=50)
    masked_fields: list[str] = Field(default_factory=list)
    latency_ms: int | None = Field(default=None, ge=0, le=600000)
    usage: dict[str, Any] = Field(default_factory=dict)
    status: AiModelCallStatus
    fallback_used: bool = False
    error_code: str | None = Field(default=None, max_length=100)


class AiModelCallLogRead(AiModelCallLogCreate):
    id: str
    created_at: str


class AiProviderCandidate(BaseModel):
    provider_profile_id: str
    provider_code: str
    display_name: str
    privacy_level: AiPrivacyLevel
    transport_type: AiTransportType
    api_family: AiApiFamily
    order: int = Field(ge=0)


class AiInvocationPlan(BaseModel):
    capability: AiCapability
    household_id: str | None = None
    requester_member_id: str | None = None
    trace_id: str
    routing_mode: AiRoutingMode
    timeout_ms: int = Field(ge=100, le=120000)
    max_retry_count: int = Field(ge=0, le=5)
    allow_remote: bool
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    response_policy: dict[str, Any] = Field(default_factory=dict)
    primary_provider: AiProviderCandidate | None = None
    fallback_providers: list[AiProviderCandidate] = Field(default_factory=list)
    template_fallback_enabled: bool = False
    blocked_reason: str | None = None
    blocked_error_code: str | None = None
    blocked_plugin_id: str | None = None


class AiPreparedPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    masked_fields: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class AiGatewayInvokeRequest(BaseModel):
    capability: AiCapability
    household_id: str | None = Field(default=None, min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    agent_id: str | None = Field(default=None, min_length=1)
    plugin_id: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_ms_override: int | None = Field(default=None, ge=100, le=120000)
    honor_timeout_override: bool = False


class AiGatewayAttemptResult(BaseModel):
    provider_code: str
    model_name: str
    status: AiModelCallStatus
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    fallback_used: bool = False


class AiGatewayInvokeResponse(BaseModel):
    capability: AiCapability
    household_id: str | None = None
    requester_member_id: str | None = None
    trace_id: str
    status: str
    degraded: bool = False
    provider_code: str
    model_name: str
    finish_reason: str
    normalized_output: dict[str, Any] = Field(default_factory=dict)
    raw_response_ref: str | None = None
    blocked_reason: str | None = None
    attempts: list[AiGatewayAttemptResult] = Field(default_factory=list)
