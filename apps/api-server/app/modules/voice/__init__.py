# Lazy imports to avoid circular dependency
# When any submodule of voice is imported, this __init__.py runs first.
# We use __getattr__ to lazily import modules that have circular dependencies.

from app.modules.voice.protocol import (
    VOICE_TERMINAL_CAPABILITY_BLACKLIST,
    VOICE_TERMINAL_CAPABILITY_WHITELIST,
    VoiceCommandEvent,
    VoiceGatewayEvent,
    build_voice_command_event,
    build_voice_gateway_event,
    sanitize_terminal_capabilities,
)

__all__ = [
    "VOICE_TERMINAL_CAPABILITY_BLACKLIST",
    "VOICE_TERMINAL_CAPABILITY_WHITELIST",
    "SpeakerHostServiceError",
    "VoiceCommandEvent",
    "VoiceGatewayEvent",
    "VoicePlaybackService",
    "build_voice_command_event",
    "build_voice_gateway_event",
    "ensure_speaker_runtime_execution_allowed",
    "get_speaker_runtime_state",
    "open_speaker_audio_session",
    "report_speaker_runtime_heartbeat",
    "sanitize_terminal_capabilities",
    "submit_speaker_text_turn",
    "voice_conversation_bridge",
    "voice_fast_action_service",
    "voice_playback_service",
    "voice_realtime_service",
    "voice_router",
    "voice_runtime_client",
]


def __getattr__(name: str):
    """Lazy import modules that have circular dependencies."""
    if name == "voice_conversation_bridge":
        from app.modules.voice.conversation_bridge import voice_conversation_bridge as obj
        return obj
    if name == "voice_fast_action_service":
        from app.modules.voice.fast_action_service import voice_fast_action_service as obj
        return obj
    if name == "voice_playback_service":
        from app.modules.voice.playback_service import voice_playback_service as obj
        return obj
    if name == "VoicePlaybackService":
        from app.modules.voice.playback_service import VoicePlaybackService as obj
        return obj
    if name == "voice_realtime_service":
        from app.modules.voice.realtime_service import voice_realtime_service as obj
        return obj
    if name == "voice_router":
        from app.modules.voice.router import voice_router as obj
        return obj
    if name == "voice_runtime_client":
        from app.modules.voice.runtime_client import voice_runtime_client as obj
        return obj
    if name == "SpeakerHostServiceError":
        from app.modules.voice.speaker_host_service import SpeakerHostServiceError as obj
        return obj
    if name == "submit_speaker_text_turn":
        from app.modules.voice.speaker_host_service import submit_speaker_text_turn as obj
        return obj
    if name == "report_speaker_runtime_heartbeat":
        from app.modules.voice.speaker_host_service import report_speaker_runtime_heartbeat as obj
        return obj
    if name == "open_speaker_audio_session":
        from app.modules.voice.speaker_host_service import open_speaker_audio_session as obj
        return obj
    if name == "ensure_speaker_runtime_execution_allowed":
        from app.modules.voice.speaker_host_service import ensure_speaker_runtime_execution_allowed as obj
        return obj
    if name == "get_speaker_runtime_state":
        from app.modules.voice.speaker_host_service import get_speaker_runtime_state as obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
