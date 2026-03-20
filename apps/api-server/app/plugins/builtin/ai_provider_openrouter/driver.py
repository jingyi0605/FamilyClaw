from __future__ import annotations

from collections.abc import Mapping

from app.modules.plugin.schemas import PluginRegistryItem
from app.plugins._ai_provider_runtime_helpers import (
    WrappedAiProviderDriver,
    clone_provider_profile_with_extra_config,
    read_provider_extra_config,
)
from app.plugins._sdk.ai_provider_drivers import build_openai_compatible_driver


def build_driver(plugin: PluginRegistryItem | None = None):
    return WrappedAiProviderDriver(
        base_driver=build_openai_compatible_driver(plugin),
        prepare_request=_prepare_request,
    )


def _prepare_request(provider_profile, capability, payload: Mapping[str, object]):
    _ = capability
    extra_config = read_provider_extra_config(provider_profile)
    site_url = str(extra_config.get("site_url") or "").strip()
    app_name = str(extra_config.get("app_name") or "").strip()
    headers = extra_config.get("headers")
    next_headers = dict(headers) if isinstance(headers, dict) else {}

    if site_url:
        next_headers.setdefault("HTTP-Referer", site_url)
    if app_name:
        next_headers.setdefault("X-Title", app_name)

    if not next_headers:
        return provider_profile, payload

    next_extra_config = dict(extra_config)
    next_extra_config["headers"] = next_headers
    return clone_provider_profile_with_extra_config(provider_profile, next_extra_config), payload
