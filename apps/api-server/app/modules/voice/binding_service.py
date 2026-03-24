from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.device.binding_capabilities import binding_supports_voice_terminal
from app.modules.device.models import Device, DeviceBinding
from app.modules.voiceprint.schemas import PendingVoiceprintEnrollmentRead
from app.modules.voiceprint.service import get_pending_voiceprint_enrollment_by_terminal


class VoiceTerminalBindingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    terminal_id: str
    room_id: str | None = None
    terminal_name: str
    voice_auto_takeover_enabled: bool = False
    voice_takeover_prefixes: list[str] = Field(default_factory=lambda: ["请"])
    pending_voiceprint_enrollment: PendingVoiceprintEnrollmentRead | None = None


def get_voice_terminal_binding(db: Session, *, fingerprint: str) -> VoiceTerminalBindingSnapshot | None:
    statement = (
        select(DeviceBinding, Device)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            DeviceBinding.external_entity_id == fingerprint,
        )
        .order_by(DeviceBinding.last_sync_at.desc().nullslast(), DeviceBinding.id.asc())
    )
    for binding, device in db.execute(statement).all():
        if not binding_supports_voice_terminal(db, device=device, binding=binding):
            continue
        return _build_voice_terminal_binding_snapshot(db, device=device)
    return None


def get_voice_terminal_binding_by_terminal_id(db: Session, *, terminal_id: str) -> VoiceTerminalBindingSnapshot | None:
    statement = (
        select(DeviceBinding, Device)
        .join(Device, Device.id == DeviceBinding.device_id)
        .where(
            Device.id == terminal_id,
        )
        .order_by(DeviceBinding.last_sync_at.desc().nullslast(), DeviceBinding.id.asc())
    )
    for binding, device in db.execute(statement).all():
        if not binding_supports_voice_terminal(db, device=device, binding=binding):
            continue
        return _build_voice_terminal_binding_snapshot(db, device=device)
    return None


def _build_voice_terminal_binding_snapshot(
    db: Session,
    *,
    device: Device,
) -> VoiceTerminalBindingSnapshot:
    pending_voiceprint_enrollment = get_pending_voiceprint_enrollment_by_terminal(
        db,
        household_id=device.household_id,
        terminal_id=device.id,
    )
    return VoiceTerminalBindingSnapshot(
        household_id=device.household_id,
        terminal_id=device.id,
        room_id=device.room_id,
        terminal_name=device.name,
        voice_auto_takeover_enabled=bool(device.voice_auto_takeover_enabled),
        voice_takeover_prefixes=device.voice_takeover_prefixes,
        pending_voiceprint_enrollment=pending_voiceprint_enrollment,
    )
