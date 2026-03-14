from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PluginType = Literal["connector", "memory-ingestor", "action", "agent-skill", "region-provider"]
PluginManifestType = Literal["connector", "memory-ingestor", "action", "agent-skill", "locale-pack", "region-provider"]
RiskLevel = Literal["low", "medium", "high"]
PluginSourceType = Literal["builtin", "official", "third_party"]
PluginExecutionBackend = Literal["in_process", "subprocess_runner"]
PluginJobStatus = Literal[
    "queued",
    "running",
    "retry_waiting",
    "waiting_response",
    "succeeded",
    "failed",
    "cancelled",
]
PluginJobAttemptStatus = Literal["running", "succeeded", "failed", "timed_out"]
PluginJobNotificationType = Literal["state_changed", "failed", "waiting_response", "recovered"]
PluginJobNotificationChannel = Literal["websocket", "in_app"]
PluginJobResponseAction = Literal["retry", "confirm", "cancel", "provide_input"]
PluginJobActorType = Literal["member", "admin", "system"]

ENTRYPOINT_KEY_BY_TYPE: dict[PluginType, str] = {
    "connector": "connector",
    "memory-ingestor": "memory_ingestor",
    "action": "action",
    "agent-skill": "agent_skill",
    "region-provider": "region_provider",
}


def _normalize_text_list(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = value.strip()
        if not item:
            raise ValueError(f"{field_name} 里不能有空字符串")
        if item in seen:
            raise ValueError(f"{field_name} 里不能有重复值: {item}")
        seen.add(item)
        normalized.append(item)
    return normalized


class PluginManifestEntrypoints(BaseModel):
    connector: str | None = None
    memory_ingestor: str | None = None
    action: str | None = None
    agent_skill: str | None = None
    region_provider: str | None = None

    @field_validator("connector", "memory_ingestor", "action", "agent_skill", "region_provider")
    @classmethod
    def validate_entrypoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("entrypoint 不能为空字符串")
        if "." not in normalized:
            raise ValueError("entrypoint 必须是模块路径加函数名")
        return normalized


class PluginManifestContextReads(BaseModel):
    household_region_context: bool = False


class PluginManifestRegionProviderSpec(BaseModel):
    provider_code: str | None = None
    country_codes: list[str] = Field(default_factory=list)
    entrypoint: str | None = None
    reserved: bool = True

    @field_validator("provider_code", "entrypoint")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空字符串")
        return normalized

    @field_validator("country_codes")
    @classmethod
    def validate_country_codes(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="country_codes")


class PluginManifestCapabilities(BaseModel):
    context_reads: PluginManifestContextReads = Field(default_factory=PluginManifestContextReads)
    region_provider: PluginManifestRegionProviderSpec | None = None


class PluginManifestLocaleSpec(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=100)
    native_label: str = Field(min_length=1, max_length=100)
    resource: str = Field(min_length=1, max_length=255)
    fallback: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("id", "label", "native_label", "fallback")
    @classmethod
    def validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("resource")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource 不能为空")

        resource_path = Path(normalized)
        if resource_path.is_absolute():
            raise ValueError("resource 必须是插件目录内的相对路径")
        if ".." in resource_path.parts:
            raise ValueError("resource 不能跳出插件目录")
        return normalized.replace("\\", "/")


class PluginManifest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=32)
    types: list[PluginManifestType] = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    triggers: list[str] = Field(default_factory=list)
    entrypoints: PluginManifestEntrypoints = Field(default_factory=PluginManifestEntrypoints)
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("id 不能为空")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(char not in allowed for char in normalized):
            raise ValueError("id 只能包含小写字母、数字和连字符")
        return normalized

    @field_validator("name", "version")
    @classmethod
    def validate_text_field(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("types")
    @classmethod
    def validate_types(cls, value: list[PluginManifestType]) -> list[PluginManifestType]:
        seen: set[str] = set()

        for item in value:
            if item in seen:
                raise ValueError(f"types 里不能有重复值: {item}")
            seen.add(item)
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="permissions")

    @field_validator("triggers")
    @classmethod
    def validate_triggers(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="triggers")

    @field_validator("locales")
    @classmethod
    def validate_locales(cls, value: list[PluginManifestLocaleSpec]) -> list[PluginManifestLocaleSpec]:
        seen: set[str] = set()
        for item in value:
            if item.id in seen:
                raise ValueError(f"locales 里不能有重复 locale id: {item.id}")
            seen.add(item.id)
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_entrypoint_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        entrypoints = data.get("entrypoints")
        if not isinstance(entrypoints, dict):
            return data

        normalized_entrypoints: dict[str, Any] = {}
        for key, value in entrypoints.items():
            normalized_key = str(key).strip().replace("-", "_")
            normalized_entrypoints[normalized_key] = value
        data = dict(data)
        data["entrypoints"] = normalized_entrypoints
        return data

    @model_validator(mode="after")
    def validate_required_entrypoints(self) -> "PluginManifest":
        missing_keys: list[str] = []
        for plugin_type in self.types:
            if plugin_type == "locale-pack":
                continue
            entrypoint_key = ENTRYPOINT_KEY_BY_TYPE[plugin_type]
            if getattr(self.entrypoints, entrypoint_key) is None:
                missing_keys.append(entrypoint_key)
        if missing_keys:
            missing_text = ", ".join(missing_keys)
            raise ValueError(f"entrypoints 缺少类型对应入口: {missing_text}")
        if "locale-pack" in self.types and not self.locales:
            raise ValueError("locale-pack 插件至少要声明一个 locale")
        if "locale-pack" not in self.types and self.locales:
            raise ValueError("只有 locale-pack 插件才能声明 locales")
        self._validate_region_provider_capability()
        return self

    def _validate_region_provider_capability(self) -> None:
        spec = self.capabilities.region_provider
        if spec is None:
            if "region-provider" in self.types:
                raise ValueError("region-provider 插件必须声明 capabilities.region_provider")
            return

        if spec.reserved:
            if "region-provider" in self.types:
                raise ValueError("region-provider 插件不能把 capabilities.region_provider 标成 reserved")
            return

        if "region-provider" not in self.types:
            raise ValueError("启用地区 provider 运行时必须把 region-provider 写进 types")
        if spec.provider_code is None:
            raise ValueError("地区 provider 运行时必须声明 provider_code")
        if spec.entrypoint is None:
            raise ValueError("地区 provider 运行时必须声明 entrypoint")
        if not spec.country_codes:
            raise ValueError("地区 provider 运行时至少要声明一个 country_code")
        if self.entrypoints.region_provider != spec.entrypoint:
            raise ValueError("entrypoints.region_provider 必须和 capabilities.region_provider.entrypoint 一致")


