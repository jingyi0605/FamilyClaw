import json
import unittest

from open_xiaoai_gateway.protocol import GatewayCommand
from open_xiaoai_gateway.translator import (
    TerminalBinaryStream,
    TerminalBridgeContext,
    TerminalRpcRequest,
    build_terminal_online_event,
    parse_open_xiaoai_text_message,
    translate_audio_chunk,
    translate_command_to_terminal,
    translate_text_message,
)


class TranslatorTests(unittest.TestCase):
    def test_terminal_online_uses_configured_identity_and_capabilities(self) -> None:
        context = TerminalBridgeContext(
            household_id="household-1",
            terminal_id="terminal-1",
            room_id="room-1",
            terminal_code="living-room-speaker",
            name="客厅小爱",
        )

        event = build_terminal_online_event(context)

        self.assertEqual("terminal.online", event.type)
        self.assertEqual("household-1", event.payload["household_id"])
        self.assertIn("audio_input", event.payload["capabilities"])
        self.assertEqual("open_xiaoai_app_message", event.payload["adapter_meta"]["protocol"])

    def test_kws_keyword_starts_voice_session(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1", room_id="room-1")

        events = translate_text_message(
            json.dumps(
                {
                    "Event": {
                        "id": "event-1",
                        "event": "kws",
                        "data": {"Keyword": "小爱同学"},
                    }
                },
                ensure_ascii=False,
            ),
            context,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("session.start", events[0].type)
        self.assertTrue(events[0].session_id)
        self.assertEqual(events[0].session_id, context.active_session_id)

    def test_instruction_final_result_commits_with_debug_transcript(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1", room_id="room-1")
        context.active_session_id = "session-1"

        events = translate_text_message(
            json.dumps(
                {
                    "Event": {
                        "id": "event-2",
                        "event": "instruction",
                        "data": {
                            "NewLine": json.dumps(
                                {
                                    "header": {
                                        "namespace": "SpeechRecognizer",
                                        "name": "RecognizeResult",
                                    },
                                    "payload": {
                                        "is_final": True,
                                        "is_vad_begin": False,
                                        "results": [{"text": "打开客厅灯"}],
                                    },
                                },
                                ensure_ascii=False,
                            )
                        },
                    }
                },
                ensure_ascii=False,
            ),
            context,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("audio.commit", events[0].type)
        self.assertEqual("打开客厅灯", events[0].payload["debug_transcript"])
        self.assertIsNone(context.active_session_id)

    def test_binary_record_stream_translates_to_audio_append(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1")
        context.active_session_id = "session-1"

        events = translate_audio_chunk(
            json.dumps(
                {
                    "id": "stream-1",
                    "tag": "record",
                    "bytes": [97, 98, 99],
                }
            ).encode("utf-8"),
            context,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("audio.append", events[0].type)
        self.assertEqual("session-1", events[0].session_id)
        self.assertEqual(3, events[0].payload["chunk_bytes"])

    def test_play_command_translates_to_controlled_run_shell_request(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1")

        messages = translate_command_to_terminal(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 3,
                    "payload": {"playback_id": "playback-1", "mode": "tts_text", "text": "你好"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            ),
            context,
        )

        self.assertEqual(1, len(messages))
        self.assertIsInstance(messages[0], TerminalRpcRequest)
        assert isinstance(messages[0], TerminalRpcRequest)
        self.assertEqual("run_shell", messages[0].command)
        self.assertIn("tts_play.sh", str(messages[0].payload))
        self.assertEqual("playback-1", context.active_playback_id)

    def test_audio_bytes_command_translates_to_rpc_then_stream(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1")

        messages = translate_command_to_terminal(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 3,
                    "payload": {"playback_id": "playback-1", "mode": "audio_bytes", "audio_base64": "YWJj"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            ),
            context,
        )

        self.assertEqual(2, len(messages))
        self.assertIsInstance(messages[0], TerminalRpcRequest)
        self.assertIsInstance(messages[1], TerminalBinaryStream)
        assert isinstance(messages[1], TerminalBinaryStream)
        self.assertEqual(b"abc", messages[1].raw_bytes)

    def test_playing_idle_marks_playback_completed(self) -> None:
        context = TerminalBridgeContext(household_id="household-1", terminal_id="terminal-1")
        context.active_playback_id = "playback-1"
        context.active_playback_session_id = "session-1"
        context.last_playing_state = "playing"

        events = translate_text_message(
            json.dumps(
                {
                    "Event": {
                        "id": "event-3",
                        "event": "playing",
                        "data": "Idle",
                    }
                }
            ),
            context,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("playback.receipt", events[0].type)
        self.assertEqual("completed", events[0].payload["status"])
        self.assertIsNone(context.active_playback_id)

    def test_parse_open_xiaoai_text_message_keeps_response_variant(self) -> None:
        frame = parse_open_xiaoai_text_message(
            json.dumps(
                {
                    "Response": {
                        "id": "req-1",
                        "code": 0,
                        "msg": "success",
                    }
                }
            )
        )

        self.assertEqual("Response", frame.variant)
        self.assertEqual("req-1", frame.Response.id)


if __name__ == "__main__":
    unittest.main()
