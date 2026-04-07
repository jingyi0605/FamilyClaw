from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.channel import repository as channel_repository
from app.modules.channel.models import ChannelPluginAccount
from app.modules.device.models import Device
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationInstance
from app.modules.region.providers import region_provider_registry
from app.modules.region.service import RegionServiceError, list_region_catalog

from . import repository
from .config_crypto import decrypt_plugin_config_secrets, encrypt_plugin_config_secrets
from .executors import execute_entrypoint_in_subprocess_runner, load_entrypoint_callable
from .import_path import collect_plugin_import_roots, plugin_runtime_import_path
from .models import PluginConfigInstance
from .schemas import (
    PluginConfigFormRead,
    PluginConfigPreviewHookResult,
    PluginConfigPreviewRequest,
    PluginConfigScopeInstanceRead,
    PluginConfigScopeListRead,
    PluginConfigScopeRead,
    PluginConfigState,
    PluginConfigUpdateRequest,
    PluginConfigView,
    PluginManifestConfigField,
    PluginManifestConfigFieldOption,
    PluginManifestConfigSpec,
    PluginRegistryItem,
)
from .service import PluginServiceError, get_household_plugin
from app.modules.device.plugin_config_bridge import (
    load_device_scope_legacy_payloads,
    sync_device_scope_legacy_fields,
)


PLUGIN_SCOPE_KEY = "default"
PLUGIN_CONFIG_SCOPE_INVALID = "plugin_config_scope_invalid"
PLUGIN_CONFIG_INSTANCE_NOT_FOUND = "plugin_config_instance_not_found"
PLUGIN_CONFIG_VALIDATION_FAILED = "plugin_config_validation_failed"
PLUGIN_CONFIG_SECRET_INVALID = "plugin_config_secret_invalid"
PLUGIN_CONFIG_PREVIEW_FAILED = "plugin_config_preview_failed"


@dataclass(slots=True)
class IntegrationInstanceRuntimeConfig:
    household_id: str
    integration_instance_id: str
    plugin_id: str
    values: dict[str, Any]
    last_synced_at: str | None
    updated_at: str | None


def list_plugin_config_scopes(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginConfigScopeListRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    items = [
        _build_scope_read(db, household_id=household_id, plugin=plugin, config_spec=config_spec)
        for config_spec in plugin.config_specs
    ]
    return PluginConfigScopeListRead(plugin_id=plugin.id, items=items)


def get_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    scope_type: str,
    scope_key: str,
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type=scope_type)
    scope_key = _normalize_scope_key(scope_type=config_spec.scope_type, scope_key=scope_key)
    scope_context = _resolve_scope_context(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        scope_key=scope_key,
    )
    return _build_plugin_config_form(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        scope_key=scope_key,
        scope_context=scope_context,
    )


def resolve_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    scope_type: str,
    scope_key: str | None,
    values: dict[str, Any],
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type=scope_type)
    normalized_scope_key = _normalize_optional_scope_key(scope_type=config_spec.scope_type, scope_key=scope_key)
    scope_context = _resolve_scope_context(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        scope_key=normalized_scope_key,
        allow_missing_scope=True,
    )
    stored_data, stored_secret_data, has_persisted_record = _load_config_payloads(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        instance=(
            repository.get_plugin_config_instance(
                db,
                household_id=household_id,
                plugin_id=plugin.id,
                scope_type=config_spec.scope_type,
                scope_key=normalized_scope_key,
            )
            if normalized_scope_key is not None
            else None
        ),
        scope_context=scope_context,
    )
    next_data = dict(stored_data)
    field_map = config_spec.config_schema.field_map()
    for field_key, value in values.items():
        field = field_map.get(field_key)
        if field is None or field.type == "secret":
            continue
        next_data[field_key] = value

    resolved_spec, field_errors, view_values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=next_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=has_persisted_record,
    )
    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=normalized_scope_key or _draft_scope_key(config_spec.scope_type),
        state=state,
        values=view_values,
        secret_fields=secret_fields,
        field_errors=field_errors,
    )


