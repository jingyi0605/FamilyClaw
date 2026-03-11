from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.ha_integration.client import HomeAssistantClient
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.service import get_household_or_404
from app.modules.room.models import Room

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
    created_rooms: int
    assigned_rooms: int
    skipped_entities: int
    failed_entities: int
    devices: list[Device]
    failures: list[SyncFailure]


@dataclass
class RoomSyncSummary:
    household_id: str
    created_rooms: int
    matched_entities: int
    skipped_entities: int
    rooms: list[Room]


@dataclass
class HaRoomCandidate:
    name: str
    entity_count: int
    exists_locally: bool
    can_sync: bool


@dataclass
class HaDeviceCandidate:
    external_device_id: str
    primary_entity_id: str
    name: str
    room_name: str | None
    device_type: str
    entity_count: int
    already_synced: bool


def get_household_ha_config(db: Session, household_id: str) -> HouseholdHaConfig | None:
    return db.get(HouseholdHaConfig, household_id)


def get_home_assistant_config_view(db: Session, household_id: str) -> dict[str, Any]:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    return {
        "household_id": household_id,
        "base_url": _normalize_optional_text(config.base_url) if config else None,
        "token_configured": bool(config and _normalize_optional_text(config.access_token)),
        "sync_rooms_enabled": bool(config.sync_rooms_enabled) if config else False,
        "last_device_sync_at": config.last_device_sync_at if config else None,
        "updated_at": config.updated_at if config else None,
    }


def upsert_household_ha_config(
    db: Session,
    *,
    household_id: str,
    base_url: str | None,
    access_token: str | None,
    clear_access_token: bool,
    sync_rooms_enabled: bool,
) -> HouseholdHaConfig:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    if config is None:
        config = HouseholdHaConfig(household_id=household_id)

    config.base_url = _normalize_optional_text(base_url)
    if clear_access_token:
        config.access_token = None
    elif access_token is not None:
        config.access_token = _normalize_optional_text(access_token)
    config.sync_rooms_enabled = bool(sync_rooms_enabled)
    config.updated_at = utc_now_iso()
    db.add(config)
    db.flush()
    return config


def build_home_assistant_client_for_household(db: Session, household_id: str) -> HomeAssistantClient:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    base_url = _normalize_optional_text(config.base_url) if config else None
    access_token = _normalize_optional_text(config.access_token) if config else None
    return HomeAssistantClient(base_url=base_url, token=access_token)


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


DOMAIN_PRIORITY = {
    "climate": 0,
    "light": 1,
    "cover": 2,
    "lock": 3,
    "media_player": 4,
    "camera": 5,
    "sensor": 6,
    "binary_sensor": 7,
}


