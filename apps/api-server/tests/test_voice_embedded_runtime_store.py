import base64
import unittest

from app.modules.voice.embedded_runtime_store import embedded_audio_session_store


class EmbeddedAudioSessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        embedded_audio_session_store.reset()

    def tearDown(self) -> None:
        embedded_audio_session_store.reset()

    def test_store_buffers_audio_and_discards_terminal_sessions(self) -> None:
        embedded_audio_session_store.start_session(
            session_id="session-1",
            terminal_id="terminal-1",
            household_id="household-1",
            room_id="room-1",
            sample_rate=16000,
            codec="pcm_s16le",
            channels=1,
            session_purpose="conversation",
            enrollment_id=None,
        )

        appended = embedded_audio_session_store.append_audio(
            session_id="session-1",
            terminal_id="terminal-1",
            chunk_base64=base64.b64encode(b"abc").decode("ascii"),
            chunk_bytes=3,
        )

        self.assertIsNotNone(appended)
        assert appended is not None
        self.assertEqual(1, appended.chunk_count)
        self.assertEqual(3, appended.received_bytes)
        self.assertEqual(b"abc", bytes(appended.audio_bytes))

        removed = embedded_audio_session_store.discard_terminal_sessions(terminal_id="terminal-1")
        self.assertEqual(1, removed)
        self.assertIsNone(embedded_audio_session_store.get("session-1"))

    def test_pop_session_returns_snapshot_and_clears_store(self) -> None:
        embedded_audio_session_store.start_session(
            session_id="session-2",
            terminal_id="terminal-2",
            household_id="household-2",
            room_id="room-2",
            sample_rate=16000,
            codec="pcm_s16le",
            channels=1,
            session_purpose="voiceprint_enrollment",
            enrollment_id="enrollment-1",
        )
        embedded_audio_session_store.append_audio(
            session_id="session-2",
            terminal_id="terminal-2",
            chunk_base64=base64.b64encode(b"\x00\x00\x01\x00").decode("ascii"),
            chunk_bytes=4,
        )

        session = embedded_audio_session_store.pop_session(
            session_id="session-2",
            terminal_id="terminal-2",
            household_id="household-2",
        )

        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual("voiceprint_enrollment", session.session_purpose)
        self.assertEqual("enrollment-1", session.enrollment_id)
        self.assertEqual(b"\x00\x00\x01\x00", bytes(session.audio_bytes))
        self.assertIsNone(embedded_audio_session_store.get("session-2"))


if __name__ == "__main__":
    unittest.main()
