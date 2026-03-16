from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.device.schemas import DeviceRead
from app.modules.device_integration.schemas import (
    DeviceIntegrationPluginPayload,
    DeviceIntegrationPluginResult,
)
from app.modules.integration import repository as integration_repository
from app.modules.household.service import get_household_or_404
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginServiceError,
    aexecute_household_plugin,
    execute_household_plugin,
    require_available_household_plugin,
)
from app.plugins.builtin.homeassistant_device_action.runtime import (
    HOME_ASSISTANT_PLUGIN_ID,
    get_home_assistant_runtime_config,
    mark_home_assistant_instance_sync_failed,
    mark_home_assistant_instance_sync_succeeded,
)
from app.modules.room.models import Room


@dataclass(slots=True)
class SyncFailure:
    entity_id: str | None
    reason: str


@dataclass(slots=True)
class SyncSummary:
    household_id: str
    created_devices: int
    updated_devices: int
    created_bindings: int
    created_rooms: int
    assigned_rooms: int
    skipped_entities: int
    failed_entities: int
    devices: list[Device]
    failures: list[SyncFailure]


@dataclass(slots=True)
class RoomSyncSummary:
    household_id: str
    created_rooms: int
    matched_entities: int
    skipped_entities: int
    rooms: list[Room]


@dataclass(slots=True)
class HaDeviceCandidate:
    external_device_id: str
    primary_entity_id: str
    name: str
    room_name: str | None
    device_type: str
    entity_count: int
    already_synced: bool


@dataclass(slots=True)
class HaRoomCandidate:
    name: str
    entity_count: int
    exists_locally: bool
    can_sync: bool


class DeviceIntegrationServiceError(PluginServiceError):
    def __init__(self, message: str, *, error_code: str, status_code: int, field: str | None = None) -> None:
        super().__init__(message, error_code=error_code, field=field, status_code=status_code)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.field = field


def list_home_assistant_device_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[HaDeviceCandidate]:
    result = _execute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="device_candidates")
    existing_bindings = _load_existing_home_assistant_bindings(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    return [
        HaDeviceCandidate(
            external_device_id=item.external_device_id,
            primary_entity_id=item.primary_entity_id,
            name=item.name,
            room_name=item.room_name,
            device_type=item.device_type,
            entity_count=item.entity_count,
            already_synced=item.external_device_id in existing_bindings,
        )
        for item in result.device_candidates
    ]


def list_home_assistant_room_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[HaRoomCandidate]:
    result = _execute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="room_candidates")
    room_cache = _load_room_cache(db, household_id)
    return [
        HaRoomCandidate(
            name=item.name,
            entity_count=item.entity_count,
            exists_locally=_normalize_room_key(item.name) in room_cache,
            can_sync=_normalize_room_key(item.name) not in room_cache,
        )
        for item in result.room_candidates
    ]


def sync_home_assistant_devices_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    external_device_ids: list[str] | None = None,
) -> SyncSummary:
    result = _execute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_sync",
        selected_external_ids=external_device_ids or [],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="device_sync")
    return _apply_device_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


def sync_home_assistant_rooms_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    room_names: list[str] | None = None,
) -> RoomSyncSummary:
    result = _execute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_sync",
        selected_external_ids=room_names or [],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="room_sync")
    return _apply_room_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


async def async_list_home_assistant_device_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[HaDeviceCandidate]:
    result = await _aexecute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="device_candidates")
    existing_bindings = _load_existing_home_assistant_bindings(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    return [
        HaDeviceCandidate(
            external_device_id=item.external_device_id,
            primary_entity_id=item.primary_entity_id,
            name=item.name,
            room_name=item.room_name,
            device_type=item.device_type,
            entity_count=item.entity_count,
            already_synced=item.external_device_id in existing_bindings,
        )
        for item in result.device_candidates
    ]


async def async_list_home_assistant_room_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[HaRoomCandidate]:
    result = await _aexecute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="room_candidates")
    room_cache = _load_room_cache(db, household_id)
    return [
        HaRoomCandidate(
            name=item.name,
            entity_count=item.entity_count,
            exists_locally=_normalize_room_key(item.name) in room_cache,
            can_sync=_normalize_room_key(item.name) not in room_cache,
        )
        for item in result.room_candidates
    ]


async def async_sync_home_assistant_devices_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    external_device_ids: list[str] | None = None,
) -> SyncSummary:
    result = await _aexecute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_sync",
        selected_external_ids=external_device_ids or [],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="device_sync")
    return _apply_device_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


async def async_sync_home_assistant_rooms_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    room_names: list[str] | None = None,
) -> RoomSyncSummary:
    result = await _aexecute_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_sync",
        selected_external_ids=room_names or [],
        options={},
    )
    _raise_if_connector_failed(result, sync_scope="room_sync")
    return _apply_room_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


