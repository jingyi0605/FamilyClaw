from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.service import get_household_or_404
from app.modules.plugin import config_service as plugin_config_service
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin.schemas import PluginConfigFormRead, PluginConfigUpdateRequest, PluginRegistryItem
from app.modules.plugin.service import PluginServiceError, list_registered_plugins_for_household
from app.modules.room.models import Room

from .schemas import (
    IntegrationCatalogItemRead,
    IntegrationCatalogListRead,
    IntegrationConfigBindingRead,
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
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    plugins_by_id = {
        item.id: item
        for item in snapshot.items
        if _is_integration_plugin(item)
    }
    resource_counts_by_plugin = _load_resource_counts_by_plugin(db, household_id=household_id)
    latest_job_by_plugin = _load_latest_job_by_plugin(db, household_id=household_id)

    items: list[IntegrationInstanceRead] = []
    for instance in plugin_repository.list_plugin_config_instances(db, household_id=household_id, scope_type="plugin"):
        plugin = plugins_by_id.get(instance.plugin_id)
        if plugin is None:
            continue
        job = latest_job_by_plugin.get(plugin.id)
        items.append(
            IntegrationInstanceRead(
                id=instance.id,
                household_id=household_id,
                plugin_id=plugin.id,
                display_name=plugin.name,
                description=_build_plugin_description(plugin),
                source_type=plugin.source_type,
                status=_resolve_instance_status(plugin=plugin, latest_job=job),
                config_state="configured",
                resource_support=_build_resource_support(plugin),
                resource_counts=resource_counts_by_plugin.get(plugin.id, IntegrationResourceCountsRead()),
                sync_state=IntegrationSyncStateRead(
                    last_synced_at=(job.created_at if job and job.status == "succeeded" else None),
                    last_job_id=(job.id if job else None),
                    last_job_status=(job.status if job else None),
                    pending_job_id=(job.id if job and job.status in {"queued", "running", "retry_waiting", "waiting_response"} else None),
                ),
                config_bindings=[
                    IntegrationConfigBindingRead(
                        scope_type=instance.scope_type,  # type: ignore[arg-type]
                        scope_key=instance.scope_key,
                        state="configured",
                        form_available=bool(plugin.config_specs),
                        config_spec=next((spec for spec in plugin.config_specs if spec.scope_type == instance.scope_type), None),
                    )
                ],
                allowed_actions=[],
                last_error=(
                    None
                    if job is None or job.status != "failed"
                    else {
                        "code": job.last_error_code or "integration_sync_failed",
                        "message": job.last_error_message or "集成同步失败",
                        "occurred_at": job.updated_at,
                    }
                ),
                created_at=instance.created_at,
                updated_at=instance.updated_at,
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

    return IntegrationInstanceRead(
        id=instance.id,
        household_id=payload.household_id,
        plugin_id=plugin.id,
        display_name=payload.display_name or plugin.name,
        description=_build_plugin_description(plugin),
        source_type=plugin.source_type,
        status=("disabled" if not plugin.enabled else "active"),
        config_state=form.view.state,
        resource_support=_build_resource_support(plugin),
        resource_counts=IntegrationResourceCountsRead(),
        sync_state=IntegrationSyncStateRead(),
        config_bindings=[
            IntegrationConfigBindingRead(
                scope_type=form.view.scope_type,
                scope_key=form.view.scope_key,
                state=form.view.state,
                form_available=True,
                config_spec=form.config_spec,
            )
        ],
        allowed_actions=[],
        last_error=None,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


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
    if "action" in plugin.types:
        actions.append("repair")
    actions.append("delete")
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
