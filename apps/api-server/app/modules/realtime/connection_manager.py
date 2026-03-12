from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from fastapi import WebSocket

from app.modules.realtime.schemas import BootstrapRealtimeEvent


class RealtimeConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[tuple[str, str], set[WebSocket]] = defaultdict(set)

    def register(self, *, household_id: str, session_id: str, websocket: WebSocket) -> None:
        self._connections[(household_id, session_id)].add(websocket)

    def unregister(self, *, household_id: str, session_id: str, websocket: WebSocket) -> None:
        key = (household_id, session_id)
        sockets = self._connections.get(key)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(key, None)

    async def send_event(self, websocket: WebSocket, event: BootstrapRealtimeEvent) -> None:
        await websocket.send_json(event.model_dump(mode="json"))

    async def broadcast(self, *, household_id: str, session_id: str, event: BootstrapRealtimeEvent) -> None:
        for websocket in list(self._iter_connections(household_id=household_id, session_id=session_id)):
            await self.send_event(websocket, event)

    def connection_count(self, *, household_id: str, session_id: str) -> int:
        return len(self._connections.get((household_id, session_id), set()))

    def _iter_connections(self, *, household_id: str, session_id: str) -> Iterable[WebSocket]:
        return self._connections.get((household_id, session_id), set())


realtime_connection_manager = RealtimeConnectionManager()
