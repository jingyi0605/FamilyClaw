from typing import cast

from app.core.config import settings
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.ai_gateway import repository
from app.modules.ai_gateway.models import AiCapabilityRoute, AiModelCallLog, AiProviderProfile
from app.modules.ai_gateway.schemas import (
    AiCapability,
    AiApiFamily,
    AiCapabilityRouteRead,
    AiCapabilityRouteUpsert,
    AiModelCallLogCreate,
    AiModelCallLogRead,
    AiModelCallStatus,
    AiPrivacyLevel,
    AiProviderProfileCreate,
    AiProviderProfileRead,
    AiRoutingMode,
    AiTransportType,
    AiProviderProfileUpdate,
)
from app.modules.plugin.schemas import PluginRegistryItem
from sqlalchemy.orm import Session


class AiGatewayConfigurationError(ValueError):
    pass


class AiGatewayNotFoundError(LookupError):
    pass


def get_capability_resolution_order(capability: AiCapability) -> tuple[AiCapability, ...]:
    if capability == "intent_recognition":
        return ("intent_recognition", "text")
    return (capability,)


def provider_supports_capability(
    capability: AiCapability,
    supported_capabilities: list[str] | tuple[str, ...],
) -> bool:
    return any(candidate in supported_capabilities for candidate in get_capability_resolution_order(capability))


def list_provider_profiles(
    db: Session,
    *,
    household_id: str | None = None,
    enabled: bool | None = None,
    capability: AiCapability | None = None,
) -> list[AiProviderProfileRead]:
    rows = repository.list_provider_profiles(db, enabled=enabled)
    plugin_map = _build_household_ai_provider_plugin_map(db, household_id=household_id) if household_id is not None else {}
    profiles = [_to_provider_profile_read(row, plugin=_resolve_profile_plugin(row, plugin_map=plugin_map)) for row in rows]
    if capability is None:
        return profiles
    return [profile for profile in profiles if provider_supports_capability(capability, profile.supported_capabilities)]


def list_provider_adapters_for_household(
    db: Session,
    *,
    household_id: str,
) -> list["AiProviderAdapterRead"]:
    from app.modules.ai_gateway.provider_config_service import list_provider_adapters_from_plugins

    plugin_map = _build_household_ai_provider_plugin_map(db, household_id=household_id)
    plugins = [plugin for plugin in plugin_map.values() if plugin.enabled]
    return list_provider_adapters_from_plugins(plugins)


def create_provider_profile(
    db: Session,
    payload: AiProviderProfileCreate,
    *,
    household_id: str | None = None,
) -> AiProviderProfileRead:
    existing = repository.get_provider_profile_by_code(db, payload.provider_code)
    if existing is not None:
        raise AiGatewayConfigurationError("provider_code 已存在")

    if household_id is not None:
        _require_available_household_ai_provider_plugin(
            db,
            household_id=household_id,
            adapter_code=_extract_adapter_code(payload.extra_config),
        )

    normalized_extra_config = _normalize_provider_extra_config(
        payload.extra_config,
        transport_type=payload.transport_type,
        api_family=payload.api_family,
        base_url=payload.base_url,
    )
    row = AiProviderProfile(
        id=new_uuid(),
        provider_code=payload.provider_code,
        display_name=payload.display_name,
        transport_type=payload.transport_type,
        api_family=payload.api_family,
        base_url=payload.base_url,
        api_version=payload.api_version,
        secret_ref=payload.secret_ref,
        enabled=payload.enabled,
        supported_capabilities_json=dump_json(payload.supported_capabilities) or "[]",
        privacy_level=payload.privacy_level,
        latency_budget_ms=payload.latency_budget_ms,
        cost_policy_json=dump_json(payload.cost_policy),
        extra_config_json=dump_json(normalized_extra_config),
        updated_at=utc_now_iso(),
    )
    repository.add_provider_profile(db, row)
    db.flush()
    plugin = _resolve_profile_plugin(
        row,
        plugin_map=_build_household_ai_provider_plugin_map(db, household_id=household_id) if household_id is not None else {},
    )
    return _to_provider_profile_read(row, plugin=plugin)


