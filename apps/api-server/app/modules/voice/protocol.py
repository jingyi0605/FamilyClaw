from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.db.utils import utc_now_iso
from app.modules.voiceprint.schemas import PendingVoiceprintEnrollmentRead

VoiceTerminalCapability = Literal[
    "audio_input",
    "audio_output",
    "playback_stop",
    "playback_abort",
    "heartbeat",
]
VoiceForbiddenCapability = Literal[
    "shell_exec",
    "script_exec",
    "system_upgrade",
    "reboot_control",
    "business_logic",
]
VoiceGatewayEventType = Literal[
    "terminal.online",
    "terminal.offline",
    "terminal.heartbeat",
    "session.start",
    "audio.append",
    "audio.commit",
    "session.cancel",
    "playback.interrupted",
    "playback.receipt",
]
VoiceCommandEventType = Literal[
    "binding.refresh",
    "session.ready",
    "play.start",
    "play.stop",
    "play.abort",
    "speaker.turn_on",
    "speaker.set_volume",
    "agent.error",
]
VoicePlaybackStatus = Literal["started", "completed", "failed", "interrupted"]
VoicePlayMode = Literal["tts_text", "audio_bytes"]
VoiceSessionPurpose = Literal["conversation", "voiceprint_enrollment"]
VoiceErrorCode = Literal[
    "gateway_auth_failed",
    "invalid_event_payload",
    "terminal_not_found",
    "terminal_not_connected",
    "terminal_capability_blocked",
    "session_not_found",
    "playback_failed",
    "voice_runtime_unavailable",
    "voice_transcript_empty",
    "fast_action_ambiguous",
    "fast_action_room_ambiguous",
    "fast_action_device_ambiguous",
    "fast_action_action_ambiguous",
    "fast_action_blocked",
    "quiet_hours_blocked",
    "child_protection_blocked",
    "high_risk_action_blocked",
    "voice_identity_conflict",
    "voice_identity_low_confidence",
    "context_conflict",
    "conversation_bridge_unavailable",
]

VOICE_TERMINAL_CAPABILITY_WHITELIST: tuple[VoiceTerminalCapability, ...] = (
    "audio_input",
    "audio_output",
    "playback_stop",
    "playback_abort",
    "heartbeat",
)
VOICE_TERMINAL_CAPABILITY_BLACKLIST: tuple[VoiceForbiddenCapability, ...] = (
    "shell_exec",
    "script_exec",
    "system_upgrade",
    "reboot_control",
    "business_logic",
)
_OPTIONAL_SESSION_EVENT_TYPES = frozenset({"terminal.online", "terminal.offline", "terminal.heartbeat"})
_PLAYBACK_EVENT_TYPES = frozenset({"playback.interrupted", "playback.receipt"})
_PLAYBACK_COMMAND_EVENT_TYPES = frozenset({"play.start", "play.stop", "play.abort"})


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def sanitize_terminal_capabilities(capabilities: list[str] | None) -> list[VoiceTerminalCapability]:
    if not capabilities:
        return list(VOICE_TERMINAL_CAPABILITY_WHITELIST)

    allowed = set(VOICE_TERMINAL_CAPABILITY_WHITELIST)
    blocked = set(VOICE_TERMINAL_CAPABILITY_BLACKLIST)
    sanitized: list[VoiceTerminalCapability] = []
    for item in capabilities:
        normalized = item.strip()
        if not normalized or normalized in blocked or normalized not in allowed:
            continue
        capability = cast(VoiceTerminalCapability, normalized)
        if capability not in sanitized:
            sanitized.append(capability)
    return sanitized


class TerminalOnlinePayload(_StrictModel):
    household_id: str = Field(min_length=1)
    room_id: str | None = None
    terminal_code: str | None = None
    name: str | None = None
    adapter_type: str = "open_xiaoai"
    transport_type: str = "gateway_ws"
    capabilities: list[VoiceTerminalCapability] = Field(default_factory=lambda: list(VOICE_TERMINAL_CAPABILITY_WHITELIST))
    adapter_meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capabilities", mode="before")
    @classmethod
    def validate_capabilities(cls, value: Any) -> list[VoiceTerminalCapability]:
        if value is None:
            return list(VOICE_TERMINAL_CAPABILITY_WHITELIST)
        if not isinstance(value, list):
            raise ValueError("capabilities 必须是数组")
        return sanitize_terminal_capabilities([str(item) for item in value])


class TerminalOfflinePayload(_StrictModel):
    household_id: str = Field(min_length=1)
    reason: str | None = None


