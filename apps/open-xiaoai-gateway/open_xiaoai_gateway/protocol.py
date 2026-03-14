from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GatewayEventType = Literal[
    "terminal.online",
    "terminal.offline",
    "terminal.heartbeat",
    "session.start",
    "audio.append",
    "audio.commit",
    "session.cancel",
    "playback.interrupted",
    "playback.receipt",
]
GatewayCommandType = Literal["session.ready", "play.start", "play.stop", "play.abort", "agent.error"]
OpenXiaoAIEventName = Literal[
    "hello",
    "terminal.online",
    "terminal.offline",
    "heartbeat",
    "terminal.heartbeat",
    "session.start",
    "listen.start",
    "audio.commit",
    "listen.stop",
    "session.cancel",
    "listen.cancel",
    "playback.interrupted",
    "playback.started",
    "playback.completed",
    "playback.failed",
    "play",
    "stop",
    "abort",
    "error",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GatewayEvent(_StrictModel):
    type: GatewayEventType
    terminal_id: str = Field(min_length=1)
    session_id: str | None = None
    seq: int = Field(ge=0)
    payload: dict[str, Any]
    ts: str = Field(min_length=1)


class GatewayCommand(_StrictModel):
    type: GatewayCommandType
    terminal_id: str = Field(min_length=1)
    session_id: str | None = None
    seq: int = Field(ge=0)
    payload: dict[str, Any]
    ts: str = Field(min_length=1)


class OpenXiaoAIEnvelope(_StrictModel):
    event: OpenXiaoAIEventName | str
    data: dict[str, Any] = Field(default_factory=dict)
