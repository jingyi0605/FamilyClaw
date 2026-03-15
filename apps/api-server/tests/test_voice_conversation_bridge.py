import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.modules.conversation.schemas import (
    ConversationMessageRead,
    ConversationSessionDetailRead,
    ConversationSessionRead,
    ConversationTurnRead,
)
from app.modules.voice.conversation_bridge import voice_conversation_bridge
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceConversationBridgeTests(unittest.TestCase):
    def test_bridge_creates_session_and_runs_real_turn_shape(self) -> None:
        conversation_session = ConversationSessionDetailRead(
            **ConversationSessionRead(
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
                message_count=0,
                latest_message_preview=None,
            ).model_dump(mode="json"),
            messages=[],
            proposal_batches=[],
        )
        turn = ConversationTurnRead(
            request_id="request-1",
            session_id="conversation-1",
            user_message_id="message-user-1",
            assistant_message_id="message-assistant-1",
            outcome="completed",
            error_message=None,
            session=conversation_session.model_copy(
                update={
                    "messages": [
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
                    ]
                }
            ),
        )

        with patch(
            "app.modules.voice.conversation_bridge.create_conversation_session",
            return_value=conversation_session,
        ) as create_session_mock, patch(
            "app.modules.voice.conversation_bridge.acreate_conversation_turn",
            new=AsyncMock(return_value=turn),
        ) as create_turn_mock:
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
        create_session_mock.assert_called_once()
        create_turn_mock.assert_awaited_once()


class _FakeDbSession:
    pass


if __name__ == "__main__":
    unittest.main()