def update_provider_profile(
    db: Session,
    provider_profile_id: str,
    payload: AiProviderProfileUpdate,
    *,
    household_id: str | None = None,
) -> AiProviderProfileRead:
    row = repository.get_provider_profile(db, provider_profile_id)
    if row is None:
        raise AiGatewayNotFoundError("provider profile 不存在")

    data = payload.model_dump(exclude_unset=True)
    next_extra_config = cast(dict[str, object], load_json(row.extra_config_json) or {})
    if "extra_config" in data:
        next_extra_config = cast(dict[str, object], data["extra_config"])
    if household_id is not None:
        _require_available_household_ai_provider_plugin(
            db,
            household_id=household_id,
            adapter_code=_extract_adapter_code(next_extra_config),
        )
    if "display_name" in data:
        row.display_name = data["display_name"]
    if "transport_type" in data:
        row.transport_type = data["transport_type"]
    if "api_family" in data:
        row.api_family = data["api_family"]
    if "base_url" in data:
        row.base_url = data["base_url"]
    if "api_version" in data:
        row.api_version = data["api_version"]
    if "secret_ref" in data:
        row.secret_ref = data["secret_ref"]
    if "enabled" in data:
        row.enabled = data["enabled"]
    if "supported_capabilities" in data:
        row.supported_capabilities_json = dump_json(data["supported_capabilities"]) or "[]"
    if "privacy_level" in data:
        row.privacy_level = data["privacy_level"]
    if "latency_budget_ms" in data:
        row.latency_budget_ms = data["latency_budget_ms"]
    if "cost_policy" in data:
        row.cost_policy_json = dump_json(data["cost_policy"])
    if "extra_config" in data:
        row.extra_config_json = dump_json(
            _normalize_provider_extra_config(
                cast(dict[str, object], data["extra_config"]),
                transport_type=data.get("transport_type", row.transport_type),
                api_family=data.get("api_family", row.api_family),
                base_url=data.get("base_url", row.base_url),
            )
        )

    row.updated_at = utc_now_iso()
    db.flush()
    plugin = _resolve_profile_plugin(
        row,
        plugin_map=_build_household_ai_provider_plugin_map(db, household_id=household_id) if household_id is not None else {},
    )
    return _to_provider_profile_read(row, plugin=plugin)


def delete_provider_profile(
    db: Session,
    provider_profile_id: str,
) -> None:
    row = repository.get_provider_profile(db, provider_profile_id)
    if row is None:
        raise AiGatewayNotFoundError("provider profile 不存在")

    for route in repository.list_all_capability_routes(db):
        fallback_ids = load_json(route.fallback_provider_profile_ids_json) or []
        if route.primary_provider_profile_id == provider_profile_id or provider_profile_id in fallback_ids:
            raise AiGatewayConfigurationError("供应商档案仍被能力路由引用，不能直接删除")

    from app.modules.agent import repository as agent_repository

    for runtime_policy in agent_repository.list_runtime_policies(db):
        model_bindings = load_json(runtime_policy.model_bindings_json) or []
        if any(isinstance(item, dict) and item.get("provider_profile_id") == provider_profile_id for item in model_bindings):
            raise AiGatewayConfigurationError("提供商档案仍被 Agent 模型绑定引用，不能直接删除")

        skill_bindings = load_json(runtime_policy.agent_skill_model_bindings_json) or []
        if any(isinstance(item, dict) and item.get("provider_profile_id") == provider_profile_id for item in skill_bindings):
            raise AiGatewayConfigurationError("提供商档案仍被 agent-skill 模型绑定引用，不能直接删除")

    repository.delete_provider_profile(db, row)
    db.flush()


def upsert_capability_route(db: Session, payload: AiCapabilityRouteUpsert) -> AiCapabilityRouteRead:
    _validate_capability_route(db, payload)

    row = repository.get_capability_route(
        db,
        capability=payload.capability,
        household_id=payload.household_id,
    )
    if row is None:
        row = AiCapabilityRoute(
            id=new_uuid(),
            capability=payload.capability,
            household_id=payload.household_id,
            primary_provider_profile_id=payload.primary_provider_profile_id,
            fallback_provider_profile_ids_json=dump_json(payload.fallback_provider_profile_ids) or "[]",
            routing_mode=payload.routing_mode,
            timeout_ms=payload.timeout_ms,
            max_retry_count=payload.max_retry_count,
            allow_remote=payload.allow_remote,
            prompt_policy_json=dump_json(payload.prompt_policy),
            response_policy_json=dump_json(payload.response_policy),
            enabled=payload.enabled,
            updated_at=utc_now_iso(),
        )
        repository.add_capability_route(db, row)
    else:
        row.primary_provider_profile_id = payload.primary_provider_profile_id
        row.fallback_provider_profile_ids_json = dump_json(payload.fallback_provider_profile_ids) or "[]"
        row.routing_mode = payload.routing_mode
        row.timeout_ms = payload.timeout_ms
        row.max_retry_count = payload.max_retry_count
        row.allow_remote = payload.allow_remote
        row.prompt_policy_json = dump_json(payload.prompt_policy)
        row.response_policy_json = dump_json(payload.response_policy)
        row.enabled = payload.enabled
        row.updated_at = utc_now_iso()

    db.flush()
    return _to_capability_route_read(row)


