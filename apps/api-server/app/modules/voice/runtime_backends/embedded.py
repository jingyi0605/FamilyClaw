from __future__ import annotations

from app.modules.voice.embedded_runtime import embedded_voice_runtime_service
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_backends.base import VoiceRuntimeBackend
from app.modules.voice.runtime_types import (
    VoiceRuntimeAppendResult,
    VoiceRuntimeStartResult,
    VoiceRuntimeTranscriptResult,
)


class EmbeddedVoiceRuntimeBackend(VoiceRuntimeBackend):
    """本地默认 runtime，实现轻缓存和 commit 时的音频产物生成。"""

    async def start_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> VoiceRuntimeStartResult:
        embedded_voice_runtime_service.start_session(
            session_id=session.session_id,
            terminal_id=terminal.terminal_id,
            household_id=session.household_id,
            room_id=session.room_id or terminal.room_id,
            sample_rate=sample_rate,
            codec=codec,
            channels=channels,
            session_purpose=session.session_purpose,
            enrollment_id=session.voiceprint_enrollment_id,
        )
        return VoiceRuntimeStartResult(
            ok=True,
            runtime_status="session_started",
            runtime_session_id=session.runtime_session_id or session.session_id,
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
        _ = (codec, sample_rate)
        buffered = embedded_voice_runtime_service.append_audio(
            session_id=session.runtime_session_id or session.session_id,
            terminal_id=terminal.terminal_id,
            chunk_base64=chunk_base64,
            chunk_bytes=chunk_bytes,
        )
        if buffered is None:
            return VoiceRuntimeAppendResult(
                ok=False,
                runtime_status="append_failed",
                runtime_session_id=session.runtime_session_id or session.session_id,
                error_code="voice_runtime_unavailable",
                detail="embedded voice session not found",
                degraded=True,
            )
        return VoiceRuntimeAppendResult(
            ok=True,
            runtime_status="streaming",
            runtime_session_id=session.runtime_session_id or session.session_id,
        )

    async def finalize_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        debug_transcript: str | None = None,
    ) -> VoiceRuntimeTranscriptResult:
        return await embedded_voice_runtime_service.finalize_session(
            session_id=session.runtime_session_id or session.session_id,
            terminal_id=terminal.terminal_id,
            household_id=session.household_id,
            debug_transcript=debug_transcript,
        )

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        return embedded_voice_runtime_service.discard_session(session_id=session_id, terminal_id=terminal_id)

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        return embedded_voice_runtime_service.discard_terminal_sessions(terminal_id=terminal_id)
