from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.device.models import Device, DeviceBinding
from app.modules.voiceprint.schemas import PendingVoiceprintEnrollmentRead
from app.modules.voiceprint.service import get_pending_voiceprint_enrollment_by_terminal

OPEN_XIAOAI_PLUGIN_ID = "open-xiaoai-speaker"
OPEN_XIAOAI_BINDING_PLATFORM = "open_xiaoai"


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
            DeviceBinding.platform == OPEN_XIAOAI_BINDING_PLATFORM,
            DeviceBinding.external_entity_id == fingerprint,
            DeviceBinding.plugin_id == OPEN_XIAOAI_PLUGIN_ID,
        )
        .order_by(DeviceBinding.last_sync_at.desc().nullslast(), DeviceBinding.id.asc())
    )
    row = db.execute(statement).first()
    if row is None:
        return None
    _binding, device = row
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
