from __future__ import annotations

from app.plugins._local_openai_provider_helpers import build_local_openai_driver


def build_driver(plugin=None):
    _ = plugin
    return build_local_openai_driver(model_discovery_strategy="ollama_tags")