def preview_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginConfigPreviewRequest,
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type=payload.scope_type)
    normalized_scope_key = _normalize_optional_scope_key(scope_type=config_spec.scope_type, scope_key=payload.scope_key)
    scope_context = _resolve_scope_context(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        scope_key=normalized_scope_key,
        allow_missing_scope=True,
    )
    stored_data, stored_secret_data, has_persisted_record = _load_config_payloads(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        instance=(
            repository.get_plugin_config_instance(
                db,
                household_id=household_id,
                plugin_id=plugin.id,
                scope_type=config_spec.scope_type,
                scope_key=normalized_scope_key,
            )
            if normalized_scope_key is not None
            else None
        ),
        scope_context=scope_context,
    )
    next_data = dict(stored_data)
    next_secret_data = dict(stored_secret_data)
    field_map = config_spec.config_schema.field_map()

    for field_key, value in payload.values.items():
        field = field_map.get(field_key)
        if field is None:
            raise PluginServiceError(
                "提交了 schema 中不存在的字段。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field_errors={field_key: "字段不存在"},
                status_code=400,
            )
        if field.type == "secret":
            raise PluginServiceError(
                f"字段 {field_key} 是 secret 字段，请走 secret_values。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        next_data[field_key] = value

    for field_key in payload.clear_secret_fields:
        field = field_map.get(field_key)
        if field is None or field.type != "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是可清空的 secret 字段。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        if field_key in payload.secret_values:
            raise PluginServiceError(
                f"字段 {field_key} 不能同时提交新值和清空请求。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        next_secret_data.pop(field_key, None)

    for field_key, value in payload.secret_values.items():
        field = field_map.get(field_key)
        if field is None or field.type != "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是 secret 字段。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        next_secret_data[field_key] = value

    resolved_spec, field_errors, view_values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=next_data,
        stored_secret_data=next_secret_data,
        has_persisted_record=has_persisted_record,
    )
    runtime_state: dict[str, Any] = {}
    preview_artifacts: list[dict[str, Any]] = []
    if not field_errors:
        hook_result = _run_plugin_config_preview_hook(
            plugin=plugin,
            household_id=household_id,
            scope_type=config_spec.scope_type,
            scope_key=normalized_scope_key or _draft_scope_key(config_spec.scope_type),
            operation="preview",
            action_key=payload.action_key,
            config_spec=resolved_spec,
            values=view_values,
            secret_fields=secret_fields,
            secret_data=next_secret_data,
        )
        field_errors.update(hook_result.field_errors)
        runtime_state = dict(hook_result.runtime_state)
        preview_artifacts = [item.model_dump(mode="json") for item in hook_result.preview_artifacts]
    if field_errors:
        state = "invalid" if has_persisted_record else "unconfigured"

    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=normalized_scope_key or _draft_scope_key(config_spec.scope_type),
        state=state,
        values=view_values,
        secret_fields=secret_fields,
        field_errors=field_errors,
        runtime_state=runtime_state,
        preview_artifacts=preview_artifacts,
    )
def save_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginConfigUpdateRequest,
    updated_by: str | None = None,
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type=payload.scope_type)
    scope_key = _normalize_scope_key(scope_type=config_spec.scope_type, scope_key=payload.scope_key)
    scope_context = _resolve_scope_context(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        scope_key=scope_key,
    )
    existing_instance = repository.get_plugin_config_instance(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
        scope_type=config_spec.scope_type,
        scope_key=scope_key,
    )
    stored_data, stored_secret_data, _ = _load_config_payloads(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        instance=existing_instance,
        scope_context=scope_context,
    )

    next_data = dict(stored_data)
    next_secret_data = dict(stored_secret_data)
    field_map = config_spec.config_schema.field_map()

    for field_key in payload.clear_fields:
        field = field_map.get(field_key)
        if field is None or field.type == "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是可清空的普通字段。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field=field_key,
                status_code=400,
            )
        if field_key in payload.values:
            raise PluginServiceError(
                f"字段 {field_key} 不能同时提交新值和清空请求。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field=field_key,
                status_code=400,
            )
        next_data.pop(field_key, None)

    for field_key in payload.clear_secret_fields:
        field = field_map.get(field_key)
        if field is None or field.type != "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是可清空的 secret 字段。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                status_code=400,
            )
        if field_key in payload.values:
            raise PluginServiceError(
                f"字段 {field_key} 不能同时提交新值和清空请求。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        next_secret_data.pop(field_key, None)

    for field_key, value in payload.values.items():
        field = field_map.get(field_key)
        if field is None:
            raise PluginServiceError(
                "提交了 schema 中不存在的字段。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field_errors={field_key: "字段不存在"},
                status_code=400,
            )
        if field.type == "secret":
            next_secret_data[field_key] = value
            continue
        next_data[field_key] = value

    resolved_spec, field_errors, values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=next_data,
        stored_secret_data=next_secret_data,
        has_persisted_record=True,
    )
    if field_errors:
        raise PluginServiceError(
            "插件配置校验失败。",
            error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
            field_errors=field_errors,
            status_code=400,
        )
    _raise_for_plugin_config_runtime_validation(
        plugin=plugin,
        household_id=household_id,
        scope_type=config_spec.scope_type,
        scope_key=scope_key,
        config_spec=resolved_spec,
        values=values,
        secret_fields=secret_fields,
        secret_data=next_secret_data,
    )

    data_json = dump_json(_extract_persisted_data(config_spec=config_spec, data=next_data)) or "{}"
    secret_data_encrypted = encrypt_plugin_config_secrets(
        _extract_persisted_secret_data(config_spec=config_spec, secret_data=next_secret_data)
    )
    now = utc_now_iso()
    device_id = scope_context.id if isinstance(scope_context, Device) else None
    if existing_instance is None:
        existing_instance = PluginConfigInstance(
            id=new_uuid(),
            household_id=household_id,
            device_id=device_id,
            plugin_id=plugin.id,
            scope_type=config_spec.scope_type,
            scope_key=scope_key,
            schema_version=config_spec.schema_version,
            data_json=data_json,
            secret_data_encrypted=secret_data_encrypted,
            updated_by=updated_by,
            created_at=now,
            updated_at=now,
        )
        repository.add_plugin_config_instance(db, existing_instance)
    else:
        existing_instance.device_id = device_id
        existing_instance.schema_version = config_spec.schema_version
        existing_instance.data_json = data_json
        existing_instance.secret_data_encrypted = secret_data_encrypted
        existing_instance.updated_by = updated_by
        existing_instance.updated_at = now

    _sync_runtime_scope_config(
        db,
        household_id=household_id,
        plugin=plugin,
        scope_context=scope_context,
        config_spec=config_spec,
        values=values,
        secret_fields=secret_fields,
        secret_data=next_secret_data,
    )
    db.flush()

    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=scope_key,
        state=state,
        values=values,
        secret_fields=secret_fields,
        field_errors=field_errors,
    )


