from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import Device, DeviceBinding
from app.modules.device_integration.service import (
    async_list_home_assistant_device_candidates_via_plugin,
    async_list_home_assistant_room_candidates_via_plugin,
    async_sync_home_assistant_devices_via_plugin,
    async_sync_home_assistant_rooms_via_plugin,
)
from app.modules.household.service import get_household_or_404
from app.modules.plugin import config_service as plugin_config_service
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin.schemas import PluginConfigFormRead, PluginConfigUpdateRequest, PluginRegistryItem
from app.modules.plugin.service import PluginServiceError, list_registered_plugins_for_household
from app.modules.room.models import Room

from .schemas import (
    IntegrationActionRead,
    IntegrationActionResultRead,
    IntegrationCatalogItemRead,
    IntegrationCatalogListRead,
    IntegrationConfigBindingRead,
    IntegrationInstanceActionRequest,
    IntegrationInstanceCreateRequest,
    IntegrationInstanceListRead,
    IntegrationInstanceRead,
    IntegrationPageViewRead,
    IntegrationResourceCountsRead,
    IntegrationResourceListRead,
    IntegrationResourceRead,
    IntegrationResourceSupportRead,
    IntegrationResourceType,
    IntegrationSyncStateRead,
)


INTEGRATION_PLUGIN_IDS = {"homeassistant"}
INTEGRATION_PERMISSION_PREFIXES = ("device.",)
INTEGRATION_PENDING_JOB_STATUSES = {"queued", "running", "retry_waiting", "waiting_response"}
HOME_ASSISTANT_SYNC_SCOPES = {"device_candidates", "device_sync", "room_candidates", "room_sync"}


def list_integration_catalog(
    db: Session,
    *,
    household_id: str,
    search: str | None = None,
    resource_type: IntegrationResourceType | None = None,
) -> IntegrationCatalogListRead:
    get_household_or_404(db, household_id)
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    configured_plugin_ids = {
        item.plugin_id
        for item in plugin_repository.list_plugin_config_instances(db, household_id=household_id, scope_type="plugin")
    }
    normalized_search = (search or "").strip().lower()

    items: list[IntegrationCatalogItemRead] = []
    for plugin in snapshot.items:
        if not _is_integration_plugin(plugin):
            continue
        resource_support = _build_resource_support(plugin)
        if resource_type is not None and not getattr(resource_support, resource_type):
            continue
        if normalized_search and normalized_search not in _build_search_text(plugin):
            continue
        items.append(
            IntegrationCatalogItemRead(
                plugin_id=plugin.id,
                name=plugin.name,
                description=_build_plugin_description(plugin),
                source_type=plugin.source_type,
                risk_level=plugin.risk_level,
                resource_support=resource_support,
                config_schema_available=bool(plugin.config_specs),
                already_added=plugin.id in configured_plugin_ids,
                supported_actions=_build_catalog_actions(plugin),
                tags=_build_catalog_tags(plugin),
            )
        )

    return IntegrationCatalogListRead(household_id=household_id, items=items)


def list_integration_instances(
    db: Session,
    *,
    household_id: str,
) -> IntegrationInstanceListRead:
    get_household_or_404(db, household_id)
    plugins_by_id = _load_integration_plugins_by_id(db, household_id=household_id)
    resource_counts_by_plugin = _load_resource_counts_by_plugin(db, household_id=household_id)
    latest_job_by_plugin = _load_latest_job_by_plugin(db, household_id=household_id)

    items: list[IntegrationInstanceRead] = []
    for instance in plugin_repository.list_plugin_config_instances(db, household_id=household_id, scope_type="plugin"):
        plugin = plugins_by_id.get(instance.plugin_id)
        if plugin is None:
            continue
        items.append(
            _build_integration_instance_read(
                db,
                household_id=household_id,
                plugin=plugin,
                instance=instance,
                resource_counts_by_plugin=resource_counts_by_plugin,
                latest_job_by_plugin=latest_job_by_plugin,
            )
        )

    return IntegrationInstanceListRead(household_id=household_id, items=items)


