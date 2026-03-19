from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.audit.models import AuditLog
from app.modules.device.entity_store import (
    build_binding_entity_ids,
    build_entity_payload_from_row,
    list_binding_entity_rows,
    update_binding_entity_state_snapshot,
)
from app.modules.device.models import Device, DeviceBinding, DeviceEntityFavorite
from app.modules.device_integration.service import load_binding_live_state_maps_via_plugin
from app.modules.device.schemas import (
    DeviceActionLogListResponse,
    DeviceActionLogRead,
    DeviceDetailBuiltinTabRead,
    DeviceDetailCapabilityRead,
    DeviceDetailPluginTabRead,
    DeviceDetailViewRead,
    DeviceEntityControlOptionRead,
    DeviceEntityControlRead,
    DeviceEntityListResponse,
    DeviceEntityRead,
    DeviceRead,
    DeviceStatus,
    DeviceUpdate,
)
from app.modules.household.service import get_household_or_404
from app.modules.room.models import Room


PLATFORM_OFFLINE_STATE = "unavailable"
PLATFORM_OFFLINE_REASON = "设备离线，集成平台当前不可用"


@dataclass(slots=True)
class LiveStateLoadResult:
    state_maps: dict[str, dict[str, dict[str, Any]]]
    unavailable_instance_ids: set[str]


def get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )
    return device


def _validate_room_in_household(db: Session, *, room_id: str | None, household_id: str) -> None:
    if room_id is None:
        return

    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room not found",
        )
    if room.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room must belong to the same household",
        )


def list_devices(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    room_id: str | None = None,
    device_type: str | None = None,
    status_value: str | None = None,
) -> tuple[list[Device], int]:
    get_household_or_404(db, household_id)

    filters = [Device.household_id == household_id]
    if room_id:
        filters.append(Device.room_id == room_id)
    if device_type:
        filters.append(Device.device_type == device_type)
    if status_value:
        filters.append(Device.status == status_value)

    total = db.scalar(select(func.count()).select_from(Device).where(*filters)) or 0
    statement = (
        select(Device)
        .where(*filters)
        .order_by(Device.updated_at.desc(), Device.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    devices = list(db.scalars(statement).all())
    return devices, total


def update_device(db: Session, device: Device, payload: DeviceUpdate) -> tuple[Device, dict[str, Any]]:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return device, {}

    device_bindings = _load_device_bindings(db, device_id=device.id)
    supports_voice_terminal = _device_supports_voice_terminal(device=device, bindings=device_bindings)

    if "room_id" in update_data:
        _validate_room_in_household(
            db,
            room_id=update_data["room_id"],
            household_id=device.household_id,
        )

    if "controllable" in update_data:
        update_data["controllable"] = 1 if update_data["controllable"] else 0

    if "voice_auto_takeover_enabled" in update_data:
        if not supports_voice_terminal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voice takeover settings only support voice terminal devices",
            )
        update_data["voice_auto_takeover_enabled"] = 1 if update_data["voice_auto_takeover_enabled"] else 0

    if "voiceprint_identity_enabled" in update_data:
        if not supports_voice_terminal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voiceprint settings only support voice terminal devices",
            )
        update_data["voiceprint_identity_enabled"] = 1 if update_data["voiceprint_identity_enabled"] else 0

    if "voice_takeover_prefixes" in update_data:
        if not supports_voice_terminal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voice takeover settings only support voice terminal devices",
            )

    for field_name, field_value in update_data.items():
        setattr(device, field_name, field_value)

    db.add(device)
    return device, update_data


def disable_device(db: Session, device: Device) -> tuple[Device, bool]:
    if device.status == "disabled":
        return device, False
    device.status = "disabled"
    db.add(device)
    return device, True


def delete_device(db: Session, device: Device) -> None:
    db.delete(device)


def list_device_entities(
    db: Session,
    *,
    device_id: str,
    view: str,
) -> DeviceEntityListResponse:
    device = get_device_or_404(db, device_id)
    bindings = _load_device_bindings(db, device_id=device.id)
    state_load_result = _load_live_state_maps(db, household_id=device.household_id, bindings=bindings)
    entities = _resolve_device_entities(
        db,
        device=device,
        bindings=bindings,
        live_state_maps=state_load_result.state_maps,
        unavailable_instance_ids=state_load_result.unavailable_instance_ids,
    )
    if view == "favorites":
        entities = [item for item in entities if item.favorite]
    device_read = DeviceRead.model_validate(device)
    if _device_has_unavailable_platform_binding(
        bindings=bindings,
        unavailable_instance_ids=state_load_result.unavailable_instance_ids,
    ):
        device_read = device_read.model_copy(update={"status": "offline"})
    return DeviceEntityListResponse(
        device=device_read,
        view=view,  # type: ignore[arg-type]
        items=entities,
    )


