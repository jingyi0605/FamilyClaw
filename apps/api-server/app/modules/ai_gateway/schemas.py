from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AiCapability = Literal[
    "qa_generation",
    "qa_structured_answer",
    "reminder_copywriting",
    "scene_explanation",
    "embedding",
    "rerank",
    "stt",
    "tts",
    "vision",
]
AiTransportType = Literal["openai_compatible", "native_sdk", "local_gateway"]
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


class AiProviderAdapterRead(BaseModel):
    adapter_code: str
    display_name: str
    description: str
    transport_type: AiTransportType
    default_privacy_level: AiPrivacyLevel
    default_supported_capabilities: list[AiCapability] = Field(default_factory=list)
    field_schema: list[AiProviderFieldRead] = Field(default_factory=list)


class AiProviderProfileBase(BaseModel):
    provider_code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    transport_type: AiTransportType
    base_url: str | None = Field(default=None, max_length=500)
    api_version: str | None = Field(default=None, max_length=50)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool = True
    supported_capabilities: list[AiCapability] = Field(default_factory=list)
    privacy_level: AiPrivacyLevel
    latency_budget_ms: int | None = Field(default=None, ge=100, le=120000)
    cost_policy: dict[str, Any] = Field(default_factory=dict)
    extra_config: dict[str, Any] = Field(default_factory=dict)


class AiProviderProfileCreate(AiProviderProfileBase):
    pass


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


class AiProviderProfileRead(AiProviderProfileBase):
    id: str
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
                raise ValueError("template_only 路由不能绑定备供应商")
            return self

        if self.primary_provider_profile_id is None:
            raise ValueError("非 template_only 路由必须绑定主供应商")

        fallback_ids = list(dict.fromkeys(self.fallback_provider_profile_ids))
        if self.primary_provider_profile_id in fallback_ids:
            raise ValueError("备供应商列表不能重复包含主供应商")

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


class AiPreparedPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    masked_fields: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class AiGatewayInvokeRequest(BaseModel):
    capability: AiCapability
    household_id: str | None = Field(default=None, min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


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