def sync_home_assistant_devices(
    db: Session,
    *,
    household_id: str,
    external_device_ids: list[str] | None = None,
    client: HomeAssistantClient | None = None,
) -> SyncSummary:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    client = client or build_home_assistant_client_for_household(db, household_id)
    device_registry = client.get_device_registry()
    entity_registry = client.get_entity_registry()
    area_registry = client.get_area_registry()
    states = client.get_states()
    state_map = _build_state_map(states)
    area_name_map = _build_area_name_map(area_registry)
    supported_entities_by_device, skipped_entities = _group_supported_entities_by_device(entity_registry)
    selected_device_ids = {
        device_id for device_id in (_normalize_optional_text(value) for value in (external_device_ids or [])) if device_id
    }

    created_devices = 0
    updated_devices = 0
    created_bindings = 0
    created_rooms = 0
    assigned_rooms = 0
    failures: list[SyncFailure] = []
    synced_devices: list[Device] = []
    room_cache = _load_room_cache(db, household_id)
    sync_rooms_enabled = bool(config and config.sync_rooms_enabled)

    for ha_device in device_registry:
        state: dict | None = None
        entity_id: str | None = None
        try:
            external_device_id = _normalize_optional_text(str(ha_device.get("id", "")))
            if not external_device_id:
                continue
            if selected_device_ids and external_device_id not in selected_device_ids:
                continue

            entity_entries = supported_entities_by_device.get(external_device_id, [])
            if not entity_entries:
                continue

            primary_entity = _select_primary_entity(entity_entries)
            entity_id_value = _normalize_optional_text(primary_entity.get("entity_id"))
            if not entity_id_value or "." not in entity_id_value:
                continue
            entity_id = entity_id_value
            domain = entity_id_value.split(".", 1)[0]
            mapping = SUPPORTED_DEVICE_TYPES[domain]
            device_type, controllable = mapping
            state = state_map.get(entity_id)
            normalized_status = _normalize_ha_device_status(entity_entries, state_map)
            room_name = _resolve_room_name(
                ha_device=ha_device,
                primary_entity=primary_entity,
                area_name_map=area_name_map,
                state_map=state_map,
            )
            device_name = _resolve_device_name(
                ha_device=ha_device,
                primary_entity=primary_entity,
                state=state,
            )
            capabilities = {
                "ha_device_id": external_device_id,
                "entity_ids": [entry["entity_id"] for entry in entity_entries],
                "primary_entity_id": entity_id,
                "domain": domain,
                "manufacturer": _normalize_optional_text(ha_device.get("manufacturer")),
                "model": _normalize_optional_text(ha_device.get("model")),
                "sw_version": _normalize_optional_text(ha_device.get("sw_version")),
                "hw_version": _normalize_optional_text(ha_device.get("hw_version")),
                "name": device_name,
                "state": state.get("state") if isinstance(state, dict) else None,
                "room_name": room_name,
                "base_url": client.get_base_url(),
            }

            with db.begin_nested():
                binding = _get_existing_binding(
                    db,
                    external_device_id=external_device_id,
                    primary_entity_id=entity_id,
                )

                if binding is None:
                    device = Device(
                        id=new_uuid(),
                        household_id=household_id,
                        room_id=None,
                        name=device_name,
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

                    device.name = device_name
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

                if sync_rooms_enabled and room_name:
                    room, room_created = _get_or_create_room_from_name(
                        db,
                        household_id=household_id,
                        room_name=room_name,
                        room_cache=room_cache,
                    )
                    if room_created:
                        created_rooms += 1
                    if device.room_id != room.id:
                        device.room_id = room.id
                        db.add(device)
                        db.flush()
                        assigned_rooms += 1

                synced_devices.append(device)
        except Exception as exc:
            failures.append(
                SyncFailure(
                    entity_id=entity_id,
                    reason=str(exc),
                )
            )

    if config is not None:
        config.last_device_sync_at = utc_now_iso()
        db.add(config)

    return SyncSummary(
        household_id=household_id,
        created_devices=created_devices,
        updated_devices=updated_devices,
        created_bindings=created_bindings,
        created_rooms=created_rooms,
        assigned_rooms=assigned_rooms,
        skipped_entities=skipped_entities,
        failed_entities=len(failures),
        devices=synced_devices,
        failures=failures,
    )


def list_home_assistant_device_candidates(
    db: Session,
    *,
    household_id: str,
    client: HomeAssistantClient | None = None,
) -> list[HaDeviceCandidate]:
    get_household_or_404(db, household_id)
    client = client or build_home_assistant_client_for_household(db, household_id)
    device_registry = client.get_device_registry()
    entity_registry = client.get_entity_registry()
    area_registry = client.get_area_registry()
    states = client.get_states()

    state_map = _build_state_map(states)
    area_name_map = _build_area_name_map(area_registry)
    supported_entities_by_device, _ = _group_supported_entities_by_device(entity_registry)
    existing_bindings = _load_existing_home_assistant_bindings(db, household_id)
    candidates: list[HaDeviceCandidate] = []

    for ha_device in device_registry:
        external_device_id = _normalize_optional_text(ha_device.get("id"))
        if not external_device_id:
            continue
        entity_entries = supported_entities_by_device.get(external_device_id, [])
        if not entity_entries:
            continue

        primary_entity = _select_primary_entity(entity_entries)
        primary_entity_id = _normalize_optional_text(primary_entity.get("entity_id"))
        if not primary_entity_id or "." not in primary_entity_id:
            continue

        domain = primary_entity_id.split(".", 1)[0]
        state = state_map.get(primary_entity_id)
        candidates.append(
            HaDeviceCandidate(
                external_device_id=external_device_id,
                primary_entity_id=primary_entity_id,
                name=_resolve_device_name(
                    ha_device=ha_device,
                    primary_entity=primary_entity,
                    state=state,
                ),
                room_name=_resolve_room_name(
                    ha_device=ha_device,
                    primary_entity=primary_entity,
                    area_name_map=area_name_map,
                    state_map=state_map,
                ),
                device_type=SUPPORTED_DEVICE_TYPES[domain][0],
                entity_count=len(entity_entries),
                already_synced=external_device_id in existing_bindings,
            )
        )

    return sorted(candidates, key=lambda item: ((item.room_name or "未分配房间"), item.name, item.external_device_id))




def sync_home_assistant_rooms(
    db: Session,
    *,
    household_id: str,
    room_names: list[str] | None = None,
    client: HomeAssistantClient | None = None,
) -> RoomSyncSummary:
    get_household_or_404(db, household_id)
    client = client or build_home_assistant_client_for_household(db, household_id)
    area_registry = client.get_area_registry()
    room_cache = _load_room_cache(db, household_id)
    requested_names = {_normalize_room_key(name) for name in (room_names or []) if name.strip()}
    matched_entities = 0
    skipped_entities = 0
    created_rooms = 0

    for area in area_registry:
        room_name = _normalize_optional_text(area.get("name"))
        if not room_name:
            skipped_entities += 1
            continue

        normalized_room_key = _normalize_room_key(room_name)
        if requested_names and normalized_room_key not in requested_names:
            skipped_entities += 1
            continue

        if normalized_room_key in room_cache:
            raise ValueError(f"room already exists locally: {room_name}")

        matched_entities += 1
        _, created = _get_or_create_room_from_name(
            db,
            household_id=household_id,
            room_name=room_name,
            room_cache=room_cache,
        )
        if created:
            created_rooms += 1

    return RoomSyncSummary(
        household_id=household_id,
        created_rooms=created_rooms,
        matched_entities=matched_entities,
        skipped_entities=skipped_entities,
        rooms=list(room_cache.values()),
    )


def list_home_assistant_room_candidates(
    db: Session,
    *,
    household_id: str,
    client: HomeAssistantClient | None = None,
) -> list[HaRoomCandidate]:
    get_household_or_404(db, household_id)
    client = client or build_home_assistant_client_for_household(db, household_id)
    area_registry = client.get_area_registry()
    device_registry = client.get_device_registry()
    entity_registry = client.get_entity_registry()
    room_cache = _load_room_cache(db, household_id)
    area_entity_counts = _build_area_entity_counts(device_registry, entity_registry)

    candidates: list[HaRoomCandidate] = []
    for area in sorted(area_registry, key=lambda item: str(item.get("name", ""))):
        room_name = _normalize_optional_text(area.get("name"))
        if not room_name:
            continue
        room_key = _normalize_room_key(room_name)
        area_id = _normalize_optional_text(area.get("area_id"))
        exists_locally = room_key in room_cache
        candidates.append(
            HaRoomCandidate(
                name=room_name,
                entity_count=area_entity_counts.get(area_id or "", 0),
                exists_locally=exists_locally,
                can_sync=not exists_locally,
            )
        )

    return candidates


def _build_state_map(states: list[dict]) -> dict[str, dict]:
    state_map: dict[str, dict] = {}
    for state in states:
        entity_id = _normalize_optional_text(state.get("entity_id")) if isinstance(state, dict) else None
        if entity_id:
            state_map[entity_id] = state
    return state_map


def _build_area_name_map(area_registry: list[dict]) -> dict[str, str]:
    area_name_map: dict[str, str] = {}
    for area in area_registry:
        area_id = _normalize_optional_text(area.get("area_id")) if isinstance(area, dict) else None
        area_name = _normalize_optional_text(area.get("name")) if isinstance(area, dict) else None
        if area_id and area_name:
            area_name_map[area_id] = area_name
    return area_name_map


def _group_supported_entities_by_device(entity_registry: list[dict]) -> tuple[dict[str, list[dict]], int]:
    grouped: dict[str, list[dict]] = {}
    skipped = 0
    for entry in entity_registry:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        entity_id = _normalize_optional_text(entry.get("entity_id"))
        device_id = _normalize_optional_text(entry.get("device_id"))
        disabled_by = _normalize_optional_text(entry.get("disabled_by"))
        if not entity_id or not device_id or disabled_by:
            skipped += 1
            continue
        if "." not in entity_id:
            skipped += 1
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in SUPPORTED_DEVICE_TYPES:
            skipped += 1
            continue
        grouped.setdefault(device_id, []).append(entry)
    return grouped, skipped


def _select_primary_entity(entity_entries: list[dict]) -> dict:
    return sorted(
        entity_entries,
        key=lambda entry: (
            DOMAIN_PRIORITY.get(str(entry.get("entity_id", "")).split(".", 1)[0], 99),
            str(entry.get("entity_id", "")),
        ),
    )[0]


def _resolve_device_name(*, ha_device: dict, primary_entity: dict, state: dict | None) -> str:
    for value in (
        ha_device.get("name_by_user"),
        ha_device.get("name"),
        primary_entity.get("name"),
        primary_entity.get("original_name"),
    ):
        normalized = _normalize_optional_text(value)
        if normalized:
            return normalized

    if isinstance(state, dict):
        attributes = state.get("attributes")
        if isinstance(attributes, dict):
            friendly_name = _normalize_optional_text(attributes.get("friendly_name"))
            if friendly_name:
                return friendly_name

    return str(primary_entity.get("entity_id"))


def _normalize_ha_device_status(entity_entries: list[dict], state_map: dict[str, dict]) -> str:
    has_active = False
    has_offline = False
    for entry in entity_entries:
        entity_id = str(entry.get("entity_id", "")).strip()
        state = state_map.get(entity_id)
        if not isinstance(state, dict):
            continue
        normalized = _normalize_device_status(str(state.get("state")))
        if normalized == "active":
            has_active = True
        elif normalized == "offline":
            has_offline = True

    if has_active:
        return "active"
    if has_offline:
        return "offline"
    return "inactive"


def _resolve_room_name(
    *,
    ha_device: dict,
    primary_entity: dict,
    area_name_map: dict[str, str],
    state_map: dict[str, dict],
) -> str | None:
    for area_id in (
        _normalize_optional_text(primary_entity.get("area_id")),
        _normalize_optional_text(ha_device.get("area_id")),
    ):
        if area_id and area_id in area_name_map:
            return area_name_map[area_id]

    state = state_map.get(str(primary_entity.get("entity_id", "")))
    return _extract_room_name(state)


def _get_existing_binding(
    db: Session,
    *,
    external_device_id: str,
    primary_entity_id: str,
) -> DeviceBinding | None:
    binding = db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_device_id == external_device_id,
        )
    )
    if binding is not None:
        return binding

    return db.scalar(
        select(DeviceBinding).where(
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_entity_id == primary_entity_id,
        )
    )