class TerminalHeartbeatPayload(_StrictModel):
    household_id: str = Field(min_length=1)
    status: str = "online"
    adapter_meta: dict[str, Any] = Field(default_factory=dict)


class SessionStartPayload(_StrictModel):
    household_id: str = Field(min_length=1)
    room_id: str | None = None
    terminal_code: str | None = None
    sample_rate: int = Field(default=16000, ge=8000, le=96000)
    codec: str = Field(default="pcm_s16le", min_length=1)
    channels: int = Field(default=1, ge=1, le=2)
    trace_id: str | None = None
    session_purpose: VoiceSessionPurpose = "conversation"
    enrollment_id: str | None = None

    @model_validator(mode="after")
    def validate_enrollment_scope(self) -> "SessionStartPayload":
        if self.session_purpose == "voiceprint_enrollment" and not self.enrollment_id:
            raise ValueError("voiceprint_enrollment 会话必须携带 enrollment_id")
        return self


class AudioAppendPayload(_StrictModel):
    chunk_base64: str = Field(min_length=1)
    chunk_bytes: int = Field(ge=1)
    codec: str = Field(default="pcm_s16le", min_length=1)
    sample_rate: int = Field(default=16000, ge=8000, le=96000)


class AudioCommitPayload(_StrictModel):
    duration_ms: int | None = Field(default=None, ge=0)
    reason: str | None = None
    debug_transcript: str | None = None
    session_purpose: VoiceSessionPurpose = "conversation"
    enrollment_id: str | None = None

    @model_validator(mode="after")
    def validate_enrollment_scope(self) -> "AudioCommitPayload":
        if self.session_purpose == "voiceprint_enrollment" and not self.enrollment_id:
            raise ValueError("voiceprint_enrollment 会话必须携带 enrollment_id")
        return self


class SessionCancelPayload(_StrictModel):
    reason: str = Field(default="user_cancelled", min_length=1)


class PlaybackInterruptedPayload(_StrictModel):
    playback_id: str = Field(min_length=1)
    reason: str | None = None


class PlaybackReceiptPayload(_StrictModel):
    playback_id: str = Field(min_length=1)
    status: VoicePlaybackStatus
    detail: str | None = None
    error_code: str | None = None


class SessionReadyPayload(_StrictModel):
    accepted: bool = True
    lane: str | None = None


class BindingRefreshBindingPayload(_StrictModel):
    household_id: str = Field(min_length=1)
    terminal_id: str = Field(min_length=1)
    room_id: str | None = None
    terminal_name: str = Field(min_length=1)
    voice_auto_takeover_enabled: bool = False
    voice_takeover_prefixes: list[str] = Field(default_factory=lambda: ["\u8bf7"])
    pending_voiceprint_enrollment: PendingVoiceprintEnrollmentRead | None = None


class BindingRefreshPayload(_StrictModel):
    reason: str | None = None
    binding: BindingRefreshBindingPayload


class PlayStartPayload(_StrictModel):
    playback_id: str = Field(min_length=1)
    mode: VoicePlayMode = "tts_text"
    text: str | None = None
    audio_base64: str | None = None
    content_type: str | None = None

    @model_validator(mode="after")
    def ensure_payload_matches_mode(self) -> "PlayStartPayload":
        if self.mode == "tts_text" and not self.text:
            raise ValueError("tts_text 模式必须提供 text")
        if self.mode == "audio_bytes" and not self.audio_base64:
            raise ValueError("audio_bytes 模式必须提供 audio_base64")
        return self


class PlayStopPayload(_StrictModel):
    playback_id: str | None = None
    reason: str | None = None


class PlayAbortPayload(_StrictModel):
    playback_id: str | None = None
    reason: str | None = None


class SpeakerTurnOnPayload(_StrictModel):
    reason: str | None = None


class SpeakerSetVolumePayload(_StrictModel):
    volume_pct: int = Field(ge=0, le=100)
    reason: str | None = None


class AgentErrorPayload(_StrictModel):
    detail: str = Field(min_length=1)
    error_code: VoiceErrorCode
    retryable: bool = False


VoiceGatewayPayload = (
    TerminalOnlinePayload
    | TerminalOfflinePayload
    | TerminalHeartbeatPayload
    | SessionStartPayload
    | AudioAppendPayload
    | AudioCommitPayload
    | SessionCancelPayload
    | PlaybackInterruptedPayload
    | PlaybackReceiptPayload
)
VoiceCommandPayload = (
    BindingRefreshPayload
    | SessionReadyPayload
    | PlayStartPayload
    | PlayStopPayload
    | PlayAbortPayload
    | SpeakerTurnOnPayload
    | SpeakerSetVolumePayload
    | AgentErrorPayload
)

