from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field

from voice_runtime.settings import settings


@dataclass(slots=True)
class RuntimeSession:
    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None
    sample_rate: int
    codec: str
    channels: int
    chunk_count: int = 0
    received_bytes: int = 0
    audio_chunks: list[bytes] = field(default_factory=list)


class VoiceRuntimeSessionStore:
    """用内存态把最小会话收住，先把协议跑通。"""

    def __init__(self) -> None:
        self._sessions: dict[str, RuntimeSession] = {}
        self._lock = asyncio.Lock()

    async def start_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
        room_id: str | None,
        sample_rate: int,
        codec: str,
        channels: int,
    ) -> RuntimeSession:
        async with self._lock:
            session = RuntimeSession(
                session_id=session_id,
                terminal_id=terminal_id,
                household_id=household_id,
                room_id=room_id,
                sample_rate=sample_rate,
                codec=codec,
                channels=channels,
            )
            self._sessions[session_id] = session
            return session

    async def append_audio(
        self,
        *,
        session_id: str,
        terminal_id: str,
        chunk_base64: str,
        chunk_bytes: int,
    ) -> RuntimeSession | None:
        chunk = base64.b64decode(chunk_base64.encode("utf-8"), validate=False)
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.terminal_id != terminal_id:
                return None
            session.chunk_count += 1
            session.received_bytes += max(chunk_bytes, len(chunk))
            session.audio_chunks.append(chunk)
            return session

    async def commit_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
    ) -> RuntimeSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.terminal_id != terminal_id or session.household_id != household_id:
                return None
            return session

    async def reset(self) -> None:
        async with self._lock:
            self._sessions.clear()


def build_transcript(session: RuntimeSession, debug_transcript: str | None = None) -> str:
    """优先走显式调试文本，其次尝试把输入当 UTF-8 文本兜底。"""

    if debug_transcript and debug_transcript.strip():
        return debug_transcript.strip()

    if session.audio_chunks:
        joined = b"".join(session.audio_chunks)
        try:
            text = joined.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        if text:
            return text

    return settings.default_commit_transcript


session_store = VoiceRuntimeSessionStore()
