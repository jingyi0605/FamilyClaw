from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from open_xiaoai_gateway.invocation_policy import GatewayInvocationPolicy
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

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass(slots=True)
class VoiceTerminalBinding:
    household_id: str
    terminal_id: str
    room_id: str | None
    terminal_name: str
    voice_auto_takeover_enabled: bool = False
    voice_takeover_prefixes: tuple[str, ...] = ("请",)


@dataclass(slots=True)
class TerminalDiscoveryInfo:
    model: str
    sn: str
    runtime_version: str
    capabilities: list[str]
    fingerprint: str


@dataclass(slots=True)
class TerminalBridgeContext:
    adapter_type: str = "open_xiaoai"
    fingerprint: str | None = None
    model: str | None = None
    sn: str | None = None
    runtime_version: str | None = None
    discovered_at: str | None = None
    household_id: str | None = None
    terminal_id: str | None = None
    room_id: str | None = None
    terminal_code: str | None = None
    name: str | None = None
    active_session_id: str | None = None
    active_playback_id: str | None = None
    active_playback_session_id: str | None = None
    last_playing_state: str = "idle"
    invocation_mode: str = field(default_factory=lambda: settings.invocation_mode)
    takeover_prefixes: tuple[str, ...] = field(default_factory=lambda: tuple(settings.takeover_prefixes))
    last_invocation_decision: str = "always_familyclaw"
    last_passthrough_reason: str | None = None
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

    def apply_discovery(self, discovery: TerminalDiscoveryInfo) -> None:
        self.model = discovery.model
        self.sn = discovery.sn
        self.runtime_version = discovery.runtime_version
        self.fingerprint = discovery.fingerprint
        if self.discovered_at is None:
            self.discovered_at = utc_now_iso()

    def apply_binding(self, binding: VoiceTerminalBinding) -> None:
        self.household_id = binding.household_id
        self.terminal_id = binding.terminal_id
        self.room_id = binding.room_id
        self.name = binding.terminal_name
        self.terminal_code = binding.terminal_id
        self.invocation_mode = "always_familyclaw" if binding.voice_auto_takeover_enabled else "native_first"
        self.takeover_prefixes = binding.voice_takeover_prefixes or ("请",)

    def is_claimed(self) -> bool:
        return bool(self.fingerprint and self.household_id and self.terminal_id and self.name)


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


@dataclass(slots=True)
class TextTranslationResult:
    events: list[GatewayEvent]
    terminal_messages: list[TerminalOutboundMessage]


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


def build_open_xiaoai_fingerprint(*, model: str, sn: str) -> str:
    return f"open_xiaoai:{model}:{sn}"


def build_discovery_info(
    *,
    model: str,
    sn: str,
    runtime_version: str,
    capabilities: list[str] | None = None,
) -> TerminalDiscoveryInfo:
    normalized_model = model.strip()
    normalized_sn = sn.strip()
    return TerminalDiscoveryInfo(
        model=normalized_model,
        sn=normalized_sn,
        runtime_version=runtime_version.strip(),
        capabilities=sanitize_capabilities(capabilities),
        fingerprint=build_open_xiaoai_fingerprint(model=normalized_model, sn=normalized_sn),
    )


def build_discovery_report_payload(
    context: TerminalBridgeContext,
    *,
    remote_addr: str | None,
    connection_status: Literal["online", "offline", "unknown"] = "online",
) -> dict[str, Any]:
    if not context.fingerprint or not context.model or not context.sn or not context.runtime_version:
        raise ValueError("terminal discovery info is incomplete")
    discovered_at = context.discovered_at or utc_now_iso()
    context.discovered_at = discovered_at
    return {
        "adapter_type": context.adapter_type,
        "fingerprint": context.fingerprint,
        "model": context.model,
        "sn": context.sn,
        "runtime_version": context.runtime_version,
        "capabilities": sanitize_capabilities(),
        "remote_addr": remote_addr,
        "discovered_at": discovered_at,
        "last_seen_at": utc_now_iso(),
        "connection_status": connection_status,
    }


def build_terminal_online_event(context: TerminalBridgeContext) -> GatewayEvent:
    if not context.is_claimed():
        raise ValueError("terminal must be claimed before reporting online")
    return GatewayEvent(
        type="terminal.online",
        terminal_id=context.terminal_id or "",
        seq=context.next_seq(),
        payload={
            "household_id": context.household_id,
            "room_id": context.room_id,
            "terminal_code": context.terminal_code,
            "name": context.name,
            "adapter_type": context.adapter_type,
            "transport_type": "gateway_ws",
            "capabilities": sanitize_capabilities(),
            "adapter_meta": {
                "protocol": "open_xiaoai_app_message",
                "fingerprint": context.fingerprint,
                "model": context.model,
                "runtime_version": context.runtime_version,
            },
        },
        ts=utc_now_iso(),
    )