def list_integration_resources(
    db: Session,
    *,
    household_id: str,
    resource_type: IntegrationResourceType,
    integration_instance_id: str | None = None,
    room_id: str | None = None,
    status: str | None = None,
) -> IntegrationResourceListRead:
    get_household_or_404(db, household_id)
    if resource_type != "device":
        return IntegrationResourceListRead(household_id=household_id, resource_type=resource_type, items=[])

    instance_map = {
        item.plugin_id: item.id
        for item in plugin_repository.list_plugin_config_instances(db, household_id=household_id, scope_type="plugin")
    }
    stmt: Select[tuple[Device, DeviceBinding, str | None]] = (
        select(Device, DeviceBinding, Room.name)
        .join(DeviceBinding, DeviceBinding.device_id == Device.id)
        .outerjoin(Room, Room.id == Device.room_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.plugin_id.is_not(None),
        )
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    if room_id is not None:
        stmt = stmt.where(Device.room_id == room_id)
    if status is not None:
        stmt = stmt.where(Device.status == status)

    items: list[IntegrationResourceRead] = []
    for device, binding, room_name in db.execute(stmt).all():
        if not binding.plugin_id:
            continue
        mapped_instance_id = instance_map.get(binding.plugin_id)
        if mapped_instance_id is None:
            continue
        if integration_instance_id is not None and mapped_instance_id != integration_instance_id:
            continue
        items.append(
            IntegrationResourceRead(
                id=device.id,
                household_id=device.household_id,
                integration_instance_id=mapped_instance_id,
                plugin_id=binding.plugin_id,
                resource_type="device",
                resource_key=(binding.external_device_id or binding.external_entity_id),
                name=device.name,
                description=None,
                category=device.device_type,
                status=device.status,  # type: ignore[arg-type]
                room_id=device.room_id,
                room_name=room_name,
                device_id=device.id,
                parent_resource_id=None,
                capabilities=_load_binding_capabilities(binding.capabilities),
                metadata={
                    "vendor": device.vendor,
                    "device_type": device.device_type,
                    "external_entity_id": binding.external_entity_id,
                    "external_device_id": binding.external_device_id,
                    "controllable": bool(device.controllable),
                },
                last_error=None,
                updated_at=device.updated_at,
            )
        )

    return IntegrationResourceListRead(household_id=household_id, resource_type=resource_type, items=items)


def build_integration_page_view(db: Session, *, household_id: str) -> IntegrationPageViewRead:
    return IntegrationPageViewRead(
        household_id=household_id,
        catalog=list_integration_catalog(db, household_id=household_id).items,
        instances=list_integration_instances(db, household_id=household_id).items,
        discoveries=[],
        resources={
            "device": list_integration_resources(db, household_id=household_id, resource_type="device").items,
            "entity": [],
            "helper": [],
        },
    )


def create_integration_instance(
    db: Session,
    *,
    payload: IntegrationInstanceCreateRequest,
    updated_by: str | None = None,
) -> IntegrationInstanceRead:
    plugin = _require_integration_plugin(db, household_id=payload.household_id, plugin_id=payload.plugin_id)
    form: PluginConfigFormRead = plugin_config_service.save_plugin_config_form(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        payload=PluginConfigUpdateRequest(
            scope_type=payload.scope_type,
            scope_key=payload.scope_key,
            values=payload.config,
            clear_secret_fields=payload.clear_secret_fields,
        ),
        updated_by=updated_by,
    )
    instance = plugin_repository.get_plugin_config_instance(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        scope_type=form.view.scope_type,
        scope_key=form.view.scope_key,
    )
    if instance is None:
        raise PluginServiceError(
            "插件配置已保存，但没有找到对应的配置实例。",
            error_code="integration_instance_not_found",
            status_code=500,
        )

    return _build_integration_instance_read(
        db,
        household_id=payload.household_id,
        plugin=plugin,
        instance=instance,
        resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=payload.household_id),
        latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=payload.household_id),
    )


async def execute_integration_instance_action(
    db: Session,
    *,
    instance_id: str,
    payload: IntegrationInstanceActionRequest,
    updated_by: str | None = None,
) -> IntegrationActionResultRead:
    instance = plugin_repository.get_plugin_config_instance_by_id(db, instance_id)
    if instance is None:
        raise PluginServiceError(
            f"集成实例不存在: {instance_id}",
            error_code="integration_instance_not_found",
            field="instance_id",
            status_code=404,
        )

    household_id = instance.household_id
    plugin = _require_integration_plugin(db, household_id=household_id, plugin_id=instance.plugin_id)

    if payload.action == "configure":
        return _execute_configure_action(
            db,
            household_id=household_id,
            plugin=plugin,
            instance=instance,
            payload=payload,
            updated_by=updated_by,
        )

    if payload.action == "sync":
        return await _execute_sync_action(
            db,
            household_id=household_id,
            plugin=plugin,
            instance=instance,
            payload=payload,
        )

    raise PluginServiceError(
        f"当前集成动作暂不支持: {payload.action}",
        error_code="integration_action_not_supported",
        field="action",
        status_code=400,
    )


