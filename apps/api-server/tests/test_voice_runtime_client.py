import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.core.config import get_settings
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.runtime_client import voice_runtime_client


class VoiceRuntimeClientTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_runtime_client.set_handler(None)
        get_settings.cache_clear()

    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_start_session_uses_http_runtime_when_enabled(self) -> None:
        with patch("app.modules.voice.runtime_client.settings.voice_runtime_enabled", True), patch(
            "app.modules.voice.runtime_client.settings.voice_runtime_base_url",
            "http://voice-runtime.local",
        ), patch(
            "app.modules.voice.runtime_client.voice_runtime_client._post_json",
            new=AsyncMock(return_value={"runtime_status": "session_started", "runtime_session_id": "runtime-1"}),
        ) as post_mock:
            result = asyncio.run(
                voice_runtime_client.start_session(
                    session=_build_session(),
                    terminal=_build_terminal(),
                    sample_rate=16000,
                    codec="pcm_s16le",
                    channels=1,
                )
            )

        self.assertTrue(result.ok)
        self.assertEqual("runtime-1", result.runtime_session_id)
        post_mock.assert_awaited_once()
        payload = post_mock.await_args.args[1]
        self.assertEqual("conversation", payload["session_purpose"])
        self.assertIsNone(payload["enrollment_id"])

    def test_finalize_session_commits_http_runtime_and_parses_audio_artifact(self) -> None:
        with patch("app.modules.voice.runtime_client.settings.voice_runtime_enabled", True), patch(
            "app.modules.voice.runtime_client.settings.voice_runtime_base_url",
            "http://voice-runtime.local",
        ), patch(
            "app.modules.voice.runtime_client.voice_runtime_client._post_json",
            new=AsyncMock(
                return_value={
                    "ok": True,
                    "runtime_status": "transcribed",
                    "runtime_session_id": "runtime-1",
                    "transcript_text": "打开客厅灯",
                    "audio_artifact_id": "artifact-1",
                    "audio_file_path": "C:/tmp/artifact-1.wav",
                    "sample_rate": 16000,
                    "channels": 1,
                    "sample_width": 2,
                    "duration_ms": 1200,
                    "audio_sha256": "abc123",
                }
            ),
        ) as post_mock:
            result = asyncio.run(
                voice_runtime_client.finalize_session(
                    session=_build_session(runtime_session_id="runtime-1"),
                    terminal=_build_terminal(),
                    debug_transcript="打开客厅灯",
                )
            )

        self.assertTrue(result.ok)
        self.assertEqual("打开客厅灯", result.transcript_text)
        self.assertEqual("runtime-1", result.runtime_session_id)
        self.assertIsNotNone(result.audio_artifact)
        assert result.audio_artifact is not None
        self.assertEqual("artifact-1", result.audio_artifact.artifact_id)
        self.assertEqual("abc123", result.audio_artifact.sha256)
        post_mock.assert_awaited_once()
        self.assertIn("X-Debug-Transcript-B64", post_mock.await_args.kwargs["extra_headers"])


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
