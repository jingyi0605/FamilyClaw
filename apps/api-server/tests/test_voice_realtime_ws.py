import asyncio
import unittest
from typing import Any, cast
from unittest.mock import patch

from fastapi import WebSocketDisconnect
from starlette.datastructures import Headers, QueryParams

from app.modules.voice.playback_service import voice_playback_service
from app.modules.voice.registry import (
    voice_gateway_connection_registry,
    voice_session_registry,
    voice_terminal_registry,
)
from app.modules.voice.realtime_service import voice_realtime_service


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


if __name__ == "__main__":
    unittest.main()
