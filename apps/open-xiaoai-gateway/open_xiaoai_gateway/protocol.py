from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
GatewayCommandType = Literal[
    "binding.refresh",
    "session.ready",
    "play.start",
    "play.stop",
    "play.abort",
    "speaker.turn_on",
    "speaker.set_volume",
    "agent.error",
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


class OpenXiaoAIRequest(_StrictModel):
    id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    payload: Any | None = None


class OpenXiaoAIResponse(_StrictModel):
    id: str = Field(min_length=1)
    code: int | None = None
    msg: str | None = None
    data: Any | None = None


class OpenXiaoAIEvent(_StrictModel):
    id: str = Field(min_length=1)
    event: str = Field(min_length=1)
    data: Any | None = None


class OpenXiaoAIStream(_StrictModel):
    id: str = Field(min_length=1)
    tag: str = Field(min_length=1)
    bytes: list[int] = Field(default_factory=list)
    data: Any | None = None

    def raw_bytes(self) -> bytes:
        return bytes(self.bytes)


class OpenXiaoAITextFrame(_StrictModel):
    Request: OpenXiaoAIRequest | None = None
    Response: OpenXiaoAIResponse | None = None
    Event: OpenXiaoAIEvent | None = None

    @model_validator(mode="after")
    def validate_single_variant(self) -> "OpenXiaoAITextFrame":
        populated = [name for name in ("Request", "Response", "Event") if getattr(self, name) is not None]
        if len(populated) != 1:
            raise ValueError("open-xiaoai 文本消息必须且只能包含一种消息体")
        return self

    @property
    def variant(self) -> Literal["Request", "Response", "Event"]:
        if self.Request is not None:
            return "Request"
        if self.Response is not None:
            return "Response"
        return "Event"


def parse_text_frame(raw_message: str) -> OpenXiaoAITextFrame:
    data = json.loads(raw_message)
    if not isinstance(data, dict):
        raise ValueError("open-xiaoai 文本消息必须是 JSON object")
    return OpenXiaoAITextFrame.model_validate(data)


def parse_stream_frame(raw_message: bytes) -> OpenXiaoAIStream:
    data = json.loads(raw_message.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("open-xiaoai 二进制消息必须是 JSON object")
    return OpenXiaoAIStream.model_validate(data)


def build_request_frame(*, request_id: str, command: str, payload: Any | None = None) -> str:
    return json.dumps(
        {
            "Request": OpenXiaoAIRequest(
                id=request_id,
                command=command,
                payload=payload,
            ).model_dump(mode="json")
        },
        ensure_ascii=False,
    )


def build_stream_frame(*, stream_id: str, tag: str, raw_bytes: bytes, data: Any | None = None) -> bytes:
    return json.dumps(
        {
            "id": stream_id,
            "tag": tag,
            "bytes": list(raw_bytes),
            "data": data,
        },
        ensure_ascii=False,
    ).encode("utf-8")
