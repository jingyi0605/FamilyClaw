from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.device.entity_store import replace_binding_entities
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.service import get_household_or_404
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin import config_crypto, repository as plugin_repository
from app.modules.plugin.service import PluginServiceError
from app.modules.region.models import RegionNode
from app.modules.region.plugin_runtime import sync_household_plugin_region_providers
from app.modules.region.providers import (
    BUILTIN_CN_MAINLAND_PROVIDER,
    RegionProviderExecutionError,
    region_provider_registry,
)
from app.modules.region.schemas import RegionNodeRead
from app.modules.region.service import resolve_household_region_context

from . import repository
from .entity_normalizer import normalize_weather_capabilities_payload as normalize_plugin_weather_capabilities_payload
from .models import WeatherDeviceBinding
from .providers import (
    WeatherProviderAdapter,
    WeatherProviderError,
    get_weather_provider as resolve_weather_provider,
)
from .schemas import (
    WEATHER_PROVIDER_DEFAULT_REFRESH_INTERVAL_MINUTES,
    WEATHER_PROVIDER_DEFAULT_TIMEOUT_SECONDS,
    WEATHER_PROVIDER_DEFAULT_TYPE,
    WEATHER_PROVIDER_DEFAULT_USER_AGENT,
    WeatherBindingCoordinateResolution,
    WeatherBindingType,
    WeatherCoordinate,
    WeatherDeviceBindingCreate,
    WeatherDeviceBindingRead,
    WeatherDeviceCardSnapshotRead,
    WeatherProviderConfig,
    WeatherSnapshot,
)


WEATHER_PLUGIN_ID = "official-weather"
WEATHER_PLUGIN_SCOPE_TYPE = "plugin"
WEATHER_PLUGIN_SCOPE_KEY = "default"
WEATHER_DEVICE_NAME = "家庭天气"
WEATHER_PLATFORM = "weather"
WEATHER_DEVICE_TYPE = "sensor"
WEATHER_DEVICE_VENDOR = "other"
WEATHER_STATE_PENDING = "pending_coordinate"
WEATHER_STATE_READY = "ready"
WEATHER_STATE_REFRESHING = "refreshing"
WEATHER_STATE_STALE = "stale"
WEATHER_STATE_ERROR = "error"
WEATHER_DEFAULT_BINDING_TYPE: WeatherBindingType = "default_household"
WEATHER_DEFAULT_BINDING_KEY = "default_household"
WEATHER_HOME_CARD_KEY = "weather-default"
WEATHER_HOME_CARD_KEY_PREFIX = "weather-"
WEATHER_BUILTIN_REGION_PROVIDER = BUILTIN_CN_MAINLAND_PROVIDER
WEATHER_REGION_PROVIDER_SELECTOR_MANUAL = "__manual__"
WEATHER_MESSAGE_WAITING_COORDINATE = "等待补充坐标"
WEATHER_MESSAGE_UNAVAILABLE = "天气数据暂不可用"
WEATHER_MESSAGE_NO_DATA = "暂无数据"
WEATHER_MESSAGE_STALE = "天气已降级为旧缓存"
WEATHER_ENTITY_PRESENTATION: dict[str, tuple[str, str | None]] = {
    "weather.condition": ("天气状态", None),
    "weather.temperature": ("温度", "°C"),
    "weather.humidity": ("湿度", "%"),
    "weather.wind_speed": ("风速", "m/s"),
    "weather.wind_direction": ("风向", "°"),
    "weather.pressure": ("气压", "hPa"),
    "weather.cloud_cover": ("云量", "%"),
    "weather.precipitation_next_1h": ("未来 1 小时降水", "mm"),
    "weather.forecast_6h": ("未来 6 小时摘要", None),
    "weather.updated_at": ("更新时间", None),
}


