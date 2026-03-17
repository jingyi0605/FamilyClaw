from __future__ import annotations

from app.core.config import VoiceRuntimeMode
from app.modules.voice.runtime_backends.base import VoiceRuntimeBackend
from app.modules.voice.runtime_backends.disabled import DisabledVoiceRuntimeBackend
from app.modules.voice.runtime_backends.embedded import EmbeddedVoiceRuntimeBackend


def build_voice_runtime_backend(mode: VoiceRuntimeMode) -> VoiceRuntimeBackend:
    if mode == "embedded":
        return EmbeddedVoiceRuntimeBackend()
    return DisabledVoiceRuntimeBackend()


__all__ = [
    "VoiceRuntimeBackend",
    "DisabledVoiceRuntimeBackend",
    "EmbeddedVoiceRuntimeBackend",
    "build_voice_runtime_backend",
]