_VOICE_GATEWAY_PAYLOAD_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "terminal.online": TypeAdapter(TerminalOnlinePayload),
    "terminal.offline": TypeAdapter(TerminalOfflinePayload),
    "terminal.heartbeat": TypeAdapter(TerminalHeartbeatPayload),
    "session.start": TypeAdapter(SessionStartPayload),
    "audio.append": TypeAdapter(AudioAppendPayload),
    "audio.commit": TypeAdapter(AudioCommitPayload),
    "session.cancel": TypeAdapter(SessionCancelPayload),
    "playback.interrupted": TypeAdapter(PlaybackInterruptedPayload),
    "playback.receipt": TypeAdapter(PlaybackReceiptPayload),
}
_VOICE_COMMAND_PAYLOAD_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "binding.refresh": TypeAdapter(BindingRefreshPayload),
    "session.ready": TypeAdapter(SessionReadyPayload),
    "play.start": TypeAdapter(PlayStartPayload),
    "play.stop": TypeAdapter(PlayStopPayload),
    "play.abort": TypeAdapter(PlayAbortPayload),
    "speaker.turn_on": TypeAdapter(SpeakerTurnOnPayload),
    "speaker.set_volume": TypeAdapter(SpeakerSetVolumePayload),
    "agent.error": TypeAdapter(AgentErrorPayload),
}


class VoiceGatewayEvent(_StrictModel):
    type: VoiceGatewayEventType
    terminal_id: str = Field(min_length=1)
    session_id: str | None = None
    seq: int = Field(ge=0)
    payload: VoiceGatewayPayload
    ts: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def parse_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        adapter = _VOICE_GATEWAY_PAYLOAD_ADAPTERS.get(str(data.get("type")))
        if adapter is None:
            return data
        normalized = dict(data)
        normalized["payload"] = adapter.validate_python(data.get("payload", {}))
        return normalized

    @model_validator(mode="after")
    def validate_scope(self) -> "VoiceGatewayEvent":
        if self.type not in _OPTIONAL_SESSION_EVENT_TYPES and not self.session_id:
            raise ValueError(f"{self.type} 必须携带 session_id")
        if self.type in _PLAYBACK_EVENT_TYPES and not self.session_id:
            raise ValueError(f"{self.type} 必须携带 session_id")
        return self


class VoiceCommandEvent(_StrictModel):
    type: VoiceCommandEventType
    terminal_id: str = Field(min_length=1)
    session_id: str | None = None
    seq: int = Field(ge=0)
    payload: VoiceCommandPayload
    ts: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def parse_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        adapter = _VOICE_COMMAND_PAYLOAD_ADAPTERS.get(str(data.get("type")))
        if adapter is None:
            return data
        normalized = dict(data)
        normalized["payload"] = adapter.validate_python(data.get("payload", {}))
        return normalized

    @model_validator(mode="after")
    def validate_scope(self) -> "VoiceCommandEvent":
        if self.type != "agent.error" and not self.session_id:
            raise ValueError(f"{self.type} 必须携带 session_id")
        if self.type in _PLAYBACK_COMMAND_EVENT_TYPES and not self.session_id:
            raise ValueError(f"{self.type} 必须携带 session_id")
        return self


def build_voice_gateway_event(
    *,
    event_type: VoiceGatewayEventType,
    terminal_id: str,
    seq: int,
    payload: dict[str, Any] | VoiceGatewayPayload,
    session_id: str | None = None,
    ts: str | None = None,
) -> VoiceGatewayEvent:
    return VoiceGatewayEvent(
        type=event_type,
        terminal_id=terminal_id,
        session_id=session_id,
        seq=seq,
        payload=cast(Any, payload),
        ts=ts or utc_now_iso(),
    )


def build_voice_command_event(
    *,
    event_type: VoiceCommandEventType,
    terminal_id: str,
    seq: int,
    payload: dict[str, Any] | VoiceCommandPayload,
    session_id: str | None = None,
    ts: str | None = None,
) -> VoiceCommandEvent:
    return VoiceCommandEvent(
        type=event_type,
        terminal_id=terminal_id,
        session_id=session_id,
        seq=seq,
        payload=cast(Any, payload),
        ts=ts or utc_now_iso(),
    )
