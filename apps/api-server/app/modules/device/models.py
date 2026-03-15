from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import dump_json, load_json, utc_now_iso


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    controllable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_auto_takeover_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voiceprint_identity_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_takeover_prefixes_json: Mapped[str] = mapped_column("voice_takeover_prefixes", Text, nullable=False, default='["请"]')
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=utc_now_iso,
        onupdate=utc_now_iso,
    )

    @property
    def voice_takeover_prefixes(self) -> list[str]:
        loaded = load_json(self.voice_takeover_prefixes_json)
        if not isinstance(loaded, list):
            return ["请"]
        normalized: list[str] = []
        for item in loaded:
            text = str(item).strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
        return normalized or ["请"]

    @voice_takeover_prefixes.setter
    def voice_takeover_prefixes(self, value: list[str] | tuple[str, ...]) -> None:
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
        self.voice_takeover_prefixes_json = dump_json(normalized or ["请"]) or '["请"]'


class DeviceBinding(Base):
    __tablename__ = "device_bindings"
    __table_args__ = (
        UniqueConstraint("platform", "external_entity_id", name="uq_device_bindings_platform_entity"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    device_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plugin_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    binding_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[str | None] = mapped_column(Text, nullable=True)

