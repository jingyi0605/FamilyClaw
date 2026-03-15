from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from open_xiaoai_gateway.protocol import (
    GatewayCommand,
    GatewayEvent,
    OpenXiaoAIEvent,
    OpenXiaoAIStream,
    OpenXiaoAITextFrame,
    build_request_frame,
    build_stream_frame,
    parse_stream_frame,
    parse_text_frame,
)
from open_xiaoai_gateway.settings import settings

VOICE_CAPABILITY_WHITELIST = ("audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat")
VOICE_CAPABILITY_BLACKLIST = ("shell_exec", "script_exec", "system_upgrade", "reboot_control", "business_logic")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass(slots=True)
class TerminalBridgeContext:
    household_id: str = settings.household_id
    terminal_id: str = settings.terminal_id
    room_id: str | None = settings.room_id
    terminal_code: str | None = settings.terminal_code
    name: str | None = settings.terminal_name
    active_session_id: str | None = None
    active_playback_id: str | None = None
    active_playback_session_id: str | None = None
    last_playing_state: str = "idle"
    seq_counter: int = 0

    def next_seq(self) -> int:
        self.seq_counter += 1
        return self.seq_counter

    def new_session_id(self) -> str:
        return f"voice-session-{uuid4()}"

    def start_session(self) -> str:
        session_id = self.new_session_id()
        self.active_session_id = session_id
        return session_id

    def clear_session(self) -> None:
        self.active_session_id = None

    def track_playback(self, *, playback_id: str, session_id: str | None) -> None:
        self.active_playback_id = playback_id
        self.active_playback_session_id = session_id

    def clear_playback(self) -> None:
        self.active_playback_id = None
        self.active_playback_session_id = None


@dataclass(slots=True)
class TerminalRpcRequest:
    command: str
    payload: Any | None = None


@dataclass(slots=True)
class TerminalBinaryStream:
    tag: str
    raw_bytes: bytes
    data: Any | None = None


TerminalOutboundMessage = TerminalRpcRequest | TerminalBinaryStream


def sanitize_capabilities(capabilities: list[str] | None = None) -> list[str]:
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


def build_terminal_online_event(context: TerminalBridgeContext) -> GatewayEvent:
    return GatewayEvent(
        type="terminal.online",
        terminal_id=context.terminal_id,
        seq=context.next_seq(),
        payload={
            "household_id": context.household_id,
            "room_id": context.room_id,
            "terminal_code": context.terminal_code,
            "name": context.name,
            "adapter_type": "open_xiaoai",
            "transport_type": "gateway_ws",
            "capabilities": sanitize_capabilities(),
            "adapter_meta": {"protocol": "open_xiaoai_app_message"},
        },
        ts=utc_now_iso(),
    )


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


def build_playback_started_event(context: TerminalBridgeContext) -> GatewayEvent | None:
    if not context.active_playback_id or not context.active_playback_session_id:
        return None
    return GatewayEvent(
        type="playback.receipt",
        terminal_id=context.terminal_id,
        session_id=context.active_playback_session_id,
        seq=context.next_seq(),
        payload={
            "playback_id": context.active_playback_id,
            "status": "started",
            "detail": None,
            "error_code": None,
        },
        ts=utc_now_iso(),
    )


def build_playback_failed_event(context: TerminalBridgeContext, *, detail: str, error_code: str) -> GatewayEvent | None:
    if not context.active_playback_id or not context.active_playback_session_id:
        return None
    event = GatewayEvent(
        type="playback.receipt",
        terminal_id=context.terminal_id,
        session_id=context.active_playback_session_id,
        seq=context.next_seq(),
        payload={
            "playback_id": context.active_playback_id,
            "status": "failed",
            "detail": detail,
            "error_code": error_code,
        },
        ts=utc_now_iso(),
    )
    context.clear_playback()
    return event


def build_playback_interrupted_event(context: TerminalBridgeContext, *, reason: str | None) -> GatewayEvent | None:
    if not context.active_playback_id or not context.active_playback_session_id:
        return None
    event = GatewayEvent(
        type="playback.interrupted",
        terminal_id=context.terminal_id,
        session_id=context.active_playback_session_id,
        seq=context.next_seq(),
        payload={
            "playback_id": context.active_playback_id,
            "reason": reason,
        },
        ts=utc_now_iso(),
    )
    context.clear_playback()
    return event


