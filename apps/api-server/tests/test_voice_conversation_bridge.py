import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.modules.conversation.schemas import ConversationMessageRead, ConversationSessionDetailRead
from app.modules.voice.conversation_bridge import voice_conversation_bridge
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceConversationBridgeTests(unittest.TestCase):
    def test_bridge_creates_session_and_runs_streaming_turn(self) -> None:
        session_detail = ConversationSessionDetailRead(
            id="conversation-1",
            household_id="household-1",
            requester_member_id="member-1",
            session_mode="family_chat",
            active_agent_id=None,
            active_agent_name=None,
            active_agent_type=None,
            title="璇煶浼氳瘽 瀹㈠巺灏忕埍",
            status="active",
            last_message_at="2026-03-15T00:00:00+08:00",
            created_at="2026-03-15T00:00:00+08:00",
            updated_at="2026-03-15T00:00:00+08:00",
            message_count=2,
            latest_message_preview="濂界殑锛屾垜鏉ュ府浣犺浣忚繖浠朵簨銆?",
            messages=[
                ConversationMessageRead(
                    id="message-user-1",
                    session_id="conversation-1",
                    request_id="request-1",
                    seq=1,
                    role="user",
                    message_type="text",
                    content="鏄庡ぉ鎻愰啋鎴戜拱鐗涘ザ",
                    status="completed",
                    created_at="2026-03-15T00:00:00+08:00",
                    updated_at="2026-03-15T00:00:00+08:00",
                ),
                ConversationMessageRead(
                    id="message-assistant-1",
                    session_id="conversation-1",
                    request_id="request-1",
                    seq=2,
                    role="assistant",
                    message_type="text",
                    content="濂界殑锛屾垜鏉ュ府浣犺浣忚繖浠朵簨銆?",
                    status="completed",
                    created_at="2026-03-15T00:00:01+08:00",
                    updated_at="2026-03-15T00:00:01+08:00",
                ),
            ],
            proposal_batches=[],
        )

        async def fake_run_conversation_realtime_turn(*args, **kwargs) -> None:
            _ = args
            connection_manager = kwargs["connection_manager"]
            await connection_manager.broadcast(
                household_id="household-1",
                session_id="conversation-1",
                event=SimpleNamespace(
                    type="agent.chunk",
                    payload=SimpleNamespace(text="濂界殑锛?"),
                ),
            )
            await connection_manager.broadcast(
                household_id="household-1",
                session_id="conversation-1",
                event=SimpleNamespace(
                    type="agent.chunk",
                    payload=SimpleNamespace(text="鎴戞潵甯綘璁颁綇杩欎欢浜嬨€?"),
                ),
            )
            await connection_manager.broadcast(
                household_id="household-1",
                session_id="conversation-1",
                event=SimpleNamespace(type="agent.done", payload=SimpleNamespace()),
            )

        with patch(
            "app.modules.voice.conversation_bridge.get_active_voice_terminal_conversation_binding",
            return_value=None,
        ), patch(
            "app.modules.voice.conversation_bridge.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(id="binding-1"),
        ) as bind_mock, patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-1"),
        ) as create_session_mock, patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=fake_run_conversation_realtime_turn),
        ), patch(
            "app.modules.voice.conversation_bridge.record_conversation_turn_source",
            return_value=SimpleNamespace(id="source-1"),
        ) as source_mock, patch(
            "app.modules.voice.conversation_bridge.get_conversation_session_detail",
            return_value=session_detail,
        ), patch(
            "app.modules.voice.playback_service.voice_playback_service.start_text_playback",
            new=AsyncMock(),
        ) as playback_mock:
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-1",
                        terminal_id="terminal-1",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-1",
                        household_id="household-1",
                        room_id="room-living",
                        name="瀹㈠巺灏忕埍",
                        status="online",
                    ),
                    transcript_text="鏄庡ぉ鎻愰啋鎴戜拱鐗涘ザ",
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="濡堝",
                        primary_member_role="adult",
                        confidence=0.85,
                        reason="涓婁笅鏂囧凡鏀舵暃銆?",
                    ),
                )
            )

        self.assertEqual("conversation-1", result.conversation_session_id)
        self.assertEqual("濂界殑锛屾垜鏉ュ府浣犺浣忚繖浠朵簨銆?", result.response_text)
        self.assertFalse(result.degraded)
        self.assertTrue(result.streaming_playback)
        create_session_mock.assert_called_once()
        bind_mock.assert_called_once()
        source_mock.assert_called_once()
        create_payload = create_session_mock.call_args.kwargs["payload"]
        self.assertEqual("member-1", create_payload.requester_member_id)
        self.assertEqual(2, playback_mock.await_count)
        first_call = playback_mock.await_args_list[0]
        second_call = playback_mock.await_args_list[1]
        self.assertEqual("voice-session-1", first_call.kwargs["session_id"])
        self.assertEqual("terminal-1", first_call.kwargs["terminal_id"])
        self.assertEqual("濂界殑锛?", first_call.kwargs["text"])
        self.assertEqual("voice-session-1", second_call.kwargs["session_id"])
        self.assertEqual("terminal-1", second_call.kwargs["terminal_id"])
        self.assertEqual("鎴戞潵甯綘璁颁綇杩欎欢浜嬨€?", second_call.kwargs["text"])

    def test_bridge_handles_new_command_before_realtime_turn(self) -> None:
        with patch(
            "app.modules.conversation.inbound_command_service.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-new"),
        ) as create_session_mock, patch(
            "app.modules.voice.service.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(
                conversation_session_id="conversation-new",
                created_at="2026-03-16T08:00:00+08:00",
                updated_at="2026-03-16T08:00:00+08:00",
            ),
        ) as bind_mock, patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=AssertionError("command should not enter realtime turn")),
        ):
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-command-1",
                        terminal_id="terminal-command-1",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-command-1",
                        household_id="household-1",
                        terminal_code="living-speaker",
                        name="客厅音箱",
                        status="online",
                    ),
                    transcript_text=" /new ",
                    identity=None,
                )
            )

        self.assertEqual("conversation-new", result.conversation_session_id)
        self.assertEqual("已开始新会话。", result.response_text)
        self.assertFalse(result.degraded)
        self.assertFalse(result.streaming_playback)
        create_session_mock.assert_called_once()
        bind_mock.assert_called_once()

    def test_bridge_handles_reset_command_before_realtime_turn(self) -> None:
        with patch(
            "app.modules.conversation.inbound_command_service.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-reset"),
        ) as create_session_mock, patch(
            "app.modules.voice.service.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(
                conversation_session_id="conversation-reset",
                created_at="2026-03-16T08:00:00+08:00",
                updated_at="2026-03-16T08:01:00+08:00",
            ),
        ) as bind_mock, patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=AssertionError("command should not enter realtime turn")),
        ):
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-command-2",
                        terminal_id="terminal-command-2",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-command-2",
                        household_id="household-1",
                        terminal_code="study-speaker",
                        name="书房音箱",
                        status="online",
                    ),
                    transcript_text="/reset",
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="Alice",
                        primary_member_role="adult",
                        confidence=0.92,
                        reason="matched",
                    ),
                )
            )

        self.assertEqual("conversation-reset", result.conversation_session_id)
        self.assertEqual("已重置当前上下文，并切换到新会话。", result.response_text)
        self.assertFalse(result.degraded)
        self.assertFalse(result.streaming_playback)
        create_session_mock.assert_called_once()
        bind_mock.assert_called_once()

    def test_bridge_returns_fallback_when_realtime_turn_crashes(self) -> None:
        with patch(
            "app.modules.voice.conversation_bridge.get_active_voice_terminal_conversation_binding",
            return_value=None,
        ), patch(
            "app.modules.voice.conversation_bridge.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(id="binding-2"),
        ), patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-2"),
        ), patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-2",
                        terminal_id="terminal-2",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-2",
                        household_id="household-1",
                        room_id="room-study",
                        name="涔︽埧灏忕埍",
                        status="online",
                    ),
                    transcript_text="璁蹭釜鏁呬簨",
                    identity=None,
                )
            )

        self.assertEqual("conversation_bridge_unavailable", result.error_code)
        self.assertTrue(result.degraded)
        self.assertFalse(result.streaming_playback)

    def test_bridge_records_turn_source_when_realtime_turn_crashes_after_turn_created(self) -> None:
        with patch(
            "app.modules.voice.conversation_bridge.get_active_voice_terminal_conversation_binding",
            return_value=None,
        ), patch(
            "app.modules.voice.conversation_bridge.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(id="binding-4"),
        ), patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-4"),
        ), patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ), patch(
            "app.modules.voice.conversation_bridge.conversation_turn_exists",
            return_value=True,
        ) as turn_exists_mock, patch(
            "app.modules.voice.conversation_bridge.record_conversation_turn_source",
            return_value=SimpleNamespace(id="source-4"),
        ) as source_mock:
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-4",
                        terminal_id="terminal-4",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-4",
                        household_id="household-1",
                        terminal_code="kitchen-speaker",
                        name="厨房音箱",
                        status="online",
                    ),
                    transcript_text="说一下今天的安排",
                    identity=None,
                )
            )

        self.assertEqual("conversation_bridge_unavailable", result.error_code)
        self.assertTrue(result.degraded)
        turn_exists_mock.assert_called_once()
        source_mock.assert_called_once()

    def test_bridge_reuses_persisted_binding_before_creating_new_session(self) -> None:
        session_detail = ConversationSessionDetailRead(
            id="conversation-bound",
            household_id="household-1",
            requester_member_id=None,
            session_mode="family_chat",
            active_agent_id=None,
            active_agent_name=None,
            active_agent_type=None,
            title="璇煶浼氳瘽 涔︽埧灏忕埍",
            status="active",
            last_message_at="2026-03-15T00:00:00+08:00",
            created_at="2026-03-15T00:00:00+08:00",
            updated_at="2026-03-15T00:00:00+08:00",
            message_count=1,
            latest_message_preview="鏀跺埌",
            messages=[
                ConversationMessageRead(
                    id="message-assistant-2",
                    session_id="conversation-bound",
                    request_id="request-2",
                    seq=1,
                    role="assistant",
                    message_type="text",
                    content="鏀跺埌",
                    status="completed",
                    created_at="2026-03-15T00:00:01+08:00",
                    updated_at="2026-03-15T00:00:01+08:00",
                ),
            ],
            proposal_batches=[],
        )

        with patch(
            "app.modules.voice.conversation_bridge.get_active_voice_terminal_conversation_binding",
            return_value=SimpleNamespace(conversation_session_id="conversation-bound"),
        ), patch(
            "app.modules.voice.conversation_bridge.bind_voice_terminal_conversation",
            return_value=SimpleNamespace(id="binding-3"),
        ), patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
        ) as create_session_mock, patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.modules.voice.conversation_bridge.record_conversation_turn_source",
            return_value=SimpleNamespace(id="source-2"),
        ), patch(
            "app.modules.voice.conversation_bridge.get_conversation_session_detail",
            return_value=session_detail,
        ):
            result = asyncio.run(
                voice_conversation_bridge.bridge(
                    _FakeDbSession(),
                    session=VoiceSessionState(
                        session_id="voice-session-3",
                        terminal_id="terminal-3",
                        household_id="household-1",
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-3",
                        household_id="household-1",
                        terminal_code="study-speaker",
                        name="涔︽埧灏忕埍",
                        status="online",
                    ),
                    transcript_text="缁х画鍒氭墠鐨勫璇?",
                    identity=None,
                )
            )

        create_session_mock.assert_not_called()
        self.assertEqual("conversation-bound", result.conversation_session_id)


class _FakeDbSession:
    def get(self, model, key):
        _ = model
        return SimpleNamespace(id=key, active_agent_id=None)

    def scalar(self, stmt):
        _ = stmt
        return None


if __name__ == "__main__":
    unittest.main()
