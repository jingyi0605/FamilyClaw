from __future__ import annotations

import hashlib
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.blocking import BlockingCallPolicy, BlockingCallTimeoutError, run_blocking
from app.core.config import settings
from app.modules.voice.embedded_runtime_store import EmbeddedAudioSession, embedded_audio_session_store
from app.modules.voice.runtime_types import VoiceRuntimeAudioArtifact, VoiceRuntimeTranscriptResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddedRuntimeFinalizePayload:
    transcript_text: str
    audio_artifact: VoiceRuntimeAudioArtifact | None


class EmbeddedVoiceRuntimeService:
    """把内嵌 runtime 的轻缓存和 finalize 落盘逻辑收在一起。"""

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
    ) -> None:
        embedded_audio_session_store.start_session(
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

    def append_audio(
        self,
        *,
        session_id: str,
        terminal_id: str,
        chunk_base64: str,
        chunk_bytes: int,
    ) -> EmbeddedAudioSession | None:
        return embedded_audio_session_store.append_audio(
            session_id=session_id,
            terminal_id=terminal_id,
            chunk_base64=chunk_base64,
            chunk_bytes=chunk_bytes,
        )

    async def finalize_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
        debug_transcript: str | None,
    ) -> VoiceRuntimeTranscriptResult:
        session = embedded_audio_session_store.pop_session(
            session_id=session_id,
            terminal_id=terminal_id,
            household_id=household_id,
        )
        if session is None:
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail="embedded voice session not found",
                runtime_status="commit_failed",
                runtime_session_id=session_id,
                degraded=True,
            )

        try:
            finalize_result = await run_blocking(
                lambda: finalize_embedded_audio_session(session=session, debug_transcript=debug_transcript),
                policy=BlockingCallPolicy(
                    label="voice.embedded_runtime.finalize",
                    kind="cpu_bound",
                    timeout_seconds=max(settings.voice_runtime_timeout_ms / 1000, 0.1),
                ),
                logger=logger,
                context={
                    "session_id": session_id,
                    "terminal_id": terminal_id,
                    "household_id": household_id,
                    "session_purpose": session.session_purpose,
                },
            )
        except BlockingCallTimeoutError:
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail="embedded voice runtime finalize timeout",
                runtime_status="commit_failed",
                runtime_session_id=session_id,
                degraded=True,
            )
        except Exception as exc:
            logger.exception(
                "内嵌语音 runtime finalize 失败 session_id=%s terminal_id=%s household_id=%s",
                session_id,
                terminal_id,
                household_id,
            )
            return VoiceRuntimeTranscriptResult(
                ok=False,
                error_code="voice_runtime_unavailable",
                detail=str(exc),
                runtime_status="commit_failed",
                runtime_session_id=session_id,
                degraded=True,
            )

        return VoiceRuntimeTranscriptResult(
            ok=True,
            transcript_text=finalize_result.transcript_text,
            runtime_status="transcribed",
            runtime_session_id=session_id,
            audio_artifact=finalize_result.audio_artifact,
            degraded=finalize_result.audio_artifact is None,
        )

    def discard_session(self, *, session_id: str, terminal_id: str | None = None) -> bool:
        return embedded_audio_session_store.discard_session(session_id=session_id, terminal_id=terminal_id)

    def discard_terminal_sessions(self, *, terminal_id: str) -> int:
        return embedded_audio_session_store.discard_terminal_sessions(terminal_id=terminal_id)


def finalize_embedded_audio_session(
    *,
    session: EmbeddedAudioSession,
    debug_transcript: str | None,
) -> EmbeddedRuntimeFinalizePayload:
    transcript_text = build_embedded_transcript(session=session, debug_transcript=debug_transcript)
    audio_artifact = persist_embedded_audio_artifact(session)
    return EmbeddedRuntimeFinalizePayload(
        transcript_text=transcript_text,
        audio_artifact=audio_artifact,
    )


def build_embedded_transcript(*, session: EmbeddedAudioSession, debug_transcript: str | None) -> str:
    if debug_transcript and debug_transcript.strip():
        return debug_transcript.strip()

    if session.audio_bytes:
        try:
            text = bytes(session.audio_bytes).decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        if text:
            return text

    return settings.voice_runtime_default_commit_transcript


def persist_embedded_audio_artifact(session: EmbeddedAudioSession) -> VoiceRuntimeAudioArtifact | None:
    sample_width = resolve_sample_width(session.codec)
    raw_audio = bytes(session.audio_bytes)
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
    artifact_dir = build_embedded_artifact_directory(session)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{artifact_id}.wav"

    with wave.open(str(artifact_path), "wb") as wav_file:
        wav_file.setnchannels(session.channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(session.sample_rate)
        wav_file.writeframes(usable_audio)

    duration_ms = max(1, int(frame_count * 1000 / session.sample_rate))
    return VoiceRuntimeAudioArtifact(
        artifact_id=artifact_id,
        file_path=str(artifact_path.resolve()),
        sample_rate=session.sample_rate,
        channels=session.channels,
        sample_width=sample_width,
        duration_ms=duration_ms,
        sha256=hashlib.sha256(usable_audio).hexdigest(),
    )


def build_embedded_artifact_directory(session: EmbeddedAudioSession) -> Path:
    artifacts_root = Path(settings.voice_runtime_artifacts_root).expanduser().resolve()
    day_bucket = session.session_id[:10] if len(session.session_id) >= 10 else "session"
    return artifacts_root / session.household_id / session.terminal_id / session.session_purpose / day_bucket


def resolve_sample_width(codec: str) -> int | None:
    codec_value = codec.strip().lower()
    if codec_value == "pcm_s16le":
        return 2
    return None


embedded_voice_runtime_service = EmbeddedVoiceRuntimeService()
