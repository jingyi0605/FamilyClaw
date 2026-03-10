from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.ha_integration.client import HomeAssistantClient
from app.modules.household.service import get_household_or_404

SUPPORTED_DEVICE_TYPES: dict[str, tuple[str, bool]] = {
    "light": ("light", True),
    "climate": ("ac", True),
    "cover": ("curtain", True),
    "media_player": ("speaker", True),
    "camera": ("camera", False),
    "lock": ("lock", True),
    "sensor": ("sensor", False),
    "binary_sensor": ("sensor", False),
}


@dataclass
class SyncFailure:
    entity_id: str | None
    reason: str


@dataclass
class SyncSummary:
    household_id: str
    created_devices: int
    updated_devices: int
    created_bindings: int
    skipped_entities: int
    failed_entities: int
    devices: list[Device]
    failures: list[SyncFailure]


@dataclass
class DeviceActionExecution:
    household_id: str
    device_id: str
    action: str
    platform: str
    service_domain: str
    service_name: str
    entity_id: str
    params: dict[str, Any]
    response_payload: dict | list


def sync_home_assistant_devices(
    db: Session,
    *,
    household_id: str,
    client: HomeAssistantClient | None = None,
) -> SyncSummary:
    get_household_or_404(db, household_id)
    client = client or HomeAssistantClient()
    states = client.get_states()

    created_devices = 0
    updated_devices = 0
    created_bindings = 0
    skipped_entities = 0
    failures: list[SyncFailure] = []
    synced_devices: list[Device] = []

    for state in states:
        try:
            entity_id = str(state.get("entity_id", "")).strip()
            if not entity_id or "." not in entity_id:
                skipped_entities += 1
                continue

            domain = entity_id.split(".", 1)[0]
            mapping = SUPPORTED_DEVICE_TYPES.get(domain)
            if mapping is None:
                skipped_entities += 1
                continue

            device_type, controllable = mapping
            attributes = state.get("attributes") or {}
            friendly_name = attributes.get("friendly_name") or entity_id
            external_device_id = (
                attributes.get("device_id")
                or attributes.get("device")
                or attributes.get("id")
            )
            normalized_status = _normalize_device_status(str(state.get("state")))
            capabilities = {
                "domain": domain,
                "device_class": attributes.get("device_class"),
                "supported_features": attributes.get("supported_features"),
                "unit_of_measurement": attributes.get("unit_of_measurement"),
                "state": state.get("state"),
            }

            with db.begin_nested():
                binding = db.scalar(
                    select(DeviceBinding).where(
                        DeviceBinding.platform == "home_assistant",
                        DeviceBinding.external_entity_id == entity_id,
                    )
                )

                if binding is None:
                    device = Device(
                        id=new_uuid(),
                        household_id=household_id,
                        room_id=None,
                        name=friendly_name,
                        device_type=device_type,
                        vendor="ha",
                        status=normalized_status,
                        controllable=1 if controllable else 0,
                    )
                    db.add(device)
                    db.flush()

                    binding = DeviceBinding(
                        id=new_uuid(),
                        device_id=device.id,
                        platform="home_assistant",
                        external_entity_id=entity_id,
                        external_device_id=str(external_device_id) if external_device_id else None,
                        capabilities=dump_json(capabilities),
                        last_sync_at=utc_now_iso(),
                    )
                    db.add(binding)
                    db.flush()
                    created_devices += 1
                    created_bindings += 1
                else:
                    device = db.get(Device, binding.device_id)
                    if device is None:
                        raise ValueError("binding exists but linked device is missing")
                    if device.household_id != household_id:
                        raise ValueError("existing binding belongs to another household")

                    device.name = friendly_name
                    device.device_type = device_type
                    device.vendor = "ha"
                    device.status = normalized_status
                    device.controllable = 1 if controllable else 0
                    binding.external_device_id = str(external_device_id) if external_device_id else None
                    binding.capabilities = dump_json(capabilities)
                    binding.last_sync_at = utc_now_iso()
                    db.add(device)
                    db.add(binding)
                    db.flush()
                    updated_devices += 1

                synced_devices.append(device)
        except Exception as exc:
            failures.append(
                SyncFailure(
                    entity_id=state.get("entity_id") if isinstance(state, dict) else None,
                    reason=str(exc),
                )
            )

    return SyncSummary(
        household_id=household_id,
        created_devices=created_devices,
        updated_devices=updated_devices,
        created_bindings=created_bindings,
        skipped_entities=skipped_entities,
        failed_entities=len(failures),
        devices=synced_devices,
        failures=failures,
    )


