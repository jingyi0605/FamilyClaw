from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.device.entity_store import replace_binding_entities_from_capabilities
from app.modules.device.models import Device, DeviceBinding
from app.modules.device_integration.schemas import IntegrationSyncPluginPayload, IntegrationSyncPluginResult
from app.modules.household.service import get_household_or_404
from app.modules.integration import repository as integration_repository
from app.modules.integration.discovery_service import mark_discovery_claimed
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin import config_service as plugin_config_service
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginServiceError,
    execute_household_plugin,
    get_household_plugin,
    require_available_household_plugin,
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
class DeviceCandidate:
    external_device_id: str
    primary_entity_id: str
    name: str
    room_name: str | None
    device_type: str
    entity_count: int
    already_synced: bool


@dataclass(slots=True)
class RoomCandidate:
    name: str
    entity_count: int
    exists_locally: bool
    can_sync: bool


@dataclass(slots=True)
class LiveStateLoadResult:
    state_maps: dict[str, dict[str, dict[str, Any]]]
    unavailable_instance_ids: set[str]


class DeviceIntegrationServiceError(PluginServiceError):
    def __init__(self, message: str, *, error_code: str, status_code: int, field: str | None = None) -> None:
        super().__init__(message, error_code=error_code, field=field, status_code=status_code)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.field = field


def list_device_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[DeviceCandidate]:
    result = _execute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="device_candidates")
    instance = _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    existing_bindings = _load_existing_binding_keys(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        platform=result.platform,
    )
    return [
        DeviceCandidate(
            external_device_id=item.external_device_id,
            primary_entity_id=item.primary_entity_id,
            name=item.name,
            room_name=item.room_name,
            device_type=item.device_type,
            entity_count=item.entity_count,
            already_synced=item.external_device_id in existing_bindings,
        )
        for item in result.device_candidates
        if item.external_device_id and instance.plugin_id == result.plugin_id
    ]


def list_room_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[RoomCandidate]:
    result = _execute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="room_candidates")
    room_cache = _load_room_cache(db, household_id)
    return [
        RoomCandidate(
            name=item.name,
            entity_count=item.entity_count,
            exists_locally=_normalize_room_key(item.name) in room_cache,
            can_sync=_normalize_room_key(item.name) not in room_cache,
        )
        for item in result.room_candidates
    ]


def sync_devices_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    external_device_ids: list[str] | None = None,
) -> SyncSummary:
    result = _execute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_sync",
        selected_external_ids=external_device_ids or [],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="device_sync")
    return _apply_device_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


def sync_rooms_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    room_names: list[str] | None = None,
) -> RoomSyncSummary:
    result = _execute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_sync",
        selected_external_ids=room_names or [],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="room_sync")
    return _apply_room_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


async def async_list_device_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[DeviceCandidate]:
    result = await _aexecute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="device_candidates")
    instance = _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    existing_bindings = _load_existing_binding_keys(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        platform=result.platform,
    )
    return [
        DeviceCandidate(
            external_device_id=item.external_device_id,
            primary_entity_id=item.primary_entity_id,
            name=item.name,
            room_name=item.room_name,
            device_type=item.device_type,
            entity_count=item.entity_count,
            already_synced=item.external_device_id in existing_bindings,
        )
        for item in result.device_candidates
        if item.external_device_id and instance.plugin_id == result.plugin_id
    ]


async def async_list_room_candidates_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> list[RoomCandidate]:
    result = await _aexecute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_candidates",
        selected_external_ids=[],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="room_candidates")
    room_cache = _load_room_cache(db, household_id)
    return [
        RoomCandidate(
            name=item.name,
            entity_count=item.entity_count,
            exists_locally=_normalize_room_key(item.name) in room_cache,
            can_sync=_normalize_room_key(item.name) not in room_cache,
        )
        for item in result.room_candidates
    ]


async def async_sync_devices_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    external_device_ids: list[str] | None = None,
) -> SyncSummary:
    result = await _aexecute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="device_sync",
        selected_external_ids=external_device_ids or [],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="device_sync")
    return _apply_device_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


async def async_sync_rooms_via_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    room_names: list[str] | None = None,
) -> RoomSyncSummary:
    result = await _aexecute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope="room_sync",
        selected_external_ids=room_names or [],
        options={},
    )
    _raise_if_integration_sync_failed(result, sync_scope="room_sync")
    return _apply_room_sync_result(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        result=result,
    )


def load_binding_live_state_maps_via_plugin(
    db: Session,
    *,
    household_id: str,
    bindings: list[DeviceBinding],
) -> LiveStateLoadResult:
    state_maps: dict[str, dict[str, dict[str, Any]]] = {}
    unavailable_instance_ids: set[str] = set()
    supported_instance_ids = _collect_live_state_supported_instance_ids(
        db,
        household_id=household_id,
        bindings=bindings,
    )
    if not supported_instance_ids:
        return LiveStateLoadResult(state_maps=state_maps, unavailable_instance_ids=unavailable_instance_ids)

    for integration_instance_id in supported_instance_ids:
        try:
            result = _execute_integration_sync_plugin(
                db,
                household_id=household_id,
                integration_instance_id=integration_instance_id,
                sync_scope="live_state_snapshot",
                selected_external_ids=[],
                options={},
            )
        except DeviceIntegrationServiceError:
            continue

        live_state_map = result.live_state_maps.get(integration_instance_id)
        if isinstance(live_state_map, dict):
            state_maps[integration_instance_id] = {
                entity_id: item
                for entity_id, item in live_state_map.items()
                if isinstance(entity_id, str) and entity_id.strip() and isinstance(item, dict)
            }

    return LiveStateLoadResult(
        state_maps=state_maps,
        unavailable_instance_ids=unavailable_instance_ids,
    )


