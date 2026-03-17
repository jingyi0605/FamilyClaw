from __future__ import annotations

from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_backends.base import VoiceRuntimeBackend
from app.modules.voice.runtime_types import (
    VoiceRuntimeAppendResult,
    VoiceRuntimeStartResult,
    VoiceRuntimeTranscriptResult,
)


class DisabledVoiceRuntimeBackend(VoiceRuntimeBackend):
    """保持当前禁用语义，必要时只吃调试 transcript 兜底。"""

    async def start_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> VoiceRuntimeStartResult:
        _ = (terminal, sample_rate, codec, channels)
        return VoiceRuntimeStartResult(
            ok=False,
            runtime_status="disabled",
            runtime_session_id=session.runtime_session_id or session.session_id,
            error_code="voice_runtime_unavailable",
            detail="voice-runtime disabled",
            degraded=True,
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
        _ = (terminal, chunk_base64, chunk_bytes, codec, sample_rate)
        return VoiceRuntimeAppendResult(
            ok=False,
            runtime_status="disabled",
            runtime_session_id=session.runtime_session_id or session.session_id,
            error_code="voice_runtime_unavailable",
            detail="voice-runtime disabled",
            degraded=True,
        )

    async def finalize_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        debug_transcript: str | None = None,
    ) -> VoiceRuntimeTranscriptResult:
        _ = terminal
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

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        _ = (session_id, terminal_id)
        return False

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        _ = terminal_id
        return 0