def _build_area_entity_counts(device_registry: list[dict], entity_registry: list[dict]) -> dict[str, int]:
    device_area_map: dict[str, str] = {}
    for device in device_registry:
        if not isinstance(device, dict):
            continue
        device_id = _normalize_optional_text(device.get("id"))
        area_id = _normalize_optional_text(device.get("area_id"))
        if device_id and area_id:
            device_area_map[device_id] = area_id

    counts: dict[str, int] = {}
    for entry in entity_registry:
        if not isinstance(entry, dict):
            continue
        entity_id = _normalize_optional_text(entry.get("entity_id"))
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in SUPPORTED_DEVICE_TYPES:
            continue
        area_id = _normalize_optional_text(entry.get("area_id"))
        if not area_id:
            device_id = _normalize_optional_text(entry.get("device_id"))
            area_id = device_area_map.get(device_id or "")
        if area_id:
            counts[area_id] = counts.get(area_id, 0) + 1
    return counts


def _load_existing_home_assistant_bindings(db: Session, household_id: str) -> set[str]:
    rows = db.execute(
        select(DeviceBinding.external_device_id)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.household_id == household_id,
            DeviceBinding.platform == "home_assistant",
            DeviceBinding.external_device_id.is_not(None),
        )
    ).all()
    return {value for (value,) in rows if isinstance(value, str) and value.strip()}


def _normalize_device_status(state_value: str) -> str:
    if state_value in {"unavailable", "unknown"}:
        return "offline"
    return "active"


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None


def _normalize_room_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _extract_room_name(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    attributes = state.get("attributes")
    if not isinstance(attributes, dict):
        return None

    for key in ("area_name", "room_name", "room", "roomName", "area"):
        value = attributes.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _load_room_cache(db: Session, household_id: str) -> dict[str, Room]:
    rooms = db.scalars(select(Room).where(Room.household_id == household_id)).all()
    return {_normalize_room_key(room.name): room for room in rooms}


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

    client = client or build_home_assistant_client_for_household(db, household_id)
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
