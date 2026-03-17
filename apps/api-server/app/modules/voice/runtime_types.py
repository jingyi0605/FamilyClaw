from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VoiceRuntimeAudioArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    file_path: str
    sample_rate: int = Field(ge=1)
    channels: int = Field(ge=1)
    sample_width: int = Field(ge=1)
    duration_ms: int = Field(ge=1)
    sha256: str


class VoiceRuntimeTranscriptResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    transcript_text: str | None = None
    error_code: str | None = None
    detail: str | None = None
    runtime_status: str = Field(default="unavailable")
    runtime_session_id: str | None = None
    audio_artifact: VoiceRuntimeAudioArtifact | None = None
    degraded: bool = False


class VoiceRuntimeStartResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    runtime_status: str = "session_started"
    runtime_session_id: str | None = None
    error_code: str | None = None
    detail: str | None = None
    degraded: bool = False


class VoiceRuntimeAppendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    runtime_status: str = "streaming"
    runtime_session_id: str | None = None
    error_code: str | None = None
    detail: str | None = None
    degraded: bool = False