def get_integration_instance_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type="integration_instance")
    instance = repository.get_plugin_config_instance_for_integration_instance(
        db,
        integration_instance_id=integration_instance_id,
        plugin_id=plugin.id,
        scope_type=config_spec.scope_type,
    )
    if instance is None and config_spec.scope_type != "plugin":
        instance = repository.get_plugin_config_instance_for_integration_instance(
            db,
            integration_instance_id=integration_instance_id,
            plugin_id=plugin.id,
            scope_type="plugin",
        )
    stored_data, stored_secret_data = _load_config_instance_payload(instance)
    resolved_spec, field_errors, values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=stored_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=instance is not None,
    )
    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=integration_instance_id,
        state=state,
        values=values,
        secret_fields=secret_fields,
        field_errors=field_errors,
    )


def get_integration_instance_runtime_config(
    db: Session,
    *,
    integration_instance_id: str,
    plugin_id: str,
) -> IntegrationInstanceRuntimeConfig:
    integration_instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if integration_instance is None or integration_instance.plugin_id != plugin_id:
        raise PluginServiceError(
            f"集成实例不存在: {integration_instance_id}",
            error_code="integration_instance_not_found",
            field="integration_instance_id",
            status_code=404,
        )

    plugin = get_household_plugin(
        db,
        household_id=integration_instance.household_id,
        plugin_id=plugin_id,
    )
    config_spec = next((item for item in plugin.config_specs if item.scope_type == "integration_instance"), None)
    runtime_values: dict[str, Any] = {}
    updated_at: str | None = integration_instance.updated_at
    if config_spec is not None:
        instance = repository.get_plugin_config_instance_for_integration_instance(
            db,
            integration_instance_id=integration_instance_id,
            plugin_id=plugin.id,
            scope_type=config_spec.scope_type,
        )
        if instance is None:
            instance = repository.get_plugin_config_instance_for_integration_instance(
                db,
                integration_instance_id=integration_instance_id,
                plugin_id=plugin.id,
                scope_type="plugin",
            )
        stored_data, stored_secret_data = _load_config_instance_payload(instance)
        runtime_values = _build_runtime_payload(
            config_spec=config_spec,
            values=stored_data,
            secret_data=stored_secret_data,
        )
        if instance is not None:
            updated_at = instance.updated_at

    return IntegrationInstanceRuntimeConfig(
        household_id=integration_instance.household_id,
        integration_instance_id=integration_instance.id,
        plugin_id=plugin.id,
        values=runtime_values,
        last_synced_at=integration_instance.last_synced_at,
        updated_at=updated_at,
    )