def build_terminal_offline_event(context: TerminalBridgeContext) -> GatewayEvent | None:
    if not context.is_claimed():
        return None
    return GatewayEvent(
        type="terminal.offline",
        terminal_id=context.terminal_id or "",
        seq=context.next_seq(),
        payload={"household_id": context.household_id, "reason": "gateway_disconnect"},
        ts=utc_now_iso(),
    )


def build_playback_started_event(context: TerminalBridgeContext) -> GatewayEvent | None:
    if not context.active_playback_id or not context.active_playback_session_id or not context.terminal_id:
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
    if not context.active_playback_id or not context.active_playback_session_id or not context.terminal_id:
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
    if not context.active_playback_id or not context.active_playback_session_id or not context.terminal_id:
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


def translate_text_message_result(raw_message: str, context: TerminalBridgeContext) -> TextTranslationResult:
    if not context.is_claimed():
        return TextTranslationResult(events=[], terminal_messages=[])
    frame = parse_open_xiaoai_text_message(raw_message)
    if frame.Event is None:
        return TextTranslationResult(events=[], terminal_messages=[])
    return _translate_open_xiaoai_event(frame.Event, context)


def translate_text_message(raw_message: str, context: TerminalBridgeContext) -> list[GatewayEvent]:
    return translate_text_message_result(raw_message, context).events


def translate_audio_chunk(raw_chunk: bytes, context: TerminalBridgeContext) -> list[GatewayEvent]:
    if not context.is_claimed():
        return []
    stream = parse_open_xiaoai_stream(raw_chunk)
    if stream.tag != "record" or not context.active_session_id or not context.terminal_id:
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
    if not context.is_claimed():
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
                payload=_build_xiaoai_tts_command(text),
            )
        ]

    if command.type in {"play.stop", "play.abort"}:
        return [TerminalRpcRequest(command="run_shell", payload="mphelper pause")]

    return []


def build_takeover_interrupt_message() -> TerminalRpcRequest:
    return TerminalRpcRequest(
        command="run_shell",
        payload="/etc/init.d/mico_aivs_lab restart >/dev/null 2>&1",
    )


def build_rpc_request_message(*, request_id: str, command: str, payload: Any | None = None) -> str:
    return build_request_frame(request_id=request_id, command=command, payload=payload)


def build_stream_message(*, stream_id: str, tag: str, raw_bytes: bytes, data: Any | None = None) -> bytes:
    return build_stream_frame(stream_id=stream_id, tag=tag, raw_bytes=raw_bytes, data=data)


def _translate_open_xiaoai_event(event: OpenXiaoAIEvent, context: TerminalBridgeContext) -> TextTranslationResult:
    if event.event == "kws":
        return _translate_kws_event(event.data, context)
    if event.event == "instruction":
        return _translate_instruction_event(event.data, context)
    if event.event == "playing":
        return _translate_playing_event(event.data, context)
    return TextTranslationResult(events=[], terminal_messages=[])


def _translate_kws_event(data: Any, context: TerminalBridgeContext) -> TextTranslationResult:
    keyword: str | None = None
    if isinstance(data, dict):
        keyword = _coerce_text(data.get("Keyword"))
    elif isinstance(data, str) and data != "Started":
        keyword = data

    if not keyword or not context.terminal_id:
        return TextTranslationResult(events=[], terminal_messages=[])

    events: list[GatewayEvent] = []
    terminal_messages: list[TerminalOutboundMessage] = []
    interrupted = build_playback_interrupted_event(context, reason=f"wake_word:{keyword}")
    if interrupted is not None:
        events.append(interrupted)

    if context.invocation_mode == "always_familyclaw" and not context.active_session_id:
        if settings.pause_on_takeover:
            terminal_messages.append(build_takeover_interrupt_message())
        session_id = context.start_session()
        events.append(_build_session_start_event(context, session_id=session_id))
        context.last_invocation_decision = "always_familyclaw"
        context.last_passthrough_reason = None
        return TextTranslationResult(events=events, terminal_messages=terminal_messages)

    context.last_invocation_decision = "await_takeover_prefix"
    context.last_passthrough_reason = None
    return TextTranslationResult(events=events, terminal_messages=terminal_messages)