class WeatherServiceError(ValueError):
    def __init__(
        self,
        detail: str,
        *,
        error_code: str,
        field: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.field = field
        self.status_code = status_code

    def to_detail(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "detail": self.detail,
            "error_code": self.error_code,
            "timestamp": utc_now_iso(),
        }
        if self.field is not None:
            payload["field"] = self.field
        return payload


def get_weather_plugin_config(
    db: Session,
    *,
    household_id: str,
    plugin_id: str = WEATHER_PLUGIN_ID,
) -> WeatherProviderConfig:
    instance = plugin_repository.get_plugin_config_instance(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        scope_type=WEATHER_PLUGIN_SCOPE_TYPE,
        scope_key=WEATHER_PLUGIN_SCOPE_KEY,
    )
    if instance is None:
        return WeatherProviderConfig(
            provider_type=WEATHER_PROVIDER_DEFAULT_TYPE,
            refresh_interval_minutes=WEATHER_PROVIDER_DEFAULT_REFRESH_INTERVAL_MINUTES,
            request_timeout_seconds=WEATHER_PROVIDER_DEFAULT_TIMEOUT_SECONDS,
            user_agent=WEATHER_PROVIDER_DEFAULT_USER_AGENT,
        )

    data = load_json(instance.data_json) or {}
    secret_data = config_crypto.decrypt_plugin_config_secrets(instance.secret_data_encrypted)
    merged = {
        "provider_type": data.get("provider_type") or WEATHER_PROVIDER_DEFAULT_TYPE,
        "refresh_interval_minutes": data.get("refresh_interval_minutes")
        or WEATHER_PROVIDER_DEFAULT_REFRESH_INTERVAL_MINUTES,
        "request_timeout_seconds": data.get("request_timeout_seconds")
        or WEATHER_PROVIDER_DEFAULT_TIMEOUT_SECONDS,
        "user_agent": data.get("user_agent") or WEATHER_PROVIDER_DEFAULT_USER_AGENT,
        "openweather_api_key": secret_data.get("openweather_api_key"),
        "weatherapi_api_key": secret_data.get("weatherapi_api_key"),
    }
    return WeatherProviderConfig.model_validate(cast(dict[str, Any], merged))


def get_weather_provider(config: WeatherProviderConfig) -> WeatherProviderAdapter:
    return resolve_weather_provider(config.provider_type)


def get_weather_integration_instance_config(
    db: Session,
    *,
    integration_instance_id: str,
    plugin_id: str = WEATHER_PLUGIN_ID,
) -> dict[str, Any]:
    config_instance = plugin_repository.get_plugin_config_instance_for_integration_instance(
        db,
        integration_instance_id=integration_instance_id,
        plugin_id=plugin_id,
        scope_type="integration_instance",
    )
    if config_instance is None:
        return {}
    payload = load_json(config_instance.data_json)
    return payload if isinstance(payload, dict) else {}


def run_weather_integration_sync(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    instance = _require_weather_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    instance_config = get_weather_integration_instance_config(db, integration_instance_id=integration_instance_id)
    candidate = _build_weather_candidate_for_instance(
        db,
        instance=instance,
        instance_config=instance_config,
    )
    selected_ids = {item.strip() for item in (selected_external_ids or []) if isinstance(item, str) and item.strip()}
    if sync_scope == "device_candidates":
        return {
            "sync_scope": sync_scope,
            "message": "天气设备候选已生成",
            "items": [candidate],
            "records": [],
            "dashboard_snapshots": [],
            "instance_status": _build_instance_status_from_weather_binding(None),
        }
    if sync_scope == "room_candidates":
        return {
            "sync_scope": sync_scope,
            "message": "天气集成不提供房间候选",
            "items": [],
            "records": [],
            "dashboard_snapshots": [],
            "instance_status": _build_instance_status_from_weather_binding(None),
        }
    if sync_scope == "device_sync" and selected_ids and str(candidate["external_device_id"]) not in selected_ids:
        return {
            "sync_scope": sync_scope,
            "message": "没有匹配到需要同步的天气设备",
            "summary": {
                "household_id": household_id,
                "created_devices": 0,
                "updated_devices": 0,
                "created_bindings": 0,
                "created_rooms": 0,
                "assigned_rooms": 0,
                "skipped_entities": 1,
                "failed_entities": 0,
                "devices": [],
                "failures": [],
            },
            "dashboard_snapshots": [],
            "records": [],
            "instance_status": _build_instance_status_from_weather_binding(None),
        }

    try:
        weather_binding, created_device, created_binding = ensure_weather_device_for_integration_instance(
            db,
            instance=instance,
            instance_config=instance_config,
        )
        refreshed_binding = refresh_weather_device_binding(db, weather_binding=weather_binding, force=True)
        dashboard_snapshot = build_weather_dashboard_snapshot_upsert(db, weather_binding=refreshed_binding)
        status_payload = _build_instance_status_from_weather_binding(refreshed_binding)
    except PluginServiceError as exc:
        return {
            "sync_scope": sync_scope,
            "message": "天气同步失败",
            "summary": {
                "household_id": household_id,
                "created_devices": 0,
                "updated_devices": 0,
                "created_bindings": 0,
                "created_rooms": 0,
                "assigned_rooms": 0,
                "skipped_entities": 0,
                "failed_entities": 1,
                "devices": [],
                "failures": [{"reason": exc.detail}],
            },
            "dashboard_snapshots": [],
            "records": [],
            "instance_status": {
                "success": False,
                "degraded": True,
                "error_code": exc.error_code,
                "error_message": exc.detail,
                "refreshed_at": utc_now_iso(),
            },
        }
    if sync_scope == "room_sync":
        return {
            "sync_scope": sync_scope,
            "message": "天气集成不提供房间同步",
            "summary": {
                "created_rooms": 0,
                "matched_entities": 0,
                "skipped_entities": 0,
                "rooms": [],
            },
            "dashboard_snapshots": [dashboard_snapshot],
            "records": [],
            "instance_status": status_payload,
        }

    return {
        "sync_scope": sync_scope,
        "message": "天气设备同步完成",
        "summary": {
            "household_id": household_id,
            "created_devices": 1 if created_device else 0,
            "updated_devices": 0 if created_device else 1,
            "created_bindings": 1 if created_binding else 0,
            "created_rooms": 0,
            "assigned_rooms": 0,
            "skipped_entities": 0,
            "failed_entities": 0 if status_payload["success"] else 1,
            "devices": [refreshed_binding.device_id],
            "failures": (
                []
                if status_payload["success"]
                else [
                    {
                        "entity_id": refreshed_binding.device_id,
                        "reason": status_payload.get("error_message") or "天气设备同步失败",
                    }
                ]
            ),
        },
        "dashboard_snapshots": [dashboard_snapshot],
        "records": [],
        "instance_status": status_payload,
    }


def ensure_weather_device_for_integration_instance(
    db: Session,
    *,
    instance: IntegrationInstance,
    instance_config: dict[str, Any] | None = None,
) -> tuple[WeatherDeviceBinding, bool, bool]:
    normalized_config = instance_config or {}
    binding_type = _resolve_instance_binding_type(normalized_config)
    binding_key = _build_binding_key_from_instance_config(normalized_config)
    provider_code, region_code = _resolve_region_binding_codes(normalized_config)
    display_name = _resolve_instance_display_name(
        db,
        instance=instance,
        binding_type=binding_type,
        instance_config=normalized_config,
    )
    existing_binding = repository.get_weather_device_binding_by_key(
        db,
        household_id=instance.household_id,
        binding_key=binding_key,
    )
    current_binding = repository.get_weather_device_binding_for_integration_instance(
        db,
        integration_instance_id=instance.id,
    )

    if existing_binding is not None and current_binding is not None and existing_binding.id != current_binding.id:
        raise PluginServiceError(
            "当前天气地区已经被别的实例占用。",
            error_code="integration_instance_conflict",
            field="region_code",
            status_code=409,
        )
    if existing_binding is not None and current_binding is None:
        current_binding = existing_binding
    if current_binding is None:
        return _create_weather_binding_for_instance(
            db,
            instance=instance,
            binding_type=binding_type,
            binding_key=binding_key,
            display_name=display_name,
            instance_config=normalized_config,
        )

    device = _require_device(db, current_binding.device_id)
    device.name = display_name
    device.updated_at = utc_now_iso()
    db.add(device)
    device_binding = _require_weather_device_binding_row(db, device_id=device.id)
    device_binding.integration_instance_id = instance.id
    device_binding.plugin_id = instance.plugin_id
    device_binding.external_entity_id = f"weather.{binding_key}"
    device_binding.external_device_id = f"weather.{binding_key}"
    current_binding.binding_type = binding_type
    current_binding.binding_key = binding_key
    current_binding.provider_code = provider_code
    current_binding.region_code = region_code
    current_binding.updated_at = utc_now_iso()
    db.add(device_binding)
    db.add(current_binding)
    db.flush()
    return current_binding, False, False


def build_weather_dashboard_snapshot_upsert(
    db: Session,
    *,
    weather_binding: WeatherDeviceBinding,
) -> dict[str, Any]:
    snapshot = _build_weather_card_snapshot(
        db=db,
        weather_binding=weather_binding,
        card_key=_build_weather_card_key(weather_binding),
    )
    payload = dict(snapshot.payload)
    payload["card_kind"] = "weather"
    payload["card_state"] = _map_weather_card_state(snapshot.state)
    payload["device_id"] = weather_binding.device_id
    payload["binding_type"] = weather_binding.binding_type
    return {
        "card_key": snapshot.card_key,
        "placement": "home",
        "title": _require_device(db, weather_binding.device_id).name,
        "subtitle": "家庭默认天气" if weather_binding.binding_type == WEATHER_DEFAULT_BINDING_TYPE else "附加地区天气",
        "payload": payload,
        "actions": [],
        "generated_at": snapshot.generated_at,
        "expires_at": snapshot.expires_at,
    }


def _build_instance_status_from_weather_binding(weather_binding: WeatherDeviceBinding | None) -> dict[str, Any]:
    if weather_binding is None:
        return {
            "success": True,
            "degraded": False,
            "refreshed_at": utc_now_iso(),
        }
    if weather_binding.state == WEATHER_STATE_READY:
        return {
            "success": True,
            "degraded": False,
            "refreshed_at": weather_binding.last_success_at or weather_binding.updated_at,
        }
    if weather_binding.state == WEATHER_STATE_STALE:
        return {
            "success": False,
            "degraded": True,
            "error_code": weather_binding.last_error_code or "weather_snapshot_stale",
            "error_message": weather_binding.last_error_message or "天气已降级为旧缓存",
            "refreshed_at": weather_binding.last_refresh_attempt_at or weather_binding.updated_at,
        }
    return {
        "success": False,
        "degraded": True,
        "error_code": weather_binding.last_error_code or "weather_sync_unavailable",
        "error_message": weather_binding.last_error_message or "天气数据暂不可用",
        "refreshed_at": weather_binding.last_refresh_attempt_at or weather_binding.updated_at,
    }


def _build_weather_candidate_for_instance(
    db: Session,
    *,
    instance: IntegrationInstance,
    instance_config: dict[str, Any],
) -> dict[str, Any]:
    binding_type = _resolve_instance_binding_type(instance_config)
    binding_key = _build_binding_key_from_instance_config(instance_config)
    return {
        "external_device_id": binding_key,
        "primary_entity_id": "weather.condition",
        "name": _resolve_instance_display_name(
            db,
            instance=instance,
            binding_type=binding_type,
            instance_config=instance_config,
        ),
        "room_name": None,
        "device_type": WEATHER_DEVICE_TYPE,
        "entity_count": 10,
        "already_synced": repository.get_weather_device_binding_for_integration_instance(
            db,
            integration_instance_id=instance.id,
        )
        is not None,
    }


def _build_weather_card_key(weather_binding: WeatherDeviceBinding) -> str:
    if weather_binding.binding_type == WEATHER_DEFAULT_BINDING_TYPE:
        return WEATHER_HOME_CARD_KEY
    return f"{WEATHER_HOME_CARD_KEY_PREFIX}{weather_binding.device_id}"


def _map_weather_card_state(snapshot_state: str) -> str:
    if snapshot_state == "ready":
        return "ready"
    if snapshot_state == "stale":
        return "stale"
    if snapshot_state == WEATHER_STATE_PENDING:
        return "empty"
    return "error"


def create_weather_device_binding(
    db: Session,
    *,
    household_id: str,
    payload: WeatherDeviceBindingCreate,
    plugin_id: str = WEATHER_PLUGIN_ID,
) -> WeatherDeviceBinding:
    from app.modules.plugin.service import require_available_household_plugin

    require_available_household_plugin(db, household_id=household_id, plugin_id=plugin_id, plugin_type="integration")
    household = get_household_or_404(db, household_id)
    display_name = (
        _normalize_device_name(payload.display_name)
        if payload.display_name
        else _build_display_name_from_payload(db, household_id=household_id, payload=payload)
    )
    binding_key = _build_binding_key(payload)
    existing = repository.get_weather_device_binding_by_key(
        db,
        household_id=household_id,
        binding_key=binding_key,
    )
    if existing is not None:
        raise WeatherServiceError(
            "当前绑定已经存在，不允许重复创建相同天气设备。",
            error_code="weather_device_binding_duplicate",
            field="binding_type",
            status_code=409,
        )

    if payload.binding_type == "region_node":
        node = _resolve_region_catalog_node(
            db,
            household_id=household_id,
            provider_code=cast(str, payload.provider_code),
            region_code=cast(str, payload.region_code),
        )
        if node is None:
            raise WeatherServiceError(
                "当前地区节点不存在，或者对应的地区 provider 不可用。",
                error_code="weather_region_not_found",
                field="region_code",
                status_code=404,
            )
        if node.latitude is None or node.longitude is None:
            raise WeatherServiceError(
                "当前地区节点还没有可用坐标，不能创建天气设备。",
                error_code="weather_coordinate_missing",
                field="region_code",
            )

    now = utc_now_iso()
    device = Device(
        id=new_uuid(),
        household_id=household.id,
        room_id=None,
        name=display_name,
        device_type=WEATHER_DEVICE_TYPE,
        vendor=WEATHER_DEVICE_VENDOR,
        status="inactive",
        controllable=0,
        created_at=now,
        updated_at=now,
    )
    db.add(device)
    db.flush()

    placeholder_payload = normalize_plugin_weather_capabilities_payload(
        _build_placeholder_capabilities(device=device, state=WEATHER_STATE_PENDING)
    )
    device_binding = DeviceBinding(
        id=new_uuid(),
        device_id=device.id,
        integration_instance_id=None,
        platform=WEATHER_PLATFORM,
        external_entity_id=f"weather.{binding_key}",
        external_device_id=f"weather.{binding_key}",
        plugin_id=plugin_id,
        binding_version=1,
        capabilities="{}",
        last_sync_at=None,
    )
    db.add(device_binding)
    _store_weather_binding_payload(db, device_binding=device_binding, payload=placeholder_payload)

    weather_binding = WeatherDeviceBinding(
        id=new_uuid(),
        device_id=device.id,
        household_id=household.id,
        plugin_id=plugin_id,
        binding_type=payload.binding_type,
        binding_key=binding_key,
        provider_code=payload.provider_code,
        region_code=payload.region_code,
        state=WEATHER_STATE_PENDING,
        latest_snapshot_json=None,
        cache_expires_at=None,
        last_refresh_attempt_at=None,
        last_success_at=None,
        last_error_code=None,
        last_error_message=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_weather_device_binding(db, weather_binding)
    db.flush()
    refresh_weather_device_binding(db, weather_binding=weather_binding, force=True)
    return weather_binding


def list_weather_device_binding_reads(
    db: Session,
    *,
    household_id: str,
) -> list[WeatherDeviceBindingRead]:
    return [_to_weather_binding_read(db, row) for row in repository.list_weather_device_bindings(db, household_id=household_id)]


def list_weather_card_snapshots(
    db: Session,
    *,
    household_id: str,
    card_key: str = WEATHER_HOME_CARD_KEY,
) -> list[WeatherDeviceCardSnapshotRead]:
    bindings = repository.list_weather_device_bindings(db, household_id=household_id)
    ordered_bindings = sorted(
        bindings,
        key=lambda item: (
            0 if item.binding_type == WEATHER_DEFAULT_BINDING_TYPE else 1,
            _require_device(db, item.device_id).name,
            item.device_id,
        ),
    )
    snapshots: list[WeatherDeviceCardSnapshotRead] = []
    for binding in ordered_bindings:
        snapshots.append(_build_weather_card_snapshot(db=db, weather_binding=binding, card_key=card_key))
    return snapshots


def delete_weather_device(
    db: Session,
    *,
    household_id: str,
    device_id: str,
) -> None:
    weather_binding = repository.get_weather_device_binding_for_household_device(
        db,
        household_id=household_id,
        device_id=device_id,
    )
    if weather_binding is None:
        raise WeatherServiceError(
            "天气设备不存在。",
            error_code="weather_device_not_found",
            field="device_id",
            status_code=404,
        )
    if weather_binding.binding_type == WEATHER_DEFAULT_BINDING_TYPE:
        raise WeatherServiceError(
            "默认家庭天气设备不能删除。",
            error_code="weather_default_device_delete_forbidden",
            field="device_id",
            status_code=409,
        )
    device = db.get(Device, device_id)
    if device is None:
        raise WeatherServiceError(
            "天气设备不存在。",
            error_code="weather_device_not_found",
            field="device_id",
            status_code=404,
        )
    db.delete(device)
    db.flush()


def refresh_weather_device_for_household(
    db: Session,
    *,
    household_id: str,
    device_id: str,
    force: bool = True,
) -> WeatherDeviceBinding:
    from app.modules.plugin.service import require_available_household_plugin

    require_available_household_plugin(db, household_id=household_id, plugin_id=WEATHER_PLUGIN_ID, plugin_type="integration")
    weather_binding = repository.get_weather_device_binding_for_household_device(
        db,
        household_id=household_id,
        device_id=device_id,
    )
    if weather_binding is None:
        raise WeatherServiceError(
            "天气设备不存在。",
            error_code="weather_device_not_found",
            field="device_id",
            status_code=404,
        )
    return refresh_weather_device_binding(db, weather_binding=weather_binding, force=force)


def get_weather_card_snapshot(
    db: Session,
    *,
    household_id: str,
    device_id: str,
    card_key: str = WEATHER_HOME_CARD_KEY,
) -> WeatherDeviceCardSnapshotRead:
    if card_key != WEATHER_HOME_CARD_KEY:
        raise WeatherServiceError(
            f"不支持的天气卡片: {card_key}",
            error_code="weather_card_not_found",
            field="card_key",
            status_code=404,
        )
    weather_binding = refresh_weather_device_for_household(
        db,
        household_id=household_id,
        device_id=device_id,
        force=False,
    )
    return _build_weather_card_snapshot(db=db, weather_binding=weather_binding)


def ensure_default_weather_device(
    db: Session,
    *,
    household_id: str,
    plugin_id: str = WEATHER_PLUGIN_ID,
) -> WeatherDeviceBinding:
    household = get_household_or_404(db, household_id)
    weather_binding = repository.get_weather_device_binding_by_key(
        db,
        household_id=household_id,
        binding_key=WEATHER_DEFAULT_BINDING_KEY,
    )
    device: Device | None = None
    device_binding: DeviceBinding | None = None
    if weather_binding is not None:
        device = db.get(Device, weather_binding.device_id)
        device_binding = _get_device_binding(db, device_id=weather_binding.device_id)

    now = utc_now_iso()
    if device is None:
        device = Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=None,
            name=WEATHER_DEVICE_NAME,
            device_type=WEATHER_DEVICE_TYPE,
            vendor=WEATHER_DEVICE_VENDOR,
            status="inactive",
            controllable=0,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
        db.flush()

    if device_binding is None:
        placeholder_payload = normalize_plugin_weather_capabilities_payload(
            _build_placeholder_capabilities(device=device, state=WEATHER_STATE_PENDING)
        )
        device_binding = DeviceBinding(
            id=new_uuid(),
            device_id=device.id,
            integration_instance_id=None,
            platform=WEATHER_PLATFORM,
            external_entity_id="weather.default_household",
            external_device_id="weather.default_household",
            plugin_id=plugin_id,
            binding_version=1,
            capabilities="{}",
            last_sync_at=None,
        )
        db.add(device_binding)
        _store_weather_binding_payload(db, device_binding=device_binding, payload=placeholder_payload)

    if weather_binding is None:
        weather_binding = WeatherDeviceBinding(
            id=new_uuid(),
            device_id=device.id,
            household_id=household.id,
            plugin_id=plugin_id,
            binding_type=WEATHER_DEFAULT_BINDING_TYPE,
            binding_key=WEATHER_DEFAULT_BINDING_KEY,
            provider_code=None,
            region_code=None,
            state=WEATHER_STATE_PENDING,
            latest_snapshot_json=None,
            cache_expires_at=None,
            last_refresh_attempt_at=None,
            last_success_at=None,
            last_error_code=None,
            last_error_message=None,
            created_at=now,
            updated_at=now,
        )
        repository.add_weather_device_binding(db, weather_binding)
    else:
        device.name = WEATHER_DEVICE_NAME
        db.add(device)

    db.flush()
    refresh_weather_device_binding(db, weather_binding=weather_binding, force=True)
    return weather_binding


def refresh_weather_device_binding(
    db: Session,
    *,
    weather_binding: WeatherDeviceBinding,
    force: bool = False,
) -> WeatherDeviceBinding:
    device = _require_device(db, weather_binding.device_id)
    device_binding = _require_weather_device_binding_row(db, device_id=device.id)
    now = _utc_now()
    current_snapshot = _load_latest_snapshot(weather_binding)

    if (
        not force
        and weather_binding.state == WEATHER_STATE_READY
        and current_snapshot is not None
        and _cache_is_valid(weather_binding, now=now)
    ):
        _apply_snapshot_to_device(
            db,
            device=device,
            device_binding=device_binding,
            weather_binding=weather_binding,
            snapshot=current_snapshot,
            state=WEATHER_STATE_READY,
        )
        _sync_default_dashboard_snapshot(db, weather_binding=weather_binding)
        return weather_binding

    weather_binding.state = WEATHER_STATE_REFRESHING
    weather_binding.last_refresh_attempt_at = _to_utc_iso(now)
    weather_binding.updated_at = weather_binding.last_refresh_attempt_at
    device.updated_at = weather_binding.last_refresh_attempt_at
    db.add(weather_binding)
    db.add(device)
    db.flush()

    resolution = _resolve_binding_coordinate(db, weather_binding=weather_binding)
    if not resolution.available or resolution.coordinate is None:
        _apply_missing_coordinate(
            db,
            device=device,
            device_binding=device_binding,
            weather_binding=weather_binding,
            detail=resolution.detail or "当前天气设备没有可用坐标。",
        )
        _sync_default_dashboard_snapshot(db, weather_binding=weather_binding)
        return weather_binding

    try:
        config = get_weather_plugin_config(db, household_id=weather_binding.household_id, plugin_id=weather_binding.plugin_id)
        provider = get_weather_provider(config)
        snapshot = provider.fetch_weather(coordinate=resolution.coordinate, config=config)
    except ValueError:
        _apply_refresh_error(
            db,
            device=device,
            device_binding=device_binding,
            weather_binding=weather_binding,
            error_code="weather_provider_key_missing",
            error_message="当前天气源配置不完整，缺少必需 key。",
            retryable=False,
            stale_snapshot=current_snapshot,
        )
        _sync_default_dashboard_snapshot(db, weather_binding=weather_binding)
        return weather_binding
    except WeatherProviderError as exc:
        _apply_refresh_error(
            db,
            device=device,
            device_binding=device_binding,
            weather_binding=weather_binding,
            error_code=exc.error_code,
            error_message=exc.detail,
            retryable=exc.retryable,
            stale_snapshot=current_snapshot,
        )
        _sync_default_dashboard_snapshot(db, weather_binding=weather_binding)
        return weather_binding

    _apply_refresh_success(
        db,
        device=device,
        device_binding=device_binding,
        weather_binding=weather_binding,
        snapshot=snapshot,
        cache_minutes=config.refresh_interval_minutes,
    )
    _sync_default_dashboard_snapshot(db, weather_binding=weather_binding)
    return weather_binding


def get_weather_device_binding_for_device(
    db: Session,
    *,
    device_id: str,
) -> WeatherDeviceBinding | None:
    return repository.get_weather_device_binding_for_device(db, device_id=device_id)


def get_weather_device_binding_read_for_household_device(
    db: Session,
    *,
    household_id: str,
    device_id: str,
) -> WeatherDeviceBindingRead:
    weather_binding = repository.get_weather_device_binding_for_household_device(
        db,
        household_id=household_id,
        device_id=device_id,
    )
    if weather_binding is None:
        raise WeatherServiceError(
            "天气设备不存在。",
            error_code="weather_device_not_found",
            field="device_id",
            status_code=404,
        )
    return _to_weather_binding_read(db, weather_binding)


def _require_weather_integration_instance(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> IntegrationInstance:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None or instance.household_id != household_id or instance.plugin_id != WEATHER_PLUGIN_ID:
        raise PluginServiceError(
            "天气集成实例不存在。",
            error_code="integration_instance_not_found",
            field="integration_instance_id",
            status_code=404,
        )
    return instance


def _resolve_instance_binding_type(instance_config: dict[str, Any]) -> WeatherBindingType:
    binding_type = _read_optional_text(instance_config.get("binding_type"))
    if binding_type == WEATHER_DEFAULT_BINDING_TYPE:
        return WEATHER_DEFAULT_BINDING_TYPE
    return "region_node"


def _build_binding_key_from_instance_config(instance_config: dict[str, Any]) -> str:
    binding_type = _resolve_instance_binding_type(instance_config)
    if binding_type == WEATHER_DEFAULT_BINDING_TYPE:
        return WEATHER_DEFAULT_BINDING_KEY
    provider_code, region_code = _resolve_region_binding_codes(instance_config)
    if not provider_code or not region_code:
        raise PluginServiceError(
            "附加地区天气必须绑定可用的地区节点。",
            error_code="integration_instance_config_invalid",
            field=_resolve_region_binding_error_field(instance_config),
            status_code=400,
        )
    return f"region_node:{provider_code}:{region_code}"


def _resolve_instance_display_name(
    db: Session,
    *,
    instance: IntegrationInstance,
    binding_type: WeatherBindingType,
    instance_config: dict[str, Any],
) -> str:
    if binding_type == WEATHER_DEFAULT_BINDING_TYPE:
        return _normalize_device_name(instance.display_name or WEATHER_DEVICE_NAME)
    provider_code, region_code = _resolve_region_binding_codes(instance_config)
    if provider_code and region_code:
        node = _resolve_region_binding_node(
            db,
            household_id=instance.household_id,
            instance_config=instance_config,
            raise_on_error=False,
        )
        if node is not None:
            return _normalize_device_name(node.full_name)
    return _normalize_device_name(instance.display_name or "地区天气")


def _create_weather_binding_for_instance(
    db: Session,
    *,
    instance: IntegrationInstance,
    binding_type: WeatherBindingType,
    binding_key: str,
    display_name: str,
    instance_config: dict[str, Any],
) -> tuple[WeatherDeviceBinding, bool, bool]:
    provider_code, region_code = _resolve_region_binding_codes(instance_config)
    if binding_type == "region_node":
        node = _resolve_region_binding_node(
            db,
            household_id=instance.household_id,
            instance_config=instance_config,
            raise_on_error=True,
        )
        if node is None:
            raise PluginServiceError(
                "当前地区节点不存在。",
                error_code="weather_region_not_found",
                field=_resolve_region_binding_error_field(instance_config),
                status_code=404,
            )
        if node.latitude is None or node.longitude is None:
            raise PluginServiceError(
                "当前地区节点还没有可用坐标，不能创建天气设备。",
                error_code="weather_coordinate_missing",
                field=_resolve_region_binding_error_field(instance_config),
                status_code=400,
            )

    now = utc_now_iso()
    device = Device(
        id=new_uuid(),
        household_id=instance.household_id,
        room_id=None,
        name=display_name,
        device_type=WEATHER_DEVICE_TYPE,
        vendor=WEATHER_DEVICE_VENDOR,
        status="inactive",
        controllable=0,
        created_at=now,
        updated_at=now,
    )
    db.add(device)
    db.flush()

    placeholder_payload = normalize_plugin_weather_capabilities_payload(
        _build_placeholder_capabilities(device=device, state=WEATHER_STATE_PENDING)
    )
    device_binding = DeviceBinding(
        id=new_uuid(),
        device_id=device.id,
        integration_instance_id=instance.id,
        platform=WEATHER_PLATFORM,
        external_entity_id=f"weather.{binding_key}",
        external_device_id=f"weather.{binding_key}",
        plugin_id=instance.plugin_id,
        binding_version=1,
        capabilities="{}",
        last_sync_at=None,
    )
    db.add(device_binding)
    _store_weather_binding_payload(db, device_binding=device_binding, payload=placeholder_payload)

    weather_binding = WeatherDeviceBinding(
        id=new_uuid(),
        device_id=device.id,
        household_id=instance.household_id,
        plugin_id=instance.plugin_id,
        binding_type=binding_type,
        binding_key=binding_key,
        provider_code=provider_code,
        region_code=region_code,
        state=WEATHER_STATE_PENDING,
        latest_snapshot_json=None,
        cache_expires_at=None,
        last_refresh_attempt_at=None,
        last_success_at=None,
        last_error_code=None,
        last_error_message=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_weather_device_binding(db, weather_binding)
    db.flush()
    return weather_binding, True, True


def _apply_refresh_success(
    db: Session,
    *,
    device: Device,
    device_binding: DeviceBinding,
    weather_binding: WeatherDeviceBinding,
    snapshot: WeatherSnapshot,
    cache_minutes: int,
) -> None:
    now = _utc_now()
    weather_binding.state = WEATHER_STATE_READY
    weather_binding.latest_snapshot_json = dump_json(snapshot.model_dump(mode="json"))
    weather_binding.cache_expires_at = _to_utc_iso(now + timedelta(minutes=cache_minutes))
    weather_binding.last_success_at = snapshot.updated_at
    weather_binding.last_error_code = None
    weather_binding.last_error_message = None
    weather_binding.updated_at = _to_utc_iso(now)
    device.status = "active"
    _apply_snapshot_to_device(
        db,
        device=device,
        device_binding=device_binding,
        weather_binding=weather_binding,
        snapshot=snapshot,
        state=WEATHER_STATE_READY,
    )


def _apply_missing_coordinate(
    db: Session,
    *,
    device: Device,
    device_binding: DeviceBinding,
    weather_binding: WeatherDeviceBinding,
    detail: str,
) -> None:
    weather_binding.state = WEATHER_STATE_PENDING
    weather_binding.last_error_code = "weather_coordinate_missing"
    weather_binding.last_error_message = detail
    weather_binding.cache_expires_at = None
    weather_binding.updated_at = utc_now_iso()
    device.status = "inactive"
    device.updated_at = weather_binding.updated_at
    payload = normalize_plugin_weather_capabilities_payload(
        _build_placeholder_capabilities(
            device=device,
            state=WEATHER_STATE_PENDING,
            error_code=weather_binding.last_error_code,
            error_message=detail,
        )
    )
    _store_weather_binding_payload(db, device_binding=device_binding, payload=payload)
    device_binding.last_sync_at = weather_binding.updated_at
    db.add(weather_binding)
    db.add(device)
    db.add(device_binding)
    db.flush()


def _apply_refresh_error(
    db: Session,
    *,
    device: Device,
    device_binding: DeviceBinding,
    weather_binding: WeatherDeviceBinding,
    error_code: str,
    error_message: str,
    retryable: bool,
    stale_snapshot: WeatherSnapshot | None,
) -> None:
    now = utc_now_iso()
    weather_binding.last_error_code = error_code
    weather_binding.last_error_message = error_message
    weather_binding.updated_at = now

    if stale_snapshot is not None:
        stale_payload = stale_snapshot.model_copy(update={"is_stale": True})
        weather_binding.state = WEATHER_STATE_STALE if retryable else WEATHER_STATE_ERROR
        device.status = "active"
        _apply_snapshot_to_device(
            db,
            device=device,
            device_binding=device_binding,
            weather_binding=weather_binding,
            snapshot=stale_payload,
            state=weather_binding.state,
            error_code=error_code,
            error_message=error_message,
        )
        return

    weather_binding.state = WEATHER_STATE_ERROR
    weather_binding.cache_expires_at = None
    device.status = "inactive"
    device.updated_at = now
    payload = normalize_plugin_weather_capabilities_payload(
        _build_placeholder_capabilities(
            device=device,
            state=WEATHER_STATE_ERROR,
            error_code=error_code,
            error_message=error_message,
        )
    )
    _store_weather_binding_payload(db, device_binding=device_binding, payload=payload)
    device_binding.last_sync_at = now
    db.add(weather_binding)
    db.add(device)
    db.add(device_binding)
    db.flush()


def _apply_snapshot_to_device(
    db: Session,
    *,
    device: Device,
    device_binding: DeviceBinding,
    weather_binding: WeatherDeviceBinding,
    snapshot: WeatherSnapshot,
    state: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    now = utc_now_iso()
    device.updated_at = now
    payload = normalize_plugin_weather_capabilities_payload(
        _build_capabilities_from_snapshot(
            device=device,
            snapshot=snapshot,
            state=state,
            error_code=error_code,
            error_message=error_message,
        )
    )
    _store_weather_binding_payload(db, device_binding=device_binding, payload=payload)
    device_binding.last_sync_at = now
    db.add(weather_binding)
    db.add(device)
    db.add(device_binding)
    db.flush()


def _store_weather_binding_payload(
    db: Session,
    *,
    device_binding: DeviceBinding,
    payload: dict[str, Any],
) -> None:
    raw_entities = payload.get("entities")
    if isinstance(raw_entities, list):
        replace_binding_entities(
            db,
            binding=device_binding,
            raw_entities=raw_entities,
            primary_entity_id=_read_optional_text(payload.get("primary_entity_id")),
        )
    device_binding.capabilities = dump_json(_build_weather_binding_capabilities_payload(payload)) or "{}"


def _build_weather_binding_capabilities_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    sanitized.pop("entities", None)
    sanitized["entity_ids"] = _normalize_entity_ids(payload.get("entity_ids"))
    return sanitized


def _build_capabilities_from_snapshot(
    *,
    device: Device,
    snapshot: WeatherSnapshot,
    state: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "state": state,
        "provider_type": snapshot.source_type,
        "is_stale": snapshot.is_stale,
    }
    if error_code:
        metadata["error_code"] = error_code
    if error_message:
        metadata["error_message"] = error_message
    entities = [
        _build_entity(
            entity_id="weather.condition",
            name="天气状态",
            state=snapshot.condition_code,
            state_display=snapshot.condition_text,
            updated_at=snapshot.updated_at,
            metadata={
                **metadata,
                "condition_code": snapshot.condition_code,
                "condition_text": snapshot.condition_text,
            },
        ),
        _build_numeric_entity(
            entity_id="weather.temperature",
            name="温度",
            value=snapshot.temperature,
            unit="°C",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.humidity",
            name="湿度",
            value=snapshot.humidity,
            unit="%",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.wind_speed",
            name="风速",
            value=snapshot.wind_speed,
            unit="m/s",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.wind_direction",
            name="风向",
            value=snapshot.wind_direction,
            unit="°",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.pressure",
            name="气压",
            value=snapshot.pressure,
            unit="hPa",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.cloud_cover",
            name="云量",
            value=snapshot.cloud_cover,
            unit="%",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_numeric_entity(
            entity_id="weather.precipitation_next_1h",
            name="未来 1 小时降水",
            value=snapshot.precipitation_next_1h,
            unit="mm",
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
        _build_forecast_entity(snapshot=snapshot, metadata=metadata),
        _build_entity(
            entity_id="weather.updated_at",
            name="更新时间",
            state=snapshot.updated_at,
            state_display=snapshot.updated_at,
            updated_at=snapshot.updated_at,
            metadata=metadata,
        ),
    ]
    return {
        "adapter_type": WEATHER_PLATFORM,
        "name": device.name,
        "domain": "weather",
        "state": snapshot.condition_code,
        "primary_entity_id": "weather.condition",
        "entity_ids": [item["entity_id"] for item in entities],
        "capability_tags": ["weather"],
        "entities": entities,
        "metadata": metadata,
    }


def _build_placeholder_capabilities(
    *,
    device: Device,
    state: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    message = error_message or (
        WEATHER_MESSAGE_WAITING_COORDINATE if state == WEATHER_STATE_PENDING else WEATHER_MESSAGE_UNAVAILABLE
    )
    metadata: dict[str, Any] = {"state": state}
    if error_code:
        metadata["error_code"] = error_code
    if error_message:
        metadata["error_message"] = error_message
    entities = [
        _build_entity(
            entity_id="weather.condition",
            name="天气状态",
            state=state,
            state_display=message,
            updated_at=now,
            metadata=metadata,
        ),
    ]
    for entity_id, entity_name, unit in (
        ("weather.temperature", "温度", "°C"),
        ("weather.humidity", "湿度", "%"),
        ("weather.wind_speed", "风速", "m/s"),
        ("weather.wind_direction", "风向", "°"),
        ("weather.pressure", "气压", "hPa"),
        ("weather.cloud_cover", "云量", "%"),
        ("weather.precipitation_next_1h", "未来 1 小时降水", "mm"),
        ("weather.forecast_6h", "未来 6 小时摘要", None),
    ):
        entities.append(
            _build_entity(
                entity_id=entity_id,
                name=entity_name,
                state="unknown",
                state_display=WEATHER_MESSAGE_NO_DATA,
                unit=unit,
                updated_at=now,
                metadata=metadata,
            )
        )
    entities.append(
        _build_entity(
            entity_id="weather.updated_at",
            name="更新时间",
            state=now,
            state_display=now,
            updated_at=now,
            metadata=metadata,
        )
    )
    return {
        "adapter_type": WEATHER_PLATFORM,
        "name": device.name,
        "domain": "weather",
        "state": state,
        "primary_entity_id": "weather.condition",
        "entity_ids": [item["entity_id"] for item in entities],
        "capability_tags": ["weather"],
        "entities": entities,
        "metadata": metadata,
    }


def _build_forecast_entity(*, snapshot: WeatherSnapshot, metadata: dict[str, Any]) -> dict[str, Any]:
    if snapshot.forecast_6h is None:
        return _build_entity(
            entity_id="weather.forecast_6h",
            name="未来 6 小时摘要",
            state="unknown",
            state_display=WEATHER_MESSAGE_NO_DATA,
            updated_at=snapshot.updated_at,
            metadata=metadata,
        )
    parts = [snapshot.forecast_6h.condition_text]
    if snapshot.forecast_6h.min_temperature is not None and snapshot.forecast_6h.max_temperature is not None:
        parts.append(
            f"{_format_decimal(snapshot.forecast_6h.min_temperature)}~{_format_decimal(snapshot.forecast_6h.max_temperature)} °C"
        )
    return _build_entity(
        entity_id="weather.forecast_6h",
        name="未来 6 小时摘要",
        state=snapshot.forecast_6h.condition_code,
        state_display=" ".join(parts),
        updated_at=snapshot.updated_at,
        metadata={
            **metadata,
            "condition_code": snapshot.forecast_6h.condition_code,
            "condition_text": snapshot.forecast_6h.condition_text,
            "min_temperature": snapshot.forecast_6h.min_temperature,
            "max_temperature": snapshot.forecast_6h.max_temperature,
        },
    )


def _build_numeric_entity(
    *,
    entity_id: str,
    name: str,
    value: float | None,
    unit: str,
    updated_at: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if value is None:
        return _build_entity(
            entity_id=entity_id,
            name=name,
            state="unknown",
            state_display=WEATHER_MESSAGE_NO_DATA,
            unit=unit,
            updated_at=updated_at,
            metadata=metadata,
        )
    formatted = _format_decimal(value)
    return _build_entity(
        entity_id=entity_id,
        name=name,
        state=formatted,
        state_display=formatted,
        unit=unit,
        updated_at=updated_at,
        metadata={**metadata, "value": value},
    )


def _build_entity(
    *,
    entity_id: str,
    name: str,
    state: str,
    state_display: str,
    updated_at: str,
    unit: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "name": name,
        "domain": "weather",
        "state": state,
        "state_display": state_display,
        "unit": unit,
        "updated_at": updated_at,
        "metadata": metadata or {},
        "control": {"kind": "none"},
    }


def normalize_weather_capabilities_payload(capabilities: dict[str, Any]) -> dict[str, Any]:
    return normalize_plugin_weather_capabilities_payload(capabilities)


def _resolve_binding_coordinate(
    db: Session,
    *,
    weather_binding: WeatherDeviceBinding,
) -> WeatherBindingCoordinateResolution:
    if weather_binding.binding_type == "default_household":
        context = resolve_household_region_context(db, weather_binding.household_id)
        if context.coordinate.available and context.coordinate.latitude is not None and context.coordinate.longitude is not None:
            return WeatherBindingCoordinateResolution(
                available=True,
                coordinate=WeatherCoordinate(
                    latitude=context.coordinate.latitude,
                    longitude=context.coordinate.longitude,
                ),
            )
        return WeatherBindingCoordinateResolution(
            available=False,
            error_code="weather_coordinate_missing",
            detail="当前家庭还没有可用坐标，请先补充家庭坐标或正式地区。",
        )

    if weather_binding.binding_type == "region_node":
        if not weather_binding.provider_code or not weather_binding.region_code:
            return WeatherBindingCoordinateResolution(
                available=False,
                error_code="weather_coordinate_missing",
                detail="当前地区天气设备没有完整的地区绑定。",
            )
        node = _get_region_node(
            db,
            household_id=weather_binding.household_id,
            provider_code=weather_binding.provider_code,
            region_code=weather_binding.region_code,
        )
        if node is None or node.latitude is None or node.longitude is None:
            return WeatherBindingCoordinateResolution(
                available=False,
                error_code="weather_coordinate_missing",
                detail="当前地区 provider 不可用、地区不存在，或者该地区还没有可用坐标。",
            )
        return WeatherBindingCoordinateResolution(
            available=True,
            coordinate=WeatherCoordinate(latitude=node.latitude, longitude=node.longitude),
        )

    return WeatherBindingCoordinateResolution(
        available=False,
        error_code="weather_coordinate_missing",
        detail="当前天气设备绑定类型不支持坐标解析。",
    )


def _require_device(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise RuntimeError(f"weather device missing: {device_id}")
    return device


def _require_weather_device_binding_row(db: Session, *, device_id: str) -> DeviceBinding:
    binding = _get_device_binding(db, device_id=device_id)
    if binding is None:
        raise RuntimeError(f"weather device binding missing: {device_id}")
    return binding


def _get_device_binding(db: Session, *, device_id: str) -> DeviceBinding | None:
    stmt = select(DeviceBinding).where(
        DeviceBinding.device_id == device_id,
        DeviceBinding.platform == WEATHER_PLATFORM,
    )
    return db.scalar(stmt)


def _load_latest_snapshot(weather_binding: WeatherDeviceBinding) -> WeatherSnapshot | None:
    payload = load_json(weather_binding.latest_snapshot_json)
    if not isinstance(payload, dict):
        return None
    return WeatherSnapshot.model_validate(payload)


def _cache_is_valid(weather_binding: WeatherDeviceBinding, *, now: datetime) -> bool:
    if not weather_binding.cache_expires_at:
        return False
    expires_at = _parse_utc_time(weather_binding.cache_expires_at)
    if expires_at is None:
        return False
    return expires_at > now


def _parse_utc_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_decimal(value: float) -> str:
    normalized = f"{value:.1f}"
    return normalized[:-2] if normalized.endswith(".0") else normalized


def _to_weather_binding_read(db: Session, row: WeatherDeviceBinding) -> WeatherDeviceBindingRead:
    device = _require_device(db, row.device_id)
    return WeatherDeviceBindingRead(
        device_id=row.device_id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        binding_type=cast(Any, row.binding_type),
        binding_key=row.binding_key,
        display_name=device.name,
        provider_code=row.provider_code,
        region_code=row.region_code,
        state=row.state,
        last_refresh_attempt_at=row.last_refresh_attempt_at,
        last_success_at=row.last_success_at,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _build_display_name_from_payload(
    db: Session,
    *,
    household_id: str,
    payload: WeatherDeviceBindingCreate,
) -> str:
    node = _get_region_node(
        db,
        household_id=household_id,
        provider_code=payload.provider_code,
        region_code=payload.region_code,
    )
    if node is not None:
        return _normalize_device_name(node.full_name)
    return "地区天气"


def _build_binding_key(payload: WeatherDeviceBindingCreate) -> str:
    return f"region_node:{payload.provider_code}:{payload.region_code}"


def _build_weather_card_snapshot(
    *,
    db: Session,
    weather_binding: WeatherDeviceBinding,
    card_key: str = WEATHER_HOME_CARD_KEY,
) -> WeatherDeviceCardSnapshotRead:
    display_name = _require_device(db, weather_binding.device_id).name
    snapshot = _load_latest_snapshot(weather_binding)
    if snapshot is not None:
        state = "stale" if weather_binding.state == WEATHER_STATE_STALE or snapshot.is_stale else "ready"
        forecast_payload = None
        if snapshot.forecast_6h is not None:
            forecast_payload = {
                "condition_code": snapshot.forecast_6h.condition_code,
                "condition_text": snapshot.forecast_6h.condition_text,
                "min_temperature": snapshot.forecast_6h.min_temperature,
                "max_temperature": snapshot.forecast_6h.max_temperature,
            }
        detail_items = _build_weather_card_detail_items(snapshot)
        footer_items = _build_weather_card_footer_items(snapshot)
        return WeatherDeviceCardSnapshotRead(
            card_key=card_key,
            device_id=weather_binding.device_id,
            display_name=display_name,
            state=cast(Any, state),
            payload={
                "provider_type": snapshot.source_type,
                "status": weather_binding.state,
                "condition_code": snapshot.condition_code,
                "condition_text": snapshot.condition_text,
                "temperature": snapshot.temperature,
                "temperature_unit": "°C",
                "icon_key": snapshot.condition_code,
                "location": display_name,
                "humidity": snapshot.humidity,
                "humidity_unit": "%",
                "wind_speed": snapshot.wind_speed,
                "wind_speed_unit": "m/s",
                "wind_direction": snapshot.wind_direction,
                "wind_direction_unit": "°",
                "pressure": snapshot.pressure,
                "pressure_unit": "hPa",
                "cloud_cover": snapshot.cloud_cover,
                "cloud_cover_unit": "%",
                "precipitation_next_1h": snapshot.precipitation_next_1h,
                "precipitation_unit": "mm",
                "forecast_6h": forecast_payload,
                "updated_at": snapshot.updated_at,
                "is_stale": snapshot.is_stale or weather_binding.state == WEATHER_STATE_STALE,
                "detail_items": detail_items,
                "footer_items": footer_items,
            },
            error_code=weather_binding.last_error_code,
            error_message=weather_binding.last_error_message,
            generated_at=snapshot.updated_at,
            expires_at=weather_binding.cache_expires_at,
        )

    state = WEATHER_STATE_PENDING if weather_binding.state == WEATHER_STATE_PENDING else WEATHER_STATE_ERROR
    return WeatherDeviceCardSnapshotRead(
        card_key=card_key,
        device_id=weather_binding.device_id,
        display_name=display_name,
        state=cast(Any, state),
        payload={
            "location": display_name,
            "status": weather_binding.state,
            "message": weather_binding.last_error_message or "天气数据暂不可用",
            "updated_at": weather_binding.updated_at,
            "detail_items": [],
            "footer_items": [
                {
                    "key": "updated_at",
                    "label": "更新时间",
                    "label_key": "official_weather.dashboard.fields.updated_at",
                    "value": weather_binding.updated_at,
                    "value_type": "relative_time",
                }
            ],
        },
        error_code=weather_binding.last_error_code,
        error_message=weather_binding.last_error_message,
        generated_at=weather_binding.updated_at,
        expires_at=None,
    )


def _build_weather_card_detail_items(snapshot: WeatherSnapshot) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, label, label_key, value, unit in (
        ("humidity", "湿度", "official_weather.dashboard.fields.humidity", snapshot.humidity, "%"),
        ("wind_speed", "风速", "official_weather.dashboard.fields.wind_speed", snapshot.wind_speed, "m/s"),
        (
            "precipitation_next_1h",
            "未来 1 小时降水",
            "official_weather.dashboard.fields.precipitation_next_1h",
            snapshot.precipitation_next_1h,
            "mm",
        ),
        ("pressure", "气压", "official_weather.dashboard.fields.pressure", snapshot.pressure, "hPa"),
    ):
        if value is None:
            continue
        items.append(
            {
                "key": key,
                "label": label,
                "label_key": label_key,
                "value": value,
                "unit": unit,
            }
        )
    return items


def _build_weather_card_footer_items(snapshot: WeatherSnapshot) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    forecast_text = _build_weather_card_forecast_text(snapshot)
    if forecast_text:
        items.append(
            {
                "key": "forecast_6h",
                "label": "未来 6 小时摘要",
                "label_key": "official_weather.dashboard.fields.forecast_6h",
                "value_display": forecast_text,
                "value_type": "text",
            }
        )
    items.append(
        {
            "key": "updated_at",
            "label": "更新时间",
            "label_key": "official_weather.dashboard.fields.updated_at",
            "value": snapshot.updated_at,
            "value_type": "relative_time",
        }
    )
    return items


def _build_weather_card_forecast_text(snapshot: WeatherSnapshot) -> str | None:
    if snapshot.forecast_6h is None:
        return None
    parts = [snapshot.forecast_6h.condition_text]
    if snapshot.forecast_6h.min_temperature is not None and snapshot.forecast_6h.max_temperature is not None:
        parts.append(
            f"{_format_decimal(snapshot.forecast_6h.min_temperature)}~{_format_decimal(snapshot.forecast_6h.max_temperature)} °C"
        )
    return " · ".join(part for part in parts if part)


def _sync_default_dashboard_snapshot(db: Session, *, weather_binding: WeatherDeviceBinding) -> None:
    from app.modules.plugin.dashboard_service import upsert_plugin_dashboard_card_snapshot
    from app.modules.plugin.schemas import PluginDashboardCardSnapshotUpsert

    snapshot_payload = build_weather_dashboard_snapshot_upsert(db, weather_binding=weather_binding)
    upsert_plugin_dashboard_card_snapshot(
        db,
        household_id=weather_binding.household_id,
        plugin_id=weather_binding.plugin_id,
        payload=PluginDashboardCardSnapshotUpsert.model_validate(snapshot_payload),
    )


def _normalize_device_name(value: str) -> str:
    normalized = value.strip() or "地区天气"
    return normalized[:100]


def _resolve_region_binding_codes(instance_config: dict[str, Any]) -> tuple[str | None, str | None]:
    provider_selector = _read_optional_text(instance_config.get("provider_selector"))
    provider_code = _read_optional_text(instance_config.get("provider_code"))
    region_code = _read_optional_text(instance_config.get("region_code"))
    province_code = _read_optional_text(instance_config.get("province_code"))
    city_code = _read_optional_text(instance_config.get("city_code"))
    district_code = _read_optional_text(instance_config.get("district_code"))
    builtin_selector_active = provider_selector == WEATHER_BUILTIN_REGION_PROVIDER or provider_code == WEATHER_BUILTIN_REGION_PROVIDER
    builtin_fields_present = bool(province_code or city_code or district_code)

    if builtin_selector_active:
        provider_code = provider_code or provider_selector or WEATHER_BUILTIN_REGION_PROVIDER
    elif provider_selector != WEATHER_REGION_PROVIDER_SELECTOR_MANUAL and provider_code is None and (
        builtin_fields_present
        or region_code
    ):
        # 兼容旧配置：历史上没显式保存 provider_code 时，内置目录默认视为中国大陆 provider。
        provider_code = WEATHER_BUILTIN_REGION_PROVIDER

    if district_code:
        region_code = district_code
    return provider_code, region_code


def _resolve_region_binding_error_field(instance_config: dict[str, Any]) -> str:
    if _read_optional_text(instance_config.get("district_code")) is not None or _uses_builtin_region_selector(instance_config):
        return "district_code"
    return "region_code"


def _resolve_region_provider_error_field(instance_config: dict[str, Any]) -> str:
    return "provider_code"


def _uses_builtin_region_selector(instance_config: dict[str, Any]) -> bool:
    provider_selector = _read_optional_text(instance_config.get("provider_selector"))
    provider_code = _read_optional_text(instance_config.get("provider_code"))
    has_builtin_region_fields = bool(
        _read_optional_text(instance_config.get("province_code"))
        or _read_optional_text(instance_config.get("city_code"))
        or _read_optional_text(instance_config.get("district_code"))
    )
    if provider_selector == WEATHER_BUILTIN_REGION_PROVIDER:
        return True
    if has_builtin_region_fields and provider_code == WEATHER_BUILTIN_REGION_PROVIDER:
        return True
    if provider_selector is None and provider_code is None and has_builtin_region_fields:
        return True
    return False


def _resolve_region_binding_node(
    db: Session,
    *,
    household_id: str,
    instance_config: dict[str, Any],
    raise_on_error: bool,
) -> RegionNodeRead | None:
    provider_code, region_code = _resolve_region_binding_codes(instance_config)
    if not provider_code or not region_code:
        return None
    node = _resolve_region_catalog_node(
        db,
        household_id=household_id,
        provider_code=provider_code,
        region_code=region_code,
        raise_on_provider_error=raise_on_error,
        provider_error_field=_resolve_region_provider_error_field(instance_config),
    )
    if node is None:
        return None
    if provider_code != WEATHER_BUILTIN_REGION_PROVIDER:
        return node
    _validate_builtin_region_binding_selection(
        instance_config=instance_config,
        node=node,
        raise_on_error=raise_on_error,
    )
    return node


def _validate_builtin_region_binding_selection(
    *,
    instance_config: dict[str, Any],
    node: RegionNodeRead,
    raise_on_error: bool,
) -> None:
    province_code = _read_optional_text(instance_config.get("province_code"))
    city_code = _read_optional_text(instance_config.get("city_code"))
    district_code = _read_optional_text(instance_config.get("district_code"))
    if province_code is None and city_code is None and district_code is None:
        return

    normalized_path_codes = [code for code in node.path_codes if isinstance(code, str)]
    expected_province = normalized_path_codes[0] if len(normalized_path_codes) >= 1 else None
    expected_city = normalized_path_codes[1] if len(normalized_path_codes) >= 2 else None
    expected_district = normalized_path_codes[2] if len(normalized_path_codes) >= 3 else node.region_code

    def _raise(detail: str, field: str) -> None:
        if not raise_on_error:
            return
        raise PluginServiceError(
            detail,
            error_code="integration_instance_config_invalid",
            field=field,
            status_code=400,
        )

    if province_code and province_code != expected_province:
        _raise("所选省份和区县不匹配。", "province_code")
    if city_code and city_code != expected_city:
        _raise("所选城市和区县不匹配。", "city_code")
    if district_code and district_code != expected_district:
        _raise("所选区县和地区编码不匹配。", "district_code")


def _read_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_entity_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    entity_ids: list[str] = []
    for item in value:
        normalized = _read_optional_text(item)
        if normalized is None or normalized in entity_ids:
            continue
        entity_ids.append(normalized)
    return entity_ids


def _resolve_region_catalog_node(
    db: Session,
    *,
    household_id: str,
    provider_code: str,
    region_code: str,
    raise_on_provider_error: bool = False,
    provider_error_field: str = "provider_code",
) -> RegionNodeRead | None:
    provider = _get_region_provider(db, household_id=household_id, provider_code=provider_code)
    if provider is None:
        legacy_node = _load_legacy_region_node(
            db,
            provider_code=provider_code,
            region_code=region_code,
        )
        if legacy_node is not None:
            return legacy_node
        if raise_on_provider_error:
            raise PluginServiceError(
                "当前地区 provider 不可用。",
                error_code="weather_region_provider_unavailable",
                field=provider_error_field,
                status_code=400,
            )
        return None
    try:
        return provider.resolve(db, region_code=region_code)
    except RegionProviderExecutionError as exc:
        if raise_on_provider_error:
            raise PluginServiceError(
                "当前地区 provider 执行失败，暂时无法解析地区。",
                error_code="weather_region_provider_execution_failed",
                field=provider_error_field,
                status_code=400,
            ) from exc
        return None


def _get_region_provider(db: Session, *, household_id: str, provider_code: str):
    sync_household_plugin_region_providers(db, household_id)
    provider = region_provider_registry.get(provider_code, household_id=household_id)
    if provider is not None:
        return provider
    return region_provider_registry.get(provider_code)


def _get_region_node(
    db: Session,
    *,
    household_id: str,
    provider_code: str,
    region_code: str,
) -> RegionNodeRead | None:
    return _resolve_region_catalog_node(
        db,
        household_id=household_id,
        provider_code=provider_code,
        region_code=region_code,
    )


def _load_legacy_region_node(
    db: Session,
    *,
    provider_code: str,
    region_code: str,
) -> RegionNodeRead | None:
    # 仅作为旧实例兼容兜底使用，主路径已经优先走地区 provider。
    row = db.scalar(
        select(RegionNode).where(
            RegionNode.provider_code == provider_code,
            RegionNode.region_code == region_code,
        )
    )
    if row is None:
        return None
    path_codes = load_json(row.path_codes)
    path_names = load_json(row.path_names)
    return RegionNodeRead(
        provider_code=row.provider_code,
        country_code=row.country_code,
        region_code=row.region_code,
        parent_region_code=row.parent_region_code,
        admin_level=cast(Any, row.admin_level),
        name=row.name,
        full_name=row.full_name,
        path_codes=path_codes if isinstance(path_codes, list) else [],
        path_names=path_names if isinstance(path_names, list) else [],
        timezone=row.timezone,
        source_version=row.source_version,
        latitude=row.latitude,
        longitude=row.longitude,
        coordinate_precision=cast(Any, row.coordinate_precision),
        coordinate_source=cast(Any, row.coordinate_source),
        coordinate_updated_at=row.coordinate_updated_at,
    )

