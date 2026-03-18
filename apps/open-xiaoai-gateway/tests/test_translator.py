import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from open_xiaoai_gateway.protocol import GatewayCommand
from open_xiaoai_gateway.translator import (
    PendingVoiceprintEnrollment,
    TerminalBinaryStream,
    TerminalBridgeContext,
    TerminalRpcRequest,
    VoiceTerminalBinding,
    build_discovery_info,
    build_discovery_report_payload,
    build_open_xiaoai_fingerprint,
    build_terminal_online_event,
    parse_open_xiaoai_text_message,
    translate_audio_chunk,
    translate_command_to_terminal,
    translate_text_message,
    translate_text_message_result,
)


class TranslatorTests(unittest.TestCase):
    def test_terminal_online_uses_configured_identity_and_capabilities(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
            )
        )

        event = build_terminal_online_event(context)

        self.assertEqual("terminal.online", event.type)
        self.assertEqual("household-1", event.payload["household_id"])
        self.assertIn("audio_input", event.payload["capabilities"])
        self.assertEqual("open_xiaoai_app_message", event.payload["adapter_meta"]["protocol"])
        self.assertEqual("open_xiaoai:LX06:SN001", event.payload["adapter_meta"]["fingerprint"])

    def test_build_discovery_info_generates_stable_fingerprint(self) -> None:
        discovery = build_discovery_info(
            model="LX06",
            sn="SN001",
            runtime_version="1.0.0",
        )

        self.assertEqual("LX06", discovery.model)
        self.assertEqual("SN001", discovery.sn)
        self.assertEqual("1.0.0", discovery.runtime_version)
        self.assertEqual(build_open_xiaoai_fingerprint(model="LX06", sn="SN001"), discovery.fingerprint)

    def test_build_discovery_report_payload_contains_required_fields(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )

        payload = build_discovery_report_payload(context, remote_addr="192.168.1.22")

        self.assertNotIn("adapter_type", payload)
        self.assertEqual("open_xiaoai:LX06:SN001", payload["fingerprint"])
        self.assertEqual("LX06", payload["model"])
        self.assertEqual("SN001", payload["sn"])
        self.assertEqual("1.0.0", payload["runtime_version"])
        self.assertEqual("online", payload["connection_status"])

    def test_kws_keyword_starts_voice_session(self) -> None:
        context = self._build_claimed_context(voice_auto_takeover_enabled=True)

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

    def test_always_familyclaw_kws_emits_takeover_pause_when_enabled(self) -> None:
        with self._patch_invocation_settings(
            invocation_mode="always_familyclaw",
            takeover_prefixes=["帮我"],
            strip_takeover_prefix=True,
            pause_on_takeover=True,
        ):
            context = self._build_claimed_context(voice_auto_takeover_enabled=True)
            result = translate_text_message_result(
                json.dumps(
                    {
                        "Event": {
                            "id": "event-kws-1",
                            "event": "kws",
                            "data": {"Keyword": "小爱同学"},
                        }
                    },
                    ensure_ascii=False,
                ),
                context,
            )

        self.assertEqual(["session.start"], [item.type for item in result.events])
        self.assertEqual(1, len(result.terminal_messages))
        self.assertIsInstance(result.terminal_messages[0], TerminalRpcRequest)
        assert isinstance(result.terminal_messages[0], TerminalRpcRequest)
        self.assertEqual("run_shell", result.terminal_messages[0].command)
        self.assertIn("mico_aivs_lab restart", str(result.terminal_messages[0].payload))

    def test_instruction_final_result_commits_with_debug_transcript(self) -> None:
        context = self._build_claimed_context(voice_auto_takeover_enabled=True)
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

    def test_regular_conversation_keeps_conversation_session_purpose(self) -> None:
        context = self._build_claimed_context(voice_auto_takeover_enabled=True)
        result = translate_text_message_result(
            self._build_recognize_result_frame(text="打开客厅灯"),
            context,
        )

        self.assertEqual(["session.start", "audio.commit"], [item.type for item in result.events])
        self.assertEqual("conversation", result.events[0].payload["session_purpose"])
        self.assertIsNone(result.events[0].payload.get("enrollment_id"))
        self.assertEqual("conversation", result.events[1].payload["session_purpose"])
        self.assertIsNone(result.events[1].payload.get("enrollment_id"))

    def test_native_first_without_matched_prefix_does_not_enter_formal_voice_session(self) -> None:
        with self._patch_invocation_settings(
            invocation_mode="native_first",
            takeover_prefixes=["帮我"],
            strip_takeover_prefix=True,
            pause_on_takeover=True,
        ):
            context = self._build_claimed_context(voice_takeover_prefixes=("帮我",))

            kws_result = translate_text_message_result(
                json.dumps(
                    {
                        "Event": {
                            "id": "event-kws-1",
                            "event": "kws",
                            "data": {"Keyword": "小爱同学"},
                        }
                    },
                    ensure_ascii=False,
                ),
                context,
            )
            final_result = translate_text_message_result(
                self._build_recognize_result_frame(text="打开客厅灯"),
                context,
            )

        self.assertEqual([], kws_result.events)
        self.assertEqual([], final_result.events)
        self.assertEqual([], final_result.terminal_messages)
        self.assertIsNone(context.active_session_id)
        self.assertEqual("native_passthrough", context.last_invocation_decision)
        self.assertEqual("takeover_prefix_not_matched", context.last_passthrough_reason)

    def test_native_first_with_matched_prefix_emits_takeover_events(self) -> None:
        with self._patch_invocation_settings(
            invocation_mode="native_first",
            takeover_prefixes=["帮我"],
            strip_takeover_prefix=True,
            pause_on_takeover=True,
        ):
            context = self._build_claimed_context(voice_takeover_prefixes=("帮我",))
            result = translate_text_message_result(
                self._build_recognize_result_frame(text="帮我 打开客厅灯"),
                context,
            )

        self.assertEqual(["session.start", "audio.commit"], [item.type for item in result.events])
        self.assertEqual("打开客厅灯", result.events[1].payload["debug_transcript"])
        self.assertEqual(1, len(result.terminal_messages))
        self.assertIsInstance(result.terminal_messages[0], TerminalRpcRequest)
        assert isinstance(result.terminal_messages[0], TerminalRpcRequest)
        self.assertEqual("run_shell", result.terminal_messages[0].command)
        self.assertIn("mico_aivs_lab restart", str(result.terminal_messages[0].payload))
        self.assertIsNone(context.active_session_id)

    def test_native_first_can_keep_prefix_when_strip_disabled(self) -> None:
        with self._patch_invocation_settings(
            invocation_mode="native_first",
            takeover_prefixes=["请"],
            strip_takeover_prefix=False,
            pause_on_takeover=False,
        ):
            context = self._build_claimed_context()
            result = translate_text_message_result(
                self._build_recognize_result_frame(text="请打开客厅灯"),
                context,
            )

        self.assertEqual(["session.start", "audio.commit"], [item.type for item in result.events])
        self.assertEqual("请打开客厅灯", result.events[1].payload["debug_transcript"])
        self.assertEqual([], result.terminal_messages)

    def test_binding_settings_override_global_invocation_strategy(self) -> None:
        with self._patch_invocation_settings(
            invocation_mode="always_familyclaw",
            takeover_prefixes=["帮我"],
            strip_takeover_prefix=True,
            pause_on_takeover=False,
        ):
            context = TerminalBridgeContext()
            context.apply_discovery(
                build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
            )
            context.apply_binding(
                VoiceTerminalBinding(
                    household_id="household-1",
                    terminal_id="terminal-1",
                    room_id="room-1",
                    terminal_name="客厅小爱",
                    voice_auto_takeover_enabled=False,
                    voice_takeover_prefixes=("请",),
                )
            )
            result = translate_text_message_result(
                self._build_recognize_result_frame(text="帮我打开客厅灯"),
                context,
            )

        self.assertEqual("native_first", context.invocation_mode)
        self.assertEqual(("请",), context.takeover_prefixes)
        self.assertEqual([], result.events)
        self.assertEqual("takeover_prefix_not_matched", context.last_passthrough_reason)

    def test_pending_voiceprint_enrollment_marks_session_and_commit_as_enrollment(self) -> None:
        context = self._build_claimed_context(
            pending_voiceprint_enrollment=PendingVoiceprintEnrollment(
                enrollment_id="enrollment-1",
                target_member_id="member-1",
                expected_phrase="我是妈妈",
                sample_goal=3,
                sample_count=1,
                expires_at="2026-03-16T12:00:00+08:00",
            )
        )

        result = translate_text_message_result(
            self._build_recognize_result_frame(text="我是妈妈"),
            context,
        )

        self.assertEqual(["session.start", "audio.commit"], [item.type for item in result.events])
        self.assertEqual("voiceprint_enrollment", result.events[0].payload["session_purpose"])
        self.assertEqual("enrollment-1", result.events[0].payload["enrollment_id"])
        self.assertEqual("voiceprint_enrollment", result.events[1].payload["session_purpose"])
        self.assertEqual("enrollment-1", result.events[1].payload["enrollment_id"])
        self.assertEqual("我是妈妈", result.events[1].payload["debug_transcript"])
        self.assertIsNone(context.active_session_id)

    def test_binary_record_stream_translates_to_audio_append(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
            )
        )
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

    def test_unclaimed_terminal_does_not_enter_formal_voice_session(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )

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

        self.assertEqual([], events)
        self.assertIsNone(context.active_session_id)

    def test_play_command_translates_to_controlled_run_shell_request(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
            )
        )

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
        self.assertFalse(str(messages[0].payload).strip().endswith("&"))
        self.assertEqual("playback-1", context.active_playback_id)

    def test_audio_bytes_command_translates_to_rpc_then_stream(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
            )
        )

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

    def test_turn_on_command_translates_to_terminal_resume_request(self) -> None:
        context = self._build_claimed_context()

        messages = translate_command_to_terminal(
            GatewayCommand.model_validate(
                {
                    "type": "speaker.turn_on",
                    "terminal_id": "terminal-1",
                    "session_id": "device-control-terminal-1",
                    "seq": 4,
                    "payload": {"reason": "device_control"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            ),
            context,
        )

        self.assertEqual(1, len(messages))
        self.assertIsInstance(messages[0], TerminalRpcRequest)
        assert isinstance(messages[0], TerminalRpcRequest)
        self.assertEqual("run_shell", messages[0].command)
        self.assertEqual("mphelper play", messages[0].payload)

    def test_set_volume_command_translates_to_terminal_volume_request(self) -> None:
        context = self._build_claimed_context()

        messages = translate_command_to_terminal(
            GatewayCommand.model_validate(
                {
                    "type": "speaker.set_volume",
                    "terminal_id": "terminal-1",
                    "session_id": "device-control-terminal-1",
                    "seq": 5,
                    "payload": {"volume_pct": 35, "reason": "device_control"},
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            ),
            context,
        )

        self.assertEqual(1, len(messages))
        self.assertIsInstance(messages[0], TerminalRpcRequest)
        assert isinstance(messages[0], TerminalRpcRequest)
        self.assertEqual("run_shell", messages[0].command)
        self.assertEqual("mphelper volume_set 35", messages[0].payload)

    def test_playing_idle_marks_playback_completed(self) -> None:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
            )
        )
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

    def _build_claimed_context(
        self,
        *,
        voice_auto_takeover_enabled: bool = False,
        voice_takeover_prefixes: tuple[str, ...] = ("请",),
        pending_voiceprint_enrollment: PendingVoiceprintEnrollment | None = None,
    ) -> TerminalBridgeContext:
        context = TerminalBridgeContext()
        context.apply_discovery(
            build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0")
        )
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
                voice_auto_takeover_enabled=voice_auto_takeover_enabled,
                voice_takeover_prefixes=voice_takeover_prefixes,
                pending_voiceprint_enrollment=pending_voiceprint_enrollment,
            )
        )
        return context

    def _build_recognize_result_frame(self, *, text: str, is_final: bool = True, is_vad_begin: bool = False) -> str:
        return json.dumps(
            {
                "Event": {
                    "id": "event-instruction-1",
                    "event": "instruction",
                    "data": {
                        "NewLine": json.dumps(
                            {
                                "header": {
                                    "namespace": "SpeechRecognizer",
                                    "name": "RecognizeResult",
                                },
                                "payload": {
                                    "is_final": is_final,
                                    "is_vad_begin": is_vad_begin,
                                    "results": [{"text": text}],
                                },
                            },
                            ensure_ascii=False,
                        )
                    },
                }
            },
            ensure_ascii=False,
        )

    def _patch_invocation_settings(
        self,
        *,
        invocation_mode: str,
        takeover_prefixes: list[str],
        strip_takeover_prefix: bool,
        pause_on_takeover: bool,
    ):
        stack = ExitStack()
        stack.enter_context(patch("open_xiaoai_gateway.translator.settings.invocation_mode", invocation_mode))
        stack.enter_context(patch("open_xiaoai_gateway.translator.settings.takeover_prefixes", list(takeover_prefixes)))
        stack.enter_context(patch("open_xiaoai_gateway.translator.settings.strip_takeover_prefix", strip_takeover_prefix))
        stack.enter_context(patch("open_xiaoai_gateway.translator.settings.pause_on_takeover", pause_on_takeover))
        return stack


if __name__ == "__main__":
    unittest.main()
