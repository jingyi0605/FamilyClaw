from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid, utc_now_iso
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
