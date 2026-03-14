from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PluginType = Literal["connector", "memory-ingestor", "action", "agent-skill"]
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

    @field_validator("connector", "memory_ingestor", "action", "agent_skill")
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


class PluginManifest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=32)
    types: list[PluginType] = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    triggers: list[str] = Field(default_factory=list)
    entrypoints: PluginManifestEntrypoints

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
    def validate_types(cls, value: list[PluginType]) -> list[PluginType]:
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
            entrypoint_key = ENTRYPOINT_KEY_BY_TYPE[plugin_type]
            if getattr(self.entrypoints, entrypoint_key) is None:
                missing_keys.append(entrypoint_key)
        if missing_keys:
            missing_text = ", ".join(missing_keys)
            raise ValueError(f"entrypoints 缺少类型对应入口: {missing_text}")
        return self


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
    types: list[PluginType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    enabled: bool
    manifest_path: str
    entrypoints: PluginManifestEntrypoints
    source_type: PluginSourceType = "builtin"
    execution_backend: PluginExecutionBackend | None = None
    runner_config: PluginRunnerConfig | None = None


class PluginRegistrySnapshot(BaseModel):
    items: list[PluginRegistryItem] = Field(default_factory=list)


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
    types: list[PluginType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    entrypoints: PluginManifestEntrypoints
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
    response_deadline_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str
    created_at: str


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


class AgentActionConfirmationRead(BaseModel):
    confirmation_request_id: str
    household_id: str
    plugin_id: str
    risk_level: RiskLevel
    status: Literal["pending", "confirmed", "consumed"]
    trigger: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