class PluginRegistryStateEntry(BaseModel):
    enabled: bool = True
    updated_at: str | None = None


class PluginRunnerConfig(BaseModel):
    plugin_root: str | None = None
    python_path: str | None = None
    working_dir: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    stdout_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    stderr_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)


class PluginRegistryItem(BaseModel):
    id: str
    name: str
    version: str
    types: list[PluginManifestType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    enabled: bool
    manifest_path: str
    entrypoints: PluginManifestEntrypoints
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)
    source_type: PluginSourceType = "builtin"
    execution_backend: PluginExecutionBackend | None = None
    runner_config: PluginRunnerConfig | None = None


class PluginRegistrySnapshot(BaseModel):
    items: list[PluginRegistryItem] = Field(default_factory=list)


class PluginLocaleRead(BaseModel):
    plugin_id: str
    locale_id: str
    label: str
    native_label: str
    fallback: str | None = None
    source_type: PluginSourceType
    messages: dict[str, str] = Field(default_factory=dict)
    overridden_plugin_ids: list[str] = Field(default_factory=list)


class PluginLocaleListRead(BaseModel):
    household_id: str
    items: list[PluginLocaleRead] = Field(default_factory=list)


class PluginMountBase(BaseModel):
    source_type: Literal["official", "third_party"] = "third_party"
    execution_backend: Literal["subprocess_runner"] = "subprocess_runner"
    plugin_root: str = Field(min_length=1)
    manifest_path: str | None = None
    python_path: str = Field(min_length=1)
    working_dir: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    stdout_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    stderr_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    enabled: bool = True


class PluginMountCreate(PluginMountBase):
    pass


class PluginMountUpdate(BaseModel):
    source_type: Literal["official", "third_party"] | None = None
    python_path: str | None = None
    working_dir: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    stdout_limit_bytes: int | None = Field(default=None, ge=1024, le=1048576)
    stderr_limit_bytes: int | None = Field(default=None, ge=1024, le=1048576)
    enabled: bool | None = None


class PluginMountRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    name: str
    version: str
    types: list[PluginManifestType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    entrypoints: PluginManifestEntrypoints
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)
    source_type: Literal["official", "third_party"]
    execution_backend: Literal["subprocess_runner"] = "subprocess_runner"
    manifest_path: str
    plugin_root: str
    python_path: str
    working_dir: str | None = None
    timeout_seconds: int
    stdout_limit_bytes: int
    stderr_limit_bytes: int
    enabled: bool
    created_at: str
    updated_at: str


class PluginJobCreate(BaseModel):
    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1, max_length=64)
    plugin_type: PluginType
    trigger: str = Field(min_length=1, max_length=50)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    payload_summary: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    initial_status: Literal["queued", "waiting_response"] = "queued"
    max_attempts: int = Field(default=1, ge=1, le=20)
    retry_after_at: str | None = None
    response_deadline_at: str | None = None


