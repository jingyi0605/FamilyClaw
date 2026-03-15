import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.modules.voice.conversation_bridge import VoiceConversationBridgeResult
from app.modules.voice.fast_action_service import VoiceRouteDecision
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.protocol import VoiceGatewayEvent
from app.modules.voice.registry import (
    voice_gateway_connection_registry,
    voice_session_registry,
    voice_terminal_registry,
)
from app.modules.voice.router import VoiceRoutingResult
from app.modules.voice.runtime_client import (
    VoiceRuntimeAppendResult,
    VoiceRuntimeStartResult,
    VoiceRuntimeTranscriptResult,
)


class VoicePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_gateway_connection_registry.reset()
        voice_terminal_registry.reset()
        voice_session_registry.reset()
        voice_terminal_registry.upsert_online(
            terminal_id="terminal-1",
            household_id="household-1",
            fingerprint="open_xiaoai:LX06:SN001",
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
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="device_action",
                        route_target="device-1:turn_on",
                        reason="命中设备",
                        response_text="好的，已处理设备：客厅灯。",
                    ),
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="妈妈",
                        primary_member_role="adult",
                        confidence=0.82,
                        inferred_room_id="room-1",
                        inferred_room_name="客厅",
                        reason="终端房间和活跃成员一致。",
                    ),
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
        self.assertEqual("member-1", session.requester_member_id)

    def test_session_start_initializes_runtime_state(self) -> None:
        voice_session_registry.reset()
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "session.start",
                "terminal_id": "terminal-1",
                "session_id": "session-runtime-1",
                "seq": 2,
                "payload": {
                    "household_id": "household-1",
                    "room_id": "room-1",
                    "sample_rate": 16000,
                    "codec": "pcm_s16le",
                    "channels": 1,
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_runtime_client.start_session",
            new=AsyncMock(
                return_value=VoiceRuntimeStartResult(
                    ok=True,
                    runtime_status="session_started",
                    runtime_session_id="runtime-session-1",
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["session.ready"], [item.type for item in commands])
        session = voice_session_registry.get("session-runtime-1")
        self.assertEqual("session_started", session.runtime_status)
        self.assertEqual("runtime-session-1", session.runtime_session_id)

    def test_audio_append_forwards_audio_to_runtime(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.append",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {
                    "chunk_base64": "YWJj",
                    "chunk_bytes": 3,
                    "codec": "pcm_s16le",
                    "sample_rate": 16000,
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_runtime_client.append_audio",
            new=AsyncMock(
                return_value=VoiceRuntimeAppendResult(
                    ok=True,
                    runtime_status="streaming",
                    runtime_session_id="runtime-session-1",
                )
            ),
        ) as append_mock:
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual([], commands)
        append_mock.assert_awaited_once()
        session = voice_session_registry.get("session-1")
        self.assertEqual("streaming", session.runtime_status)
        self.assertEqual("runtime-session-1", session.runtime_session_id)

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
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="conversation",
                        reason="回退慢路径",
                        handoff_to_conversation=True,
                    ),
                    identity=VoiceIdentityResolution(
                        status="anonymous",
                        reason="没有可信身份候选。",
                    ),
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_conversation_bridge.bridge",
            new=AsyncMock(
                return_value=VoiceConversationBridgeResult(
                    conversation_session_id="conversation-1",
                    response_text="明白了，我已经把这件事交给完整对话链路处理。",
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["play.start"], [item.type for item in commands])
        session = voice_session_registry.get("session-1")
        self.assertEqual("conversation", session.lane)
        self.assertEqual("conversation-1", session.conversation_session_id)

    def test_takeover_commit_keeps_existing_fast_action_pipeline(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {
                    "duration_ms": None,
                    "reason": "takeover_prefix_matched",
                    "debug_transcript": "打开客厅灯",
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="device_action",
                        route_target="device-1:turn_on",
                        reason="接管后继续命中快路径",
                        response_text="好的，已处理设备：客厅灯。",
                    ),
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="妈妈",
                        primary_member_role="adult",
                        confidence=0.82,
                        inferred_room_id="room-1",
                        inferred_room_name="客厅",
                        reason="终端房间和活跃成员一致。",
                    ),
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
        self.assertEqual("fast_action", session.lane)
        self.assertEqual("device_action", session.route_type)

    def test_takeover_commit_keeps_existing_conversation_pipeline(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {
                    "duration_ms": None,
                    "reason": "takeover_prefix_matched",
                    "debug_transcript": "提醒我明天买牛奶",
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="conversation",
                        reason="接管后继续回到慢路径",
                        handoff_to_conversation=True,
                    ),
                    identity=VoiceIdentityResolution(
                        status="anonymous",
                        reason="没有可信身份候选。",
                    ),
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_conversation_bridge.bridge",
            new=AsyncMock(
                return_value=VoiceConversationBridgeResult(
                    conversation_session_id="conversation-1",
                    response_text="明白了，我已经把这件事交给完整对话链路处理。",
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["play.start"], [item.type for item in commands])
        self.assertEqual("明白了，我已经把这件事交给完整对话链路处理。", commands[0].payload.text)
        session = voice_session_registry.get("session-1")
        self.assertEqual("conversation", session.lane)
        self.assertEqual("conversation-1", session.conversation_session_id)

    def test_audio_commit_returns_direct_prompt_for_blocked_fast_action(self) -> None:
        event = VoiceGatewayEvent.model_validate(
            {
                "type": "audio.commit",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 2,
                "payload": {"duration_ms": 900, "debug_transcript": "打开灯"},
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch(
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="conversation",
                        reason="设备歧义",
                        error_code="fast_action_device_ambiguous",
                        response_text="我找到了多个灯，你得把房间说清楚。",
                        handoff_to_conversation=False,
                    ),
                    identity=VoiceIdentityResolution(
                        status="degraded",
                        inferred_room_id="room-1",
                        inferred_room_name="客厅",
                        context_conflict=True,
                        reason="终端房间和候选成员冲突。",
                    ),
                )
            ),
        ):
            commands = asyncio.run(voice_pipeline_service.handle_inbound_event(_FakeDbSession(), event))

        self.assertEqual(["play.start"], [item.type for item in commands])
        self.assertEqual("我找到了多个灯，你得把房间说清楚。", commands[0].payload.text)
        session = voice_session_registry.get("session-1")
        self.assertEqual("fast_action_device_ambiguous", session.route_error_code)

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
