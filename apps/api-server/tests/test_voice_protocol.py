import unittest

from pydantic import ValidationError

from app.modules.voice.protocol import (
    VOICE_TERMINAL_CAPABILITY_WHITELIST,
    VoiceCommandEvent,
    VoiceGatewayEvent,
    sanitize_terminal_capabilities,
)


class VoiceProtocolTests(unittest.TestCase):
    def test_capability_whitelist_filters_blacklist_and_unknown(self) -> None:
        capabilities = sanitize_terminal_capabilities(
            ["audio_input", "shell_exec", "heartbeat", "unknown_capability", "heartbeat"]
        )

        self.assertEqual(["audio_input", "heartbeat"], capabilities)
        self.assertIn("audio_output", VOICE_TERMINAL_CAPABILITY_WHITELIST)

    def test_playback_receipt_requires_session_id(self) -> None:
        with self.assertRaises(ValidationError):
            VoiceGatewayEvent.model_validate(
                {
                    "type": "playback.receipt",
                    "terminal_id": "terminal-1",
                    "seq": 1,
                    "payload": {"playback_id": "playback-1", "status": "completed"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )

    def test_play_start_requires_text_or_audio_by_mode(self) -> None:
        with self.assertRaises(ValidationError):
            VoiceCommandEvent.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 2,
                    "payload": {"playback_id": "playback-1", "mode": "tts_text"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )


if __name__ == "__main__":
    unittest.main()
