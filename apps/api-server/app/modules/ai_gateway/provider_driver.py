from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.ai_gateway.models import AiProviderProfile
from app.modules.ai_gateway.schemas import AiCapability
from app.modules.plugin.executors import load_entrypoint_callable
from app.modules.plugin.schemas import PluginRegistryItem

from . import provider_runtime


_AI_PROVIDER_DRIVER_BUILDERS: dict[tuple[str, str, str], Callable[[PluginRegistryItem], object]] = {}


class AiProviderDriver(Protocol):
    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> provider_runtime.ProviderInvokeResult: ...

    async def ainvoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> provider_runtime.ProviderInvokeResult: ...

    def stream(
        self,
        *,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> AsyncIterator[str]: ...


def resolve_ai_provider_driver(plugin: PluginRegistryItem) -> AiProviderDriver:
    entrypoint = plugin.entrypoints.ai_provider
    if entrypoint is None:
        raise ValueError(f"AI provider 插件 {plugin.id} 没有声明 entrypoints.ai_provider")

    builder = _load_ai_provider_driver_builder(plugin)
    driver = builder(plugin)
    if not _looks_like_ai_provider_driver(driver):
        raise TypeError(f"AI provider driver 入口返回了非法对象: {entrypoint}")
    return driver


def prime_ai_provider_driver_cache(plugin: PluginRegistryItem) -> None:
    if plugin.entrypoints.ai_provider is None:
        return
    _load_ai_provider_driver_builder(plugin)


def resolve_ai_provider_driver_for_profile(
    db: Session,
    *,
    provider_profile: AiProviderProfile,
    household_id: str | None = None,
) -> AiProviderDriver | None:
    plugin = _resolve_ai_provider_plugin_for_profile(
        db,
        provider_profile=provider_profile,
        household_id=household_id,
    )
    if plugin is None:
        return None
    return resolve_ai_provider_driver(plugin)


def _resolve_ai_provider_plugin_for_profile(
    db: Session,
    *,
    provider_profile: AiProviderProfile,
    household_id: str | None,
) -> PluginRegistryItem | None:
    from app.modules.ai_gateway.service import get_household_ai_provider_plugin_for_profile
    from app.modules.plugin.service import list_registered_plugins

    if household_id is not None:
        plugin = get_household_ai_provider_plugin_for_profile(
            db,
            household_id=household_id,
            provider_profile=provider_profile,
        )
        if plugin is not None:
            return plugin

    extra_config = load_json(provider_profile.extra_config_json) or {}
    adapter_code = _normalize_adapter_code(extra_config.get("adapter_code"))
    if adapter_code is None:
        return None

    snapshot = list_registered_plugins()
    for item in snapshot.items:
        capability = item.capabilities.ai_provider
        if capability is None:
            continue
        if capability.adapter_code == adapter_code:
            return item
    return None


def _looks_like_ai_provider_driver(value: object) -> bool:
    return all(callable(getattr(value, attr, None)) for attr in ("invoke", "ainvoke", "stream"))


def _load_ai_provider_driver_builder(plugin: PluginRegistryItem) -> Callable[[PluginRegistryItem], object]:
    entrypoint = plugin.entrypoints.ai_provider
    if entrypoint is None:
        raise ValueError(f"AI provider 插件 {plugin.id} 没有声明 entrypoints.ai_provider")

    cache_key = (plugin.id, entrypoint, plugin.manifest_path)
    builder = _AI_PROVIDER_DRIVER_BUILDERS.get(cache_key)
    if builder is not None:
        return builder

    with _plugin_runtime_import_path(plugin):
        loaded = load_entrypoint_callable(entrypoint)

    _AI_PROVIDER_DRIVER_BUILDERS[cache_key] = loaded
    return loaded


def _normalize_adapter_code(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


@contextmanager
def _plugin_runtime_import_path(plugin: PluginRegistryItem):
    plugin_root = plugin.runner_config.plugin_root if plugin.runner_config is not None else None
    if not plugin_root:
        plugin_root = str(Path(plugin.manifest_path).resolve().parent)
    if not plugin_root:
        yield
        return

    resolved_path = Path(plugin_root).resolve()
    candidate_paths = [str(resolved_path.parent), str(resolved_path)]
    inserted_paths: list[str] = []
    for candidate in candidate_paths:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            inserted_paths.append(candidate)
    try:
        yield
    finally:
        for candidate in reversed(inserted_paths):
            try:
                sys.path.remove(candidate)
            except ValueError:
                pass
