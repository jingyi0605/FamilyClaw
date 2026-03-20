from __future__ import annotations

from app.plugins._sdk.ai_provider_drivers import build_gemini_generate_content_driver


def build_driver(plugin=None):
    return build_gemini_generate_content_driver(plugin)