def mark_integration_instance_sync_succeeded(db: Session, *, integration_instance_id: str) -> None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None:
        return
    instance.status = "active"
    instance.last_synced_at = utc_now_iso()
    instance.last_error_code = None
    instance.last_error_message = None
    instance.updated_at = utc_now_iso()
    db.add(instance)


def mark_integration_instance_sync_failed(
    db: Session,
    *,
    integration_instance_id: str,
    error_code: str,
    error_message: str,
) -> None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None:
        return
    instance.status = "degraded"
    instance.last_error_code = error_code
    instance.last_error_message = error_message
    instance.updated_at = utc_now_iso()
    db.add(instance)


def _execute_integration_sync_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> IntegrationSyncPluginResult:
    instance = _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    payload = _build_payload(
        db,
        instance=instance,
        sync_scope=sync_scope,
        selected_external_ids=selected_external_ids,
        options=options,
    )
    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=instance.plugin_id,
            plugin_type="integration",
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
    return _parse_plugin_result(execution.output, expected_plugin_id=instance.plugin_id)


async def _aexecute_integration_sync_plugin(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> IntegrationSyncPluginResult:
    # 这里先复用同步执行链，避免测试数据库在线程切换时重复抢连接池。
    return _execute_integration_sync_plugin(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
        sync_scope=sync_scope,
        selected_external_ids=selected_external_ids,
        options=options,
    )

    instance = _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    payload = _build_payload(
        db,
        instance=instance,
        sync_scope=sync_scope,
        selected_external_ids=selected_external_ids,
        options=options,
    )
    execution = await aexecute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=instance.plugin_id,
            plugin_type="integration",
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
    return _parse_plugin_result(execution.output, expected_plugin_id=instance.plugin_id)


def _require_syncable_integration_instance(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
) -> IntegrationInstance:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None or instance.household_id != household_id:
        raise DeviceIntegrationServiceError(
            "集成实例不存在或不属于当前家庭",
            error_code="integration_instance_not_found",
            status_code=404,
        )
    try:
        require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=instance.plugin_id,
            plugin_type="integration",
        )
    except PluginServiceError as exc:
        raise DeviceIntegrationServiceError(exc.detail, error_code=exc.error_code, status_code=exc.status_code) from exc
    return instance


def _build_payload(
    db: Session,
    *,
    instance: IntegrationInstance,
    sync_scope: str,
    selected_external_ids: list[str],
    options: dict[str, Any],
) -> IntegrationSyncPluginPayload:
    return IntegrationSyncPluginPayload(
        household_id=instance.household_id,
        plugin_id=instance.plugin_id,
        integration_instance_id=instance.id,
        sync_scope=sync_scope,  # type: ignore[arg-type]
        selected_external_ids=[item for item in selected_external_ids if isinstance(item, str) and item.strip()],
        options=options,
        runtime_config=_load_runtime_config(
            db,
            integration_instance_id=instance.id,
            plugin_id=instance.plugin_id,
        ),
    )


def _parse_plugin_result(output: Any, *, expected_plugin_id: str) -> IntegrationSyncPluginResult:
    try:
        result = IntegrationSyncPluginResult.model_validate(output or {})
    except ValidationError as exc:
        raise DeviceIntegrationServiceError(
            f"插件返回结果不合法: {exc.errors()[0].get('msg', 'unknown error')}",
            error_code="plugin_result_invalid",
            status_code=502,
        ) from exc
    if result.plugin_id != expected_plugin_id:
        raise DeviceIntegrationServiceError("插件返回了错误的 plugin_id", error_code="plugin_result_invalid", status_code=502)
    return result