class PluginJobAttemptRead(BaseModel):
    id: str
    job_id: str
    attempt_no: int
    status: PluginJobAttemptStatus
    worker_id: str | None = None
    started_at: str
    finished_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    output_summary: Any | None = None


class PluginJobNotificationRead(BaseModel):
    id: str
    job_id: str
    notification_type: PluginJobNotificationType
    channel: PluginJobNotificationChannel
    payload: Any
    delivered_at: str | None = None
    created_at: str


class PluginJobResponseCreate(BaseModel):
    action: PluginJobResponseAction
    actor_type: PluginJobActorType
    actor_id: str | None = None
    payload: dict[str, Any] | None = None


class PluginJobResponseRead(BaseModel):
    id: str
    job_id: str
    action: PluginJobResponseAction
    actor_type: PluginJobActorType
    actor_id: str | None = None
    payload: Any | None = None
    created_at: str


class PluginJobRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    plugin_type: PluginType
    trigger: str
    status: PluginJobStatus
    request_payload: Any
    payload_summary: Any | None = None
    idempotency_key: str | None = None
    current_attempt: int
    max_attempts: int
    last_error_code: str | None = None
    last_error_message: str | None = None
    retry_after_at: str | None = None
    response_deadline_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str
    created_at: str


class PluginJobNotificationSummaryRead(BaseModel):
    id: str
    notification_type: PluginJobNotificationType
    channel: PluginJobNotificationChannel
    delivered_at: str | None = None
    created_at: str
    payload: Any


class PluginJobDetailRead(BaseModel):
    job: PluginJobRead
    latest_attempt: PluginJobAttemptRead | None = None
    allowed_actions: list[PluginJobResponseAction] = Field(default_factory=list)
    recent_notifications: list[PluginJobNotificationSummaryRead] = Field(default_factory=list)


class PluginJobListItemRead(BaseModel):
    job: PluginJobRead
    allowed_actions: list[PluginJobResponseAction] = Field(default_factory=list)


class PluginJobListRead(BaseModel):
    items: list[PluginJobListItemRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class PluginJobEnqueueRequest(BaseModel):
    plugin_id: str = Field(min_length=1, max_length=64)
    plugin_type: PluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="manual", min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    payload_summary: dict[str, Any] | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=20)


class PluginExecutionRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    plugin_type: PluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="manual", min_length=1, max_length=50)
    execution_backend: PluginExecutionBackend | None = None


class PluginExecutionResult(BaseModel):
    run_id: str
    plugin_id: str
    plugin_type: PluginType
    execution_backend: PluginExecutionBackend | None = None
    success: bool
    trigger: str
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None


class PluginRawRecordCreate(BaseModel):
    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    trigger: str = Field(min_length=1, max_length=50)
    record_type: str = Field(min_length=1, max_length=50)
    source_ref: str | None = Field(default=None, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    captured_at: str | None = None


class PluginRawRecordRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    run_id: str
    trigger: str
    record_type: str
    source_ref: str | None = None
    payload: Any | None = None
    captured_at: str
    created_at: str


PluginRunStatus = Literal["running", "success", "failed"]


class PluginRunRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    plugin_type: PluginType
    trigger: str
    status: PluginRunStatus
    raw_record_count: int
    memory_card_count: int
    error_code: str | None = None
    error_message: str | None = None
    started_at: str
    finished_at: str | None = None
    created_at: str


class PluginSyncPipelineResult(BaseModel):
    run: PluginRunRead
    execution: PluginExecutionResult
    raw_records: list[PluginRawRecordRead] = Field(default_factory=list)
    written_memory_cards: list[dict[str, Any]] = Field(default_factory=list)


AgentCallablePluginType = Literal["connector", "agent-skill"]


class AgentPluginInvokeRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    plugin_type: AgentCallablePluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="agent", min_length=1, max_length=50)


class AgentPluginInvokeResult(BaseModel):
    agent_id: str
    agent_name: str
    plugin_id: str
    plugin_type: AgentCallablePluginType
    run_id: str
    success: bool
    trigger: str
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    queued: bool = False
    job_id: str | None = None
    job_status: PluginJobStatus | None = None


class AgentActionPluginInvokeRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="agent-action", min_length=1, max_length=50)


class AgentActionPluginInvokeResult(BaseModel):
    agent_id: str
    agent_name: str
    plugin_id: str
    plugin_type: Literal["action"] = "action"
    run_id: str
    success: bool
    trigger: str
    risk_level: RiskLevel
    authorization_status: Literal["allowed", "denied", "confirmation_required"]
    confirmation_request_id: str | None = None
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    queued: bool = False
    job_id: str | None = None
    job_status: PluginJobStatus | None = None


class AgentActionConfirmationRead(BaseModel):
    confirmation_request_id: str
    household_id: str
    plugin_id: str
    risk_level: RiskLevel
    status: Literal["pending", "confirmed", "consumed"]
    trigger: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