def save_integration_instance_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
    values: dict[str, Any],
    clear_fields: list[str],
    clear_secret_fields: list[str],
    updated_by: str | None = None,
) -> PluginConfigFormRead:
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    config_spec = _require_config_spec(plugin, scope_type="integration_instance")
    existing_instance = repository.get_plugin_config_instance_for_integration_instance(
        db,
        integration_instance_id=integration_instance_id,
        plugin_id=plugin.id,
        scope_type=config_spec.scope_type,
    )
    if existing_instance is None and config_spec.scope_type != "plugin":
        existing_instance = repository.get_plugin_config_instance_for_integration_instance(
            db,
            integration_instance_id=integration_instance_id,
            plugin_id=plugin.id,
            scope_type="plugin",
        )
    stored_data, stored_secret_data = _load_config_instance_payload(existing_instance)

    next_data = dict(stored_data)
    next_secret_data = dict(stored_secret_data)
    field_map = config_spec.config_schema.field_map()

    for field_key in clear_fields:
        field = field_map.get(field_key)
        if field is None or field.type == "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是可清空的普通字段。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field=field_key,
                status_code=400,
            )
        if field_key in values:
            raise PluginServiceError(
                f"字段 {field_key} 不能同时提交新值和清空请求。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field=field_key,
                status_code=400,
            )
        next_data.pop(field_key, None)

    for field_key in clear_secret_fields:
        field = field_map.get(field_key)
        if field is None or field.type != "secret":
            raise PluginServiceError(
                f"字段 {field_key} 不是可清空的 secret 字段。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                status_code=400,
            )
        if field_key in values:
            raise PluginServiceError(
                f"字段 {field_key} 不能同时提交新值和清空请求。",
                error_code=PLUGIN_CONFIG_SECRET_INVALID,
                field=field_key,
                status_code=400,
            )
        next_secret_data.pop(field_key, None)

    for field_key, value in values.items():
        field = field_map.get(field_key)
        if field is None:
            raise PluginServiceError(
                "提交了 schema 中不存在的字段。",
                error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
                field_errors={field_key: "字段不存在"},
                status_code=400,
            )
        if field.type == "secret":
            next_secret_data[field_key] = value
            continue
        next_data[field_key] = value

    resolved_spec, field_errors, view_values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=next_data,
        stored_secret_data=next_secret_data,
        has_persisted_record=True,
    )
    if field_errors:
        raise PluginServiceError(
            "插件配置校验失败。",
            error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
            field_errors=field_errors,
            status_code=400,
        )
    _raise_for_plugin_config_runtime_validation(
        plugin=plugin,
        household_id=household_id,
        scope_type=config_spec.scope_type,
        scope_key=integration_instance_id,
        config_spec=resolved_spec,
        values=view_values,
        secret_fields=secret_fields,
        secret_data=next_secret_data,
    )

    data_json = dump_json(_extract_persisted_data(config_spec=config_spec, data=next_data)) or "{}"
    secret_data_encrypted = encrypt_plugin_config_secrets(
        _extract_persisted_secret_data(config_spec=config_spec, secret_data=next_secret_data)
    )
    now = utc_now_iso()

    if existing_instance is None:
        existing_instance = PluginConfigInstance(
            id=new_uuid(),
            household_id=household_id,
            integration_instance_id=integration_instance_id,
            plugin_id=plugin.id,
            scope_type=config_spec.scope_type,
            scope_key=integration_instance_id,
            schema_version=config_spec.schema_version,
            data_json=data_json,
            secret_data_encrypted=secret_data_encrypted,
            updated_by=updated_by,
            created_at=now,
            updated_at=now,
        )
        repository.add_plugin_config_instance(db, existing_instance)
    else:
        existing_instance.integration_instance_id = integration_instance_id
        existing_instance.scope_type = config_spec.scope_type
        existing_instance.schema_version = config_spec.schema_version
        existing_instance.scope_key = integration_instance_id
        existing_instance.data_json = data_json
        existing_instance.secret_data_encrypted = secret_data_encrypted
        existing_instance.updated_by = updated_by
        existing_instance.updated_at = now

    db.flush()
    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=integration_instance_id,
        state=state,
        values=view_values,
        secret_fields=secret_fields,
        field_errors=field_errors,
    )


def _build_config_form_read(
    *,
    plugin_id: str,
    config_spec: PluginManifestConfigSpec,
    scope_type: str,
    scope_key: str,
    state: PluginConfigState,
    values: dict[str, Any],
    secret_fields: dict[str, Any],
    field_errors: dict[str, str],
    runtime_state: dict[str, Any] | None = None,
    preview_artifacts: list[dict[str, Any]] | None = None,
) -> PluginConfigFormRead:
    return PluginConfigFormRead(
        plugin_id=plugin_id,
        config_spec=config_spec,
        view=PluginConfigView(
            scope_type=scope_type,
            scope_key=scope_key,
            schema_version=config_spec.schema_version,
            state=state,
            values=values,
            secret_fields=secret_fields,
            field_errors=field_errors,
            runtime_state=dict(runtime_state or {}),
            preview_artifacts=list(preview_artifacts or []),
        ),
    )
def _raise_for_plugin_config_runtime_validation(
    *,
    plugin: PluginRegistryItem,
    household_id: str,
    scope_type: str,
    scope_key: str,
    config_spec: PluginManifestConfigSpec,
    values: dict[str, Any],
    secret_fields: dict[str, Any],
    secret_data: dict[str, Any],
) -> None:
    hook_result = _run_plugin_config_preview_hook(
        plugin=plugin,
        household_id=household_id,
        scope_type=scope_type,
        scope_key=scope_key,
        operation="validate",
        action_key=None,
        config_spec=config_spec,
        values=values,
        secret_fields=secret_fields,
        secret_data=secret_data,
    )
    if not hook_result.field_errors:
        return
    raise PluginServiceError(
        "插件配置校验失败。",
        error_code=PLUGIN_CONFIG_VALIDATION_FAILED,
        field_errors=hook_result.field_errors,
        status_code=400,
    )


