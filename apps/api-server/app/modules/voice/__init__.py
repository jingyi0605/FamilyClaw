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
    "VoiceCommandEvent",
    "VoiceGatewayEvent",
    "VoicePlaybackService",
    "build_voice_command_event",
    "build_voice_gateway_event",
    "sanitize_terminal_capabilities",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
