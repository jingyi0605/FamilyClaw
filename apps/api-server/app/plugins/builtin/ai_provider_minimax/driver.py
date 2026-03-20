from __future__ import annotations

from app.plugins._sdk.ai_provider_drivers import build_anthropic_messages_driver


def build_driver(plugin=None):
    return build_anthropic_messages_driver(plugin)
