from __future__ import annotations

from app.plugins._sdk.ai_provider_drivers import build_openai_compatible_driver


def build_driver(plugin=None):
    return build_openai_compatible_driver(plugin)