def parse_open_xiaoai_text_message(raw_message: str) -> OpenXiaoAITextFrame:
    return parse_text_frame(raw_message)


def parse_open_xiaoai_stream(raw_message: bytes) -> OpenXiaoAIStream:
    return parse_stream_frame(raw_message)


def translate_text_message(raw_message: str, context: TerminalBridgeContext) -> list[GatewayEvent]:
    frame = parse_open_xiaoai_text_message(raw_message)
    if frame.Event is None:
        return []
    return _translate_open_xiaoai_event(frame.Event, context)


def translate_audio_chunk(raw_chunk: bytes, context: TerminalBridgeContext) -> list[GatewayEvent]:
    stream = parse_open_xiaoai_stream(raw_chunk)
    if stream.tag != "record" or not context.active_session_id:
        return []

    raw_bytes = stream.raw_bytes()
    if not raw_bytes:
        return []

    return [
        GatewayEvent(
            type="audio.append",
            terminal_id=context.terminal_id,
            session_id=context.active_session_id,
            seq=context.next_seq(),
            payload={
                "chunk_base64": base64.b64encode(raw_bytes).decode("ascii"),
                "chunk_bytes": len(raw_bytes),
                "codec": "pcm_s16le",
                "sample_rate": settings.recording_sample_rate,
            },
            ts=utc_now_iso(),
        )
    ]


def translate_command_to_terminal(command: GatewayCommand, context: TerminalBridgeContext) -> list[TerminalOutboundMessage]:
    if command.type in {"session.ready", "agent.error"}:
        return []

    if command.type == "play.start":
        playback_id = str(command.payload.get("playback_id") or "").strip()
        if not playback_id:
            return []
        context.track_playback(playback_id=playback_id, session_id=command.session_id)
        mode = str(command.payload.get("mode") or "tts_text")
        if mode == "audio_bytes":
            audio_base64 = str(command.payload.get("audio_base64") or "")
            if not audio_base64:
                return []
            return [
                TerminalRpcRequest(command="start_play", payload=_build_playback_audio_config()),
                TerminalBinaryStream(tag="play", raw_bytes=base64.b64decode(audio_base64.encode("ascii"))),
            ]

        text = str(command.payload.get("text") or "").strip()
        if not text:
            return []
        return [
            TerminalRpcRequest(
                command="run_shell",
                payload=f"/usr/sbin/tts_play.sh {_shell_quote(text)}",
            )
        ]

    if command.type in {"play.stop", "play.abort"}:
        return [
            TerminalRpcRequest(
                command="run_shell",
                payload="mphelper pause",
            )
        ]

    return []


def build_rpc_request_message(*, request_id: str, command: str, payload: Any | None = None) -> str:
    return build_request_frame(request_id=request_id, command=command, payload=payload)


def build_stream_message(*, stream_id: str, tag: str, raw_bytes: bytes, data: Any | None = None) -> bytes:
    return build_stream_frame(stream_id=stream_id, tag=tag, raw_bytes=raw_bytes, data=data)


def _translate_open_xiaoai_event(event: OpenXiaoAIEvent, context: TerminalBridgeContext) -> list[GatewayEvent]:
    if event.event == "kws":
        return _translate_kws_event(event.data, context)
    if event.event == "instruction":
        return _translate_instruction_event(event.data, context)
    if event.event == "playing":
        return _translate_playing_event(event.data, context)
    return []


def _translate_kws_event(data: Any, context: TerminalBridgeContext) -> list[GatewayEvent]:
    keyword: str | None = None
    if isinstance(data, dict):
        keyword = _coerce_text(data.get("Keyword"))
    elif isinstance(data, str) and data != "Started":
        keyword = data

    if not keyword:
        return []

    events: list[GatewayEvent] = []
    interrupted = build_playback_interrupted_event(context, reason=f"wake_word:{keyword}")
    if interrupted is not None:
        events.append(interrupted)

    if not context.active_session_id:
        session_id = context.start_session()
        events.append(_build_session_start_event(context, session_id=session_id))
    return events