def _execute_configure_action(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    instance,
    payload: IntegrationInstanceActionRequest,
    updated_by: str | None,
) -> IntegrationActionResultRead:
    raw_values = payload.payload.get("values")
    clear_secret_fields = payload.payload.get("clear_secret_fields")
    if raw_values is not None and not isinstance(raw_values, dict):
        raise PluginServiceError(
            "configure.payload.values 必须是对象。",
            error_code="integration_action_payload_invalid",
            field="payload.values",
            status_code=400,
        )
    if clear_secret_fields is not None and not isinstance(clear_secret_fields, list):
        raise PluginServiceError(
            "configure.payload.clear_secret_fields 必须是数组。",
            error_code="integration_action_payload_invalid",
            field="payload.clear_secret_fields",
            status_code=400,
        )

    form = plugin_config_service.save_plugin_config_form(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
        payload=PluginConfigUpdateRequest(
            scope_type=str(payload.payload.get("scope_type") or instance.scope_type),
            scope_key=str(payload.payload.get("scope_key") or instance.scope_key),
            values=(raw_values if isinstance(raw_values, dict) else {}),
            clear_secret_fields=(
                [item for item in clear_secret_fields if isinstance(item, str)]
                if isinstance(clear_secret_fields, list)
                else []
            ),
        ),
        updated_by=updated_by,
    )
    db.flush()

    refreshed_instance = plugin_repository.get_plugin_config_instance_by_id(db, instance.id)
    if refreshed_instance is None:
        raise PluginServiceError(
            f"集成实例不存在: {instance.id}",
            error_code="integration_instance_not_found",
            field="instance_id",
            status_code=404,
        )

    integration_instance = _build_integration_instance_read(
        db,
        household_id=household_id,
        plugin=plugin,
        instance=refreshed_instance,
        resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=household_id),
        latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=household_id),
    )
    return IntegrationActionResultRead(
        action="configure",
        execution_mode="immediate",
        message="插件配置已保存。",
        instance=integration_instance,
        config_form=form,
        output={},
    )