def _execute_connector_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> DeviceIntegrationPluginResult:
    _require_homeassistant_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    payload = _build_payload(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope=sync_scope,
        selected_external_ids=selected_external_ids,
        options=options,
    )
    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            plugin_type="connector",
            payload=_serialize_payload(payload),
            trigger="device-integration",
        ),
    )
    if not execution.success:
        raise DeviceIntegrationServiceError(
            execution.error_message or "插件执行失败",
            error_code=execution.error_code or "plugin_execution_failed",
            status_code=502,
        )
    return _parse_plugin_result(execution.output)


async def _aexecute_connector_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> DeviceIntegrationPluginResult:
    _require_homeassistant_connector_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    payload = _build_payload(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope=sync_scope,
        selected_external_ids=selected_external_ids,
        options=options,
    )
    execution = await aexecute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            plugin_type="connector",
            payload=_serialize_payload(payload),
            trigger="device-integration",
        ),
    )
    if not execution.success:
        raise DeviceIntegrationServiceError(
            execution.error_message or "插件执行失败",
            error_code=execution.error_code or "plugin_execution_failed",
            status_code=502,
        )
    return _parse_plugin_result(execution.output)


def _require_homeassistant_connector_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None or instance.household_id != household_id or instance.plugin_id != HOME_ASSISTANT_PLUGIN_ID:
        raise DeviceIntegrationServiceError(
            "Home Assistant 实例不存在或不属于当前家庭",
            error_code="integration_instance_not_found",
            status_code=404,
        )
    try:
        require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            plugin_type="connector",
        )
    except PluginServiceError as exc:
        raise DeviceIntegrationServiceError(exc.detail, error_code=exc.error_code, status_code=exc.status_code) from exc


