import base64
import unittest

from fastapi.testclient import TestClient

from voice_runtime.app import app
from voice_runtime.service import session_store


class VoiceRuntimeAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._reset_store()

    def tearDown(self) -> None:
        self._reset_store()

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

        response = self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode("打开客厅灯".encode("utf-8")).decode("utf-8"),
                "chunk_bytes": 15,
                "codec": "pcm_s16le",
                "sample_rate": 16000,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["buffered_chunk_count"])
        self.assertEqual(15, response.json()["received_bytes"])

    def test_commit_returns_transcript_from_debug_header(self) -> None:
        self._start_session()
        self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "session-1",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode(b"\x01\x02\x03").decode("utf-8"),
                "chunk_bytes": 3,
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
                "X-Debug-Transcript-B64": base64.b64encode("关闭卧室灯".encode("utf-8")).decode("ascii"),
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("关闭卧室灯", response.json()["transcript_text"])

    def test_append_unknown_session_returns_not_found(self) -> None:
        response = self.client.post(
            "/v1/voice/sessions/append",
            json={
                "session_id": "missing-session",
                "terminal_id": "terminal-1",
                "chunk_base64": base64.b64encode(b"abc").decode("utf-8"),
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
        import asyncio

        asyncio.run(session_store.reset())


if __name__ == "__main__":
    unittest.main()
