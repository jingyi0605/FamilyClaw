import asyncio
import base64
import tempfile
import unittest
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from voice_runtime.app import app
from voice_runtime.service import session_store
from voice_runtime.settings import settings


def _build_pcm16_silence(*, frame_count: int) -> bytes:
    return b"\x00\x00" * frame_count


class VoiceRuntimeAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_artifacts_root = settings.artifacts_root
        settings.artifacts_root = Path(self._tempdir.name)
        self._reset_store()

    def tearDown(self) -> None:
        self._reset_store()
        settings.artifacts_root = self._previous_artifacts_root
        self._tempdir.cleanup()

    def test_start_session_returns_runtime_session_id(self) -> None:
        response = self.client.post(
            "/v1/voice/sessions/start",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "household_id": "household-1",
                "room_id": "room-1",
                "sample_rate": 16000,
                "codec": "pcm_s16le",
                "channels": 1,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("session-1", response.json()["runtime_session_id"])

    def test_append_audio_updates_buffer_stats(self) -> None:
        self._start_session()
        chunk = _build_pcm16_silence(frame_count=160)

        response = self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode(chunk).decode("ascii"),
                "chunk_bytes": len(chunk),
                "codec": "pcm_s16le",
                "sample_rate": 16000,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["buffered_chunk_count"])
        self.assertEqual(len(chunk), response.json()["received_bytes"])

    def test_commit_returns_audio_artifact_metadata_and_persisted_wav(self) -> None:
        self._start_session()
        chunk = _build_pcm16_silence(frame_count=1600)
        self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode(chunk).decode("ascii"),
                "chunk_bytes": len(chunk),
                "codec": "pcm_s16le",
                "sample_rate": 16000,
            },
        )

        response = self.client.post(
            "/v1/voice/sessions/commit",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "household_id": "household-1",
            },
            headers={
                "X-Debug-Transcript-B64": base64.b64encode("我是妈妈".encode("utf-8")).decode("ascii"),
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("我是妈妈", payload["transcript_text"])
        self.assertIsNotNone(payload["audio_artifact_id"])
        self.assertIsNotNone(payload["audio_file_path"])
        self.assertEqual(16000, payload["sample_rate"])
        self.assertEqual(1, payload["channels"])
        self.assertEqual(2, payload["sample_width"])
        self.assertGreater(payload["duration_ms"], 0)
        self.assertFalse(payload["degraded"])

        artifact_path = Path(payload["audio_file_path"])
        self.assertTrue(artifact_path.exists())
        with wave.open(str(artifact_path), "rb") as wav_file:
            self.assertEqual(1, wav_file.getnchannels())
            self.assertEqual(2, wav_file.getsampwidth())
            self.assertEqual(16000, wav_file.getframerate())
            self.assertGreater(wav_file.getnframes(), 0)

    def test_append_unknown_session_returns_not_found(self) -> None:
        response = self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "missing-session",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode(b"abc").decode("ascii"),
                "chunk_bytes": 3,
                "codec": "pcm_s16le",
                "sample_rate": 16000,
            },
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("voice_session_not_found", response.json()["detail"]["error_code"])

    def _start_session(self) -> None:
        response = self.client.post(
            "/v1/voice/sessions/start",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "household_id": "household-1",
                "room_id": "room-1",
                "sample_rate": 16000,
                "codec": "pcm_s16le",
                "channels": 1,
            },
        )
        self.assertEqual(200, response.status_code)

    def _reset_store(self) -> None:
        asyncio.run(session_store.reset())


if __name__ == "__main__":
    unittest.main()
