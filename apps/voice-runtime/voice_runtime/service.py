from __future__ import annotations

import asyncio
import base64
import hashlib
import wave
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from voice_runtime.settings import settings


@dataclass(slots=True)
class RuntimeAudioArtifact:
    artifact_id: str
    file_path: str
    sample_rate: int
    channels: int
    sample_width: int
    duration_ms: int
    sha256: str


@dataclass(slots=True)
class RuntimeCommitResult:
    session: "RuntimeSession"
    audio_artifact: RuntimeAudioArtifact | None


@dataclass(slots=True)
class RuntimeSession:
    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None
    sample_rate: int
    codec: str
    channels: int
    session_purpose: str = "conversation"
    enrollment_id: str | None = None
    chunk_count: int = 0
    received_bytes: int = 0
    audio_chunks: list[bytes] = field(default_factory=list)


class VoiceRuntimeSessionStore:
    """先把音频落盘链路站稳，不能只在内存里攒字节。"""

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
        session_purpose: str,
        enrollment_id: str | None,
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
                session_purpose=session_purpose,
                enrollment_id=enrollment_id,
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
    ) -> RuntimeCommitResult | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.terminal_id != terminal_id or session.household_id != household_id:
                return None

            audio_artifact = persist_audio_artifact(session)
            self._sessions.pop(session_id, None)
            return RuntimeCommitResult(session=session, audio_artifact=audio_artifact)

    async def reset(self) -> None:
        async with self._lock:
            self._sessions.clear()


def build_transcript(session: RuntimeSession, debug_transcript: str | None = None) -> str:
    """优先吃显式调试文本，其次尝试从字节里兜底。"""

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


def persist_audio_artifact(session: RuntimeSession) -> RuntimeAudioArtifact | None:
    sample_width = resolve_sample_width(session.codec)
    raw_audio = b"".join(session.audio_chunks)
    if sample_width is None or not raw_audio:
        return None

    frame_width = sample_width * session.channels
    if frame_width <= 0:
        return None

    frame_count = len(raw_audio) // frame_width
    if frame_count <= 0:
        return None

    usable_audio = raw_audio[: frame_count * frame_width]
    artifact_id = str(uuid4())
    artifact_dir = build_artifact_directory(session)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{artifact_id}.wav"

    with wave.open(str(artifact_path), "wb") as wav_file:
        wav_file.setnchannels(session.channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(session.sample_rate)
        wav_file.writeframes(usable_audio)

    duration_ms = max(1, int(frame_count * 1000 / session.sample_rate))
    return RuntimeAudioArtifact(
        artifact_id=artifact_id,
        file_path=str(artifact_path.resolve()),
        sample_rate=session.sample_rate,
        channels=session.channels,
        sample_width=sample_width,
        duration_ms=duration_ms,
        sha256=hashlib.sha256(usable_audio).hexdigest(),
    )


def build_artifact_directory(session: RuntimeSession) -> Path:
    day_bucket = session.session_id[:10] if len(session.session_id) >= 10 else "session"
    return (
        settings.artifacts_root
        / session.household_id
        / session.terminal_id
        / session.session_purpose
        / day_bucket
    )


def resolve_sample_width(codec: str) -> int | None:
    codec_value = codec.strip().lower()
    if codec_value == "pcm_s16le":
        return 2
    return None


session_store = VoiceRuntimeSessionStore()
