from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SpeakerAdapterMode = Literal["text_turn", "audio_session"]
SpeakerTextTurnResultType = Literal["text", "audio_url", "none", "error"]
SpeakerAudioSessionStage = Literal["open", "append", "close"]
SpeakerRuntimeState = Literal["idle", "running", "degraded", "error", "stopped"]


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _validate_iso_datetime(value: str, *, field_name: str) -> str:
    normalized = _normalize_required_text(value, field_name=field_name)
    candidate = normalized.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是合法 ISO 时间") from exc
    return normalized


def _normalize_mode_list(value: list[SpeakerAdapterMode]) -> list[SpeakerAdapterMode]:
    normalized: list[SpeakerAdapterMode] = []
    for item in value:
        if item in normalized:
            raise ValueError(f"supported_modes 里不能有重复值: {item}")
        normalized.append(item)
    if not normalized:
        raise ValueError("supported_modes 至少要声明一个模式")
    return normalized


class SpeakerAdapterCapability(BaseModel):
    """宿主对 speaker 插件能力的正式快照。"""

    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1)
    adapter_code: str = Field(min_length=1)
    supported_modes: list[SpeakerAdapterMode] = Field(default_factory=list)
    supported_domains: list[str] = Field(default_factory=list)
    requires_runtime_worker: bool = False
    supports_discovery: bool = False
    supports_commands: bool = False
    runtime_entrypoint: str | None = None

    @field_validator("plugin_id", "adapter_code", "runtime_entrypoint")
    @classmethod
    def validate_capability_text(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))

    @field_validator("supported_modes")
    @classmethod
    def validate_supported_modes(cls, value: list[SpeakerAdapterMode]) -> list[SpeakerAdapterMode]:
        return _normalize_mode_list(value)

    @field_validator("supported_domains")
    @classmethod
    def validate_supported_domains(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            text = _normalize_required_text(str(item), field_name="supported_domains")
            if text in normalized:
                raise ValueError(f"supported_domains 里不能有重复值: {text}")
            normalized.append(text)
        if "speaker" not in normalized:
            raise ValueError("supported_domains 至少要包含 speaker")
        return normalized


class SpeakerTextTurnRequest(BaseModel):
    """文本轮询型 speaker 插件提交到宿主的正式 turn 请求。"""

    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    integration_instance_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    device_id: str | None = Field(default=None, min_length=1)
    external_device_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    input_text: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "household_id",
        "plugin_id",
        "integration_instance_id",
        "binding_id",
        "device_id",
        "external_device_id",
        "conversation_id",
        "turn_id",
        mode="before",
    )
    @classmethod
    def validate_text_identifiers(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="input_text")

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        return _validate_iso_datetime(value, field_name="occurred_at")


class SpeakerTextTurnResult(BaseModel):
    """宿主返回给文本轮询插件的统一 turn 结果。"""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    duplicated: bool = False
    result_type: SpeakerTextTurnResultType
    request_id: str | None = None
    conversation_session_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    reply_text: str | None = None
    audio_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    conversation_state: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "request_id",
        "conversation_session_id",
        "user_message_id",
        "assistant_message_id",
        "reply_text",
        "audio_url",
        "error_code",
        "error_message",
    )
    @classmethod
    def validate_optional_text_fields(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def validate_result_payload(self) -> "SpeakerTextTurnResult":
        if self.result_type == "text" and self.reply_text is None:
            raise ValueError("result_type=text 时必须提供 reply_text")
        if self.result_type == "audio_url" and self.audio_url is None:
            raise ValueError("result_type=audio_url 时必须提供 audio_url")
        if self.result_type == "error" and self.error_code is None:
            raise ValueError("result_type=error 时必须提供 error_code")
        return self


class SpeakerAudioSessionEnvelope(BaseModel):
    """音频会话型插件进入宿主桥接层的正式会话载荷。"""

    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    integration_instance_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    device_id: str | None = Field(default=None, min_length=1)
    external_device_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    stage: SpeakerAudioSessionStage
    audio_ref: str | None = None
    occurred_at: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "household_id",
        "plugin_id",
        "integration_instance_id",
        "binding_id",
        "device_id",
        "external_device_id",
        "conversation_id",
        "session_id",
        "audio_ref",
    )
    @classmethod
    def validate_audio_session_text(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))

    @field_validator("occurred_at")
    @classmethod
    def validate_audio_occurred_at(cls, value: str) -> str:
        return _validate_iso_datetime(value, field_name="occurred_at")

    @model_validator(mode="after")
    def validate_audio_stage(self) -> "SpeakerAudioSessionEnvelope":
        if self.stage == "append" and self.audio_ref is None:
            raise ValueError("stage=append 时必须提供 audio_ref")
        return self


class SpeakerAudioSessionResult(BaseModel):
    """宿主对音频会话桥接请求的统一确认结果。"""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    session_id: str
    stage: SpeakerAudioSessionStage
    conversation_session_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    conversation_state: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id", "conversation_session_id", "error_code", "error_message")
    @classmethod
    def validate_audio_result_text(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))


class SpeakerCommandEnvelope(BaseModel):
    """宿主统一 speaker 动作路由到插件时使用的命令模型。"""

    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    integration_instance_id: str | None = Field(default=None, min_length=1)
    binding_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("household_id", "plugin_id", "integration_instance_id", "binding_id", "action")
    @classmethod
    def validate_command_text(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))


class SpeakerRuntimeHeartbeat(BaseModel):
    """常驻 speaker worker 向宿主上报的统一健康快照。"""

    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    integration_instance_id: str = Field(min_length=1)
    state: SpeakerRuntimeState
    consecutive_failures: int = Field(ge=0)
    reported_at: str = Field(min_length=1)
    last_succeeded_at: str | None = None
    last_failed_at: str | None = None
    last_error_summary: str | None = None

    @field_validator("household_id", "plugin_id", "integration_instance_id", "last_error_summary")
    @classmethod
    def validate_runtime_text(cls, value: str | None, info: Any) -> str | None:
        return _normalize_optional_text(value, field_name=str(info.field_name))

    @field_validator("reported_at", "last_succeeded_at", "last_failed_at")
    @classmethod
    def validate_runtime_timestamps(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _validate_iso_datetime(value, field_name=str(info.field_name))


class SpeakerRuntimeHeartbeatAck(BaseModel):
    """宿主对 heartbeat 的确认回执。"""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    integration_instance_id: str = Field(min_length=1)
    runtime_state: SpeakerRuntimeState
    last_heartbeat_at: str = Field(min_length=1)

    @field_validator("integration_instance_id")
    @classmethod
    def validate_runtime_ack_text(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="integration_instance_id")

    @field_validator("last_heartbeat_at")
    @classmethod
    def validate_runtime_ack_timestamp(cls, value: str) -> str:
        return _validate_iso_datetime(value, field_name="last_heartbeat_at")


class SpeakerRuntimeStateRead(BaseModel):
    """宿主持久化后的 speaker runtime 状态快照。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    household_id: str
    plugin_id: str
    integration_instance_id: str
    adapter_code: str
    runtime_state: SpeakerRuntimeState
    consecutive_failures: int = Field(ge=0)
    last_succeeded_at: str | None = None
    last_failed_at: str | None = None
    last_error_summary: str | None = None
    last_heartbeat_at: str
    created_at: str
    updated_at: str