def _run_plugin_config_preview_hook(
    *,
    plugin: PluginRegistryItem,
    household_id: str,
    scope_type: str,
    scope_key: str,
    operation: Literal["preview", "validate"],
    action_key: str | None,
    config_spec: PluginManifestConfigSpec,
    values: dict[str, Any],
    secret_fields: dict[str, Any],
    secret_data: dict[str, Any],
) -> PluginConfigPreviewHookResult:
    entrypoint_path = plugin.entrypoints.config_preview
    if not entrypoint_path:
        return PluginConfigPreviewHookResult()

    runtime_secret_data = {
        key: secret_data.get(key, field.default)
        for key, field in config_spec.config_schema.field_map().items()
        if field.type == "secret" and secret_fields.get(key, {}).get("has_value")
    }
    payload = {
        "plugin_id": plugin.id,
        "household_id": household_id,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "operation": operation,
        "action_key": action_key,
        "runtime_config": _build_runtime_payload(
            config_spec=config_spec,
            values=values,
            secret_data=runtime_secret_data,
        ),
    }
    try:
        if plugin.source_type == "third_party" and plugin.execution_backend == "subprocess_runner":
            result = execute_entrypoint_in_subprocess_runner(
                plugin,
                entrypoint_path=entrypoint_path,
                payload=payload,
                trigger="config_preview",
                plugin_type="config_preview",
            )
        else:
            with plugin_runtime_import_path(
                plugin.runner_config.plugin_root if plugin.runner_config is not None else None,
                package_names=collect_plugin_import_roots(plugin),
            ):
                handler = load_entrypoint_callable(entrypoint_path)
                result = handler(payload)
    except PluginServiceError:
        raise
    except Exception as exc:
        raise PluginServiceError(
            f"插件配置预检失败: {exc}",
            error_code=PLUGIN_CONFIG_PREVIEW_FAILED,
            status_code=400,
        ) from exc

    try:
        return PluginConfigPreviewHookResult.model_validate(result or {})
    except Exception as exc:
        raise PluginServiceError(
            f"插件配置预检返回格式不合法: {exc}",
            error_code=PLUGIN_CONFIG_PREVIEW_FAILED,
            status_code=400,
        ) from exc


def _build_scope_read(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    config_spec: PluginManifestConfigSpec,
) -> PluginConfigScopeRead:
    if config_spec.scope_type == "plugin":
        form = _build_plugin_config_form(
            db,
            household_id=household_id,
            plugin=plugin,
            config_spec=config_spec,
            scope_key=PLUGIN_SCOPE_KEY,
            scope_context=None,
        )
        return PluginConfigScopeRead(
            scope_type=config_spec.scope_type,
            title=config_spec.title,
            description=config_spec.description,
            instances=[
                PluginConfigScopeInstanceRead(
                    scope_key=PLUGIN_SCOPE_KEY,
                    label="榛樿閰嶇疆",
                    description="当前插件在这个家庭下只有一份插件级配置。",
                    configured=form.view.state != "unconfigured",
                )
            ],
        )

    if config_spec.scope_type == "device":
        instances: list[PluginConfigScopeInstanceRead] = []
        for device in repository.list_plugin_scope_devices(
            db,
            household_id=household_id,
            plugin_id=plugin.id,
        ):
            form = _build_plugin_config_form(
                db,
                household_id=household_id,
                plugin=plugin,
                config_spec=config_spec,
                scope_key=device.id,
                scope_context=device,
            )
            instances.append(
                PluginConfigScopeInstanceRead(
                    scope_key=device.id,
                    label=device.name,
                    description=device.device_type,
                    configured=form.view.state != "unconfigured",
                )
            )
        return PluginConfigScopeRead(
            scope_type=config_spec.scope_type,
            title=config_spec.title,
            description=config_spec.description,
            instances=instances,
        )

    if config_spec.scope_type == "integration_instance":
        instances: list[PluginConfigScopeInstanceRead] = []
        for integration_instance in integration_repository.list_integration_instances(db, household_id=household_id):
            if integration_instance.plugin_id != plugin.id:
                continue
            form = _build_plugin_config_form(
                db,
                household_id=household_id,
                plugin=plugin,
                config_spec=config_spec,
                scope_key=integration_instance.id,
                scope_context=integration_instance,
            )
            instances.append(
                PluginConfigScopeInstanceRead(
                    scope_key=integration_instance.id,
                    label=integration_instance.display_name,
                    description=integration_instance.status,
                    configured=form.view.state != "unconfigured",
                )
            )
        return PluginConfigScopeRead(
            scope_type=config_spec.scope_type,
            title=config_spec.title,
            description=config_spec.description,
            instances=instances,
        )

    instances: list[PluginConfigScopeInstanceRead] = []
    for account in channel_repository.list_channel_plugin_accounts(db, household_id=household_id):
        if account.plugin_id != plugin.id:
            continue
        form = _build_plugin_config_form(
            db,
            household_id=household_id,
            plugin=plugin,
            config_spec=config_spec,
            scope_key=account.id,
            scope_context=account,
        )
        instances.append(
            PluginConfigScopeInstanceRead(
                scope_key=account.id,
                label=account.display_name,
                description=account.account_code,
                configured=form.view.state != "unconfigured",
            )
        )
    return PluginConfigScopeRead(
        scope_type=config_spec.scope_type,
        title=config_spec.title,
        description=config_spec.description,
        instances=instances,
    )