def _normalize_device_status(state_value: str) -> str:
    if state_value in {"unavailable", "unknown"}:
        return "offline"
    return "active"


SUPPORTED_DEVICE_ACTIONS: dict[str, dict[str, tuple[str, str]]] = {
    "light": {
        "turn_on": ("light", "turn_on"),
        "turn_off": ("light", "turn_off"),
        "set_brightness": ("light", "turn_on"),
    },
    "ac": {
        "turn_on": ("climate", "turn_on"),
        "turn_off": ("climate", "turn_off"),
        "set_temperature": ("climate", "set_temperature"),
        "set_hvac_mode": ("climate", "set_hvac_mode"),
    },
    "curtain": {
        "open": ("cover", "open_cover"),
        "close": ("cover", "close_cover"),
        "stop": ("cover", "stop_cover"),
    },
    "speaker": {
        "turn_on": ("media_player", "turn_on"),
        "turn_off": ("media_player", "turn_off"),
        "play_pause": ("media_player", "media_play_pause"),
        "set_volume": ("media_player", "volume_set"),
    },
    "lock": {
        "lock": ("lock", "lock"),
        "unlock": ("lock", "unlock"),
    },
}


def get_home_assistant_binding_for_device(db: Session, device_id: str) -> DeviceBinding | None:
    return db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.device_id == device_id,
            DeviceBinding.platform == "home_assistant",
        )
    )


def _normalize_action_params(
    *,
    device_type: str,
    action: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    if device_type == "light" and action == "set_brightness":
        brightness = params.get("brightness")
        if not isinstance(brightness, (int, float)):
            raise ValueError("brightness must be a number")
        normalized["brightness_pct"] = max(1, min(100, int(round(brightness))))
        return normalized

    if device_type == "ac" and action == "set_temperature":
        temperature = params.get("temperature")
        if not isinstance(temperature, (int, float)):
            raise ValueError("temperature must be a number")
        normalized["temperature"] = float(temperature)
        hvac_mode = params.get("hvac_mode")
        if hvac_mode is not None:
            if not isinstance(hvac_mode, str) or not hvac_mode.strip():
                raise ValueError("hvac_mode must be a non-empty string")
            normalized["hvac_mode"] = hvac_mode.strip()
        return normalized

    if device_type == "ac" and action == "set_hvac_mode":
        hvac_mode = params.get("hvac_mode")
        if not isinstance(hvac_mode, str) or not hvac_mode.strip():
            raise ValueError("hvac_mode must be a non-empty string")
        normalized["hvac_mode"] = hvac_mode.strip()
        return normalized

    if device_type == "speaker" and action == "set_volume":
        volume = params.get("volume")
        if not isinstance(volume, (int, float)):
            raise ValueError("volume must be a number")
        normalized["volume_level"] = max(0, min(1, float(volume)))
        return normalized

    return normalized


def execute_home_assistant_device_action(
    db: Session,
    *,
    household_id: str,
    device: Device,
    action: str,
    params: dict[str, Any],
    client: HomeAssistantClient | None = None,
) -> DeviceActionExecution:
    get_household_or_404(db, household_id)
    binding = get_home_assistant_binding_for_device(db, device.id)
    if binding is None:
        raise ValueError("home assistant binding not found for device")

    if device.device_type not in SUPPORTED_DEVICE_ACTIONS:
        raise ValueError("device type does not support action execution")

    action_mapping = SUPPORTED_DEVICE_ACTIONS[device.device_type]
    if action not in action_mapping:
        raise ValueError("unsupported action for device type")

    capabilities = load_json(binding.capabilities)
    if capabilities is not None and not isinstance(capabilities, dict):
        capabilities = None

    client = client or HomeAssistantClient()
    service_domain, service_name = action_mapping[action]
    normalized_params = _normalize_action_params(
        device_type=device.device_type,
        action=action,
        params=params,
    )
    service_data = {
        "entity_id": binding.external_entity_id,
        **normalized_params,
    }
    response_payload = client.call_service(
        domain=service_domain,
        service=service_name,
        data=service_data,
    )

    if capabilities is not None:
        capabilities["last_action"] = action
        capabilities["last_action_params"] = normalized_params
        binding.capabilities = dump_json(capabilities)
        binding.last_sync_at = utc_now_iso()
        db.add(binding)

    return DeviceActionExecution(
        household_id=household_id,
        device_id=device.id,
        action=action,
        platform="home_assistant",
        service_domain=service_domain,
        service_name=service_name,
        entity_id=binding.external_entity_id,
        params=normalized_params,
        response_payload=response_payload,
    )