def _translate_instruction_event(data: Any, context: TerminalBridgeContext) -> list[GatewayEvent]:
    if not isinstance(data, dict):
        return []
    line = _coerce_text(data.get("NewLine"))
    if not line:
        return []

    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return []
    if not isinstance(message, dict):
        return []

    header = message.get("header") or {}
    payload = message.get("payload") or {}
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return []
    if header.get("namespace") != "SpeechRecognizer" or header.get("name") != "RecognizeResult":
        return []

    is_vad_begin = bool(payload.get("is_vad_begin"))
    is_final = bool(payload.get("is_final"))
    results = payload.get("results") or []
    text = ""
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            text = _coerce_text(first.get("text")) or ""

    events: list[GatewayEvent] = []
    if is_vad_begin and not context.active_session_id:
        session_id = context.start_session()
        events.append(_build_session_start_event(context, session_id=session_id))

    if not is_final:
        return events

    if text.strip():
        if not context.active_session_id:
            session_id = context.start_session()
            events.append(_build_session_start_event(context, session_id=session_id))
        session_id = context.active_session_id
        context.clear_session()
        events.append(
            GatewayEvent(
                type="audio.commit",
                terminal_id=context.terminal_id,
                session_id=session_id,
                seq=context.next_seq(),
                payload={
                    "duration_ms": None,
                    "reason": "speech_recognizer_final",
                    "debug_transcript": text.strip(),
                },
                ts=utc_now_iso(),
            )
        )
        return events

    if context.active_session_id:
        session_id = context.active_session_id
        context.clear_session()
        events.append(
            GatewayEvent(
                type="session.cancel",
                terminal_id=context.terminal_id,
                session_id=session_id,
                seq=context.next_seq(),
                payload={"reason": "speech_recognizer_empty"},
                ts=utc_now_iso(),
            )
        )
    return events


def _translate_playing_event(data: Any, context: TerminalBridgeContext) -> list[GatewayEvent]:
    state = _normalize_playing_state(data)
    if state is None:
        return []

    events: list[GatewayEvent] = []
    if state == "idle" and context.active_playback_id and context.active_playback_session_id and context.last_playing_state != "idle":
        events.append(
            GatewayEvent(
                type="playback.receipt",
                terminal_id=context.terminal_id,
                session_id=context.active_playback_session_id,
                seq=context.next_seq(),
                payload={
                    "playback_id": context.active_playback_id,
                    "status": "completed",
                    "detail": None,
                    "error_code": None,
                },
                ts=utc_now_iso(),
            )
        )
        context.clear_playback()
    context.last_playing_state = state
    return events


def _build_session_start_event(context: TerminalBridgeContext, *, session_id: str) -> GatewayEvent:
    return GatewayEvent(
        type="session.start",
        terminal_id=context.terminal_id,
        session_id=session_id,
        seq=context.next_seq(),
        payload={
            "household_id": context.household_id,
            "room_id": context.room_id,
            "terminal_code": context.terminal_code,
            "sample_rate": settings.recording_sample_rate,
            "codec": "pcm_s16le",
            "channels": settings.recording_channels,
            "trace_id": None,
        },
        ts=utc_now_iso(),
    )


def _build_playback_audio_config() -> dict[str, object]:
    return {
        "pcm": "noop",
        "channels": settings.playback_channels,
        "bits_per_sample": settings.playback_bits_per_sample,
        "sample_rate": settings.playback_sample_rate,
        "period_size": settings.playback_period_size,
        "buffer_size": settings.playback_buffer_size,
    }


def build_recording_rpc_payload() -> dict[str, object]:
    return {
        "pcm": settings.recording_pcm,
        "channels": settings.recording_channels,
        "bits_per_sample": settings.recording_bits_per_sample,
        "sample_rate": settings.recording_sample_rate,
        "period_size": settings.recording_period_size,
        "buffer_size": settings.recording_buffer_size,
    }


def _normalize_playing_state(data: Any) -> Literal["playing", "paused", "idle"] | None:
    if isinstance(data, str):
        lowered = data.strip().lower()
        if lowered in {"playing", "paused", "idle"}:
            return lowered
    return None


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
