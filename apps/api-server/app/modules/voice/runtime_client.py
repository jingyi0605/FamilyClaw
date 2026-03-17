from __future__ import annotations

from typing import Awaitable, Callable

from app.core.config import VoiceRuntimeMode, settings
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_backends import VoiceRuntimeBackend, build_voice_runtime_backend
from app.modules.voice.runtime_types import (
    VoiceRuntimeAppendResult,
    VoiceRuntimeAudioArtifact,
    VoiceRuntimeStartResult,
    VoiceRuntimeTranscriptResult,
)


VoiceRuntimeFinalizeHandler = Callable[[VoiceSessionState, VoiceTerminalState], Awaitable[VoiceRuntimeTranscriptResult]]


class VoiceRuntimeClient:
    """统一走 voice-runtime 接缝，调试转写也不能绕过正式 commit。"""

    def __init__(self) -> None:
        self._finalize_handler: VoiceRuntimeFinalizeHandler | None = None

    def set_handler(self, handler: VoiceRuntimeFinalizeHandler | None) -> None:
        self._finalize_handler = handler

    def get_runtime_mode(self) -> VoiceRuntimeMode:
        return settings.resolved_voice_runtime_mode

    def get_backend(self) -> VoiceRuntimeBackend:
        return build_voice_runtime_backend(self.get_runtime_mode())

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        return self.get_backend().discard_session(session_id=session_id, terminal_id=terminal_id)

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        return self.get_backend().discard_terminal_sessions(terminal_id=terminal_id)

    async def start_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> VoiceRuntimeStartResult:
        return await self.get_backend().start_session(
            session=session,
            terminal=terminal,
            sample_rate=sample_rate,
            codec=codec,
            channels=channels,
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
        return await self.get_backend().append_audio(
            session=session,
            terminal=terminal,
            chunk_base64=chunk_base64,
            chunk_bytes=chunk_bytes,
            codec=codec,
            sample_rate=sample_rate,
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
        return await self.get_backend().finalize_session(
            session=session,
            terminal=terminal,
            debug_transcript=debug_transcript,
        )


voice_runtime_client = VoiceRuntimeClient()