def list_capability_routes(
    db: Session,
    *,
    household_id: str | None = None,
) -> list[AiCapabilityRouteRead]:
    rows = repository.list_capability_routes(db, household_id=household_id)
    return [_to_capability_route_read(row) for row in rows]


def resolve_capability_route(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None = None,
) -> AiCapabilityRouteRead | None:
    for candidate_capability in get_capability_resolution_order(capability):
        if household_id is not None:
            household_route = repository.get_capability_route(
                db,
                capability=candidate_capability,
                household_id=household_id,
            )
            if household_route is not None:
                return _to_capability_route_read(household_route)

        global_route = repository.get_capability_route(
            db,
            capability=candidate_capability,
            household_id=None,
        )
        if global_route is not None:
            return _to_capability_route_read(global_route)
    return None


def log_model_call(db: Session, payload: AiModelCallLogCreate) -> AiModelCallLogRead:
    row = AiModelCallLog(
        id=new_uuid(),
        capability=payload.capability,
        provider_code=payload.provider_code,
        model_name=payload.model_name,
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        trace_id=payload.trace_id,
        input_policy=payload.input_policy,
        masked_fields_json=dump_json(payload.masked_fields),
        latency_ms=payload.latency_ms,
        usage_json=dump_json(payload.usage),
        status=payload.status,
        fallback_used=payload.fallback_used,
        error_code=payload.error_code,
        created_at=utc_now_iso(),
    )
    repository.add_model_call_log(db, row)
    db.flush()
    return _to_model_call_log_read(row)


def list_model_call_logs(
    db: Session,
    *,
    household_id: str | None = None,
    capability: AiCapability | None = None,
    limit: int = 50,
) -> list[AiModelCallLogRead]:
    rows = repository.list_model_call_logs(
        db,
        household_id=household_id,
        capability=capability,
        limit=limit,
    )
    return [_to_model_call_log_read(row) for row in rows]


def get_runtime_defaults() -> dict[str, object]:
    return settings.ai_runtime.model_dump(mode="json")


def _validate_capability_route(db: Session, payload: AiCapabilityRouteUpsert) -> None:
    provider_ids = [
        provider_id
        for provider_id in [payload.primary_provider_profile_id, *payload.fallback_provider_profile_ids]
        if provider_id
    ]
    if not provider_ids:
        return

    provider_rows = repository.list_provider_profiles_by_ids(db, provider_ids)
    provider_map = {row.id: row for row in provider_rows}

    missing_provider_ids = [provider_id for provider_id in provider_ids if provider_id not in provider_map]
    if missing_provider_ids:
        raise AiGatewayConfigurationError("能力路由绑定了不存在的供应商档案")

    for provider_id in provider_ids:
        provider_row = provider_map[provider_id]
        if not provider_row.enabled:
            raise AiGatewayConfigurationError("能力路由不能绑定已禁用的供应商档案")
        if payload.household_id is not None:
            _require_available_household_ai_provider_plugin(
                db,
                household_id=payload.household_id,
                adapter_code=_extract_adapter_code(load_json(provider_row.extra_config_json) or {}),
            )

        supported_capabilities = load_json(provider_row.supported_capabilities_json) or []
        if not provider_supports_capability(payload.capability, supported_capabilities):
            raise AiGatewayConfigurationError("供应商档案不支持当前 capability")

        if not payload.allow_remote and provider_row.privacy_level != "local_only":
            raise AiGatewayConfigurationError("allow_remote=false 时不能绑定远端供应商")

        if payload.routing_mode == "local_only" and provider_row.privacy_level != "local_only":
            raise AiGatewayConfigurationError("local_only 路由只能绑定本地供应商")


def _normalize_provider_extra_config(
    extra_config: dict[str, object] | None,
    *,
    transport_type: str | None,
    api_family: str | None,
    base_url: str | None,
) -> dict[str, object]:
    _ = transport_type, api_family, base_url
    return dict(extra_config or {})


