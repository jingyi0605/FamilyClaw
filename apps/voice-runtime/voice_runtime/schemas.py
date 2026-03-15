from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None = None
    sample_rate: int = Field(ge=1)
    codec: str
    channels: int = Field(ge=1)


class AppendAudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    terminal_id: str
    chunk_base64: str
    chunk_bytes: int = Field(ge=0)
    codec: str
    sample_rate: int = Field(ge=1)


class CommitSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    terminal_id: str
    household_id: str


class StartSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    runtime_status: str = "session_started"
    runtime_session_id: str
    degraded: bool = True


class AppendAudioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    runtime_status: str = "streaming"
    runtime_session_id: str
    buffered_chunk_count: int
    received_bytes: int
    degraded: bool = True


class CommitSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    runtime_status: str = "transcribed"
    runtime_session_id: str
    transcript_text: str
    buffered_chunk_count: int
    received_bytes: int
    degraded: bool = True


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    error_code: str
    detail: str