def _raise_if_integration_sync_failed(result: IntegrationSyncPluginResult, *, sync_scope: str) -> None:
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
    result: IntegrationSyncPluginResult,
) -> SyncSummary:
    instance = _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
    get_household_or_404(db, household_id)
    room_cache = _load_room_cache(db, household_id)
    sync_rooms_enabled = _should_auto_assign_rooms(db, instance=instance)

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
                    household_id=household_id,
                    integration_instance_id=integration_instance_id,
                    platform=result.platform,
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
                        vendor=_resolve_vendor(platform=result.platform, capabilities=item.capabilities),
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
                    replace_binding_entities_from_capabilities(
                        db,
                        binding=binding,
                        capabilities=item.capabilities,
                    )
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
                    device.vendor = _resolve_vendor(platform=result.platform, capabilities=item.capabilities)
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
                    replace_binding_entities_from_capabilities(
                        db,
                        binding=binding,
                        capabilities=item.capabilities,
                    )
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

                mark_discovery_claimed(
                    db,
                    integration_instance_id=integration_instance_id,
                    plugin_id=result.plugin_id,
                    external_device_id=item.external_device_id,
                    external_entity_id=item.primary_entity_id,
                    device_id=device.id,
                )
                db.flush()
                synced_devices.append(device)
        except Exception as exc:
            failures.append(SyncFailure(entity_id=item.primary_entity_id, reason=str(exc)))

    for failure in result.failures:
        failures.append(SyncFailure(entity_id=failure.external_ref, reason=failure.reason))

    if failures:
        mark_integration_instance_sync_failed(
            db,
            integration_instance_id=integration_instance_id,
            error_code="integration_sync_failed",
            error_message=failures[0].reason,
        )
    else:
        mark_integration_instance_sync_succeeded(db, integration_instance_id=integration_instance_id)

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
    result: IntegrationSyncPluginResult,
) -> RoomSyncSummary:
    _require_syncable_integration_instance(
        db,
        household_id=household_id,
        integration_instance_id=integration_instance_id,
    )
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

    mark_integration_instance_sync_succeeded(db, integration_instance_id=integration_instance_id)

    return RoomSyncSummary(
        household_id=household_id,
        created_rooms=created_rooms,
        matched_entities=matched_entities,
        skipped_entities=skipped_entities,
        rooms=list(room_cache.values()),
    )


def _serialize_payload(payload: IntegrationSyncPluginPayload) -> dict[str, Any]:
    payload_dict = payload.model_dump(mode="json")
    if payload.system_context is not None:
        payload_dict["_system_context"] = payload.system_context
    return payload_dict


def _get_existing_binding(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    platform: str,
    external_device_id: str,
    primary_entity_id: str,
) -> DeviceBinding | None:
    scoped_binding = db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == platform,
            DeviceBinding.external_device_id == external_device_id,
        )
    )
    if scoped_binding is not None:
        return scoped_binding

    scoped_entity_binding = db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == platform,
            DeviceBinding.external_entity_id == primary_entity_id,
        )
    )
    if scoped_entity_binding is not None:
        return scoped_entity_binding

    for candidate in db.scalars(
        select(DeviceBinding).where(
            DeviceBinding.platform == platform,
            (DeviceBinding.external_device_id == external_device_id) | (DeviceBinding.external_entity_id == primary_entity_id),
        )
    ).all():
        device = db.get(Device, candidate.device_id)
        if device is None:
            continue
        if device.household_id != household_id:
            raise ValueError("existing binding belongs to another household")
        return candidate
    return None


def _load_existing_binding_keys(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    platform: str,
) -> set[str]:
    rows = db.execute(
        select(DeviceBinding.external_device_id)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.integration_instance_id == integration_instance_id,
            DeviceBinding.platform == platform,
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


def _should_auto_assign_rooms(db: Session, *, instance: IntegrationInstance) -> bool:
    runtime_config = _load_runtime_config(
        db,
        integration_instance_id=instance.id,
        plugin_id=instance.plugin_id,
    )
    return bool(runtime_config.get("sync_rooms_enabled"))


def _load_runtime_config(
    db: Session,
    *,
    integration_instance_id: str,
    plugin_id: str,
) -> dict[str, Any]:
    runtime_config = plugin_config_service.get_integration_instance_runtime_config(
        db,
        integration_instance_id=integration_instance_id,
        plugin_id=plugin_id,
    )
    return runtime_config.values


def _collect_live_state_supported_instance_ids(
    db: Session,
    *,
    household_id: str,
    bindings: list[DeviceBinding],
) -> list[str]:
    instance_ids: list[str] = []
    seen_instance_ids: set[str] = set()
    plugin_support_cache: dict[str, bool] = {}

    for binding in bindings:
        integration_instance_id = _normalize_optional_text(binding.integration_instance_id)
        plugin_id = _normalize_optional_text(binding.plugin_id)
        if not integration_instance_id or not plugin_id or integration_instance_id in seen_instance_ids:
            continue
        supports_live_state = plugin_support_cache.get(plugin_id)
        if supports_live_state is None:
            supports_live_state = _plugin_supports_live_state(
                db,
                household_id=household_id,
                plugin_id=plugin_id,
            )
            plugin_support_cache[plugin_id] = supports_live_state
        if not supports_live_state:
            continue
        seen_instance_ids.add(integration_instance_id)
        instance_ids.append(integration_instance_id)
    return instance_ids


def _plugin_supports_live_state(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> bool:
    try:
        plugin = get_household_plugin(
            db,
            household_id=household_id,
            plugin_id=plugin_id,
        )
    except PluginServiceError:
        return False
    integration_capability = plugin.capabilities.integration
    return bool(integration_capability and integration_capability.supports_live_state)


def _resolve_vendor(*, platform: str, capabilities: dict[str, Any]) -> str:
    for key in ("vendor", "vendor_code"):
        value = capabilities.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if platform == "open_xiaoai":
        return "xiaomi"
    return platform


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
