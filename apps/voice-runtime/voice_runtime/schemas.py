from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VoiceSessionPurpose = Literal["conversation", "voiceprint_enrollment"]


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None = None
    sample_rate: int = Field(ge=1)
    codec: str
    channels: int = Field(ge=1)
    session_purpose: VoiceSessionPurpose = "conversation"
    enrollment_id: str | None = None

    @model_validator(mode="after")
    def validate_enrollment_scope(self) -> "StartSessionRequest":
        if self.session_purpose == "voiceprint_enrollment" and not self.enrollment_id:
            raise ValueError("voiceprint_enrollment 会话必须携带 enrollment_id")
        return self


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
    audio_artifact_id: str | None = None
    audio_file_path: str | None = None
    sample_rate: int | None = Field(default=None, ge=1)
    channels: int | None = Field(default=None, ge=1)
    sample_width: int | None = Field(default=None, ge=1)
    duration_ms: int | None = Field(default=None, ge=1)
    audio_sha256: str | None = None
    degraded: bool = True


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    error_code: str
    detail: str

