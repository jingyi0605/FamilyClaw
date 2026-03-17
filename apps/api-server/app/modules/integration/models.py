from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class IntegrationInstance(Base):
    __tablename__ = "integration_instances"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    last_synced_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class IntegrationDiscovery(Base):
    __tablename__ = "integration_discoveries"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id",
            "discovery_key",
            name="uq_integration_discoveries_plugin_key",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    integration_instance_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("integration_instances.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    gateway_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    discovery_key: Mapped[str] = mapped_column(String(255), nullable=False)
    discovery_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="device")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adapter_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capability_tags_json: Mapped[str] = mapped_column("capability_tags", Text, nullable=False, default="[]")
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False, default="{}")
    payload_json: Mapped[str] = mapped_column("payload", Text, nullable=False, default="{}")
    claimed_device_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    discovered_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    last_seen_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
