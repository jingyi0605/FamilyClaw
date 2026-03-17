from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.utils import load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.device_integration.service import (
    async_list_device_candidates_via_plugin,
    async_list_room_candidates_via_plugin,
    async_sync_devices_via_plugin,
    async_sync_rooms_via_plugin,
)
from app.modules.household.service import get_household_or_404
from app.modules.integration import repository as integration_repository
from app.modules.integration.discovery_service import (
    attach_open_xiaoai_discoveries_to_instance,
    list_integration_discoveries,
    list_unbound_open_xiaoai_gateway_ids,
)
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin import config_service as plugin_config_service
from app.modules.plugin.schemas import PluginConfigFormRead, PluginManifestConfigSpec, PluginRegistryItem
from app.modules.plugin.service import (
    PluginServiceError,
    get_household_plugin,
    list_registered_plugins_for_household,
    require_available_household_plugin,
)
from app.modules.room.models import Room
from app.modules.voice.binding_service import OPEN_XIAOAI_PLUGIN_ID

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


INTEGRATION_PERMISSION_PREFIXES = ("device.",)
SUPPORTED_SYNC_SCOPES = {"device_candidates", "device_sync", "room_candidates", "room_sync"}


def list_integration_catalog(
    db: Session,
    *,
    household_id: str,
    search: str | None = None,
    resource_type: IntegrationResourceType | None = None,
) -> IntegrationCatalogListRead:
    get_household_or_404(db, household_id)
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    added_plugin_ids = {
        item.plugin_id
        for item in integration_repository.list_integration_instances(db, household_id=household_id)
    }
    normalized_search = (search or "").strip().lower()

    items: list[IntegrationCatalogItemRead] = []
    for plugin in snapshot.items:
        if not _is_integration_plugin(plugin):
            continue
        if not plugin.enabled:
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
                config_schema_available=bool(_get_plugin_config_spec(plugin)),
                config_spec=_get_plugin_config_spec(plugin),
                already_added=plugin.id in added_plugin_ids,
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
    resource_counts_by_instance = _load_resource_counts_by_instance(db, household_id=household_id)

    items: list[IntegrationInstanceRead] = []
    for instance in integration_repository.list_integration_instances(db, household_id=household_id):
        plugin = plugins_by_id.get(instance.plugin_id)
        if plugin is None:
            continue
        items.append(
            _build_integration_instance_read(
                db,
                plugin=plugin,
                instance=instance,
                resource_counts_by_instance=resource_counts_by_instance,
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

    stmt: Select[tuple[Device, DeviceBinding, str | None]] = (
        select(Device, DeviceBinding, Room.name)
        .join(DeviceBinding, DeviceBinding.device_id == Device.id)
        .outerjoin(Room, Room.id == Device.room_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.integration_instance_id.is_not(None),
        )
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    if integration_instance_id is not None:
        stmt = stmt.where(DeviceBinding.integration_instance_id == integration_instance_id)
    if room_id is not None:
        stmt = stmt.where(Device.room_id == room_id)
    if status is not None:
        stmt = stmt.where(Device.status == status)

    items: list[IntegrationResourceRead] = []
    for device, binding, room_name in db.execute(stmt).all():
        if not binding.integration_instance_id or not binding.plugin_id:
            continue
        items.append(
            IntegrationResourceRead(
                id=device.id,
                household_id=device.household_id,
                integration_instance_id=binding.integration_instance_id,
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
        discoveries=list_integration_discoveries(db, household_id=household_id).items,
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
    plugin = _require_available_integration_plugin(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
    )
    normalized_config = _normalize_instance_config(
        db,
        household_id=payload.household_id,
        plugin_id=plugin.id,
        config=payload.config,
    )
    instance = IntegrationInstance(
        id=new_uuid(),
        household_id=payload.household_id,
        plugin_id=plugin.id,
        display_name=payload.display_name.strip(),
        status="draft",
        last_synced_at=None,
        last_error_code=None,
        last_error_message=None,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    integration_repository.add_integration_instance(db, instance)
    db.flush()

    form = plugin_config_service.save_integration_instance_plugin_config_form(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        integration_instance_id=instance.id,
        values=normalized_config,
        clear_secret_fields=payload.clear_secret_fields,
        updated_by=updated_by,
    )
    if plugin.id == OPEN_XIAOAI_PLUGIN_ID:
        attach_open_xiaoai_discoveries_to_instance(
            db,
            household_id=payload.household_id,
            integration_instance_id=instance.id,
            gateway_id=str(normalized_config.get("gateway_id") or ""),
        )
    instance.status = "active" if form.view.state == "configured" else "draft"
    instance.updated_at = utc_now_iso()
    db.add(instance)
    db.flush()

    return _build_integration_instance_read(
        db,
        plugin=plugin,
        instance=instance,
        resource_counts_by_instance=_load_resource_counts_by_instance(db, household_id=payload.household_id),
    )


async def execute_integration_instance_action(
    db: Session,
    *,
    instance_id: str,
    payload: IntegrationInstanceActionRequest,
    updated_by: str | None = None,
) -> IntegrationActionResultRead:
    instance = integration_repository.get_integration_instance(db, instance_id)
    if instance is None:
        raise PluginServiceError(
            f"集成实例不存在: {instance_id}",
            error_code="integration_instance_not_found",
            field="instance_id",
            status_code=404,
        )

    plugin = _get_integration_plugin(
        db,
        household_id=instance.household_id,
        plugin_id=instance.plugin_id,
    )

    if payload.action == "configure":
        return _execute_configure_action(
            db,
            plugin=plugin,
            instance=instance,
            payload=payload,
            updated_by=updated_by,
        )

    if payload.action == "sync":
        plugin = _require_available_integration_plugin(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
        )
        return await _execute_sync_action(
            db,
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
    plugin: PluginRegistryItem,
    instance: IntegrationInstance,
    payload: IntegrationInstanceActionRequest,
    updated_by: str | None,
) -> IntegrationActionResultRead:
    raw_values = payload.payload.get("values")
    clear_secret_fields = payload.payload.get("clear_secret_fields")
    if raw_values is not None and not isinstance(raw_values, dict):
        raise PluginServiceError(
            "configure.payload.values 必须是对象",
            error_code="integration_action_payload_invalid",
            field="payload.values",
            status_code=400,
        )
    if clear_secret_fields is not None and not isinstance(clear_secret_fields, list):
        raise PluginServiceError(
            "configure.payload.clear_secret_fields 必须是数组",
            error_code="integration_action_payload_invalid",
            field="payload.clear_secret_fields",
            status_code=400,
        )

    form = plugin_config_service.save_integration_instance_plugin_config_form(
        db,
        household_id=instance.household_id,
        plugin_id=plugin.id,
        integration_instance_id=instance.id,
        values=(raw_values if isinstance(raw_values, dict) else {}),
        clear_secret_fields=(
            [item for item in clear_secret_fields if isinstance(item, str)]
            if isinstance(clear_secret_fields, list)
            else []
        ),
        updated_by=updated_by,
    )
    instance.status = "active" if form.view.state == "configured" else "draft"
    instance.updated_at = utc_now_iso()
    db.add(instance)
    db.flush()

    integration_instance = _build_integration_instance_read(
        db,
        plugin=plugin,
        instance=instance,
        resource_counts_by_instance=_load_resource_counts_by_instance(db, household_id=instance.household_id),
    )
    return IntegrationActionResultRead(
        action="configure",
        execution_mode="immediate",
        message="插件配置已保存",
        instance=integration_instance,
        config_form=form,
        output={},
    )


async def _execute_sync_action(
    db: Session,
    *,
    plugin: PluginRegistryItem,
    instance: IntegrationInstance,
    payload: IntegrationInstanceActionRequest,
) -> IntegrationActionResultRead:
    sync_scope = payload.payload.get("sync_scope")
    if not isinstance(sync_scope, str) or sync_scope not in SUPPORTED_SYNC_SCOPES:
        raise PluginServiceError(
            "sync.payload.sync_scope 不合法",
            error_code="integration_action_payload_invalid",
            field="payload.sync_scope",
            status_code=400,
        )

    selected_ids = payload.payload.get("selected_external_ids")
    if selected_ids is not None and not isinstance(selected_ids, list):
        raise PluginServiceError(
            "sync.payload.selected_external_ids 必须是数组",
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
        items = await async_list_device_candidates_via_plugin(
            db,
            household_id=instance.household_id,
            integration_instance_id=instance.id,
        )
        return _build_sync_items_result(db, instance=instance, plugin=plugin, sync_scope=sync_scope, items=items)

    if sync_scope == "room_candidates":
        items = await async_list_room_candidates_via_plugin(
            db,
            household_id=instance.household_id,
            integration_instance_id=instance.id,
        )
        return _build_sync_items_result(db, instance=instance, plugin=plugin, sync_scope=sync_scope, items=items)

    if sync_scope == "device_sync":
        summary = await async_sync_devices_via_plugin(
            db,
            household_id=instance.household_id,
            integration_instance_id=instance.id,
            external_device_ids=normalized_selected_ids,
        )
        db.flush()
        return IntegrationActionResultRead(
            action="sync",
            execution_mode="immediate",
            message=f"{plugin.name} 设备同步完成",
            instance=_build_integration_instance_read(
                db,
                plugin=plugin,
                instance=instance,
                resource_counts_by_instance=_load_resource_counts_by_instance(db, household_id=instance.household_id),
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

    summary = await async_sync_rooms_via_plugin(
        db,
        household_id=instance.household_id,
        integration_instance_id=instance.id,
        room_names=normalized_selected_ids,
    )
    db.flush()
    return IntegrationActionResultRead(
        action="sync",
        execution_mode="immediate",
        message=f"{plugin.name} 房间同步完成",
        instance=_build_integration_instance_read(
            db,
            plugin=plugin,
            instance=instance,
            resource_counts_by_instance=_load_resource_counts_by_instance(db, household_id=instance.household_id),
        ),
        output={
            "sync_scope": sync_scope,
            "summary": {
                "household_id": summary.household_id,
                "created_rooms": summary.created_rooms,
                "matched_entities": summary.matched_entities,
                "skipped_entities": summary.skipped_entities,
                "rooms": [{"id": room.id, "name": room.name} for room in summary.rooms],
            },
        },
    )


def _build_sync_items_result(
    db: Session,
    *,
    instance: IntegrationInstance,
    plugin: PluginRegistryItem,
    sync_scope: str,
    items: list[Any],
) -> IntegrationActionResultRead:
    serialized_items: list[dict[str, Any]] = []
    for item in items:
        if sync_scope == "device_candidates":
            serialized_items.append(
                {
                    "external_device_id": item.external_device_id,
                    "primary_entity_id": item.primary_entity_id,
                    "name": item.name,
                    "room_name": item.room_name,
                    "device_type": item.device_type,
                    "entity_count": item.entity_count,
                    "already_synced": item.already_synced,
                }
            )
        else:
            serialized_items.append(
                {
                    "name": item.name,
                    "entity_count": item.entity_count,
                    "exists_locally": item.exists_locally,
                    "can_sync": item.can_sync,
                }
            )
    return IntegrationActionResultRead(
        action="sync",
        execution_mode="immediate",
        instance=_build_integration_instance_read(
            db,
            plugin=plugin,
            instance=instance,
            resource_counts_by_instance=_load_resource_counts_by_instance(db, household_id=instance.household_id),
        ),
        output={
            "sync_scope": sync_scope,
            "items": serialized_items,
        },
    )


def _build_integration_instance_read(
    db: Session,
    *,
    plugin: PluginRegistryItem,
    instance: IntegrationInstance,
    resource_counts_by_instance: dict[str, IntegrationResourceCountsRead],
) -> IntegrationInstanceRead:
    config_form = plugin_config_service.get_integration_instance_plugin_config_form(
        db,
        household_id=instance.household_id,
        plugin_id=plugin.id,
        integration_instance_id=instance.id,
    )
    plugin_disabled_reason = None if plugin.enabled else plugin.disabled_reason
    instance_status = instance.status if plugin.enabled or instance.status == "deleted" else "disabled"
    instance_last_error = (
        None
        if not instance.last_error_code and not instance.last_error_message and plugin_disabled_reason is None
        else {
            "code": instance.last_error_code or ("plugin_disabled" if plugin_disabled_reason else "integration_sync_failed"),
            "message": instance.last_error_message or plugin_disabled_reason or "集成同步失败",
            "occurred_at": instance.updated_at,
        }
    )
    return IntegrationInstanceRead(
        id=instance.id,
        household_id=instance.household_id,
        plugin_id=plugin.id,
        display_name=instance.display_name,
        description=_build_plugin_description(plugin),
        source_type=plugin.source_type,
        status=instance_status,  # type: ignore[arg-type]
        config_state=config_form.view.state,
        resource_support=_build_resource_support(plugin),
        resource_counts=resource_counts_by_instance.get(instance.id, IntegrationResourceCountsRead()),
        sync_state=IntegrationSyncStateRead(
            last_synced_at=instance.last_synced_at,
            last_job_id=None,
            last_job_status=None,
            pending_job_id=None,
        ),
        config_bindings=[
            IntegrationConfigBindingRead(
                scope_type=config_form.view.scope_type,
                scope_key=config_form.view.scope_key,
                state=config_form.view.state,
                form_available=bool(_get_plugin_config_spec(plugin)),
                config_spec=config_form.config_spec,
            )
        ],
        allowed_actions=_build_instance_actions(plugin, config_form=config_form),
        last_error=instance_last_error,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def _load_integration_plugins_by_id(db: Session, *, household_id: str) -> dict[str, PluginRegistryItem]:
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    return {item.id: item for item in snapshot.items if _is_integration_plugin(item)}


def _get_integration_plugin(db: Session, *, household_id: str, plugin_id: str) -> PluginRegistryItem:
    plugin = get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    if not _is_integration_plugin(plugin):
        raise PluginServiceError(
            f"插件 {plugin_id} 不属于设备与集成目录",
            error_code="integration_plugin_not_found",
            field="plugin_id",
            status_code=404,
        )
    return plugin


def _require_available_integration_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginRegistryItem:
    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        plugin_type="connector",
    )
    if not _is_integration_plugin(plugin):
        raise PluginServiceError(
            f"插件 {plugin_id} 不属于设备与集成目录",
            error_code="integration_plugin_not_found",
            field="plugin_id",
            status_code=404,
        )
    return plugin


def _is_integration_plugin(plugin: PluginRegistryItem) -> bool:
    if "connector" not in plugin.types:
        return False
    return any(permission.startswith(INTEGRATION_PERMISSION_PREFIXES) for permission in plugin.permissions)


def _build_resource_support(plugin: PluginRegistryItem) -> IntegrationResourceSupportRead:
    supports_device = any(permission.startswith("device.") for permission in plugin.permissions)
    return IntegrationResourceSupportRead(
        device=supports_device,
        entity=(plugin.id == "homeassistant"),
        helper=(plugin.id == "homeassistant"),
    )


def _build_search_text(plugin: PluginRegistryItem) -> str:
    return " ".join([plugin.id, plugin.name, *plugin.permissions, *plugin.triggers]).lower()


def _build_plugin_description(plugin: PluginRegistryItem) -> str | None:
    if plugin.id == "homeassistant":
        return "通过正式集成实例接入 Home Assistant，并把设备同步到统一平台资源链路。"
    if plugin.id == "open-xiaoai-speaker":
        return "把一个小爱网关实例接入平台，并在该实例下发现和管理多台小爱音箱。"
    return None


def _build_catalog_actions(plugin: PluginRegistryItem) -> list[str]:
    actions: list[str] = []
    if _get_plugin_config_spec(plugin) is not None:
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
    if _get_plugin_config_spec(plugin) is not None:
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
        sync_disabled_reason = plugin.disabled_reason
        if sync_disabled_reason is None and config_form.view.state != "configured":
            sync_disabled_reason = "请先完成配置"
        actions.append(
            IntegrationActionRead(
                action="sync",
                label="同步资源",
                destructive=False,
                disabled=sync_disabled_reason is not None,
                disabled_reason=sync_disabled_reason,
            )
        )
    actions.append(
        IntegrationActionRead(
            action="delete",
            label="删除集成",
            destructive=True,
            disabled=True,
            disabled_reason="删除动作还没有接通",
        )
    )
    return actions


def _build_catalog_tags(plugin: PluginRegistryItem) -> list[str]:
    return sorted({*plugin.types, *plugin.permissions})


def _get_plugin_config_spec(plugin: PluginRegistryItem) -> PluginManifestConfigSpec | None:
    return next((item for item in plugin.config_specs if item.scope_type == "plugin"), None)


def _load_resource_counts_by_instance(
    db: Session,
    *,
    household_id: str,
) -> dict[str, IntegrationResourceCountsRead]:
    stmt: Select[tuple[str | None, str]] = (
        select(DeviceBinding.integration_instance_id, Device.id)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.integration_instance_id.is_not(None),
        )
    )
    counts: dict[str, IntegrationResourceCountsRead] = defaultdict(IntegrationResourceCountsRead)
    for integration_instance_id, _device_id in db.execute(stmt).all():
        if not integration_instance_id:
            continue
        entry = counts[integration_instance_id]
        entry.device += 1
    return counts


def _load_binding_capabilities(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    loaded = load_json(raw_value)
    return loaded if isinstance(loaded, dict) else {}


def _normalize_instance_config(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(config)
    if plugin_id != OPEN_XIAOAI_PLUGIN_ID:
        return normalized

    gateway_id = str(normalized.get("gateway_id") or "").strip()
    if gateway_id:
        normalized["gateway_id"] = gateway_id
        return normalized

    gateway_candidates = list_unbound_open_xiaoai_gateway_ids(db)
    if len(gateway_candidates) == 1:
        normalized["gateway_id"] = gateway_candidates[0]
        return normalized

    if not gateway_candidates:
        raise PluginServiceError(
            "还没有发现可用的小爱网关。",
            error_code="integration_instance_config_invalid",
            field_errors={"gateway_id": "还没有发现可用的小爱网关，请先让 open-xiaoai-gateway 连到平台。"},
            status_code=400,
        )

    raise PluginServiceError(
        "已发现多个小爱网关，请先选择要接入的网关。",
        error_code="integration_instance_config_invalid",
        field_errors={"gateway_id": "已发现多个小爱网关，请先选择要接入的网关。"},
        status_code=400,
    )
