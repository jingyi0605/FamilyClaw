from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SpeakerHostResultType = Literal["text", "audio_url", "none", "error"]
SpeakerRuntimeState = Literal["idle", "running", "degraded", "error", "stopped"]


class SpeakerTextTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1, max_length=64)
    integration_instance_id: str = Field(min_length=1)
    device_id: str | None = Field(default=None, min_length=1)
    external_device_id: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)
    turn_id: str = Field(min_length=1, max_length=255)
    input_text: str = Field(min_length=1, max_length=4000)
    occurred_at: str = Field(min_length=1, max_length=64)
    requester_member_id: str | None = Field(default=None, min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "plugin_id",
        "integration_instance_id",
        "device_id",
        "external_device_id",
        "conversation_id",
        "turn_id",
        "occurred_at",
        "requester_member_id",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("input_text 不能为空")
        return normalized


class SpeakerTextTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    conversation_session_id: str | None = None
    turn_id: str
    result_type: SpeakerHostResultType
    reply_text: str | None = None
    audio_url: str | None = None
    audio_content_type: str | None = None
    degraded: bool = False
    assistant_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @field_validator("reply_text", "audio_url", "audio_content_type", "assistant_message_id", "error_code", "error_message")
    @classmethod
    def validate_optional_result_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class SpeakerRuntimeHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1, max_length=64)
    integration_instance_id: str = Field(min_length=1)
    state: SpeakerRuntimeState
    consecutive_failures: int = Field(ge=0, default=0)
    last_succeeded_at: str | None = Field(default=None, max_length=64)
    last_failed_at: str | None = Field(default=None, max_length=64)
    last_error_summary: str | None = Field(default=None, max_length=500)

    @field_validator(
        "plugin_id",
        "integration_instance_id",
        "last_succeeded_at",
        "last_failed_at",
        "last_error_summary",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class SpeakerRuntimeHeartbeatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    integration_instance_id: str
    plugin_id: str
    state: SpeakerRuntimeState
    instance_status: str
    error_code: str | None = None
    error_message: str | None = None
