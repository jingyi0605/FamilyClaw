from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import contextmanager
import asyncio
from dataclasses import dataclass
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


SyncInvoke = Callable[..., provider_runtime.ProviderInvokeResult]
AsyncInvoke = Callable[..., asyncio.Future | object]
StreamInvoke = Callable[..., AsyncIterator[str]]


@dataclass(slots=True)
class _RuntimeBackedAiProviderDriver:
    sync_invoke: SyncInvoke
    async_invoke: Callable[..., object]
    stream_invoke: StreamInvoke

    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> provider_runtime.ProviderInvokeResult:
        _raise_if_simulated_failure(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )
        return self.sync_invoke(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        )

    async def ainvoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> provider_runtime.ProviderInvokeResult:
        _raise_if_simulated_failure(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )
        result = self.async_invoke(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        )
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]

    async def stream(
        self,
        *,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> AsyncIterator[str]:
        _raise_if_simulated_failure(
            capability=_resolve_stream_capability(provider_profile),
            provider_profile=provider_profile,
            payload=payload,
        )
        async for chunk in self.stream_invoke(
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk


def build_openai_compatible_driver(plugin: PluginRegistryItem | None = None) -> AiProviderDriver:
    return _RuntimeBackedAiProviderDriver(
        sync_invoke=provider_runtime._invoke_openai_compatible,
        async_invoke=provider_runtime._ainvoke_openai_compatible,
        stream_invoke=provider_runtime.stream_provider_invoke,
    )


def build_anthropic_messages_driver(plugin: PluginRegistryItem | None = None) -> AiProviderDriver:
    return _RuntimeBackedAiProviderDriver(
        sync_invoke=provider_runtime._invoke_anthropic_messages,
        async_invoke=_build_threaded_async_invoke(provider_runtime._invoke_anthropic_messages),
        stream_invoke=provider_runtime.stream_provider_invoke,
    )


def build_gemini_generate_content_driver(plugin: PluginRegistryItem | None = None) -> AiProviderDriver:
    return _RuntimeBackedAiProviderDriver(
        sync_invoke=provider_runtime._invoke_gemini_generate_content,
        async_invoke=_build_threaded_async_invoke(provider_runtime._invoke_gemini_generate_content),
        stream_invoke=provider_runtime.stream_provider_invoke,
    )


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


def _build_threaded_async_invoke(sync_invoke: SyncInvoke) -> Callable[..., object]:
    async def _invoke_async(**kwargs):
        return await asyncio.to_thread(sync_invoke, **kwargs)

    return _invoke_async


def _raise_if_simulated_failure(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
) -> None:
    extra_config = load_json(provider_profile.extra_config_json) or {}
    if not provider_runtime._should_fail(
        extra_config=extra_config,
        payload=payload,
        capability=capability,
        provider_code=provider_profile.provider_code,
    ):
        return
    error_code = str(extra_config.get("simulate_error_code") or "provider_failed")
    raise provider_runtime.ProviderRuntimeError(error_code, f"{provider_profile.provider_code} simulated failure")


def _resolve_stream_capability(provider_profile: AiProviderProfile) -> AiCapability:
    supported_capabilities = load_json(provider_profile.supported_capabilities_json) or []
    if "text" in supported_capabilities:
        return "text"
    if supported_capabilities:
        return supported_capabilities[0]
    return "text"


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

    resolved_root = str(Path(plugin_root).resolve())
    inserted = False
    if resolved_root not in sys.path:
        sys.path.insert(0, resolved_root)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(resolved_root)
            except ValueError:
                pass
