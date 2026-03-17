from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from threading import Lock


@dataclass(slots=True)
class EmbeddedAudioSession:
    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None
    sample_rate: int
    codec: str
    channels: int
    session_purpose: str = "conversation"
    enrollment_id: str | None = None
    audio_bytes: bytearray = field(default_factory=bytearray)
    chunk_count: int = 0
    received_bytes: int = 0


class EmbeddedAudioSessionStore:
    """短生命周期音频缓存，只服务 runtime，不污染业务 session。"""

    def __init__(self) -> None:
        self._sessions: dict[str, EmbeddedAudioSession] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()

    def start_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
        room_id: str | None,
        sample_rate: int,
        codec: str,
        channels: int,
        session_purpose: str,
        enrollment_id: str | None,
    ) -> EmbeddedAudioSession:
        with self._lock:
            session = EmbeddedAudioSession(
                session_id=session_id,
                terminal_id=terminal_id,
                household_id=household_id,
                room_id=room_id,
                sample_rate=sample_rate,
                codec=codec,
                channels=channels,
                session_purpose=session_purpose,
                enrollment_id=enrollment_id,
            )
            self._sessions[session_id] = session
            return self._clone_session(session)

    def append_audio(
        self,
        *,
        session_id: str,
        terminal_id: str,
        chunk_base64: str,
        chunk_bytes: int,
    ) -> EmbeddedAudioSession | None:
        try:
            chunk = base64.b64decode(chunk_base64.encode("utf-8"), validate=False)
        except (ValueError, binascii.Error):
            return None

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.terminal_id != terminal_id:
                return None
            session.chunk_count += 1
            session.received_bytes += max(chunk_bytes, len(chunk))
            session.audio_bytes.extend(chunk)
            return self._clone_session(session)

    def pop_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
    ) -> EmbeddedAudioSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.terminal_id != terminal_id or session.household_id != household_id:
                return None
            self._sessions.pop(session_id, None)
            return self._clone_session(session)

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if terminal_id is not None and session.terminal_id != terminal_id:
                return False
            self._sessions.pop(session_id, None)
            return True

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        with self._lock:
            to_remove = [session_id for session_id, session in self._sessions.items() if session.terminal_id == terminal_id]
            for session_id in to_remove:
                self._sessions.pop(session_id, None)
            return len(to_remove)

    def get(self, session_id: str) -> EmbeddedAudioSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return self._clone_session(session)

    def _clone_session(self, session: EmbeddedAudioSession) -> EmbeddedAudioSession:
        return EmbeddedAudioSession(
            session_id=session.session_id,
            terminal_id=session.terminal_id,
            household_id=session.household_id,
            room_id=session.room_id,
            sample_rate=session.sample_rate,
            codec=session.codec,
            channels=session.channels,
            session_purpose=session.session_purpose,
            enrollment_id=session.enrollment_id,
            audio_bytes=bytearray(session.audio_bytes),
            chunk_count=session.chunk_count,
            received_bytes=session.received_bytes,
        )


embedded_audio_session_store = EmbeddedAudioSessionStore()
