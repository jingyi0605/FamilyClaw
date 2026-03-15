import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.modules.conversation.schemas import (
    ConversationMessageRead,
    ConversationSessionDetailRead,
)
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
            title="语音会话 客厅小爱",
            status="active",
            last_message_at="2026-03-15T00:00:00+08:00",
            created_at="2026-03-15T00:00:00+08:00",
            updated_at="2026-03-15T00:00:00+08:00",
            message_count=2,
            latest_message_preview="好的，我来帮你记住这件事。",
            messages=[
                ConversationMessageRead(
                    id="message-user-1",
                    session_id="conversation-1",
                    request_id="request-1",
                    seq=1,
                    role="user",
                    message_type="text",
                    content="明天提醒我买牛奶",
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
                    content="好的，我来帮你记住这件事。",
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
                    payload=SimpleNamespace(text="好的，"),
                ),
            )
            await connection_manager.broadcast(
                household_id="household-1",
                session_id="conversation-1",
                event=SimpleNamespace(
                    type="agent.chunk",
                    payload=SimpleNamespace(text="我来帮你记住这件事。"),
                ),
            )
            await connection_manager.broadcast(
                household_id="household-1",
                session_id="conversation-1",
                event=SimpleNamespace(type="agent.done", payload=SimpleNamespace()),
            )

        with patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
            return_value=SimpleNamespace(id="conversation-1"),
        ) as create_session_mock, patch(
            "app.modules.voice.conversation_bridge.run_conversation_realtime_turn",
            new=AsyncMock(side_effect=fake_run_conversation_realtime_turn),
        ), patch(
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
                        name="客厅小爱",
                        status="online",
                    ),
                    transcript_text="明天提醒我买牛奶",
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="妈妈",
                        primary_member_role="adult",
                        confidence=0.85,
                        reason="上下文已收敛。",
                    ),
                )
            )

        self.assertEqual("conversation-1", result.conversation_session_id)
        self.assertEqual("好的，我来帮你记住这件事。", result.response_text)
        self.assertFalse(result.degraded)
        self.assertTrue(result.streaming_playback)
        create_session_mock.assert_called_once()
        playback_mock.assert_awaited_once_with(
            session_id="voice-session-1",
            terminal_id="terminal-1",
            text="好的，我来帮你记住这件事。",
        )

    def test_bridge_returns_fallback_when_realtime_turn_crashes(self) -> None:
        with patch(
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
                        name="书房小爱",
                        status="online",
                    ),
                    transcript_text="讲个故事",
                    identity=None,
                )
            )

        self.assertEqual("conversation_bridge_unavailable", result.error_code)
        self.assertTrue(result.degraded)
        self.assertFalse(result.streaming_playback)


class _FakeDbSession:
    pass


if __name__ == "__main__":
    unittest.main()
