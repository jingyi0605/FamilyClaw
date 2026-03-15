from __future__ import annotations

from threading import Lock
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.room.models import Room

VoiceDiscoveryConnectionStatus = Literal["online", "offline", "unknown"]
OPEN_XIAOAI_BINDING_PLATFORM = "open_xiaoai"


class VoiceTerminalBindingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    terminal_id: str
    room_id: str | None = None
    terminal_name: str
    voice_auto_takeover_enabled: bool = False
    voice_takeover_prefixes: list[str] = Field(default_factory=lambda: ["请"])


class VoiceTerminalDiscoveryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_type: str = "open_xiaoai"
    fingerprint: str = Field(min_length=1)
    model: str = Field(min_length=1)
    sn: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    remote_addr: str | None = None
    discovered_at: str = Field(default_factory=utc_now_iso)
    last_seen_at: str = Field(default_factory=utc_now_iso)
    connection_status: VoiceDiscoveryConnectionStatus = "unknown"
    claimed_binding: VoiceTerminalBindingSnapshot | None = None


class VoiceTerminalDiscoveryRegistry:
    def __init__(self) -> None:
        self._records: dict[str, VoiceTerminalDiscoveryRecord] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def upsert(
        self,
        *,
        adapter_type: str,
        fingerprint: str,
        model: str,
        sn: str,
        runtime_version: str,
        capabilities: list[str],
        remote_addr: str | None,
        discovered_at: str | None,
        last_seen_at: str | None,
        connection_status: VoiceDiscoveryConnectionStatus,
        claimed_binding: VoiceTerminalBindingSnapshot | None,
    ) -> VoiceTerminalDiscoveryRecord:
        with self._lock:
            current = self._records.get(fingerprint)
            normalized_discovered_at = discovered_at or (current.discovered_at if current else utc_now_iso())
            normalized_last_seen_at = last_seen_at or utc_now_iso()
            record = VoiceTerminalDiscoveryRecord(
                adapter_type=adapter_type,
                fingerprint=fingerprint,
                model=model,
                sn=sn,
                runtime_version=runtime_version,
                capabilities=list(dict.fromkeys(capabilities)),
                remote_addr=remote_addr if remote_addr is not None else current.remote_addr if current else None,
                discovered_at=normalized_discovered_at,
                last_seen_at=normalized_last_seen_at,
                connection_status=connection_status,
                claimed_binding=claimed_binding,
            )
            self._records[fingerprint] = record
            return record

    def get(self, fingerprint: str) -> VoiceTerminalDiscoveryRecord | None:
        return self._records.get(fingerprint)

    def attach_binding(self, *, fingerprint: str, binding: VoiceTerminalBindingSnapshot | None) -> VoiceTerminalDiscoveryRecord | None:
        with self._lock:
            current = self._records.get(fingerprint)
            if current is None:
                return None
            updated = current.model_copy(update={"claimed_binding": binding, "last_seen_at": utc_now_iso()})
            self._records[fingerprint] = updated
            return updated

    def list_pending(self) -> list[VoiceTerminalDiscoveryRecord]:
        records = list(self._records.values())
        pending = [item for item in records if item.claimed_binding is None]
        pending.sort(key=lambda item: (item.last_seen_at, item.discovered_at, item.fingerprint), reverse=True)
        return pending


def build_minimal_discovery(
    *,
    fingerprint: str,
    model: str,
    sn: str,
    connection_status: VoiceDiscoveryConnectionStatus = "unknown",
) -> VoiceTerminalDiscoveryRecord | None:
    adapter_type, parsed_model, parsed_sn = _parse_open_xiaoai_fingerprint(fingerprint)
    if adapter_type is None or parsed_model is None or parsed_sn is None:
        return None
    if parsed_model != model.strip() or parsed_sn != sn.strip():
        return None

    now = utc_now_iso()
    return VoiceTerminalDiscoveryRecord(
        adapter_type=adapter_type,
        fingerprint=fingerprint,
        model=model.strip(),
        sn=sn.strip(),
        runtime_version="unknown",
        capabilities=[],
        remote_addr=None,
        discovered_at=now,
        last_seen_at=now,
        connection_status=connection_status,
        claimed_binding=None,
    )