def _translate_instruction_event(data: Any, context: TerminalBridgeContext) -> TextTranslationResult:
    if not isinstance(data, dict):
        return TextTranslationResult(events=[], terminal_messages=[])
    line = _coerce_text(data.get("NewLine"))
    if not line or not context.terminal_id:
        return TextTranslationResult(events=[], terminal_messages=[])

    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return TextTranslationResult(events=[], terminal_messages=[])
    if not isinstance(message, dict):
        return TextTranslationResult(events=[], terminal_messages=[])

    header = message.get("header") or {}
    payload = message.get("payload") or {}
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return TextTranslationResult(events=[], terminal_messages=[])
    if header.get("namespace") != "SpeechRecognizer" or header.get("name") != "RecognizeResult":
        return TextTranslationResult(events=[], terminal_messages=[])

    is_vad_begin = bool(payload.get("is_vad_begin"))
    is_final = bool(payload.get("is_final"))
    results = payload.get("results") or []
    text = ""
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            text = _coerce_text(first.get("text")) or ""

    events: list[GatewayEvent] = []
    terminal_messages: list[TerminalOutboundMessage] = []
    if is_vad_begin and context.invocation_mode == "always_familyclaw" and not context.active_session_id:
        if settings.pause_on_takeover:
            terminal_messages.append(build_takeover_interrupt_message())
        session_id = context.start_session()
        events.append(_build_session_start_event(context, session_id=session_id))

    if not is_final:
        return TextTranslationResult(events=events, terminal_messages=terminal_messages)

    if text.strip():
        if context.invocation_mode == "always_familyclaw":
            if not context.active_session_id:
                if settings.pause_on_takeover:
                    terminal_messages.append(build_takeover_interrupt_message())
                session_id = context.start_session()
                events.append(_build_session_start_event(context, session_id=session_id))
            session_id = context.active_session_id
            context.clear_session()
            events.append(_build_audio_commit_event(context, session_id=session_id, transcript_text=text.strip(), reason="speech_recognizer_final"))
            context.last_invocation_decision = "always_familyclaw"
            context.last_passthrough_reason = None
            return TextTranslationResult(events=events, terminal_messages=terminal_messages)

        decision = GatewayInvocationPolicy(
            mode=context.invocation_mode,
            takeover_prefixes=context.takeover_prefixes,
            strip_takeover_prefix=settings.strip_takeover_prefix,
            pause_on_takeover=settings.pause_on_takeover,
        ).decide(text)
        logger.info(
            "invocation decision fingerprint=%s decision=%s reason=%s matched_prefix=%s transcript=%s",
            context.fingerprint,
            decision.decision_type,
            decision.reason,
            decision.matched_prefix,
            text.strip(),
        )
        context.last_invocation_decision = decision.decision_type
        context.last_passthrough_reason = decision.reason if decision.decision_type != "familyclaw_takeover" else None
        if decision.decision_type != "familyclaw_takeover" or not decision.resolved_text:
            return TextTranslationResult(events=events, terminal_messages=[])

        terminal_messages: list[TerminalOutboundMessage] = []
        if decision.should_pause:
            terminal_messages.append(build_takeover_interrupt_message())
        if not context.active_session_id:
            session_id = context.start_session()
            events.append(_build_session_start_event(context, session_id=session_id))
        session_id = context.active_session_id
        context.clear_session()
        events.append(
            _build_audio_commit_event(
                context,
                session_id=session_id,
                transcript_text=decision.resolved_text,
                reason=decision.reason,
            )
        )
        return TextTranslationResult(events=events, terminal_messages=terminal_messages)

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
    context.last_invocation_decision = "native_passthrough" if context.invocation_mode == "native_first" else context.last_invocation_decision
    context.last_passthrough_reason = "speech_recognizer_empty"
    return TextTranslationResult(events=events, terminal_messages=[])


def _build_xiaoai_tts_command(text: str) -> str:
    normalized_text = _normalize_tts_text(text)
    return f"/usr/sbin/tts_play.sh {_shell_quote(normalized_text)} >/tmp/familyclaw-tts.log 2>&1"


def _translate_playing_event(data: Any, context: TerminalBridgeContext) -> TextTranslationResult:
    state = _normalize_playing_state(data)
    if state is None:
        return TextTranslationResult(events=[], terminal_messages=[])

    events: list[GatewayEvent] = []
    if (
        state == "idle"
        and context.active_playback_id
        and context.active_playback_session_id
        and context.last_playing_state != "idle"
        and context.terminal_id
    ):
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
    return TextTranslationResult(events=events, terminal_messages=[])


def _build_session_start_event(context: TerminalBridgeContext, *, session_id: str) -> GatewayEvent:
    return GatewayEvent(
        type="session.start",
        terminal_id=context.terminal_id or "",
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


def _build_audio_commit_event(
    context: TerminalBridgeContext,
    *,
    session_id: str | None,
    transcript_text: str,
    reason: str,
) -> GatewayEvent:
    return GatewayEvent(
        type="audio.commit",
        terminal_id=context.terminal_id or "",
        session_id=session_id,
        seq=context.next_seq(),
        payload={
            "duration_ms": None,
            "reason": reason,
            "debug_transcript": transcript_text,
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


def _normalize_tts_text(text: str) -> str:
    return " ".join(str(text).split())


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
