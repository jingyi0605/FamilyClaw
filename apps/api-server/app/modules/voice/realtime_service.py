from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.protocol import VoiceCommandEvent, VoiceGatewayEvent
from app.modules.voice.registry import voice_gateway_connection_registry, voice_terminal_registry

logger = logging.getLogger(__name__)


class VoiceGatewayConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    def reset(self) -> None:
        self._connections.clear()

    def register(self, *, terminal_id: str, websocket: WebSocket) -> None:
        self._connections[terminal_id] = websocket

    def unregister(self, *, terminal_id: str, websocket: WebSocket) -> None:
        current = self._connections.get(terminal_id)
        if current is websocket:
            self._connections.pop(terminal_id, None)

    def get(self, terminal_id: str) -> WebSocket | None:
        return self._connections.get(terminal_id)

    async def send_event(self, *, terminal_id: str, event: VoiceCommandEvent) -> None:
        websocket = self._connections.get(terminal_id)
        if websocket is None:
            raise LookupError(f"terminal {terminal_id} not connected")
        await websocket.send_json(event.model_dump(mode="json"))


class VoiceRealtimeService:
    def __init__(self) -> None:
        self.connection_manager = VoiceGatewayConnectionManager()

    async def handle_gateway_websocket(self, websocket: WebSocket) -> None:
        household_id = (websocket.query_params.get("household_id") or "").strip()
        terminal_id = (websocket.query_params.get("terminal_id") or "").strip()
        gateway_token = (websocket.headers.get("x-voice-gateway-token") or websocket.query_params.get("gateway_token") or "").strip()
        remote_addr = websocket.client.host if websocket.client else None
        accepted = False
        db = SessionLocal()

        if not household_id or not terminal_id or gateway_token != settings.voice_gateway_token:
            db.close()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        accepted = True

        connection = voice_gateway_connection_registry.register(
            household_id=household_id,
            terminal_id=terminal_id,
            remote_addr=remote_addr,
        )
        self.connection_manager.register(terminal_id=terminal_id, websocket=websocket)
        voice_terminal_registry.bind_connection(
            terminal_id=terminal_id,
            household_id=household_id,
            connection_id=connection.connection_id,
            remote_addr=remote_addr,
        )

        try:
            while True:
                event = VoiceGatewayEvent.model_validate(await websocket.receive_json())
                if event.terminal_id != terminal_id:
                    await self.send_command(
                        VoiceCommandEvent.model_validate(
                            {
                                "type": "agent.error",
                                "terminal_id": terminal_id,
                                "session_id": event.session_id,
                                "seq": 0,
                                "payload": {
                                    "detail": "terminal_id 不匹配",
                                    "error_code": "invalid_event_payload",
                                    "retryable": False,
                                },
                                "ts": event.ts,
                            }
                        )
                    )
                    continue
                outbound_events = await voice_pipeline_service.handle_inbound_event(db, event)
                for outbound_event in outbound_events:
                    await self.send_command(outbound_event)
        except WebSocketDisconnect:
            return
        except Exception:
            logger.exception("语音网关 WebSocket 异常 household_id=%s terminal_id=%s", household_id, terminal_id)
            if accepted:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        finally:
            voice_pipeline_service.handle_terminal_disconnect(terminal_id=terminal_id)
            voice_gateway_connection_registry.unregister(terminal_id=terminal_id)
            self.connection_manager.unregister(terminal_id=terminal_id, websocket=websocket)
            db.close()

    async def send_command(self, event: VoiceCommandEvent) -> None:
        await self.connection_manager.send_event(terminal_id=event.terminal_id, event=event)


voice_realtime_service = VoiceRealtimeService()