def set_device_entity_favorite(
    db: Session,
    *,
    device_id: str,
    entity_id: str,
    favorite: bool,
    created_by: str | None,
) -> DeviceEntityListResponse:
    device = get_device_or_404(db, device_id)
    entities = _resolve_device_entities(db, device=device)
    if not any(item.entity_id == entity_id for item in entities):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device entity not found")

    row = db.scalar(
        select(DeviceEntityFavorite).where(
            DeviceEntityFavorite.household_id == device.household_id,
            DeviceEntityFavorite.device_id == device.id,
            DeviceEntityFavorite.entity_id == entity_id,
        )
    )
    if favorite:
        if row is None:
            db.add(
                DeviceEntityFavorite(
                    id=new_uuid(),
                    household_id=device.household_id,
                    device_id=device.id,
                    entity_id=entity_id,
                    created_by=created_by,
                    created_at=utc_now_iso(),
                )
            )
    elif row is not None:
        db.delete(row)

    db.flush()
    return list_device_entities(db, device_id=device_id, view="all")


def list_device_action_logs(
    db: Session,
    *,
    device_id: str,
    page: int,
    page_size: int,
) -> DeviceActionLogListResponse:
    device = get_device_or_404(db, device_id)
    entity_names = {
        item.entity_id: item.name
        for item in _resolve_device_entities(db, device=device)
    }
    filters = [
        AuditLog.household_id == device.household_id,
        AuditLog.target_id == device.id,
        or_(
            AuditLog.action.like("device.%"),
            AuditLog.action == "device_action.execute",
        ),
    ]
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    statement = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        _build_device_action_log_read(item, entity_names=entity_names)
        for item in db.scalars(statement).all()
    ]
    return DeviceActionLogListResponse(
        device=DeviceRead.model_validate(device),
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


def get_device_detail_view(
    db: Session,
    *,
    device_id: str,
) -> DeviceDetailViewRead:
    device = get_device_or_404(db, device_id)
    bindings = _load_device_bindings(db, device_id=device.id)
    capabilities = _build_device_detail_capabilities(device=device, bindings=bindings)
    return DeviceDetailViewRead(
        device=DeviceRead.model_validate(device),
        capabilities=capabilities,
        builtin_tabs=_build_device_detail_builtin_tabs(capabilities=capabilities),
        plugin_tabs=_build_device_detail_plugin_tabs(
            db,
            device=device,
            bindings=bindings,
        ),
    )


def _resolve_device_entities(
    db: Session,
    *,
    device: Device,
    bindings: list[DeviceBinding] | None = None,
    live_state_maps: dict[str, dict[str, dict[str, Any]]] | None = None,
    unavailable_instance_ids: set[str] | None = None,
) -> list[DeviceEntityRead]:
    favorite_ids = set(
        db.scalars(
            select(DeviceEntityFavorite.entity_id).where(
                DeviceEntityFavorite.household_id == device.household_id,
                DeviceEntityFavorite.device_id == device.id,
            )
        ).all()
    )
    if bindings is None:
        bindings = _load_device_bindings(db, device_id=device.id)
    live_state_maps = live_state_maps or {}
    unavailable_instance_ids = unavailable_instance_ids or set()

    items: list[DeviceEntityRead] = []
    seen_entity_ids: set[str] = set()
    for binding in bindings:
        capabilities = _load_binding_capabilities(binding)
        binding_entity_rows = list_binding_entity_rows(db, binding_id=binding.id)
        raw_entities = [build_entity_payload_from_row(row) for row in binding_entity_rows]
        if _binding_is_platform_unavailable(
            binding=binding,
            unavailable_instance_ids=unavailable_instance_ids,
        ):
            if raw_entities:
                unavailable_items = _build_unavailable_items_from_raw_entities(
                    raw_entities=raw_entities,
                    binding=binding,
                    device=device,
                    favorite_ids=favorite_ids,
                )
            else:
                unavailable_items = _build_unavailable_binding_entities(
                    binding=binding,
                    device=device,
                    capabilities=capabilities,
                    favorite_ids=favorite_ids,
                )
            for item in unavailable_items:
                if item.entity_id in seen_entity_ids:
                    continue
                items.append(item)
                seen_entity_ids.add(item.entity_id)
            continue
        if raw_entities:
            _apply_live_state_snapshot_to_raw_entities(
                device=device,
                raw_entities=raw_entities,
                live_state_map=live_state_maps.get(binding.integration_instance_id or ""),
            )
            for raw_entity in raw_entities:
                item = _normalize_entity_snapshot(
                    raw_entity,
                    binding=binding,
                    device=device,
                    favorite_ids=favorite_ids,
                )
                if item is None or item.entity_id in seen_entity_ids:
                    continue
                items.append(item)
                seen_entity_ids.add(item.entity_id)
            continue
        _apply_live_state_snapshot(
            device=device,
            binding=binding,
            capabilities=capabilities,
            live_state_map=live_state_maps.get(binding.integration_instance_id or ""),
        )
        legacy_entities = capabilities.get("entities")
        if isinstance(legacy_entities, list):
            for raw_entity in legacy_entities:
                item = _normalize_entity_snapshot(
                    raw_entity,
                    binding=binding,
                    device=device,
                    favorite_ids=favorite_ids,
                )
                if item is None or item.entity_id in seen_entity_ids:
                    continue
                items.append(item)
                seen_entity_ids.add(item.entity_id)
        fallback = _build_fallback_entity_snapshot(
            binding=binding,
            device=device,
            capabilities=capabilities,
            favorite_ids=favorite_ids,
        )
        if fallback is not None and fallback.entity_id not in seen_entity_ids:
            items.append(fallback)
            seen_entity_ids.add(fallback.entity_id)

    items.sort(key=lambda item: (0 if item.favorite else 1, item.name.lower(), item.entity_id))
    return items


def _normalize_entity_snapshot(
    raw_entity: Any,
    *,
    binding: DeviceBinding,
    device: Device,
    favorite_ids: set[str],
) -> DeviceEntityRead | None:
    if not isinstance(raw_entity, dict):
        return None
    entity_id = str(raw_entity.get("entity_id") or "").strip()
    if not entity_id:
        return None
    domain = str(raw_entity.get("domain") or entity_id.split(".", 1)[0] or "").strip()
    state = str(raw_entity.get("state") or "unknown").strip() or "unknown"
    control = _build_entity_control(
        raw_entity.get("control"),
        device_status=device.status,
        device=device,
        domain=domain,
        state=state,
    )
    metadata = raw_entity.get("metadata") if isinstance(raw_entity.get("metadata"), dict) else {}
    return DeviceEntityRead(
        device_id=device.id,
        integration_instance_id=binding.integration_instance_id,
        entity_id=entity_id,
        name=str(raw_entity.get("name") or entity_id),
        domain=domain,
        state=state,
        state_display=str(raw_entity.get("state_display") or _friendly_state_display(state)),
        unit=_normalize_optional_text(raw_entity.get("unit")),
        favorite=entity_id in favorite_ids,
        read_only=control.kind == "none",
        control=control,
        metadata=metadata,
        updated_at=str(raw_entity.get("updated_at") or device.updated_at),
    )


def _build_fallback_entity_snapshot(
    *,
    binding: DeviceBinding,
    device: Device,
    capabilities: dict[str, Any],
    favorite_ids: set[str],
) -> DeviceEntityRead | None:
    entity_id = _resolve_binding_primary_entity_id(binding, capabilities)
    if not entity_id:
        return None
    state = _normalize_optional_text(capabilities.get("state")) or "unknown"
    raw_entity = {
        "entity_id": entity_id,
        "name": capabilities.get("name") or device.name,
        "domain": _normalize_optional_text(capabilities.get("domain")) or entity_id.split(".", 1)[0],
        "state": state,
        "state_display": _friendly_state_display(state),
        "unit": None,
        "metadata": {
            "fallback": True,
            "binding_external_entity_id": binding.external_entity_id,
            "primary_entity_id": _normalize_optional_text(capabilities.get("primary_entity_id")),
            "manufacturer": capabilities.get("manufacturer"),
            "model": capabilities.get("model"),
        },
        "control": _build_canonical_control_payload(
            device=device,
            domain=_normalize_optional_text(capabilities.get("domain")) or entity_id.split(".", 1)[0],
            state=state,
            raw_control=None,
            attributes={},
        ),
        "updated_at": device.updated_at,
    }
    return _normalize_entity_snapshot(raw_entity, binding=binding, device=device, favorite_ids=favorite_ids)


def _build_unavailable_binding_entities(
    *,
    binding: DeviceBinding,
    device: Device,
    capabilities: dict[str, Any],
    favorite_ids: set[str],
) -> list[DeviceEntityRead]:
    items: list[DeviceEntityRead] = []
    raw_entities = capabilities.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            item = _build_unavailable_entity_snapshot(
                raw_entity=raw_entity,
                binding=binding,
                device=device,
                favorite_ids=favorite_ids,
            )
            if item is not None:
                items.append(item)
    if items:
        return items
    fallback = _build_unavailable_fallback_entity_snapshot(
        binding=binding,
        device=device,
        capabilities=capabilities,
        favorite_ids=favorite_ids,
    )
    return [fallback] if fallback is not None else []


def _build_unavailable_items_from_raw_entities(
    *,
    raw_entities: list[dict[str, Any]],
    binding: DeviceBinding,
    device: Device,
    favorite_ids: set[str],
) -> list[DeviceEntityRead]:
    items: list[DeviceEntityRead] = []
    for raw_entity in raw_entities:
        item = _build_unavailable_entity_snapshot(
            raw_entity=raw_entity,
            binding=binding,
            device=device,
            favorite_ids=favorite_ids,
        )
        if item is not None:
            items.append(item)
    return items


def _build_unavailable_entity_snapshot(
    *,
    raw_entity: Any,
    binding: DeviceBinding,
    device: Device,
    favorite_ids: set[str],
) -> DeviceEntityRead | None:
    if not isinstance(raw_entity, dict):
        return None
    entity_id = _normalize_optional_text(raw_entity.get("entity_id"))
    if not entity_id:
        return None
    domain = _normalize_optional_text(raw_entity.get("domain")) or entity_id.split(".", 1)[0]
    raw_snapshot = {
        "entity_id": entity_id,
        "name": raw_entity.get("name") or entity_id,
        "domain": domain,
        "state": PLATFORM_OFFLINE_STATE,
        "state_display": _friendly_state_display(PLATFORM_OFFLINE_STATE),
        "unit": raw_entity.get("unit"),
        "metadata": {
            **(raw_entity.get("metadata") if isinstance(raw_entity.get("metadata"), dict) else {}),
            "live_state_available": False,
        },
        "control": _mark_control_unavailable(
            _build_canonical_control_payload(
                device=device,
                domain=domain,
                state=PLATFORM_OFFLINE_STATE,
                raw_control=raw_entity.get("control") if isinstance(raw_entity.get("control"), dict) else None,
                attributes={},
            )
        ),
        "updated_at": raw_entity.get("updated_at") or device.updated_at,
    }
    return _normalize_entity_snapshot(raw_snapshot, binding=binding, device=device, favorite_ids=favorite_ids)


def _build_unavailable_fallback_entity_snapshot(
    *,
    binding: DeviceBinding,
    device: Device,
    capabilities: dict[str, Any],
    favorite_ids: set[str],
) -> DeviceEntityRead | None:
    entity_id = _resolve_binding_primary_entity_id(binding, capabilities)
    if not entity_id:
        return None
    domain = _normalize_optional_text(capabilities.get("domain")) or entity_id.split(".", 1)[0]
    raw_snapshot = {
        "entity_id": entity_id,
        "name": capabilities.get("name") or device.name,
        "domain": domain,
        "state": PLATFORM_OFFLINE_STATE,
        "state_display": _friendly_state_display(PLATFORM_OFFLINE_STATE),
        "unit": None,
        "metadata": {
            "fallback": True,
            "live_state_available": False,
            "binding_external_entity_id": binding.external_entity_id,
            "primary_entity_id": _normalize_optional_text(capabilities.get("primary_entity_id")),
        },
        "control": _mark_control_unavailable(
            _build_canonical_control_payload(
                device=device,
                domain=domain,
                state=PLATFORM_OFFLINE_STATE,
                raw_control=None,
                attributes={},
            )
        ),
        "updated_at": device.updated_at,
    }
    return _normalize_entity_snapshot(raw_snapshot, binding=binding, device=device, favorite_ids=favorite_ids)


def _friendly_state_display(state: str) -> str:
    mapping = {
        "on": "开启",
        "off": "关闭",
        "open": "打开",
        "closed": "关闭",
        "locked": "已上锁",
        "unlocked": "未上锁",
        "playing": "播放中",
        "paused": "已暂停",
        "idle": "空闲",
        "cool": "制冷",
        "heat": "制热",
        "auto": "自动",
        "dry": "除湿",
        "fan_only": "送风",
        "unavailable": "离线",
        "unknown": "未知",
    }
    normalized = state.strip().lower()
    return mapping.get(normalized, state.strip() or "未知")


def _build_entity_control(
    raw_control: Any,
    *,
    device_status: str,
    device: Device,
    domain: str,
    state: str,
) -> DeviceEntityControlRead:
    raw_control_payload = raw_control if isinstance(raw_control, dict) else None
    payload = _build_canonical_control_payload(
        device=device,
        domain=domain,
        state=state,
        raw_control=raw_control_payload,
        attributes={},
    )
    kind = payload.get("kind")
    if kind not in {"none", "toggle", "range", "action_set"}:
        kind = "none"
    control = DeviceEntityControlRead(
        kind=kind,
        value=payload.get("value"),
        unit=_normalize_optional_text(payload.get("unit")),
        min_value=_coerce_float(payload.get("min_value")),
        max_value=_coerce_float(payload.get("max_value")),
        step=_coerce_float(payload.get("step")),
        action=_normalize_optional_text(payload.get("action")),
        action_on=_normalize_optional_text(payload.get("action_on")),
        action_off=_normalize_optional_text(payload.get("action_off")),
        options=[
            DeviceEntityControlOptionRead(
                label=str(option.get("label") or option.get("value") or ""),
                value=str(option.get("value") or ""),
                action=str(option.get("action") or ""),
                params=option.get("params") if isinstance(option.get("params"), dict) else {},
            )
            for option in payload.get("options", [])
            if isinstance(option, dict) and option.get("value") is not None and option.get("action")
        ],
        disabled=bool(payload.get("disabled")),
        disabled_reason=_normalize_optional_text(payload.get("disabled_reason")),
    )
    if device_status == "disabled":
        control.disabled = True
        control.disabled_reason = "设备已停用"
    elif raw_control_payload is not None:
        if bool(raw_control_payload.get("disabled")):
            control.disabled = True
        raw_disabled_reason = _normalize_optional_text(raw_control_payload.get("disabled_reason"))
        if raw_disabled_reason:
            control.disabled_reason = raw_disabled_reason
    return control


def _default_control_for_device(*, device: Device, state: str) -> dict[str, Any]:
    if device.status == "disabled":
        return {"kind": "none", "disabled": True, "disabled_reason": "设备已停用"}
    if device.device_type in {"light", "speaker", "ac"}:
        return {
            "kind": "toggle",
            "value": state not in {"off", "inactive", "offline", "unknown"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if device.device_type == "lock":
        return {
            "kind": "action_set",
            "value": state,
            "options": [
                {"label": "上锁", "value": "locked", "action": "lock", "params": {}},
                {"label": "解锁", "value": "unlocked", "action": "unlock", "params": {}},
            ],
        }
    if device.device_type == "curtain":
        return {
            "kind": "action_set",
            "value": state,
            "options": [
                {"label": "打开", "value": "open", "action": "open", "params": {}},
                {"label": "关闭", "value": "closed", "action": "close", "params": {}},
                {"label": "停止", "value": "stopped", "action": "stop", "params": {}},
            ],
        }
    return {"kind": "none"}


def _mark_control_unavailable(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["disabled"] = True
    result["disabled_reason"] = PLATFORM_OFFLINE_REASON
    return result


def _build_canonical_control_payload(
    *,
    device: Device,
    domain: str,
    state: str,
    raw_control: dict[str, Any] | None,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    normalized_domain = domain.strip().lower()
    normalized_state = state.strip().lower()
    payload = dict(raw_control or {})
    if device.status == "disabled":
        return {"kind": "none", "disabled": True, "disabled_reason": "设备已停用"}
    if normalized_domain in {"sensor", "binary_sensor", "camera"}:
        return {"kind": "none"}
    if device.device_type == "light" and normalized_domain == "light":
        return {
            "kind": "toggle",
            "value": normalized_state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if device.device_type == "ac" and normalized_domain == "climate":
        hvac_modes = attributes.get("hvac_modes")
        if isinstance(hvac_modes, list):
            options = [
                {
                    "label": _friendly_state_display(str(mode)),
                    "value": str(mode),
                    "action": "set_hvac_mode",
                    "params": {"hvac_mode": str(mode)},
                }
                for mode in hvac_modes
                if isinstance(mode, str) and mode.strip()
            ]
            if options:
                return {
                    "kind": "action_set",
                    "value": normalized_state or state,
                    "options": options,
                }
        return {
            "kind": "toggle",
            "value": normalized_state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if device.device_type == "speaker" and normalized_domain == "media_player":
        volume_level = attributes.get("volume_level")
        if isinstance(volume_level, (int, float)):
            return {
                "kind": "range",
                "value": int(round(float(volume_level) * 100)),
                "min_value": 0,
                "max_value": 100,
                "step": 5,
                "unit": "%",
                "action": "set_volume",
            }
        return {
            "kind": "toggle",
            "value": normalized_state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if device.device_type == "lock" and normalized_domain == "lock":
        return {
            "kind": "action_set",
            "value": normalized_state or state,
            "options": [
                {"label": "上锁", "value": "locked", "action": "lock", "params": {}},
                {"label": "解锁", "value": "unlocked", "action": "unlock", "params": {}},
            ],
        }
    if device.device_type == "curtain" and normalized_domain == "cover":
        return {
            "kind": "action_set",
            "value": normalized_state or state,
            "options": [
                {"label": "打开", "value": "open", "action": "open", "params": {}},
                {"label": "关闭", "value": "closed", "action": "close", "params": {}},
                {"label": "停止", "value": "stopped", "action": "stop", "params": {}},
            ],
        }
    if payload.get("kind") == "toggle":
        payload["value"] = normalized_state not in {"off", "unknown", "unavailable"}
        payload["action_on"] = "turn_on"
        payload["action_off"] = "turn_off"
    return payload


def _build_device_action_log_read(
    item: AuditLog,
    *,
    entity_names: dict[str, str],
) -> DeviceActionLogRead:
    details = load_json(item.details) if item.details else {}
    if not isinstance(details, dict):
        details = {}
    entity_id = _normalize_optional_text(
        details.get("resolved_entity_id")
        or details.get("entity_id")
        or details.get("requested_entity_id")
    )
    return DeviceActionLogRead(
        id=item.id,
        action=item.action,
        target_type=item.target_type,
        result=item.result,
        actor_type=item.actor_type,
        actor_id=item.actor_id,
        entity_id=entity_id,
        entity_name=entity_names.get(entity_id or ""),
        message=_extract_log_message(item.action, details),
        details=details,
        created_at=item.created_at,
    )


def _extract_log_message(action: str, details: dict[str, Any]) -> str | None:
    if action == "device_action.execute":
        error = details.get("error")
        if isinstance(error, dict):
            detail = error.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
            if isinstance(error.get("error_code"), str):
                return str(error["error_code"])
        if isinstance(error, str) and error.strip():
            return error.strip()
        if isinstance(details.get("action"), str):
            return str(details["action"])
        return "设备控制"
    if action == "device.disable":
        return "设备已停用"
    if action == "device.delete":
        return "设备已删除"
    if action == "device.update":
        return "设备信息已更新"
    return None


def _build_device_detail_capabilities(
    *,
    device: Device,
    bindings: list[DeviceBinding],
) -> DeviceDetailCapabilityRead:
    adapter_type: str | None = None
    plugin_id: str | None = None
    vendor_code: str | None = None
    capability_tags: list[str] = []

    for binding in bindings:
        binding_capabilities = _load_binding_capabilities(binding)
        if plugin_id is None and binding.plugin_id:
            plugin_id = binding.plugin_id
        if adapter_type is None:
            adapter_type = _normalize_optional_text(binding_capabilities.get("adapter_type"))
        if vendor_code is None:
            vendor_code = _normalize_optional_text(binding_capabilities.get("vendor_code"))
        for tag in _load_capability_tags(binding_capabilities):
            if tag not in capability_tags:
                capability_tags.append(tag)

    if vendor_code is None and device.vendor:
        vendor_code = device.vendor

    supports_voice_terminal = _device_supports_voice_terminal(device=device, bindings=bindings)
    return DeviceDetailCapabilityRead(
        supports_voice_terminal=supports_voice_terminal,
        supports_voiceprint=supports_voice_terminal,
        adapter_type=adapter_type,
        plugin_id=plugin_id,
        vendor_code=vendor_code,
        capability_tags=capability_tags,
    )


def _build_device_detail_builtin_tabs(
    *,
    capabilities: DeviceDetailCapabilityRead,
) -> list[DeviceDetailBuiltinTabRead]:
    tabs: list[DeviceDetailBuiltinTabRead] = []
    if capabilities.supports_voiceprint:
        tabs.append(DeviceDetailBuiltinTabRead(key="voiceprint"))
    return tabs


def _build_device_detail_plugin_tabs(
    db: Session,
    *,
    device: Device,
    bindings: list[DeviceBinding],
) -> list[DeviceDetailPluginTabRead]:
    from app.modules.plugin.config_service import get_plugin_config_form
    from app.modules.plugin.service import PluginServiceError, get_household_plugin

    tabs: list[DeviceDetailPluginTabRead] = []
    seen_plugin_ids: set[str] = set()

    for binding in bindings:
        if not binding.plugin_id or binding.plugin_id in seen_plugin_ids:
            continue
        seen_plugin_ids.add(binding.plugin_id)
        try:
            plugin = get_household_plugin(
                db,
                household_id=device.household_id,
                plugin_id=binding.plugin_id,
            )
        except PluginServiceError:
            continue
        for tab in plugin.capabilities.device_detail_tabs:
            try:
                config_form = get_plugin_config_form(
                    db,
                    household_id=device.household_id,
                    plugin_id=plugin.id,
                    scope_type=tab.config_scope_type,
                    scope_key=device.id,
                )
            except PluginServiceError:
                continue
            tabs.append(
                DeviceDetailPluginTabRead(
                    tab_key=tab.tab_key,
                    title=tab.title,
                    description=tab.description,
                    plugin_id=plugin.id,
                    plugin_name=plugin.name,
                    config_form=config_form,
                )
            )
    return tabs


def _load_binding_capabilities(binding: DeviceBinding) -> dict[str, Any]:
    loaded = load_json(binding.capabilities)
    return loaded if isinstance(loaded, dict) else {}


def _load_capability_tags(capabilities: dict[str, Any]) -> list[str]:
    raw_tags = capabilities.get("capability_tags")
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    for item in raw_tags:
        text = str(item).strip().lower()
        if not text or text in tags:
            continue
        tags.append(text)
    return tags


def _binding_supports_voice_terminal(
    *,
    device: Device,
    binding: DeviceBinding,
    capabilities: dict[str, Any],
) -> bool:
    if binding.platform == "open_xiaoai":
        return True
    if binding.plugin_id == "open-xiaoai-speaker":
        return True

    adapter_type = _normalize_optional_text(capabilities.get("adapter_type"))
    if adapter_type in {"open_xiaoai", "voice_terminal"}:
        return True

    vendor_code = _normalize_optional_text(capabilities.get("vendor_code"))
    if vendor_code == "xiaomi" and device.device_type == "speaker":
        return True

    capability_tags = set(_load_capability_tags(capabilities))
    if capability_tags.intersection({"voice_terminal", "voiceprint", "speaker", "microphone"}):
        return True
    return False


def _device_supports_voice_terminal(
    *,
    device: Device,
    bindings: list[DeviceBinding],
) -> bool:
    for binding in bindings:
        if _binding_supports_voice_terminal(
            device=device,
            binding=binding,
            capabilities=_load_binding_capabilities(binding),
        ):
            return True
    return device.device_type == "speaker" and device.vendor == "xiaomi"


def _load_device_bindings(db: Session, *, device_id: str) -> list[DeviceBinding]:
    return list(
        db.scalars(
            select(DeviceBinding)
            .where(DeviceBinding.device_id == device_id)
            .order_by(DeviceBinding.last_sync_at.desc().nullslast(), DeviceBinding.id.desc())
        ).all()
    )


def _load_live_state_maps(
    db: Session,
    *,
    household_id: str,
    bindings: list[DeviceBinding],
) -> LiveStateLoadResult:
    return load_binding_live_state_maps_via_plugin(
        db,
        household_id=household_id,
        bindings=bindings,
    )


def _binding_is_platform_unavailable(
    *,
    binding: DeviceBinding,
    unavailable_instance_ids: set[str],
) -> bool:
    integration_instance_id = _normalize_optional_text(binding.integration_instance_id)
    if not integration_instance_id:
        return False
    return integration_instance_id in unavailable_instance_ids


def _device_has_unavailable_platform_binding(
    *,
    bindings: list[DeviceBinding],
    unavailable_instance_ids: set[str],
) -> bool:
    return any(
        _binding_is_platform_unavailable(
            binding=binding,
            unavailable_instance_ids=unavailable_instance_ids,
        )
        for binding in bindings
    )


def _apply_live_state_snapshot(
    *,
    device: Device,
    binding: DeviceBinding,
    capabilities: dict[str, Any],
    live_state_map: dict[str, dict[str, Any]] | None,
) -> None:
    if not live_state_map:
        return
    raw_entities = capabilities.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            entity_id = _normalize_optional_text(raw_entity.get("entity_id"))
            if not entity_id:
                continue
            live_state = live_state_map.get(entity_id)
            if live_state is None:
                continue
            _apply_live_state_to_entity_payload(
                device=device,
                raw_entity=raw_entity,
                live_state=live_state,
            )
        capabilities["entities"] = raw_entities

    primary_entity_id = _resolve_binding_primary_entity_id(binding, capabilities)
    if not primary_entity_id:
        return
    live_state = live_state_map.get(primary_entity_id)
    if live_state is None:
        return
    state_value = _extract_live_state_value(live_state)
    capabilities["state"] = state_value
    capabilities["domain"] = _normalize_optional_text(capabilities.get("domain")) or primary_entity_id.split(".", 1)[0]


def _apply_live_state_snapshot_to_raw_entities(
    *,
    device: Device,
    raw_entities: list[dict[str, Any]],
    live_state_map: dict[str, dict[str, Any]] | None,
) -> None:
    if not live_state_map:
        return
    for raw_entity in raw_entities:
        entity_id = _normalize_optional_text(raw_entity.get("entity_id"))
        if not entity_id:
            continue
        live_state = live_state_map.get(entity_id)
        if live_state is None:
            continue
        _apply_live_state_to_entity_payload(
            device=device,
            raw_entity=raw_entity,
            live_state=live_state,
        )


def _apply_live_state_to_entity_payload(
    *,
    device: Device,
    raw_entity: dict[str, Any],
    live_state: dict[str, Any],
) -> None:
    entity_id = _normalize_optional_text(raw_entity.get("entity_id")) or ""
    domain = _normalize_optional_text(raw_entity.get("domain")) or (entity_id.split(".", 1)[0] if "." in entity_id else "")
    state_value = _extract_live_state_value(live_state)
    attributes = live_state.get("attributes") if isinstance(live_state.get("attributes"), dict) else {}
    raw_entity["domain"] = domain
    raw_entity["state"] = state_value
    raw_entity["state_display"] = _friendly_state_display(state_value)
    live_unit = _normalize_optional_text(attributes.get("unit_of_measurement")) if isinstance(attributes, dict) else None
    if live_unit:
        raw_entity["unit"] = live_unit
    raw_entity["control"] = _build_canonical_control_payload(
        device=device,
        domain=domain,
        state=state_value,
        raw_control=raw_entity.get("control") if isinstance(raw_entity.get("control"), dict) else None,
        attributes=attributes if isinstance(attributes, dict) else {},
    )
    raw_entity["updated_at"] = (
        _normalize_optional_text(live_state.get("last_updated"))
        or _normalize_optional_text(live_state.get("last_changed"))
        or raw_entity.get("updated_at")
        or device.updated_at
    )


def _extract_live_state_value(live_state: dict[str, Any]) -> str:
    return _normalize_optional_text(live_state.get("state")) or "unknown"


def _resolve_binding_primary_entity_id(binding: DeviceBinding, capabilities: dict[str, Any]) -> str | None:
    candidates: list[Any] = [
        capabilities.get("primary_entity_id"),
        binding.external_entity_id,
    ]
    raw_entity_ids = capabilities.get("entity_ids")
    if isinstance(raw_entity_ids, list):
        candidates.extend(raw_entity_ids)
    for candidate in candidates:
        normalized = _normalize_optional_text(candidate)
        if normalized:
            return normalized
    return None


def _binding_contains_entity_id(
    db: Session,
    binding: DeviceBinding,
    capabilities: dict[str, Any],
    entity_id: str,
) -> bool:
    normalized_entity_id = _normalize_optional_text(entity_id)
    if not normalized_entity_id:
        return False
    return normalized_entity_id in build_binding_entity_ids(
        db=db,
        binding=binding,
        capabilities=capabilities,
    )


def update_binding_entity_state(
    db: Session,
    *,
    binding: DeviceBinding,
    resolved_entity_id: str | None,
    patch: dict[str, Any] | None,
) -> None:
    if not resolved_entity_id or not isinstance(patch, dict):
        return
    changed = update_binding_entity_state_snapshot(
        db,
        binding=binding,
        resolved_entity_id=resolved_entity_id,
        patch=patch,
    )
    capabilities = _load_binding_capabilities(binding)
    raw_entities = capabilities.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            if str(raw_entity.get("entity_id") or "").strip() != resolved_entity_id:
                continue
            if isinstance(patch.get("state"), str) and patch["state"].strip():
                raw_entity["state"] = patch["state"].strip()
                raw_entity["state_display"] = _friendly_state_display(patch["state"].strip())
                changed = True
            if "value" in patch:
                control = raw_entity.get("control")
                if isinstance(control, dict):
                    control["value"] = patch.get("value")
                    changed = True
            raw_entity["updated_at"] = utc_now_iso()
            break
        capabilities["entities"] = raw_entities
    if isinstance(patch.get("state"), str) and patch["state"].strip():
        if _binding_contains_entity_id(db, binding, capabilities, resolved_entity_id):
            capabilities["state"] = patch["state"].strip()
            changed = True
    if not changed:
        return
    binding.capabilities = dump_json(capabilities)
    db.add(binding)


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
