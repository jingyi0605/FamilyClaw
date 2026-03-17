from __future__ import annotations

from typing import Protocol

from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_types import (
    VoiceRuntimeAppendResult,
    VoiceRuntimeStartResult,
    VoiceRuntimeTranscriptResult,
)


class VoiceRuntimeBackend(Protocol):
    """统一 runtime backend 接口，上层不需要知道底下到底是本地还是远程。"""

    async def start_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> VoiceRuntimeStartResult:
        ...

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
        ...

    async def finalize_session(
        self,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        debug_transcript: str | None = None,
    ) -> VoiceRuntimeTranscriptResult:
        ...

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        ...

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        ...