async def _execute_sync_action(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    instance,
    payload: IntegrationInstanceActionRequest,
) -> IntegrationActionResultRead:
    sync_scope = payload.payload.get("sync_scope")
    if not isinstance(sync_scope, str) or sync_scope not in HOME_ASSISTANT_SYNC_SCOPES:
        raise PluginServiceError(
            "sync.payload.sync_scope 不合法。",
            error_code="integration_action_payload_invalid",
            field="payload.sync_scope",
            status_code=400,
        )
    if plugin.id != "homeassistant":
        raise PluginServiceError(
            f"插件 {plugin.id} 还没有接通统一同步动作。",
            error_code="integration_action_not_supported",
            field="action",
            status_code=400,
        )

    selected_ids = payload.payload.get("selected_external_ids")
    if selected_ids is not None and not isinstance(selected_ids, list):
        raise PluginServiceError(
            "sync.payload.selected_external_ids 必须是数组。",
            error_code="integration_action_payload_invalid",
            field="payload.selected_external_ids",
            status_code=400,
        )
    normalized_selected_ids = [
        item.strip()
        for item in (selected_ids or [])
        if isinstance(item, str) and item.strip()
    ]

    if sync_scope == "device_candidates":
        items = await async_list_home_assistant_device_candidates_via_plugin(db, household_id=household_id)
        return IntegrationActionResultRead(
            action="sync",
            execution_mode="immediate",
            instance=_build_integration_instance_read(
                db,
                household_id=household_id,
                plugin=plugin,
                instance=instance,
                resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=household_id),
                latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=household_id),
            ),
            output={
                "sync_scope": sync_scope,
                "items": [
                    {
                        "external_device_id": item.external_device_id,
                        "primary_entity_id": item.primary_entity_id,
                        "name": item.name,
                        "room_name": item.room_name,
                        "device_type": item.device_type,
                        "entity_count": item.entity_count,
                        "already_synced": item.already_synced,
                    }
                    for item in items
                ],
            },
        )

    if sync_scope == "room_candidates":
        items = await async_list_home_assistant_room_candidates_via_plugin(db, household_id=household_id)
        return IntegrationActionResultRead(
            action="sync",
            execution_mode="immediate",
            instance=_build_integration_instance_read(
                db,
                household_id=household_id,
                plugin=plugin,
                instance=instance,
                resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=household_id),
                latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=household_id),
            ),
            output={
                "sync_scope": sync_scope,
                "items": [
                    {
                        "name": item.name,
                        "entity_count": item.entity_count,
                        "exists_locally": item.exists_locally,
                        "can_sync": item.can_sync,
                    }
                    for item in items
                ],
            },
        )

    if sync_scope == "device_sync":
        summary = await async_sync_home_assistant_devices_via_plugin(
            db,
            household_id=household_id,
            external_device_ids=normalized_selected_ids,
        )
        db.flush()
        return IntegrationActionResultRead(
            action="sync",
            execution_mode="immediate",
            message="Home Assistant 设备同步完成。",
            instance=_build_integration_instance_read(
                db,
                household_id=household_id,
                plugin=plugin,
                instance=instance,
                resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=household_id),
                latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=household_id),
            ),
            output={
                "sync_scope": sync_scope,
                "summary": {
                    "household_id": summary.household_id,
                    "created_devices": summary.created_devices,
                    "updated_devices": summary.updated_devices,
                    "created_bindings": summary.created_bindings,
                    "created_rooms": summary.created_rooms,
                    "assigned_rooms": summary.assigned_rooms,
                    "skipped_entities": summary.skipped_entities,
                    "failed_entities": summary.failed_entities,
                    "devices": [device.id for device in summary.devices],
                    "failures": [
                        {
                            "entity_id": failure.entity_id,
                            "reason": failure.reason,
                        }
                        for failure in summary.failures
                    ],
                },
            },
        )

    summary = await async_sync_home_assistant_rooms_via_plugin(
        db,
        household_id=household_id,
        room_names=normalized_selected_ids,
    )
    db.flush()
    return IntegrationActionResultRead(
        action="sync",
        execution_mode="immediate",
        message="Home Assistant 房间同步完成。",
        instance=_build_integration_instance_read(
            db,
            household_id=household_id,
            plugin=plugin,
            instance=instance,
            resource_counts_by_plugin=_load_resource_counts_by_plugin(db, household_id=household_id),
            latest_job_by_plugin=_load_latest_job_by_plugin(db, household_id=household_id),
        ),
        output={
            "sync_scope": sync_scope,
            "summary": {
                "household_id": summary.household_id,
                "created_rooms": summary.created_rooms,
                "matched_entities": summary.matched_entities,
                "skipped_entities": summary.skipped_entities,
                "rooms": [
                    {
                        "id": room.id,
                        "name": room.name,
                    }
                    for room in summary.rooms
                ],
            },
        },
    )


