from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.channel import repository as channel_repository
from app.modules.channel.models import ChannelPluginAccount
from app.modules.device.models import Device
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationInstance

from . import repository
from .config_crypto import decrypt_plugin_config_secrets, encrypt_plugin_config_secrets
from .models import PluginConfigInstance
from .schemas import (
    PluginConfigFormRead,
    PluginConfigScopeInstanceRead,
    PluginConfigScopeListRead,
    PluginConfigScopeRead,
    PluginConfigState,
    PluginConfigUpdateRequest,
    PluginConfigView,
    PluginManifestConfigField,
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

    field_errors, values, secret_fields, state = _build_view_payload(
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
    from app.modules.plugin_marketplace.service import refresh_marketplace_plugin_instance_config_status

    refresh_marketplace_plugin_instance_config_status(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
    )

    return PluginConfigFormRead(
        plugin_id=plugin.id,
        config_spec=config_spec,
        view=PluginConfigView(
            scope_type=config_spec.scope_type,
            scope_key=scope_key,
            schema_version=config_spec.schema_version,
            state=state,
            values=values,
            secret_fields=secret_fields,
            field_errors=field_errors,
        ),
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
    field_errors, values, secret_fields, state = _build_view_payload(
        config_spec=config_spec,
        stored_data=stored_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=instance is not None,
    )
    return PluginConfigFormRead(
        plugin_id=plugin.id,
        config_spec=config_spec,
        view=PluginConfigView(
            scope_type=config_spec.scope_type,
            scope_key=integration_instance_id,
            schema_version=config_spec.schema_version,
            state=state,
            values=values,
            secret_fields=secret_fields,
            field_errors=field_errors,
        ),
    )


def save_integration_instance_plugin_config_form(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
    values: dict[str, Any],
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

    field_errors, view_values, secret_fields, state = _build_view_payload(
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
    from app.modules.plugin_marketplace.service import refresh_marketplace_plugin_instance_config_status

    refresh_marketplace_plugin_instance_config_status(
        db,
        household_id=household_id,
        plugin_id=plugin.id,
    )
    return PluginConfigFormRead(
        plugin_id=plugin.id,
        config_spec=config_spec,
        view=PluginConfigView(
            scope_type=config_spec.scope_type,
            scope_key=integration_instance_id,
            schema_version=config_spec.schema_version,
            state=state,
            values=view_values,
            secret_fields=secret_fields,
            field_errors=field_errors,
        ),
    )


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
    field_errors, values, secret_fields, state = _build_view_payload(
        config_spec=config_spec,
        stored_data=stored_data,
        stored_secret_data=stored_secret_data,
        has_persisted_record=has_persisted_record,
    )
    return PluginConfigFormRead(
        plugin_id=plugin.id,
        config_spec=config_spec,
        view=PluginConfigView(
            scope_type=config_spec.scope_type,
            scope_key=scope_key,
            schema_version=config_spec.schema_version,
            state=state,
            values=values,
            secret_fields=secret_fields,
            field_errors=field_errors,
        ),
    )


def _load_config_payloads(
    db: Session,
    *,
    household_id: str,
    plugin: PluginRegistryItem,
    config_spec: PluginManifestConfigSpec,
    instance: PluginConfigInstance | None,
    scope_context: ChannelPluginAccount | Device | None,
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

    if not has_persisted_record:
        state: PluginConfigState = "unconfigured"
    elif field_errors:
        state = "invalid"
    else:
        state = "configured"
    return field_errors, values, secret_fields, state


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

    runtime_payload = dict(values)
    for field in config_spec.config_schema.fields:
        if field.type != "secret":
            continue
        if secret_fields.get(field.key, {}).get("has_value"):
            runtime_payload[field.key] = secret_data.get(field.key, field.default)
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
    scope_key: str,
) -> ChannelPluginAccount | Device | IntegrationInstance | None:
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