def _build_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    config_spec: PluginManifestConfigSpec,
    scope_key: str,
    scope_context: ChannelPluginAccount | Device | IntegrationInstance | None,
) -> PluginConfigFormRead:
    instance = repository.get_plugin_config_instance(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
        scope_type=config_spec.scope_type,
        scope_key=scope_key,
    )
    stored_data, stored_secret_data, has_persisted_record = _load_config_payloads(
        db,
        household_id=household_id,
        plugin=plugin,
        config_spec=config_spec,
        instance=instance,
        scope_context=scope_context,
    )
    resolved_spec, field_errors, values, secret_fields, state = _build_form_state(
        db,
        household_id=household_id,
        config_spec=config_spec,
        stored_data=stored_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=has_persisted_record,
    )
    return _build_config_form_read(
        plugin_id=plugin.id,
        config_spec=resolved_spec,
        scope_type=config_spec.scope_type,
        scope_key=scope_key,
        state=state,
        values=values,
        secret_fields=secret_fields,
        field_errors=field_errors,
    )


def _build_form_state(
    db: Session,
    *,
    household_id: str,
    config_spec: PluginManifestConfigSpec,
    stored_data: dict[str, Any],
    stored_secret_data: dict[str, Any],
    has_persisted_record: bool,
) -> tuple[PluginManifestConfigSpec, dict[str, str], dict[str, Any], dict[str, Any], PluginConfigState]:
    effective_values = _build_effective_non_secret_values(config_spec=config_spec, stored_data=stored_data)
    resolved_spec = _resolve_dynamic_config_spec(
        db,
        household_id=household_id,
        config_spec=config_spec,
        current_values=effective_values,
    )
    field_errors, values, secret_fields, state = _build_view_payload(
        config_spec=resolved_spec,
        stored_data=stored_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=has_persisted_record,
    )
    return resolved_spec, field_errors, values, secret_fields, state


def _load_config_payloads(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    config_spec: PluginManifestConfigSpec,
    instance: PluginConfigInstance | None,
    scope_context: ChannelPluginAccount | Device | IntegrationInstance | None,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    legacy_data: dict[str, Any] = {}
    legacy_secret_data: dict[str, Any] = {}
    legacy_has_record = False
    if isinstance(scope_context, Device):
        legacy_data, legacy_secret_data, legacy_has_record = load_device_scope_legacy_payloads(
            plugin_id=plugin.id,
            config_spec=config_spec,
            device=scope_context,
        )

    if instance is not None:
        data_payload, secret_payload = _load_config_instance_payload(instance)
        for key, value in legacy_data.items():
            data_payload.setdefault(key, value)
        for key, value in legacy_secret_data.items():
            secret_payload.setdefault(key, value)
        return data_payload, secret_payload, True

    if scope_context is None:
        return {}, {}, False

    if isinstance(scope_context, Device):
        return legacy_data, legacy_secret_data, legacy_has_record

    if isinstance(scope_context, IntegrationInstance):
        return {}, {}, False

    raw_payload = load_json(scope_context.config_json)
    if not isinstance(raw_payload, dict):
        return {}, {}, False

    data_payload: dict[str, Any] = {}
    secret_payload: dict[str, Any] = {}
    for field in config_spec.config_schema.fields:
        if field.key not in raw_payload:
            continue
        if field.type == "secret":
            secret_payload[field.key] = raw_payload[field.key]
        else:
            data_payload[field.key] = raw_payload[field.key]
    return data_payload, secret_payload, bool(data_payload or secret_payload)


def _build_view_payload(
    *,
    config_spec: PluginManifestConfigSpec,
    stored_data: dict[str, Any],
    stored_secret_data: dict[str, Any],
    has_persisted_record: bool,
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], PluginConfigState]:
    field_errors: dict[str, str] = {}
    values: dict[str, Any] = {}
    secret_fields: dict[str, Any] = {}

    for field in config_spec.config_schema.fields:
        if field.type == "secret":
            has_secret_value = field.key in stored_secret_data or field.default is not None
            actual_secret_value = stored_secret_data.get(field.key, field.default)
            secret_fields[field.key] = {
                "has_value": has_secret_value,
                "masked": "******" if has_secret_value else None,
            }
            _validate_field_value(field, actual_secret_value, has_value=has_secret_value, field_errors=field_errors)
            continue

        has_value = field.key in stored_data or field.default is not None
        actual_value = stored_data.get(field.key, field.default)
        if has_value and actual_value is not None:
            values[field.key] = actual_value
        _validate_field_value(field, actual_value, has_value=has_value, field_errors=field_errors)

    if field_errors:
        if has_persisted_record:
            state: PluginConfigState = "invalid"
        else:
            state = "unconfigured"
    else:
        state = "configured"
    return field_errors, values, secret_fields, state