def _build_integration_instance_read(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    instance,
    resource_counts_by_plugin: dict[str, IntegrationResourceCountsRead],
    latest_job_by_plugin: dict[str, Any],
) -> IntegrationInstanceRead:
    config_form = plugin_config_service.get_plugin_config_form(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
        scope_type=instance.scope_type,
        scope_key=instance.scope_key,
    )
    latest_job = latest_job_by_plugin.get(plugin.id)
    return IntegrationInstanceRead(
        id=instance.id,
        household_id=household_id,
        plugin_id=plugin.id,
        display_name=plugin.name,
        description=_build_plugin_description(plugin),
        source_type=plugin.source_type,
        status=_resolve_instance_status(plugin=plugin, latest_job=latest_job),
        config_state=config_form.view.state,
        resource_support=_build_resource_support(plugin),
        resource_counts=resource_counts_by_plugin.get(plugin.id, IntegrationResourceCountsRead()),
        sync_state=IntegrationSyncStateRead(
            last_synced_at=(latest_job.created_at if latest_job and latest_job.status == "succeeded" else None),
            last_job_id=(latest_job.id if latest_job else None),
            last_job_status=(latest_job.status if latest_job else None),
            pending_job_id=(
                latest_job.id
                if latest_job and latest_job.status in INTEGRATION_PENDING_JOB_STATUSES
                else None
            ),
        ),
        config_bindings=[
            IntegrationConfigBindingRead(
                scope_type=config_form.view.scope_type,
                scope_key=config_form.view.scope_key,
                state=config_form.view.state,
                form_available=bool(plugin.config_specs),
                config_spec=config_form.config_spec,
            )
        ],
        allowed_actions=_build_instance_actions(plugin, config_form=config_form),
        last_error=(
            None
            if latest_job is None or latest_job.status != "failed"
            else {
                "code": latest_job.last_error_code or "integration_sync_failed",
                "message": latest_job.last_error_message or "集成同步失败",
                "occurred_at": latest_job.updated_at,
            }
        ),
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def _load_integration_plugins_by_id(db: Session, *, household_id: str) -> dict[str, PluginRegistryItem]:
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    return {
        item.id: item
        for item in snapshot.items
        if _is_integration_plugin(item)
    }


def _require_integration_plugin(db: Session, *, household_id: str, plugin_id: str) -> PluginRegistryItem:
    plugin = next(
        (item for item in list_registered_plugins_for_household(db, household_id=household_id).items if item.id == plugin_id),
        None,
    )
    if plugin is None or not _is_integration_plugin(plugin):
        raise PluginServiceError(
            f"插件 {plugin_id} 不属于设备与集成目录。",
            error_code="integration_plugin_not_found",
            field="plugin_id",
            status_code=404,
        )
    return plugin


def _is_integration_plugin(plugin: PluginRegistryItem) -> bool:
    if plugin.id in INTEGRATION_PLUGIN_IDS:
        return True
    return any(permission.startswith(INTEGRATION_PERMISSION_PREFIXES) for permission in plugin.permissions)


def _build_resource_support(plugin: PluginRegistryItem) -> IntegrationResourceSupportRead:
    if plugin.id == "homeassistant":
        return IntegrationResourceSupportRead(device=True, entity=True, helper=True)
    supports_device = any(permission.startswith("device.") for permission in plugin.permissions)
    return IntegrationResourceSupportRead(
        device=supports_device,
        entity=supports_device,
        helper=False,
    )


def _build_search_text(plugin: PluginRegistryItem) -> str:
    return " ".join([plugin.id, plugin.name, *plugin.permissions, *plugin.triggers]).lower()


def _build_plugin_description(plugin: PluginRegistryItem) -> str | None:
    if plugin.id == "homeassistant":
        return "通过统一插件目录接入 Home Assistant，并把设备、实体和辅助元素纳入同一套管理模型。"
    return None


def _build_catalog_actions(plugin: PluginRegistryItem) -> list[str]:
    actions: list[str] = []
    if plugin.config_specs:
        actions.append("configure")
    if "connector" in plugin.types:
        actions.append("sync")
    actions.append("delete")
    return actions


def _build_instance_actions(
    plugin: PluginRegistryItem,
    *,
    config_form: PluginConfigFormRead,
) -> list[IntegrationActionRead]:
    actions: list[IntegrationActionRead] = []
    if plugin.config_specs:
        actions.append(
            IntegrationActionRead(
                action="configure",
                label="更新配置",
                destructive=False,
                disabled=False,
                disabled_reason=None,
            )
        )
    if "connector" in plugin.types:
        sync_disabled = config_form.view.state != "configured"
        actions.append(
            IntegrationActionRead(
                action="sync",
                label="同步资源",
                destructive=False,
                disabled=sync_disabled,
                disabled_reason=("请先完成配置" if sync_disabled else None),
            )
        )
    actions.append(
        IntegrationActionRead(
            action="delete",
            label="删除集成",
            destructive=True,
            disabled=True,
            disabled_reason="删除动作还没有接通。",
        )
    )
    return actions


def _build_catalog_tags(plugin: PluginRegistryItem) -> list[str]:
    return sorted({*plugin.types, *plugin.permissions})


def _load_resource_counts_by_plugin(db: Session, *, household_id: str) -> dict[str, IntegrationResourceCountsRead]:
    stmt: Select[tuple[DeviceBinding.plugin_id, str]] = (
        select(DeviceBinding.plugin_id, Device.id)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.plugin_id.is_not(None),
        )
    )
    counts: dict[str, IntegrationResourceCountsRead] = defaultdict(IntegrationResourceCountsRead)
    for plugin_id, _device_id in db.execute(stmt).all():
        if not plugin_id:
            continue
        entry = counts[plugin_id]
        entry.device += 1
    return counts


def _load_latest_job_by_plugin(db: Session, *, household_id: str) -> dict[str, Any]:
    rows = plugin_repository.list_plugin_jobs(db, household_id=household_id)
    latest: dict[str, Any] = {}
    for row in rows:
        latest.setdefault(row.plugin_id, row)
    return latest


def _resolve_instance_status(*, plugin: PluginRegistryItem, latest_job: Any | None) -> str:
    if not plugin.enabled:
        return "disabled"
    if latest_job is None:
        return "active"
    if latest_job.status == "failed":
        return "degraded"
    return "active"


def _load_binding_capabilities(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    loaded = load_json(raw_value)
    return loaded if isinstance(loaded, dict) else {}
