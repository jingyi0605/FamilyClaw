from __future__ import annotations

from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceRuntimeTranscriptResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    transcript_text: str | None = None
    error_code: str | None = None
    detail: str | None = None
    runtime_status: str = Field(default="unavailable")
    degraded: bool = False


VoiceRuntimeHandler = Callable[[VoiceSessionState, VoiceTerminalState], Awaitable[VoiceRuntimeTranscriptResult]]


class VoiceRuntimeClient:
    """`voice-runtime` 的最小接缝，当前先保留可替换 handler。"""

    def __init__(self) -> None:
        self._handler: VoiceRuntimeHandler | None = None

    def set_handler(self, handler: VoiceRuntimeHandler | None) -> None:
        self._handler = handler

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
                degraded=True,
            )

        if self._handler is None:
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail="voice-runtime 尚未接入，当前只保留最小接缝。",
                runtime_status="unavailable",
                degraded=True,
            )

        return await self._handler(session, terminal)


voice_runtime_client = VoiceRuntimeClient()