def _build_payload(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> DeviceIntegrationPluginPayload:
    database_url = _build_database_url(db)
    return DeviceIntegrationPluginPayload(
        household_id=household_id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        integration_instance_id=integration_instance_id,
        sync_scope=sync_scope,  # type: ignore[arg-type]
        selected_external_ids=[item for item in selected_external_ids if isinstance(item, str) and item.strip()],
        options=options,
        system_context={"device_integration": {"database_url": database_url}} if database_url else None,
    )


def _parse_plugin_result(output: Any) -> DeviceIntegrationPluginResult:
    try:
        result = DeviceIntegrationPluginResult.model_validate(output or {})
    except ValidationError as exc:
        raise DeviceIntegrationServiceError(
            f"插件返回结果不合法: {exc.errors()[0].get('msg', 'unknown error')}",
            error_code="plugin_result_invalid",
            status_code=502,
        ) from exc
    if result.plugin_id != HOME_ASSISTANT_PLUGIN_ID:
        raise DeviceIntegrationServiceError("插件返回了错误的 plugin_id", error_code="plugin_result_invalid", status_code=502)
    return result


def _raise_if_connector_failed(result: DeviceIntegrationPluginResult, *, sync_scope: str) -> None:
    if not result.failures:
        return

    success_count_map = {
        "device_candidates": len(result.device_candidates),
        "device_sync": len(result.devices),
        "room_candidates": len(result.room_candidates),
        "room_sync": len(result.rooms),
    }
    if success_count_map.get(sync_scope, 0) > 0:
        return

    first_failure = result.failures[0]
    raise DeviceIntegrationServiceError(
        first_failure.reason,
        error_code="plugin_execution_failed",
        status_code=502,
    )


def _apply_device_sync_result(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    result: DeviceIntegrationPluginResult,
) -> SyncSummary:
    get_household_or_404(db, household_id)
    runtime_config = get_home_assistant_runtime_config(db, integration_instance_id=integration_instance_id)
    room_cache = _load_room_cache(db, household_id)
    sync_rooms_enabled = bool(runtime_config.sync_rooms_enabled)

    created_devices = 0
    updated_devices = 0
    created_bindings = 0
    created_rooms = 0
    assigned_rooms = 0
    failures: list[SyncFailure] = []
    synced_devices: list[Device] = []

    for item in result.devices:
        try:
            with db.begin_nested():
                binding = _get_existing_binding(
                    db,
                    integration_instance_id=integration_instance_id,
                    external_device_id=item.external_device_id,
                    primary_entity_id=item.primary_entity_id,
                )

                if binding is None:
                    device = Device(
                        id=new_uuid(),
                        household_id=household_id,
                        room_id=None,
                        name=item.name,
                        device_type=item.device_type,
                        vendor="ha",
                        status=item.status,
                        controllable=1 if item.controllable else 0,
                    )
                    db.add(device)
                    db.flush()
                    binding = DeviceBinding(
                        id=new_uuid(),
                        device_id=device.id,
                        integration_instance_id=integration_instance_id,
                        platform=result.platform,
                        plugin_id=result.plugin_id,
                        binding_version=1,
                        external_entity_id=item.primary_entity_id,
                        external_device_id=item.external_device_id,
                        capabilities=dump_json(item.capabilities),
                        last_sync_at=utc_now_iso(),
                    )
                    db.add(binding)
                    created_devices += 1
                    created_bindings += 1
                else:
                    device = db.get(Device, binding.device_id)
                    if device is None:
                        raise ValueError("binding exists but linked device is missing")
                    if device.household_id != household_id:
                        raise ValueError("existing binding belongs to another household")
                    device.name = item.name
                    device.device_type = item.device_type
                    device.vendor = "ha"
                    device.status = item.status
                    device.controllable = 1 if item.controllable else 0
                    binding.external_entity_id = item.primary_entity_id
                    binding.external_device_id = item.external_device_id
                    binding.integration_instance_id = integration_instance_id
                    binding.plugin_id = result.plugin_id
                    binding.binding_version = 1
                    binding.capabilities = dump_json(item.capabilities)
                    binding.last_sync_at = utc_now_iso()
                    db.add(device)
                    db.add(binding)
                    updated_devices += 1

                if sync_rooms_enabled and item.room_name:
                    room, room_created = _get_or_create_room_from_name(
                        db,
                        household_id=household_id,
                        room_name=item.room_name,
                        room_cache=room_cache,
                    )
                    if room_created:
                        created_rooms += 1
                    if device.room_id != room.id:
                        device.room_id = room.id
                        db.add(device)
                        assigned_rooms += 1

                db.flush()
                synced_devices.append(device)
        except Exception as exc:
            failures.append(SyncFailure(entity_id=item.primary_entity_id, reason=str(exc)))

    for failure in result.failures:
        failures.append(SyncFailure(entity_id=failure.external_ref, reason=failure.reason))

    if failures:
        mark_home_assistant_instance_sync_failed(
            db,
            integration_instance_id=integration_instance_id,
            error_code="integration_sync_failed",
            error_message=failures[0].reason,
        )
    else:
        mark_home_assistant_instance_sync_succeeded(db, integration_instance_id=integration_instance_id)

    return SyncSummary(
        household_id=household_id,
        created_devices=created_devices,
        updated_devices=updated_devices,
        created_bindings=created_bindings,
        created_rooms=created_rooms,
        assigned_rooms=assigned_rooms,
        skipped_entities=0,
        failed_entities=len(failures),
        devices=synced_devices,
        failures=failures,
    )


def _apply_room_sync_result(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    result: DeviceIntegrationPluginResult,
) -> RoomSyncSummary:
    get_household_or_404(db, household_id)
    room_cache = _load_room_cache(db, household_id)
    created_rooms = 0
    matched_entities = 0
    skipped_entities = 0

    for item in result.rooms:
        room_key = _normalize_room_key(item.name)
        if room_key in room_cache:
            skipped_entities += 1
            continue
        matched_entities += 1
        _, created = _get_or_create_room_from_name(db, household_id=household_id, room_name=item.name, room_cache=room_cache)
        if created:
            created_rooms += 1

    mark_home_assistant_instance_sync_succeeded(db, integration_instance_id=integration_instance_id)

    return RoomSyncSummary(
        household_id=household_id,
        created_rooms=created_rooms,
        matched_entities=matched_entities,
        skipped_entities=skipped_entities,
        rooms=list(room_cache.values()),
    )


def _serialize_payload(payload: DeviceIntegrationPluginPayload) -> dict[str, Any]:
    payload_dict = payload.model_dump(mode="json")
    if payload.system_context is not None:
        payload_dict["_system_context"] = payload.system_context
    return payload_dict


def _build_database_url(db: Session) -> str | None:
    bind = db.get_bind()
    if hasattr(bind, "url"):
        return _render_database_url(bind.url)
    engine = getattr(bind, "engine", None)
    if engine is not None and hasattr(engine, "url"):
        return _render_database_url(engine.url)
    return None


def _render_database_url(url: Any) -> str:
    if hasattr(url, "render_as_string"):
        return url.render_as_string(hide_password=False)
    return str(url)


def _get_existing_binding(
    db: Session,
    *,
    integration_instance_id: str,
    external_device_id: str,
    primary_entity_id: str,
) -> DeviceBinding | None:
    binding = db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_device_id == external_device_id,
        )
    )
    if binding is not None:
        return binding
    return db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_entity_id == primary_entity_id,
        )
    )


def _load_existing_home_assistant_bindings(
    db: Session,
    household_id: str,
    integration_instance_id: str,
) -> set[str]:
    rows = db.execute(
        select(DeviceBinding.external_device_id)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_device_id.is_not(None),
        )
    ).all()
    return {value for (value,) in rows if isinstance(value, str) and value.strip()}


def _load_room_cache(db: Session, household_id: str) -> dict[str, Room]:
    rooms = db.scalars(select(Room).where(Room.household_id == household_id)).all()
    return {_normalize_room_key(room.name): room for room in rooms}


def _normalize_room_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _get_or_create_room_from_name(
    db: Session,
    *,
    household_id: str,
    room_name: str,
    room_cache: dict[str, Room],
) -> tuple[Room, bool]:
    room_key = _normalize_room_key(room_name)
    existing_room = room_cache.get(room_key)
    if existing_room is not None:
        return existing_room, False
    room = Room(
        id=new_uuid(),
        household_id=household_id,
        name=room_name.strip(),
        room_type="living_room",
        privacy_level="public",
    )
    db.add(room)
    db.flush()
    room_cache[room_key] = room
    return room, True