def _to_provider_profile_read(
    row: AiProviderProfile,
    *,
    plugin: PluginRegistryItem | None = None,
) -> AiProviderProfileRead:
    transport_type: AiTransportType = cast(AiTransportType, row.transport_type)
    api_family: AiApiFamily = cast(AiApiFamily, row.api_family)
    privacy_level: AiPrivacyLevel = cast(AiPrivacyLevel, row.privacy_level)
    return AiProviderProfileRead(
        id=row.id,
        plugin_id=plugin.id if plugin is not None else None,
        plugin_enabled=plugin.enabled if plugin is not None else None,
        plugin_disabled_reason=plugin.disabled_reason if plugin is not None else None,
        provider_code=row.provider_code,
        display_name=row.display_name,
        transport_type=transport_type,
        api_family=api_family,
        base_url=row.base_url,
        api_version=row.api_version,
        secret_ref=row.secret_ref,
        enabled=row.enabled,
        supported_capabilities=load_json(row.supported_capabilities_json) or [],
        privacy_level=privacy_level,
        latency_budget_ms=row.latency_budget_ms,
        cost_policy=load_json(row.cost_policy_json) or {},
        extra_config=load_json(row.extra_config_json) or {},
        updated_at=row.updated_at,
    )


def _normalize_adapter_code(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _extract_adapter_code(extra_config: dict[str, object] | None) -> str | None:
    if not isinstance(extra_config, dict):
        return None
    return _normalize_adapter_code(extra_config.get("adapter_code"))


def _build_household_ai_provider_plugin_map(
    db: Session,
    *,
    household_id: str,
) -> dict[str, PluginRegistryItem]:
    from app.modules.plugin import list_registered_plugins_for_household

    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    plugin_map: dict[str, PluginRegistryItem] = {}
    for item in snapshot.items:
        capability = item.capabilities.ai_provider
        if "ai-provider" not in item.types or capability is None:
            continue
        plugin_map[capability.adapter_code] = item
    return plugin_map


def get_household_ai_provider_plugin_for_profile(
    db: Session,
    *,
    household_id: str,
    provider_profile: AiProviderProfile,
) -> PluginRegistryItem | None:
    return _resolve_profile_plugin(
        provider_profile,
        plugin_map=_build_household_ai_provider_plugin_map(db, household_id=household_id),
    )


def _resolve_profile_plugin(
    row: AiProviderProfile,
    *,
    plugin_map: dict[str, PluginRegistryItem],
) -> PluginRegistryItem | None:
    adapter_code = _extract_adapter_code(load_json(row.extra_config_json) or {})
    if adapter_code is None:
        return None
    return plugin_map.get(adapter_code)


def _require_available_household_ai_provider_plugin(
    db: Session,
    *,
    household_id: str,
    adapter_code: str | None,
) -> PluginRegistryItem:
    if adapter_code is None:
        raise AiGatewayConfigurationError("AI 供应商档案缺少 adapter_code，无法关联插件状态")

    plugin_map = _build_household_ai_provider_plugin_map(db, household_id=household_id)
    plugin = plugin_map.get(adapter_code)
    if plugin is None:
        raise AiGatewayConfigurationError(f"当前家庭看不到 AI 供应商插件 {adapter_code}")

    from app.modules.plugin import require_available_household_plugin

    return require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
        plugin_type="ai-provider",
    )

def _to_capability_route_read(row: AiCapabilityRoute) -> AiCapabilityRouteRead:
    capability: AiCapability = cast(AiCapability, row.capability)
    routing_mode: AiRoutingMode = cast(AiRoutingMode, row.routing_mode)
    return AiCapabilityRouteRead(
        id=row.id,
        capability=capability,
        household_id=row.household_id,
        primary_provider_profile_id=row.primary_provider_profile_id,
        fallback_provider_profile_ids=load_json(row.fallback_provider_profile_ids_json) or [],
        routing_mode=routing_mode,
        timeout_ms=row.timeout_ms,
        max_retry_count=row.max_retry_count,
        allow_remote=row.allow_remote,
        prompt_policy=load_json(row.prompt_policy_json) or {},
        response_policy=load_json(row.response_policy_json) or {},
        enabled=row.enabled,
        updated_at=row.updated_at,
    )


def _to_model_call_log_read(row: AiModelCallLog) -> AiModelCallLogRead:
    capability: AiCapability = cast(AiCapability, row.capability)
    status: AiModelCallStatus = cast(AiModelCallStatus, row.status)
    return AiModelCallLogRead(
        id=row.id,
        capability=capability,
        provider_code=row.provider_code,
        model_name=row.model_name,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        trace_id=row.trace_id,
        input_policy=row.input_policy,
        masked_fields=load_json(row.masked_fields_json) or [],
        latency_ms=row.latency_ms,
        usage=load_json(row.usage_json) or {},
        status=status,
        fallback_used=row.fallback_used,
        error_code=row.error_code,
        created_at=row.created_at,
    )
