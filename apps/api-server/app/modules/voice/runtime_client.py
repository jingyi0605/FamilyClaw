from __future__ import annotations

import base64
from typing import Awaitable, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


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


VoiceRuntimeFinalizeHandler = Callable[[VoiceSessionState, VoiceTerminalState], Awaitable[VoiceRuntimeTranscriptResult]]


class VoiceRuntimeClient:
    """统一走 voice-runtime 接缝，调试转写也不能绕过正式 commit。"""

    def __init__(self) -> None:
        self._finalize_handler: VoiceRuntimeFinalizeHandler | None = None

    def set_handler(self, handler: VoiceRuntimeFinalizeHandler | None) -> None:
        self._finalize_handler = handler

    async def start_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> VoiceRuntimeStartResult:
        if not self._runtime_enabled():
            return VoiceRuntimeStartResult(
                ok=False,
                runtime_status="disabled",
                error_code="voice_runtime_unavailable",
                detail="voice-runtime disabled",
                degraded=True,
            )

        try:
            response = await self._post_json(
                "/v1/voice/sessions/start",
                {
                    "session_id": session.session_id,
                    "terminal_id": terminal.terminal_id,
                    "household_id": session.household_id,
                    "room_id": session.room_id or terminal.room_id,
                    "sample_rate": sample_rate,
                    "codec": codec,
                    "channels": channels,
                    "session_purpose": session.session_purpose,
                    "enrollment_id": session.voiceprint_enrollment_id,
                },
            )
        except httpx.HTTPError as exc:
            return VoiceRuntimeStartResult(
                ok=False,
                runtime_status="start_failed",
                runtime_session_id=session.session_id,
                error_code="voice_runtime_unavailable",
                detail=str(exc),
                degraded=True,
            )

        return VoiceRuntimeStartResult(
            ok=True,
            runtime_status=str(response.get("runtime_status") or "session_started"),
            runtime_session_id=str(response.get("runtime_session_id") or session.session_id),
            degraded=bool(response.get("degraded", False)),
        )

    async def append_audio(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        chunk_base64: str,
        chunk_bytes: int,
        codec: str,
        sample_rate: int,
    ) -> VoiceRuntimeAppendResult:
        if not self._runtime_enabled():
            return VoiceRuntimeAppendResult(
                ok=False,
                runtime_status="disabled",
                runtime_session_id=session.runtime_session_id or session.session_id,
                error_code="voice_runtime_unavailable",
                detail="voice-runtime disabled",
                degraded=True,
            )

        try:
            response = await self._post_json(
                "/v1/voice/sessions/append",
                {
                    "session_id": session.runtime_session_id or session.session_id,
                    "terminal_id": terminal.terminal_id,
                    "chunk_base64": chunk_base64,
                    "chunk_bytes": chunk_bytes,
                    "codec": codec,
                    "sample_rate": sample_rate,
                },
            )
        except httpx.HTTPError as exc:
            return VoiceRuntimeAppendResult(
                ok=False,
                runtime_status="append_failed",
                runtime_session_id=session.runtime_session_id or session.session_id,
                error_code="voice_runtime_unavailable",
                detail=str(exc),
                degraded=True,
            )

        return VoiceRuntimeAppendResult(
            ok=True,
            runtime_status=str(response.get("runtime_status") or "streaming"),
            runtime_session_id=str(response.get("runtime_session_id") or session.runtime_session_id or session.session_id),
            degraded=bool(response.get("degraded", False)),
        )

    async def finalize_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        debug_transcript: str | None = None,
    ) -> VoiceRuntimeTranscriptResult:
        if self._finalize_handler is not None:
            return await self._finalize_handler(session, terminal)

        if not self._runtime_enabled():
            if debug_transcript and debug_transcript.strip():
                return VoiceRuntimeTranscriptResult(
                    ok=True,
                    transcript_text=debug_transcript.strip(),
                    runtime_status="debug_transcript",
                    runtime_session_id=session.runtime_session_id or session.session_id,
                    degraded=True,
                )
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail="voice-runtime disabled",
                runtime_status="unavailable",
                runtime_session_id=session.runtime_session_id or session.session_id,
                degraded=True,
            )

        headers: dict[str, str] = {}
        if debug_transcript and debug_transcript.strip():
            headers["X-Debug-Transcript-B64"] = base64.b64encode(debug_transcript.strip().encode("utf-8")).decode("ascii")

        try:
            response = await self._post_json(
                "/v1/voice/sessions/commit",
                {
                    "session_id": session.runtime_session_id or session.session_id,
                    "terminal_id": terminal.terminal_id,
                    "household_id": session.household_id,
                },
                extra_headers=headers,
            )
        except httpx.HTTPError as exc:
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail=str(exc),
                runtime_status="commit_failed",
                runtime_session_id=session.runtime_session_id or session.session_id,
                degraded=True,
            )

        transcript_text = str(response.get("transcript_text") or "").strip() or None
        ok = bool(response.get("ok", transcript_text is not None))
        error_code = None if ok else str(response.get("error_code") or "voice_runtime_unavailable")
        return VoiceRuntimeTranscriptResult(
            ok=ok,
            transcript_text=transcript_text,
            error_code=error_code,
            detail=None if ok else str(response.get("detail") or "voice-runtime returned invalid transcript"),
            runtime_status=str(response.get("runtime_status") or ("transcribed" if ok else "commit_failed")),
            runtime_session_id=str(response.get("runtime_session_id") or session.runtime_session_id or session.session_id),
            audio_artifact=self._parse_audio_artifact(response),
            degraded=bool(response.get("degraded", False)),
        )

    def _runtime_enabled(self) -> bool:
        return bool(settings.voice_runtime_enabled and settings.voice_runtime_base_url)

    async def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        base_url = (settings.voice_runtime_base_url or "").rstrip("/")
        if not base_url:
            raise httpx.ConnectError("voice runtime base url is empty")

        headers: dict[str, str] = {}
        if settings.voice_runtime_api_key:
            headers["Authorization"] = f"Bearer {settings.voice_runtime_api_key}"
        if extra_headers:
            headers.update(extra_headers)

        timeout = httpx.Timeout(settings.voice_runtime_timeout_ms / 1000)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}{path}", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise httpx.HTTPError("voice runtime response must be a json object")
            return data

    def _parse_audio_artifact(self, response: dict[str, object]) -> VoiceRuntimeAudioArtifact | None:
        artifact_id = str(response.get("audio_artifact_id") or "").strip()
        if not artifact_id:
            return None
        return VoiceRuntimeAudioArtifact(
            artifact_id=artifact_id,
            file_path=str(response.get("audio_file_path") or ""),
            sample_rate=int(response.get("sample_rate") or 0),
            channels=int(response.get("channels") or 0),
            sample_width=int(response.get("sample_width") or 0),
            duration_ms=int(response.get("duration_ms") or 0),
            sha256=str(response.get("audio_sha256") or ""),
        )


voice_runtime_client = VoiceRuntimeClient()
