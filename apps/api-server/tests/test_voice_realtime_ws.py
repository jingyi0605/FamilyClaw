import asyncio
import time
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import WebSocketDisconnect
from starlette.datastructures import Headers, QueryParams

from app.core.blocking import BlockingCallPolicy, run_blocking
from app.modules.context.schemas import (
    ContextOverviewActiveMember,
    ContextOverviewDeviceSummary,
    ContextOverviewMemberState,
    ContextOverviewRead,
    ContextOverviewRoomOccupancy,
)
from app.modules.voice.fast_action_service import VoiceRouteDecision
from app.modules.voice.playback_service import voice_playback_service
from app.modules.voice.registry import (
    voice_gateway_connection_registry,
    voice_session_registry,
    voice_terminal_registry,
)
from app.modules.voice.realtime_service import voice_realtime_service
from app.modules.voice.runtime_client import VoiceRuntimeAudioArtifact, VoiceRuntimeStartResult, VoiceRuntimeTranscriptResult
from app.modules.voiceprint.service import VoiceprintIdentificationRead


class _FakeVoiceWebSocket:
    def __init__(
        self,
        *,
        household_id: str,
        terminal_id: str,
        fingerprint: str = "open_xiaoai:LX06:SN0001",
        token: str,
        inbound_messages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.query_params = QueryParams(
            {"household_id": household_id, "terminal_id": terminal_id, "fingerprint": fingerprint}
        )
        self.headers = Headers({"x-voice-gateway-token": token})
        self._inbound_messages = list(inbound_messages or [])
        self.accepted = False
        self.sent_messages: list[dict[str, Any]] = []
        self.close_code: int | None = None
        self.client = cast(Any, type("Client", (), {"host": "127.0.0.1", "port": 4399})())

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict[str, Any]:
        if self._inbound_messages:
            return self._inbound_messages.pop(0)
        raise WebSocketDisconnect(code=1000)

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_messages.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.close_code = code


class _FakeDbSession:
    def close(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class VoiceRealtimeWsTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_gateway_connection_registry.reset()
        voice_terminal_registry.reset()
        voice_session_registry.reset()
        voice_realtime_service.connection_manager.reset()

    def test_voice_gateway_rejects_invalid_token(self) -> None:
        websocket = _FakeVoiceWebSocket(
            household_id="household-1",
            terminal_id="terminal-1",
            token="bad-token",
        )

        with patch(
            "app.modules.voice.realtime_service.get_voice_terminal_binding",
            return_value=None,
        ):
            asyncio.run(voice_realtime_service.handle_gateway_websocket(cast(Any, websocket)))

        self.assertFalse(websocket.accepted)
        self.assertEqual(1008, websocket.close_code)

    def test_unclaimed_terminal_is_rejected_before_entering_voice_chain(self) -> None:
        websocket = _FakeVoiceWebSocket(
            household_id="household-1",
            terminal_id="terminal-1",
            token="dev-voice-gateway-token",
        )

        with patch(
            "app.modules.voice.realtime_service.get_voice_terminal_binding",
            return_value=None,
        ):
            asyncio.run(voice_realtime_service.handle_gateway_websocket(cast(Any, websocket)))

        self.assertFalse(websocket.accepted)
        self.assertEqual(1008, websocket.close_code)
        self.assertIsNone(voice_terminal_registry.get("terminal-1"))

    def test_voice_gateway_session_start_returns_session_ready(self) -> None:
        websocket = _FakeVoiceWebSocket(
            household_id="household-1",
            terminal_id="terminal-1",
            token="dev-voice-gateway-token",
            inbound_messages=[
                {
                    "type": "terminal.online",
                    "terminal_id": "terminal-1",
                    "seq": 1,
                    "payload": {
                        "household_id": "household-1",
                        "room_id": "room-1",
                        "terminal_code": "living-room-speaker",
                        "name": "客厅小爱",
                        "capabilities": ["audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat"],
                    },
                    "ts": "2026-03-15T00:00:00+08:00",
                },
                {
                    "type": "session.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 2,
                    "payload": {
                        "household_id": "household-1",
                        "room_id": "room-1",
                        "sample_rate": 16000,
                        "codec": "pcm_s16le",
                    },
                    "ts": "2026-03-15T00:00:01+08:00",
                },
            ],
        )

        with patch(
            "app.modules.voice.realtime_service.get_voice_terminal_binding",
            return_value=type(
                "Binding",
                (),
                {
                    "household_id": "household-1",
                    "terminal_id": "terminal-1",
                    "room_id": "room-1",
                    "terminal_name": "客厅小爱",
                },
            )(),
        ):
            asyncio.run(voice_realtime_service.handle_gateway_websocket(cast(Any, websocket)))

        self.assertTrue(websocket.accepted)
        self.assertEqual(["session.ready"], [item["type"] for item in websocket.sent_messages])
        session = voice_session_registry.get("session-1")
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual("terminal-1", session.terminal_id)

    def test_playback_service_sends_play_start_to_registered_terminal(self) -> None:
        websocket = _FakeVoiceWebSocket(
            household_id="household-1",
            terminal_id="terminal-1",
            token="dev-voice-gateway-token",
        )
        voice_realtime_service.connection_manager.register(terminal_id="terminal-1", websocket=cast(Any, websocket))
        voice_terminal_registry.upsert_online(
            terminal_id="terminal-1",
            household_id="household-1",
            fingerprint="open_xiaoai:LX06:SN0001",
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
            session_purpose="conversation",
            voiceprint_enrollment_id=None,
            inbound_seq=2,
        )

        asyncio.run(
            voice_playback_service.start_text_playback(
                session_id="session-1",
                terminal_id="terminal-1",
                text="好的，已经打开客厅灯。",
                playback_id="playback-1",
            )
        )

        self.assertEqual(["play.start"], [item["type"] for item in websocket.sent_messages])
        self.assertEqual("好的，已经打开客厅灯。", websocket.sent_messages[0]["payload"]["text"])

    def test_slow_voiceprint_identify_does_not_block_http_request(self) -> None:
        from app.main import app

        websocket = _FakeVoiceWebSocket(
            household_id="household-1",
            terminal_id="terminal-1",
            token="dev-voice-gateway-token",
            inbound_messages=[
                {
                    "type": "terminal.online",
                    "terminal_id": "terminal-1",
                    "seq": 1,
                    "payload": {
                        "household_id": "household-1",
                        "room_id": "room-1",
                        "terminal_code": "living-room-speaker",
                        "name": "客厅小爱",
                        "capabilities": ["audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat"],
                    },
                    "ts": "2026-03-15T00:00:00+08:00",
                },
                {
                    "type": "session.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-slow-1",
                    "seq": 2,
                    "payload": {
                        "household_id": "household-1",
                        "room_id": "room-1",
                        "sample_rate": 16000,
                        "codec": "pcm_s16le",
                    },
                    "ts": "2026-03-15T00:00:01+08:00",
                },
                {
                    "type": "audio.commit",
                    "terminal_id": "terminal-1",
                    "session_id": "session-slow-1",
                    "seq": 3,
                    "payload": {"duration_ms": 1200, "debug_transcript": "打开客厅灯"},
                    "ts": "2026-03-15T00:00:02+08:00",
                },
            ],
        )

        async def slow_voiceprint_identify(**kwargs):
            _ = kwargs
            await run_blocking(
                lambda: time.sleep(0.12),
                policy=BlockingCallPolicy(
                    label="tests.voiceprint.identify",
                    kind="cpu_bound",
                    timeout_seconds=1.0,
                ),
            )
            return VoiceprintIdentificationRead(
                provider="sherpa_onnx_wespeaker_resnet34",
                status="unavailable",
                threshold=0.75,
                reason="slow identify but degraded",
                candidate_count=0,
            )

        async def _run_scenario() -> tuple[float, float, int]:
            transport = httpx.ASGITransport(app=app)
            request_finished_at = 0.0
            websocket_finished_at = 0.0

            async def _run_websocket() -> None:
                nonlocal websocket_finished_at
                await voice_realtime_service.handle_gateway_websocket(cast(Any, websocket))
                websocket_finished_at = time.perf_counter()

            async def _run_http_request() -> int:
                nonlocal request_finished_at
                await asyncio.sleep(0.02)
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/")
                request_finished_at = time.perf_counter()
                return response.status_code

            websocket_task = asyncio.create_task(_run_websocket())
            status_code = await _run_http_request()
            await websocket_task
            return request_finished_at, websocket_finished_at, status_code

        with patch(
            "app.modules.voice.realtime_service.SessionLocal",
            side_effect=lambda: _FakeDbSession(),
        ), patch(
            "app.modules.voice.realtime_service.get_voice_terminal_binding",
            return_value=type(
                "Binding",
                (),
                {
                    "household_id": "household-1",
                    "terminal_id": "terminal-1",
                    "room_id": "room-1",
                    "terminal_name": "客厅小爱",
                },
            )(),
        ), patch(
            "app.modules.voice.pipeline.voice_runtime_client.start_session",
            new=AsyncMock(
                return_value=VoiceRuntimeStartResult(
                    ok=True,
                    runtime_status="session_started",
                    runtime_session_id="runtime-slow-1",
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_runtime_client.finalize_session",
            new=AsyncMock(
                return_value=VoiceRuntimeTranscriptResult(
                    ok=True,
                    transcript_text="打开客厅灯",
                    runtime_status="transcribed",
                    runtime_session_id="runtime-slow-1",
                    audio_artifact=VoiceRuntimeAudioArtifact(
                        artifact_id="artifact-slow-1",
                        file_path="C:/tmp/query.wav",
                        sample_rate=16000,
                        channels=1,
                        sample_width=2,
                        duration_ms=1200,
                        sha256="sha-slow-1",
                    ),
                )
            ),
        ), patch(
            "app.modules.voice.router.get_context_overview",
            return_value=_build_context_overview(),
        ), patch(
            "app.modules.voice.identity_service.async_identify_household_member_by_voiceprint",
            side_effect=slow_voiceprint_identify,
        ), patch(
            "app.modules.voice.router.voice_fast_action_service.resolve",
            new=AsyncMock(
                return_value=VoiceRouteDecision(
                    route_type="conversation",
                    reason="slow identify done",
                    response_text="好的，已处理设备：客厅灯。",
                    handoff_to_conversation=False,
                )
            ),
        ):
            request_finished_at, websocket_finished_at, status_code = asyncio.run(_run_scenario())

        self.assertEqual(200, status_code)
        self.assertLess(request_finished_at, websocket_finished_at)
        self.assertEqual(["session.ready", "play.start"], [item["type"] for item in websocket.sent_messages])


def _build_context_overview() -> ContextOverviewRead:
    return ContextOverviewRead(
        household_id="household-1",
        household_name="测试家庭",
        home_mode="home",
        privacy_mode="balanced",
        automation_level="assisted",
        platform_health_status="healthy",
        voice_fast_path_enabled=True,
        guest_mode_enabled=False,
        child_protection_enabled=False,
        elder_care_watch_enabled=False,
        quiet_hours_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        active_member=ContextOverviewActiveMember(
            member_id="member-1",
            name="妈妈",
            role="adult",
            presence="home",
            activity="active",
            current_room_id="room-1",
            current_room_name="客厅",
            confidence=95,
            source="snapshot",
        ),
        member_states=[
            ContextOverviewMemberState(
                member_id="member-1",
                name="妈妈",
                role="adult",
                presence="home",
                activity="active",
                current_room_id="room-1",
                current_room_name="客厅",
                confidence=95,
                last_seen_minutes=1,
                highlight="",
                source="snapshot",
                source_summary=None,
                updated_at="2026-03-15T00:00:00+08:00",
            )
        ],
        room_occupancy=[
            ContextOverviewRoomOccupancy(
                room_id="room-1",
                name="客厅",
                room_type="living_room",
                privacy_level="public",
                occupant_count=1,
                occupants=[],
                device_count=1,
                online_device_count=1,
                scene_preset="welcome",
                climate_policy="follow_room",
                privacy_guard_enabled=False,
                announcement_enabled=True,
            )
        ],
        device_summary=ContextOverviewDeviceSummary(
            total=1,
            active=1,
            offline=0,
            inactive=0,
            controllable=1,
            controllable_active=1,
            controllable_offline=0,
        ),
        insights=[],
        degraded=False,
        generated_at="2026-03-15T00:00:00+08:00",
    )


if __name__ == "__main__":
    unittest.main()
