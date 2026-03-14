import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.modules.voice.conversation_bridge import VoiceConversationBridgeResult
from app.modules.voice.fast_action_service import VoiceRouteDecision
from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.protocol import VoiceGatewayEvent
from app.modules.voice.registry import (
    voice_gateway_connection_registry,
    voice_session_registry,
    voice_terminal_registry,
)
from app.modules.voice.runtime_client import VoiceRuntimeTranscriptResult


class VoicePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_gateway_connection_registry.reset()
        voice_terminal_registry.reset()
        voice_session_registry.reset()
        voice_terminal_registry.upsert_online(
            terminal_id="terminal-1",
            household_id="household-1",
            room_id="room-1",
            terminal_code="living-room-speaker",
            name="客厅小爱",
            adapter_type="open_xiaoai",
            transport_type="gateway_ws",
            capabilities=["audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat"],
            adapter_meta={},
            connection_id="connection-1",
            remote_addr="127.0.0.1",
        )
        voice_session_registry.start_session(
            session_id="session-1",
            terminal_id="terminal-1",
            household_id="household-1",
            room_id="room-1",
            inbound_seq=1,
        )
        voice_session_registry.mark_ready(session_id="session-1")

    def test_audio_commit_routes_fast_action_and_returns_playback_command(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {"duration_ms": 1200, "debug_transcript": "打开客厅灯"},
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_fast_action_service.resolve",
            new=AsyncMock(
                return_value=VoiceRouteDecision(
                    route_type="device_action",
                    route_target="device-1:turn_on",
                    reason="命中设备",
                    response_text="好的，正在处理客厅灯。",
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_fast_action_service.execute",
            new=AsyncMock(
                return_value=VoiceRouteDecision(
                    route_type="device_action",
                    route_target="device-1:turn_on",
                    reason="执行完成",
                    response_text="好的，已处理设备：客厅灯。",
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["play.start"], [item.type for item in commands])
        self.assertEqual("好的，已处理设备：客厅灯。", commands[0].payload.text)
        session = voice_session_registry.get("session-1")
        self.assertEqual("打开客厅灯", session.transcript_text)
        self.assertEqual("fast_action", session.lane)
        self.assertEqual("device_action", session.route_type)

    def test_audio_commit_falls_back_to_conversation_bridge(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {"duration_ms": 900, "debug_transcript": "明天提醒我买牛奶"},
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_fast_action_service.resolve",
            new=AsyncMock(
                return_value=VoiceRouteDecision(
                    route_type="conversation",
                    reason="回退慢路径",
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_conversation_bridge.bridge",
            new=AsyncMock(
                return_value=VoiceConversationBridgeResult(
                    conversation_session_id="conversation-1",
                    response_text="已收到你的语音请求：明天提醒我买牛奶。慢路径桥接已建立，后续接入完整对话主链。",
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["play.start"], [item.type for item in commands])
        session = voice_session_registry.get("session-1")
        self.assertEqual("conversation", session.lane)
        self.assertEqual("conversation-1", session.conversation_session_id)

    def test_audio_commit_returns_agent_error_when_runtime_unavailable(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {"duration_ms": 900},
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_runtime_client.finalize_session",
            new=AsyncMock(
                return_value=VoiceRuntimeTranscriptResult(
                    ok=False,
                    error_code="voice_runtime_unavailable",
                    detail="voice-runtime 尚未接入。",
                    runtime_status="unavailable",
                    degraded=True,
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["agent.error"], [item.type for item in commands])
        self.assertEqual("voice_runtime_unavailable", commands[0].payload.error_code)
        session = voice_session_registry.get("session-1")
        self.assertEqual("failed", session.status)


class _FakeDbSession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
