from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from open_xiaoai_gateway.protocol import GatewayCommand, GatewayEvent, OpenXiaoAIEnvelope

VOICE_CAPABILITY_WHITELIST = ("audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat")
VOICE_CAPABILITY_BLACKLIST = ("shell_exec", "script_exec", "system_upgrade", "reboot_control", "business_logic")
_TEXT_EVENT_ALIASES = {
    "hello": "terminal.online",
    "terminal.online": "terminal.online",
    "terminal.offline": "terminal.offline",
    "heartbeat": "terminal.heartbeat",
    "terminal.heartbeat": "terminal.heartbeat",
    "session.start": "session.start",
    "listen.start": "session.start",
    "audio.commit": "audio.commit",
    "listen.stop": "audio.commit",
    "session.cancel": "session.cancel",
    "listen.cancel": "session.cancel",
    "playback.interrupted": "playback.interrupted",
    "playback.started": "playback.receipt",
    "playback.completed": "playback.receipt",
    "playback.failed": "playback.receipt",
}
_FORBIDDEN_OPEN_XIAOAI_EVENTS = {"shell.exec", "script.exec", "system.upgrade", "reboot.control", "business.logic"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class TerminalBridgeContext:
    terminal_id: str | None = None
    household_id: str | None = None
    room_id: str | None = None
    terminal_code: str | None = None
    name: str | None = None
    active_session_id: str | None = None
    seq_counter: int = 0
    capabilities: list[str] = field(default_factory=lambda: list(VOICE_CAPABILITY_WHITELIST))

    def next_seq(self) -> int:
        self.seq_counter += 1
        return self.seq_counter


def sanitize_capabilities(capabilities: list[str] | None) -> list[str]:
    if not capabilities:
        return list(VOICE_CAPABILITY_WHITELIST)

    allowed = set(VOICE_CAPABILITY_WHITELIST)
    blocked = set(VOICE_CAPABILITY_BLACKLIST)
    sanitized: list[str] = []
    for item in capabilities:
        normalized = item.strip()
        if not normalized or normalized in blocked or normalized not in allowed:
            continue
        if normalized not in sanitized:
            sanitized.append(normalized)
    return sanitized


def translate_text_message(raw_message: str, context: TerminalBridgeContext) -> list[GatewayEvent]:
    envelope = OpenXiaoAIEnvelope.model_validate(json.loads(raw_message))
    event_name = str(envelope.event)
    if event_name in _FORBIDDEN_OPEN_XIAOAI_EVENTS:
        return []

    mapped_type = _TEXT_EVENT_ALIASES.get(event_name)
    if mapped_type is None:
        return []

    data = dict(envelope.data)
    terminal_id = str(data.get("terminal_id") or context.terminal_id or "").strip()
    if not terminal_id:
        return []

    context.terminal_id = terminal_id
    household_id = str(data.get("household_id") or context.household_id or "").strip() or None
    context.household_id = household_id
    context.room_id = str(data.get("room_id") or context.room_id or "").strip() or context.room_id
    context.terminal_code = str(data.get("terminal_code") or context.terminal_code or "").strip() or context.terminal_code
    context.name = str(data.get("name") or context.name or "").strip() or context.name

    session_id = str(data.get("session_id") or context.active_session_id or "").strip() or None
    if mapped_type == "session.start" and session_id:
        context.active_session_id = session_id
    if mapped_type in {"audio.commit", "session.cancel"} and session_id:
        context.active_session_id = session_id

    payload: dict[str, Any] = {}
    if mapped_type == "terminal.online":
        context.capabilities = sanitize_capabilities([str(item) for item in data.get("capabilities", [])])
        payload = {
            "household_id": household_id or "unknown-household",
            "room_id": context.room_id,
            "terminal_code": context.terminal_code,
            "name": context.name,
            "adapter_type": "open_xiaoai",
            "transport_type": "gateway_ws",
            "capabilities": context.capabilities,
            "adapter_meta": {key: value for key, value in data.items() if key not in {"capabilities"}},
        }
    elif mapped_type == "terminal.offline":
        payload = {
            "household_id": household_id or "unknown-household",
            "reason": str(data.get("reason") or "terminal_disconnect"),
        }
    elif mapped_type == "terminal.heartbeat":
        payload = {
            "household_id": household_id or "unknown-household",
            "status": str(data.get("status") or "online"),
            "adapter_meta": data,
        }
    elif mapped_type == "session.start":
        payload = {
            "household_id": household_id or "unknown-household",
            "room_id": context.room_id,
            "terminal_code": context.terminal_code,
            "sample_rate": int(data.get("sample_rate") or 16000),
            "codec": str(data.get("codec") or "pcm_s16le"),
            "channels": int(data.get("channels") or 1),
            "trace_id": data.get("trace_id"),
        }
    elif mapped_type == "audio.commit":
        payload = {
            "duration_ms": int(data["duration_ms"]) if data.get("duration_ms") is not None else None,
            "reason": data.get("reason"),
        }
    elif mapped_type == "session.cancel":
        payload = {"reason": str(data.get("reason") or "user_cancelled")}
    elif mapped_type == "playback.interrupted":
        payload = {
            "playback_id": str(data.get("playback_id") or "unknown-playback"),
            "reason": data.get("reason"),
        }
    elif mapped_type == "playback.receipt":
        playback_status = "started"
        if event_name == "playback.completed":
            playback_status = "completed"
        elif event_name == "playback.failed":
            playback_status = "failed"
        payload = {
            "playback_id": str(data.get("playback_id") or "unknown-playback"),
            "status": playback_status,
            "detail": data.get("detail"),
            "error_code": data.get("error_code"),
        }

    return [
        GatewayEvent(
            type=mapped_type,
            terminal_id=terminal_id,
            session_id=session_id,
            seq=context.next_seq(),
            payload=payload,
            ts=utc_now_iso(),
        )
    ]


def translate_audio_chunk(raw_chunk: bytes, context: TerminalBridgeContext) -> list[GatewayEvent]:
    if not context.terminal_id or not context.active_session_id:
        return []

    return [
        GatewayEvent(
            type="audio.append",
            terminal_id=context.terminal_id,
            session_id=context.active_session_id,
            seq=context.next_seq(),
            payload={
                "chunk_base64": base64.b64encode(raw_chunk).decode("ascii"),
                "chunk_bytes": len(raw_chunk),
                "codec": "pcm_s16le",
                "sample_rate": 16000,
            },
            ts=utc_now_iso(),
        )
    ]


def translate_command_to_terminal(command: GatewayCommand) -> str:
    if command.type == "session.ready":
        envelope = {"event": "session.ready", "data": {"session_id": command.session_id, **command.payload}}
    elif command.type == "play.start":
        envelope = {"event": "play", "data": {"session_id": command.session_id, **command.payload}}
    elif command.type == "play.stop":
        envelope = {"event": "stop", "data": {"session_id": command.session_id, **command.payload}}
    elif command.type == "play.abort":
        envelope = {"event": "abort", "data": {"session_id": command.session_id, **command.payload}}
    else:
        envelope = {"event": "error", "data": {"session_id": command.session_id, **command.payload}}
    return json.dumps(envelope, ensure_ascii=False)


def build_terminal_offline_event(context: TerminalBridgeContext) -> GatewayEvent | None:
    if not context.terminal_id or not context.household_id:
        return None
    return GatewayEvent(
        type="terminal.offline",
        terminal_id=context.terminal_id,
        seq=context.next_seq(),
        payload={"household_id": context.household_id, "reason": "gateway_disconnect"},
        ts=utc_now_iso(),
    )
