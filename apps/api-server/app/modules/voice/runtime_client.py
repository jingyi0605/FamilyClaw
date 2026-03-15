from __future__ import annotations

from typing import Awaitable, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceRuntimeTranscriptResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    transcript_text: str | None = None
    error_code: str | None = None
    detail: str | None = None
    runtime_status: str = Field(default="unavailable")
    runtime_session_id: str | None = None
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
    """给 voice-runtime 一个正式 HTTP 接缝，同时保留可注入 handler 方便测试。"""

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
                detail="voice-runtime 未启用，当前不建立实时语音运行时会话。",
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
                detail="voice-runtime 未启用，当前不会转发音频流。",
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
        if debug_transcript and debug_transcript.strip():
            return VoiceRuntimeTranscriptResult(
                ok=True,
                transcript_text=debug_transcript.strip(),
                runtime_status="debug_transcript",
                runtime_session_id=session.runtime_session_id or session.session_id,
                degraded=True,
            )

        if self._finalize_handler is not None:
            return await self._finalize_handler(session, terminal)

        if not self._runtime_enabled():
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail="voice-runtime 尚未接入，当前只保留正式接缝。",
                runtime_status="unavailable",
                runtime_session_id=session.runtime_session_id or session.session_id,
                degraded=True,
            )

        try:
            response = await self._post_json(
                "/v1/voice/sessions/commit",
                {
                    "session_id": session.runtime_session_id or session.session_id,
                    "terminal_id": terminal.terminal_id,
                    "household_id": session.household_id,
                },
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
            detail=None if ok else str(response.get("detail") or "voice-runtime 未返回有效转写结果。"),
            runtime_status=str(response.get("runtime_status") or ("transcribed" if ok else "commit_failed")),
            runtime_session_id=str(response.get("runtime_session_id") or session.runtime_session_id or session.session_id),
            degraded=bool(response.get("degraded", False)),
        )

    def _runtime_enabled(self) -> bool:
        return bool(settings.voice_runtime_enabled and settings.voice_runtime_base_url)

    async def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        base_url = (settings.voice_runtime_base_url or "").rstrip("/")
        if not base_url:
            raise httpx.ConnectError("voice runtime base url is empty")

        headers: dict[str, str] = {}
        if settings.voice_runtime_api_key:
            headers["Authorization"] = f"Bearer {settings.voice_runtime_api_key}"

        timeout = httpx.Timeout(settings.voice_runtime_timeout_ms / 1000)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}{path}", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise httpx.HTTPError("voice runtime response must be a json object")
            return data


voice_runtime_client = VoiceRuntimeClient()
