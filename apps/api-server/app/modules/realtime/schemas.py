from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.db.utils import utc_now_iso

BootstrapRealtimeEventType = Literal[
    "session.ready",
    "session.snapshot",
    "user.message.accepted",
    "agent.chunk",
    "agent.state_patch",
    "agent.done",
    "agent.error",
    "ping",
    "pong",
]
BootstrapRealtimeClientEventType = Literal["user.message", "ping"]

DISPLAY_TEXT_EVENT_TYPES = frozenset({"agent.chunk"})
AGENT_STATE_EVENT_TYPES = frozenset({"agent.state_patch"})
REQUEST_SCOPED_EVENT_TYPES = frozenset({
    "user.message.accepted",
    "agent.chunk",
    "agent.state_patch",
    "agent.done",
})
FORBIDDEN_TEXT_PROTOCOL_MARKERS = ("<config", "</config>", "<json", "</json>", "---")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionReadyPayload(_StrictModel):
    pass


class SessionSnapshotPayload(_StrictModel):
    snapshot: dict[str, Any]


class UserMessageAcceptedPayload(_StrictModel):
    pass


class AgentChunkPayload(_StrictModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("agent.chunk.text 不能为空")
        lowered = trimmed.lower()
        for marker in FORBIDDEN_TEXT_PROTOCOL_MARKERS:
            if marker in lowered:
                raise ValueError("agent.chunk.text 只能承载纯展示文本，不能混入控制协议")
        return value


class AgentStatePatchPayload(_StrictModel):
    display_name: str | None = None
    speaking_style: str | None = None
    personality_traits: list[str] | None = None

    @field_validator("personality_traits")
    @classmethod
    def normalize_traits(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        result: list[str] = []
        for item in value:
            trimmed = item.strip()
            if trimmed and trimmed not in result:
                result.append(trimmed)
        return result

    @model_validator(mode="after")
    def ensure_non_empty_patch(self) -> "AgentStatePatchPayload":
        if self.display_name is None and self.speaking_style is None and self.personality_traits is None:
            raise ValueError("agent.state_patch 至少要包含一个字段")
        return self


class AgentDonePayload(_StrictModel):
    pass


class AgentErrorPayload(_StrictModel):
    detail: str = Field(min_length=1)
    error_code: str = Field(min_length=1)


class PingPayload(_StrictModel):
    nonce: str | None = None


class PongPayload(_StrictModel):
    nonce: str | None = None


class UserMessagePayload(_StrictModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user.message.payload.text 不能为空")
        return value


class BootstrapRealtimeClientEvent(_StrictModel):
    type: BootstrapRealtimeClientEventType
    session_id: str = Field(min_length=1)
    request_id: str | None = None
    payload: UserMessagePayload | PingPayload

    @model_validator(mode="before")
    @classmethod
    def parse_client_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        payload = data.get("payload", {})
        event_type = data.get("type")
        if event_type == "user.message":
            normalized["payload"] = TypeAdapter(UserMessagePayload).validate_python(payload)
        elif event_type == "ping":
            normalized["payload"] = TypeAdapter(PingPayload).validate_python(payload)
        return normalized

    @model_validator(mode="after")
    def validate_client_scope(self) -> "BootstrapRealtimeClientEvent":
        if self.type == "user.message" and not self.request_id:
            raise ValueError("user.message 必须携带 request_id")
        return self


BootstrapRealtimePayload = (
    SessionReadyPayload
    | SessionSnapshotPayload
    | UserMessageAcceptedPayload
    | AgentChunkPayload
    | AgentStatePatchPayload
    | AgentDonePayload
    | AgentErrorPayload
    | PingPayload
    | PongPayload
)

_PAYLOAD_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "session.ready": TypeAdapter(SessionReadyPayload),
    "session.snapshot": TypeAdapter(SessionSnapshotPayload),
    "user.message.accepted": TypeAdapter(UserMessageAcceptedPayload),
    "agent.chunk": TypeAdapter(AgentChunkPayload),
    "agent.state_patch": TypeAdapter(AgentStatePatchPayload),
    "agent.done": TypeAdapter(AgentDonePayload),
    "agent.error": TypeAdapter(AgentErrorPayload),
    "ping": TypeAdapter(PingPayload),
    "pong": TypeAdapter(PongPayload),
}


class BootstrapRealtimeEvent(_StrictModel):
    type: BootstrapRealtimeEventType
    session_id: str = Field(min_length=1)
    request_id: str | None = None
    seq: int = Field(ge=0)
    payload: BootstrapRealtimePayload
    ts: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def parse_payload_by_type(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        event_type = data.get("type")
        payload = data.get("payload", {})
        adapter = _PAYLOAD_ADAPTERS.get(str(event_type))
        if adapter is None:
            return data
        normalized = dict(data)
        normalized["payload"] = adapter.validate_python(payload)
        return normalized

    @model_validator(mode="after")
    def validate_scope(self) -> "BootstrapRealtimeEvent":
        if self.type in REQUEST_SCOPED_EVENT_TYPES and not self.request_id:
            raise ValueError(f"{self.type} 必须携带 request_id")
        if self.type in DISPLAY_TEXT_EVENT_TYPES and not isinstance(self.payload, AgentChunkPayload):
            raise ValueError("agent.chunk 只能使用文本 payload")
        if self.type in AGENT_STATE_EVENT_TYPES and not isinstance(self.payload, AgentStatePatchPayload):
            raise ValueError("agent.state_patch 只能使用结构化状态 payload")
        return self


def build_bootstrap_realtime_event(
    *,
    event_type: BootstrapRealtimeEventType,
    session_id: str,
    seq: int,
    payload: dict[str, Any] | BootstrapRealtimePayload | None = None,
    request_id: str | None = None,
    ts: str | None = None,
) -> BootstrapRealtimeEvent:
    return BootstrapRealtimeEvent(
        type=event_type,
        session_id=session_id,
        request_id=request_id,
        seq=seq,
        payload=cast(Any, payload or {}),
        ts=ts or utc_now_iso(),
    )
