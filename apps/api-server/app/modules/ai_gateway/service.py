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
from sqlalchemy.orm import Session


class AiGatewayConfigurationError(ValueError):
    pass


class AiGatewayNotFoundError(LookupError):
    pass


def list_provider_profiles(
    db: Session,
    *,
    enabled: bool | None = None,
    capability: AiCapability | None = None,
) -> list[AiProviderProfileRead]:
    rows = repository.list_provider_profiles(db, enabled=enabled)
    profiles = [_to_provider_profile_read(row) for row in rows]
    if capability is None:
        return profiles
    return [profile for profile in profiles if capability in profile.supported_capabilities]


def create_provider_profile(db: Session, payload: AiProviderProfileCreate) -> AiProviderProfileRead:
    existing = repository.get_provider_profile_by_code(db, payload.provider_code)
    if existing is not None:
        raise AiGatewayConfigurationError("provider_code 已存在")

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
    return _to_provider_profile_read(row)


def update_provider_profile(
    db: Session,
    provider_profile_id: str,
    payload: AiProviderProfileUpdate,
) -> AiProviderProfileRead:
    row = repository.get_provider_profile(db, provider_profile_id)
    if row is None:
        raise AiGatewayNotFoundError("provider profile 不存在")

    data = payload.model_dump(exclude_unset=True)
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
    return _to_provider_profile_read(row)


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
    if household_id is not None:
        household_route = repository.get_capability_route(
            db,
            capability=capability,
            household_id=household_id,
        )
        if household_route is not None:
            return _to_capability_route_read(household_route)

    global_route = repository.get_capability_route(
        db,
        capability=capability,
        household_id=None,
    )
    if global_route is None:
        return None
    return _to_capability_route_read(global_route)


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

        supported_capabilities = load_json(provider_row.supported_capabilities_json) or []
        if payload.capability not in supported_capabilities:
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
    normalized = dict(extra_config or {})
    if not _should_disable_thinking_by_default(
        extra_config=normalized,
        transport_type=transport_type,
        api_family=api_family,
        base_url=base_url,
    ):
        return normalized

    default_request_body = normalized.get("default_request_body")
    if not isinstance(default_request_body, dict):
        default_request_body = {}

    if "enable_thinking" not in default_request_body:
        default_request_body["enable_thinking"] = False
    if "thinking_budget" not in default_request_body:
        default_request_body["thinking_budget"] = 128

    normalized["default_request_body"] = default_request_body
    return normalized


def _should_disable_thinking_by_default(
    *,
    extra_config: dict[str, object],
    transport_type: str | None,
    api_family: str | None,
    base_url: str | None,
) -> bool:
    transport = str(transport_type or "").strip().lower()
    api_family_value = str(api_family or "").strip().lower()
    adapter_code = str(extra_config.get("adapter_code") or "").strip().lower()
    model_name = str(extra_config.get("model_name") or extra_config.get("default_model") or "").strip().lower()
    base_url_value = str(base_url or "").strip().lower()

    if transport != "openai_compatible" and api_family_value != "openai_chat_completions":
        return False
    if adapter_code != "siliconflow" and "siliconflow.cn" not in base_url_value:
        return False

    is_qwen3_thinking = (
        "qwen3-" in model_name or model_name.endswith("qwen3") or "/qwen3" in model_name
    ) and "qwen3-235b" not in model_name
    is_qwen35_thinking = "qwen3.5-" in model_name or "/qwen3.5" in model_name
    is_deepseek_r1 = "deepseek-r1" in model_name
    return is_qwen3_thinking or is_qwen35_thinking or is_deepseek_r1


def _to_provider_profile_read(row: AiProviderProfile) -> AiProviderProfileRead:
    transport_type: AiTransportType = cast(AiTransportType, row.transport_type)
    api_family: AiApiFamily = cast(AiApiFamily, row.api_family)
    privacy_level: AiPrivacyLevel = cast(AiPrivacyLevel, row.privacy_level)
    return AiProviderProfileRead(
        id=row.id,
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
