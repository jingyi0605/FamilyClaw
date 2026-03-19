from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.modules.ai_gateway.provider_driver import resolve_ai_provider_driver
from app.modules.ai_gateway.schemas import AiProviderDiscoveredModelRead, AiProviderModelDiscoveryRead
from app.modules.plugin import list_registered_plugins_for_household, require_available_household_plugin
from app.modules.plugin.schemas import PluginRegistryItem


def discover_provider_models_for_household(
    db: Session,
    *,
    household_id: str,
    adapter_code: str,
    values: Mapping[str, object] | None = None,
) -> AiProviderModelDiscoveryRead:
    plugin = _require_household_ai_provider_plugin(
        db,
        household_id=household_id,
        adapter_code=adapter_code,
    )
    driver = resolve_ai_provider_driver(plugin)
    discover_models = getattr(driver, "discover_models", None)
    if not callable(discover_models):
        raise ValueError("当前供应商插件没有声明模型自动发现能力。")

    raw_models = discover_models(values=dict(values or {}))
    return AiProviderModelDiscoveryRead(
        adapter_code=adapter_code,
        models=_normalize_discovered_models(raw_models),
    )


def _require_household_ai_provider_plugin(
    db: Session,
    *,
    household_id: str,
    adapter_code: str,
) -> PluginRegistryItem:
    normalized_adapter_code = adapter_code.strip().lower()
    if not normalized_adapter_code:
        raise ValueError("adapter_code 不能为空。")

    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    matched_plugin = next(
        (
            item
            for item in snapshot.items
            if "ai-provider" in item.types
            and item.capabilities.ai_provider is not None
            and item.capabilities.ai_provider.adapter_code == normalized_adapter_code
        ),
        None,
    )
    if matched_plugin is None:
        raise ValueError(f"当前家庭看不到 AI 供应商插件 {normalized_adapter_code}。")

    return require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=matched_plugin.id,
        plugin_type="ai-provider",
    )


def _normalize_discovered_models(raw_models: object) -> list[AiProviderDiscoveredModelRead]:
    if not isinstance(raw_models, Sequence) or isinstance(raw_models, str):
        raise RuntimeError("模型发现结果格式不合法。")

    result: list[AiProviderDiscoveredModelRead] = []
    seen: set[str] = set()
    for item in raw_models:
        model_id, label = _normalize_model_item(item)
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        result.append(AiProviderDiscoveredModelRead(id=model_id, label=label or model_id))
    return result


def _normalize_model_item(item: object) -> tuple[str, str]:
    if isinstance(item, str):
        normalized = item.strip()
        return normalized, normalized
    if isinstance(item, Mapping):
        model_id = str(item.get("id") or item.get("model") or item.get("name") or "").strip()
        label = str(item.get("label") or item.get("display_name") or model_id).strip()
        return model_id, label or model_id
    return "", ""