def get_voice_terminal_binding(db: Session, *, fingerprint: str) -> VoiceTerminalBindingSnapshot | None:
    statement = (
        select(DeviceBinding, Device)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            DeviceBinding.platform == OPEN_XIAOAI_BINDING_PLATFORM,
            DeviceBinding.external_entity_id == fingerprint,
        )
    )
    row = db.execute(statement).first()
    if row is None:
        return None
    binding, device = row
    return VoiceTerminalBindingSnapshot(
        household_id=device.household_id,
        terminal_id=device.id,
        room_id=device.room_id,
        terminal_name=device.name,
        voice_auto_takeover_enabled=bool(device.voice_auto_takeover_enabled),
        voice_takeover_prefixes=device.voice_takeover_prefixes,
    )


def claim_voice_terminal_discovery(
    db: Session,
    *,
    discovery: VoiceTerminalDiscoveryRecord,
    household_id: str,
    room_id: str,
    terminal_name: str,
) -> VoiceTerminalBindingSnapshot:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="room not found")
    if room.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room must belong to the same household",
        )

    statement = (
        select(DeviceBinding, Device)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            DeviceBinding.platform == OPEN_XIAOAI_BINDING_PLATFORM,
            DeviceBinding.external_entity_id == discovery.fingerprint,
        )
    )
    row = db.execute(statement).first()

    if row is not None:
        binding, device = row
        if device.household_id != household_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="voice terminal already claimed by another household",
            )
        device.name = terminal_name
        device.room_id = room_id
        device.status = _map_device_status(discovery.connection_status)
        binding.external_device_id = discovery.sn
        binding.capabilities = dump_json(discovery.capabilities)
        binding.last_sync_at = utc_now_iso()
        db.add(device)
        db.add(binding)
        return VoiceTerminalBindingSnapshot(
            household_id=device.household_id,
            terminal_id=device.id,
            room_id=device.room_id,
            terminal_name=device.name,
            voice_auto_takeover_enabled=bool(device.voice_auto_takeover_enabled),
            voice_takeover_prefixes=device.voice_takeover_prefixes,
        )

    device = Device(
        id=new_uuid(),
        household_id=household_id,
        room_id=room_id,
        name=terminal_name,
        device_type="speaker",
        vendor="xiaomi",
        status=_map_device_status(discovery.connection_status),
        controllable=0,
        voice_auto_takeover_enabled=0,
    )
    device.voice_takeover_prefixes = ["请"]
    db.add(device)
    db.flush()

    binding = DeviceBinding(
        id=new_uuid(),
        device_id=device.id,
        platform=OPEN_XIAOAI_BINDING_PLATFORM,
        external_entity_id=discovery.fingerprint,
        external_device_id=discovery.sn,
        capabilities=dump_json(discovery.capabilities),
        last_sync_at=utc_now_iso(),
    )
    db.add(binding)
    return VoiceTerminalBindingSnapshot(
        household_id=device.household_id,
        terminal_id=device.id,
        room_id=device.room_id,
        terminal_name=device.name,
        voice_auto_takeover_enabled=bool(device.voice_auto_takeover_enabled),
        voice_takeover_prefixes=device.voice_takeover_prefixes,
    )


def read_binding_capabilities(db: Session, *, fingerprint: str) -> list[str]:
    statement = select(DeviceBinding.capabilities).where(
        DeviceBinding.platform == OPEN_XIAOAI_BINDING_PLATFORM,
        DeviceBinding.external_entity_id == fingerprint,
    )
    raw_value = db.scalar(statement)
    loaded = load_json(raw_value)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _map_device_status(connection_status: VoiceDiscoveryConnectionStatus) -> str:
    if connection_status == "online":
        return "active"
    return "offline"


def _parse_open_xiaoai_fingerprint(fingerprint: str) -> tuple[str | None, str | None, str | None]:
    parts = fingerprint.split(":", 2)
    if len(parts) != 3:
        return None, None, None

    adapter_type, model, sn = (part.strip() for part in parts)
    if adapter_type != OPEN_XIAOAI_BINDING_PLATFORM or not model or not sn:
        return None, None, None
    return adapter_type, model, sn


voice_terminal_discovery_registry = VoiceTerminalDiscoveryRegistry()
