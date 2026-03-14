import unittest

from open_xiaoai_gateway.protocol import GatewayCommand
from open_xiaoai_gateway.translator import TerminalBridgeContext, translate_audio_chunk, translate_command_to_terminal, translate_text_message


class TranslatorTests(unittest.TestCase):
    def test_terminal_online_filters_dangerous_capabilities(self) -> None:
        context = TerminalBridgeContext()
        events = translate_text_message(
            '{"event":"hello","data":{"terminal_id":"terminal-1","household_id":"household-1","capabilities":["audio_input","shell_exec","heartbeat"]}}',
            context,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("terminal.online", events[0].type)
        self.assertEqual(["audio_input", "heartbeat"], events[0].payload["capabilities"])

    def test_binary_audio_translates_to_audio_append(self) -> None:
        context = TerminalBridgeContext(terminal_id="terminal-1", household_id="household-1", active_session_id="session-1")
        events = translate_audio_chunk(b"abc", context)

        self.assertEqual(1, len(events))
        self.assertEqual("audio.append", events[0].type)
        self.assertEqual("session-1", events[0].session_id)
        self.assertEqual(3, events[0].payload["chunk_bytes"])

    def test_play_command_translates_to_terminal_message(self) -> None:
        message = translate_command_to_terminal(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 3,
                    "payload": {"playback_id": "playback-1", "mode": "tts_text", "text": "你好"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )
        )

        self.assertIn('"event": "play"', message)
        self.assertIn('"text": "你好"', message)


if __name__ == "__main__":
    unittest.main()
