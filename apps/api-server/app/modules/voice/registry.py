from __future__ import annotations

from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.utils import new_uuid, utc_now_iso
from app.modules.voice.protocol import VoicePlaybackStatus, VoiceTerminalCapability

VoiceTerminalStatus = Literal["online", "offline", "disabled"]
VoiceSessionStatus = Literal["streaming", "ready", "committed", "cancelled", "completed", "failed"]


class VoiceGatewayConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_id: str
    household_id: str
    terminal_id: str
    connected_at: str
    last_seen_at: str
    remote_addr: str | None = None


class VoiceTerminalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terminal_id: str
    household_id: str
    room_id: str | None = None
    terminal_code: str | None = None
    name: str | None = None
    adapter_type: str = "open_xiaoai"
    transport_type: str = "gateway_ws"
    capabilities: list[VoiceTerminalCapability] = Field(default_factory=list)
    status: VoiceTerminalStatus = "offline"
    last_seen_at: str = Field(default_factory=utc_now_iso)
    adapter_meta: dict[str, object] = Field(default_factory=dict)
    gateway_connection_id: str | None = None
    remote_addr: str | None = None


class VoicePlaybackReceiptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    playback_id: str
    session_id: str
    terminal_id: str
    status: VoicePlaybackStatus
    detail: str | None = None
    error_code: str | None = None
    observed_at: str = Field(default_factory=utc_now_iso)


class VoiceSessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    terminal_id: str
    household_id: str
    room_id: str | None = None
    status: VoiceSessionStatus = "streaming"
    started_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    last_event_seq: int = 0
    audio_chunk_count: int = 0
    audio_bytes: int = 0
    committed_at: str | None = None
    cancelled_at: str | None = None
    active_playback_id: str | None = None
    last_error_code: str | None = None
    lane: str | None = None
    transcript_text: str | None = None
    runtime_status: str | None = None
    route_type: str | None = None
    route_target: str | None = None
    conversation_session_id: str | None = None
    last_response_text: str | None = None
    playback_receipts: list[VoicePlaybackReceiptRecord] = Field(default_factory=list)


class VoiceTerminalRegistry:
    def __init__(self) -> None:
        self._terminals: dict[str, VoiceTerminalState] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._terminals.clear()

    def upsert_online(
        self,
        *,
        terminal_id: str,
        household_id: str,
        room_id: str | None,
        terminal_code: str | None,
        name: str | None,
        adapter_type: str,
        transport_type: str,
        capabilities: list[VoiceTerminalCapability],
        adapter_meta: dict[str, object],
        connection_id: str | None,
        remote_addr: str | None,
    ) -> VoiceTerminalState:
        with self._lock:
            now = utc_now_iso()
            current = self._terminals.get(terminal_id)
            terminal = VoiceTerminalState(
                terminal_id=terminal_id,
                household_id=household_id,
                room_id=room_id if room_id is not None else current.room_id if current else None,
                terminal_code=terminal_code if terminal_code is not None else current.terminal_code if current else None,
                name=name if name is not None else current.name if current else None,
                adapter_type=adapter_type,
                transport_type=transport_type,
                capabilities=capabilities,
                status="online",
                last_seen_at=now,
                adapter_meta=adapter_meta,
                gateway_connection_id=connection_id if connection_id is not None else current.gateway_connection_id if current else None,
                remote_addr=remote_addr if remote_addr is not None else current.remote_addr if current else None,
            )
            self._terminals[terminal_id] = terminal
            return terminal

    def bind_connection(self, *, terminal_id: str, household_id: str, connection_id: str, remote_addr: str | None) -> VoiceTerminalState:
        with self._lock:
            current = self._terminals.get(terminal_id)
            terminal = VoiceTerminalState(
                terminal_id=terminal_id,
                household_id=household_id if current is None else current.household_id,
                room_id=current.room_id if current else None,
                terminal_code=current.terminal_code if current else None,
                name=current.name if current else None,
                adapter_type=current.adapter_type if current else "open_xiaoai",
                transport_type=current.transport_type if current else "gateway_ws",
                capabilities=current.capabilities if current else [],
                status=current.status if current else "offline",
                last_seen_at=utc_now_iso(),
                adapter_meta=current.adapter_meta if current else {},
                gateway_connection_id=connection_id,
                remote_addr=remote_addr,
            )
            self._terminals[terminal_id] = terminal
            return terminal

    def touch(self, *, terminal_id: str, household_id: str, adapter_meta: dict[str, object] | None = None) -> VoiceTerminalState:
        with self._lock:
            current = self._terminals.get(terminal_id)
            terminal = VoiceTerminalState(
                terminal_id=terminal_id,
                household_id=household_id if current is None else current.household_id,
                room_id=current.room_id if current else None,
                terminal_code=current.terminal_code if current else None,
                name=current.name if current else None,
                adapter_type=current.adapter_type if current else "open_xiaoai",
                transport_type=current.transport_type if current else "gateway_ws",
                capabilities=current.capabilities if current else [],
                status="online" if current is None or current.status != "disabled" else "disabled",
                last_seen_at=utc_now_iso(),
                adapter_meta=adapter_meta if adapter_meta is not None else current.adapter_meta if current else {},
                gateway_connection_id=current.gateway_connection_id if current else None,
                remote_addr=current.remote_addr if current else None,
            )
            self._terminals[terminal_id] = terminal
            return terminal

    def mark_offline(self, *, terminal_id: str) -> VoiceTerminalState | None:
        with self._lock:
            current = self._terminals.get(terminal_id)
            if current is None:
                return None
            terminal = current.model_copy(update={"status": "offline", "last_seen_at": utc_now_iso(), "gateway_connection_id": None})
            self._terminals[terminal_id] = terminal
            return terminal

    def get(self, terminal_id: str) -> VoiceTerminalState | None:
        return self._terminals.get(terminal_id)


class VoiceSessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSessionState] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()

    def start_session(
        self,
        *,
        session_id: str,
        terminal_id: str,
        household_id: str,
        room_id: str | None,
        inbound_seq: int,
    ) -> VoiceSessionState:
        with self._lock:
            now = utc_now_iso()
            session = VoiceSessionState(
                session_id=session_id,
                terminal_id=terminal_id,
                household_id=household_id,
                room_id=room_id,
                status="streaming",
                started_at=now,
                updated_at=now,
                last_event_seq=inbound_seq,
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> VoiceSessionState | None:
        return self._sessions.get(session_id)

    def claim_next_seq(self, *, session_id: str) -> int:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            next_seq = session.last_event_seq + 1
            self._sessions[session_id] = session.model_copy(update={"last_event_seq": next_seq, "updated_at": utc_now_iso()})
            return next_seq

    def mark_ready(self, *, session_id: str) -> VoiceSessionState | None:
        return self._update(session_id=session_id, status="ready")

    def append_audio(self, *, session_id: str, chunk_bytes: int, inbound_seq: int) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "audio_chunk_count": session.audio_chunk_count + 1,
                    "audio_bytes": session.audio_bytes + chunk_bytes,
                    "last_event_seq": max(session.last_event_seq, inbound_seq),
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def commit_audio(self, *, session_id: str, inbound_seq: int) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "status": "committed",
                    "committed_at": utc_now_iso(),
                    "last_event_seq": max(session.last_event_seq, inbound_seq),
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def cancel(self, *, session_id: str, inbound_seq: int) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "status": "cancelled",
                    "cancelled_at": utc_now_iso(),
                    "last_event_seq": max(session.last_event_seq, inbound_seq),
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def attach_playback_receipt(
        self,
        *,
        session_id: str,
        playback_id: str,
        terminal_id: str,
        status: VoicePlaybackStatus,
        detail: str | None,
        error_code: str | None,
        inbound_seq: int,
    ) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            receipt = VoicePlaybackReceiptRecord(
                playback_id=playback_id,
                session_id=session_id,
                terminal_id=terminal_id,
                status=status,
                detail=detail,
                error_code=error_code,
            )
            session_status: VoiceSessionStatus = session.status
            if status == "completed":
                session_status = "completed"
            elif status == "failed":
                session_status = "failed"
            updated = session.model_copy(
                update={
                    "status": session_status,
                    "playback_receipts": [*session.playback_receipts, receipt],
                    "active_playback_id": None if status in {"completed", "failed", "interrupted"} else playback_id,
                    "last_error_code": error_code,
                    "last_event_seq": max(session.last_event_seq, inbound_seq),
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def set_active_playback(self, *, session_id: str, playback_id: str) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update={"active_playback_id": playback_id, "updated_at": utc_now_iso()})
            self._sessions[session_id] = updated
            return updated

    def update_transcript(
        self,
        *,
        session_id: str,
        transcript_text: str,
        runtime_status: str,
    ) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "transcript_text": transcript_text,
                    "runtime_status": runtime_status,
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def update_route(
        self,
        *,
        session_id: str,
        lane: str,
        route_type: str,
        route_target: str | None,
    ) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "lane": lane,
                    "route_type": route_type,
                    "route_target": route_target,
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def attach_conversation(
        self,
        *,
        session_id: str,
        conversation_session_id: str,
    ) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "conversation_session_id": conversation_session_id,
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def record_response_text(self, *, session_id: str, response_text: str) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "last_response_text": response_text,
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def mark_failed(self, *, session_id: str, error_code: str) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(
                update={
                    "status": "failed",
                    "last_error_code": error_code,
                    "updated_at": utc_now_iso(),
                }
            )
            self._sessions[session_id] = updated
            return updated

    def _update(self, *, session_id: str, status: VoiceSessionStatus) -> VoiceSessionState | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update={"status": status, "updated_at": utc_now_iso()})
            self._sessions[session_id] = updated
            return updated


class VoiceGatewayConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, VoiceGatewayConnection] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._connections.clear()

    def register(self, *, household_id: str, terminal_id: str, remote_addr: str | None) -> VoiceGatewayConnection:
        with self._lock:
            connection = VoiceGatewayConnection(
                connection_id=new_uuid(),
                household_id=household_id,
                terminal_id=terminal_id,
                connected_at=utc_now_iso(),
                last_seen_at=utc_now_iso(),
                remote_addr=remote_addr,
            )
            self._connections[terminal_id] = connection
            return connection

    def unregister(self, *, terminal_id: str) -> VoiceGatewayConnection | None:
        with self._lock:
            return self._connections.pop(terminal_id, None)

    def touch(self, *, terminal_id: str) -> VoiceGatewayConnection | None:
        with self._lock:
            connection = self._connections.get(terminal_id)
            if connection is None:
                return None
            updated = connection.model_copy(update={"last_seen_at": utc_now_iso()})
            self._connections[terminal_id] = updated
            return updated

    def get(self, terminal_id: str) -> VoiceGatewayConnection | None:
        return self._connections.get(terminal_id)


voice_terminal_registry = VoiceTerminalRegistry()
voice_session_registry = VoiceSessionRegistry()
voice_gateway_connection_registry = VoiceGatewayConnectionRegistry()
