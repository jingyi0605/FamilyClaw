import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import get_settings
from app.modules.voice.embedded_runtime_store import embedded_audio_session_store
from app.modules.voice.runtime_backends import EmbeddedVoiceRuntimeBackend
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_client import voice_runtime_client


class VoiceRuntimeClientTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_runtime_client.set_handler(None)
        embedded_audio_session_store.reset()
        get_settings.cache_clear()

    def tearDown(self) -> None:
        embedded_audio_session_store.reset()
        get_settings.cache_clear()

    def test_runtime_mode_selects_embedded_backend(self) -> None:
        with patch("app.modules.voice.runtime_client.settings.voice_runtime_mode", "embedded"):
            backend = voice_runtime_client.get_backend()

        self.assertIsInstance(backend, EmbeddedVoiceRuntimeBackend)
        self.assertEqual("embedded", voice_runtime_client.get_runtime_mode())

    def test_runtime_mode_defaults_to_embedded(self) -> None:
        self.assertEqual("embedded", voice_runtime_client.get_runtime_mode())

    def test_finalize_session_keeps_disabled_degrade_semantics(self) -> None:
        with patch("app.modules.voice.runtime_client.settings.voice_runtime_mode", "disabled"):
            result = asyncio.run(
                voice_runtime_client.finalize_session(
                    session=_build_session(runtime_session_id="runtime-1"),
                    terminal=_build_terminal(),
                    debug_transcript="打开客厅灯",
                )
            )

        self.assertTrue(result.ok)
        self.assertTrue(result.degraded)
        self.assertEqual("debug_transcript", result.runtime_status)
        self.assertEqual("打开客厅灯", result.transcript_text)

    def test_embedded_finalize_persists_audio_artifact(self) -> None:
        pcm_bytes = b"\x00\x00" * 1600
        chunk_base64 = base64.b64encode(pcm_bytes).decode("ascii")
        with tempfile.TemporaryDirectory() as tempdir, patch(
            "app.modules.voice.runtime_client.settings.voice_runtime_mode",
            "embedded",
        ), patch(
            "app.modules.voice.embedded_runtime.settings.voice_runtime_artifacts_root",
            tempdir,
        ):
            start_result = asyncio.run(
                voice_runtime_client.start_session(
                    session=_build_session(),
                    terminal=_build_terminal(),
                    sample_rate=16000,
                    codec="pcm_s16le",
                    channels=1,
                )
            )
            append_result = asyncio.run(
                voice_runtime_client.append_audio(
                    session=_build_session(runtime_session_id=start_result.runtime_session_id),
                    terminal=_build_terminal(),
                    chunk_base64=chunk_base64,
                    chunk_bytes=len(pcm_bytes),
                    codec="pcm_s16le",
                    sample_rate=16000,
                )
            )
            result = asyncio.run(
                voice_runtime_client.finalize_session(
                    session=_build_session(runtime_session_id=start_result.runtime_session_id),
                    terminal=_build_terminal(),
                    debug_transcript="打开客厅灯",
                )
            )

            self.assertTrue(start_result.ok)
            self.assertTrue(append_result.ok)
            self.assertTrue(result.ok)
            self.assertFalse(result.degraded)
            self.assertEqual("打开客厅灯", result.transcript_text)
            self.assertIsNotNone(result.audio_artifact)
            assert result.audio_artifact is not None
            artifact_path = Path(result.audio_artifact.file_path)
            self.assertTrue(artifact_path.is_file())
            self.assertEqual(16000, result.audio_artifact.sample_rate)
            self.assertEqual(1, result.audio_artifact.channels)
            self.assertEqual(2, result.audio_artifact.sample_width)
            self.assertGreater(result.audio_artifact.duration_ms, 0)


def _build_session(*, runtime_session_id: str | None = None) -> VoiceSessionState:
    return VoiceSessionState(
        session_id="session-1",
        terminal_id="terminal-1",
        household_id="household-1",
        room_id="room-1",
        runtime_session_id=runtime_session_id,
        session_purpose="conversation",
        voiceprint_enrollment_id=None,
    )


def _build_terminal() -> VoiceTerminalState:
    return VoiceTerminalState(
        terminal_id="terminal-1",
        household_id="household-1",
        room_id="room-1",
        name="客厅小爱",
        status="online",
    )


if __name__ == "__main__":
    unittest.main()
