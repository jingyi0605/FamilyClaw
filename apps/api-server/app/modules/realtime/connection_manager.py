from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Callable

from fastapi import WebSocket
from pydantic import BaseModel

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
            try:
                await self.send_event(websocket, event)
            except Exception:
                self.unregister(household_id=household_id, session_id=session_id, websocket=websocket)

    def connection_count(self, *, household_id: str, session_id: str) -> int:
        return len(self._connections.get((household_id, session_id), set()))

    async def broadcast_household(
        self,
        *,
        household_id: str,
        event_builder: Callable[[str, int], BaseModel],
    ) -> None:
        for seq, session_id in enumerate(sorted(self._session_ids(household_id=household_id)), start=1):
            event = event_builder(session_id, seq)
            for websocket in list(self._iter_connections(household_id=household_id, session_id=session_id)):
                try:
                    await websocket.send_json(event.model_dump(mode="json"))
                except Exception:
                    self.unregister(household_id=household_id, session_id=session_id, websocket=websocket)

    def _iter_connections(self, *, household_id: str, session_id: str) -> Iterable[WebSocket]:
        return self._connections.get((household_id, session_id), set())

    def _session_ids(self, *, household_id: str) -> set[str]:
        return {session_id for owner_household_id, session_id in self._connections.keys() if owner_household_id == household_id}


realtime_connection_manager = RealtimeConnectionManager()