def _build_effective_non_secret_values(
    *,
    config_spec: PluginManifestConfigSpec,
    stored_data: dict[str, Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in config_spec.config_schema.fields:
        if field.type == "secret":
            continue
        has_value = field.key in stored_data or field.default is not None
        actual_value = stored_data.get(field.key, field.default)
        if has_value and actual_value is not None:
            values[field.key] = actual_value
    return values


def _resolve_dynamic_config_spec(
    db: Session,
    *,
    household_id: str,
    config_spec: PluginManifestConfigSpec,
    current_values: dict[str, Any],
) -> PluginManifestConfigSpec:
    resolved_spec = config_spec.model_copy(deep=True)
    for field in resolved_spec.config_schema.fields:
        if field.option_source is None:
            continue
        field.enum_options = _resolve_dynamic_field_options(
            db,
            household_id=household_id,
            field=field,
            current_values=current_values,
        )
    return resolved_spec


def _resolve_dynamic_field_options(
    db: Session,
    *,
    household_id: str,
    field: PluginManifestConfigField,
    current_values: dict[str, Any],
) -> list[PluginManifestConfigFieldOption]:
    option_source = field.option_source
    if option_source is None:
        return field.enum_options

    if option_source.source == "region_provider_list":
        options: list[PluginManifestConfigFieldOption] = []
        for provider in region_provider_registry.list(household_id=household_id):
            if provider.country_code != option_source.country_code:
                continue
            label = (provider.plugin_name or "").strip() or provider.provider_code
            options.append(PluginManifestConfigFieldOption(label=label, value=provider.provider_code))
        return options

    provider_code = option_source.provider_code or _read_option_source_text(current_values.get(option_source.provider_field or ""))
    if provider_code is None:
        return []
    parent_region_code = _read_option_source_text(current_values.get(option_source.parent_field or ""))
    try:
        nodes = list_region_catalog(
            db,
            provider_code=provider_code,
            country_code=option_source.country_code or "",
            household_id=household_id,
            parent_region_code=parent_region_code,
            admin_level=option_source.admin_level,
        )
    except RegionServiceError:
        return []
    return [PluginManifestConfigFieldOption(label=node.name, value=node.region_code) for node in nodes]


def _read_option_source_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _validate_field_value(
    field: PluginManifestConfigField,
    actual_value: Any,
    *,
    has_value: bool,
    field_errors: dict[str, str],
) -> None:
    if not has_value:
        if field.required and not field.nullable:
            field_errors[field.key] = f"{field.label} 涓嶈兘涓虹┖"
        return

    if isinstance(actual_value, str) and field.type in {"string", "text", "secret"} and field.required and not actual_value.strip():
        field_errors[field.key] = f"{field.label} 涓嶈兘涓虹┖"
        return

    try:
        field.validate_value(actual_value)
    except ValueError as exc:
        field_errors[field.key] = str(exc)


def _extract_persisted_data(
    *,
    config_spec: PluginManifestConfigSpec,
    data: dict[str, Any],
) -> dict[str, Any]:
    field_keys = {field.key for field in config_spec.config_schema.fields if field.type != "secret"}
    return {key: value for key, value in data.items() if key in field_keys}


def _extract_persisted_secret_data(
    *,
    config_spec: PluginManifestConfigSpec,
    secret_data: dict[str, Any],
) -> dict[str, Any]:
    field_keys = {field.key for field in config_spec.config_schema.fields if field.type == "secret"}
    return {key: value for key, value in secret_data.items() if key in field_keys}


def _build_runtime_payload(
    *,
    config_spec: PluginManifestConfigSpec,
    values: dict[str, Any],
    secret_data: dict[str, Any],
) -> dict[str, Any]:
    runtime_payload = dict(values)
    for field in config_spec.config_schema.fields:
        if field.type == "secret":
            if field.key in secret_data:
                runtime_payload[field.key] = secret_data[field.key]
            elif field.default is not None:
                runtime_payload[field.key] = field.default
            continue
        if field.key not in runtime_payload and field.default is not None:
            runtime_payload[field.key] = field.default
    return runtime_payload


def _sync_runtime_scope_config(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    scope_context: ChannelPluginAccount | Device | IntegrationInstance | None,
    config_spec: PluginManifestConfigSpec,
    values: dict[str, Any],
    secret_fields: dict[str, Any],
    secret_data: dict[str, Any],
) -> None:
    if scope_context is None:
        return

    if isinstance(scope_context, Device):
        if config_spec.scope_type != "device":
            return
        sync_device_scope_legacy_fields(
            plugin_id=plugin.id,
            config_spec=config_spec,
            device=scope_context,
            values=values,
        )
        return

    if config_spec.scope_type != "channel_account":
        return

    runtime_payload = _build_runtime_payload(
        config_spec=config_spec,
        values=values,
        secret_data={
            key: secret_data.get(key, field.default)
            for key, field in config_spec.config_schema.field_map().items()
            if field.type == "secret" and secret_fields.get(key, {}).get("has_value")
        },
    )
    scope_context.config_json = dump_json(runtime_payload) or "{}"
    scope_context.updated_at = utc_now_iso()


def _require_config_spec(plugin: PluginRegistryItem, *, scope_type: str) -> PluginManifestConfigSpec:
    config_spec = next((item for item in plugin.config_specs if item.scope_type == scope_type), None)
    if config_spec is None:
        raise PluginServiceError(
            f"插件 {plugin.id} 没有声明 {scope_type} 配置作用域。",
            error_code=PLUGIN_CONFIG_SCOPE_INVALID,
            field="scope_type",
            status_code=404,
        )
    return config_spec


def _load_config_instance_payload(instance: PluginConfigInstance | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if instance is None:
        return {}, {}
    stored_data = load_json(instance.data_json)
    data_payload = stored_data if isinstance(stored_data, dict) else {}
    return data_payload, decrypt_plugin_config_secrets(instance.secret_data_encrypted)


def _draft_scope_key(scope_type: str) -> str:
    if scope_type == "plugin":
        return PLUGIN_SCOPE_KEY
    return "__draft__"


def _normalize_optional_scope_key(*, scope_type: str, scope_key: str | None) -> str | None:
    if scope_type == "plugin":
        return PLUGIN_SCOPE_KEY
    if scope_key is None:
        return None
    return _normalize_scope_key(scope_type=scope_type, scope_key=scope_key)


def _normalize_scope_key(*, scope_type: str, scope_key: str) -> str:
    normalized = scope_key.strip()
    if scope_type == "plugin":
        if normalized != PLUGIN_SCOPE_KEY:
            raise PluginServiceError(
                "plugin 作用域的 scope_key 固定为 default。",
                error_code=PLUGIN_CONFIG_SCOPE_INVALID,
                field="scope_key",
                status_code=400,
            )
        return PLUGIN_SCOPE_KEY
    if not normalized:
        raise PluginServiceError(
            "scope_key 不能为空。",
            error_code=PLUGIN_CONFIG_SCOPE_INVALID,
            field="scope_key",
            status_code=400,
        )
    return normalized


def _resolve_scope_context(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    config_spec: PluginManifestConfigSpec,
    scope_key: str | None,
    allow_missing_scope: bool = False,
) -> ChannelPluginAccount | Device | IntegrationInstance | None:
    if scope_key is None:
        if allow_missing_scope:
            return None
        raise PluginServiceError(
            "scope_key 不能为空。",
            error_code=PLUGIN_CONFIG_SCOPE_INVALID,
            field="scope_key",
            status_code=400,
        )
    if config_spec.scope_type == "plugin":
        return None

    if config_spec.scope_type == "integration_instance":
        integration_instance = integration_repository.get_integration_instance(db, scope_key)
        if integration_instance is None or integration_instance.household_id != household_id or integration_instance.plugin_id != plugin.id:
            raise PluginServiceError(
                "请求的 integration_instance 作用域不存在。",
                error_code=PLUGIN_CONFIG_INSTANCE_NOT_FOUND,
                field="scope_key",
                status_code=404,
            )
        return integration_instance

    if config_spec.scope_type == "device":
        device = db.get(Device, scope_key)
        if device is None or device.household_id != household_id:
            raise PluginServiceError(
                "请求的 device 作用域不存在。",
                error_code=PLUGIN_CONFIG_INSTANCE_NOT_FOUND,
                field="scope_key",
                status_code=404,
            )
        return device

    account = channel_repository.get_channel_plugin_account(db, scope_key)
    if account is None or account.household_id != household_id or account.plugin_id != plugin.id:
        raise PluginServiceError(
            "请求的 channel_account 作用域不存在。",
            error_code=PLUGIN_CONFIG_INSTANCE_NOT_FOUND,
            field="scope_key",
            status_code=404,
        )
    return account

