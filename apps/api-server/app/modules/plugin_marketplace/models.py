from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class PluginMarketplaceSource(Base):
    __tablename__ = "plugin_marketplace_sources"

    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    market_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    repo_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="github")
    api_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mirror_repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mirror_repo_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mirror_api_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    entry_root: Mapped[str] = mapped_column(String(255), nullable=False)
    trusted_level: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_sync_error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class PluginMarketplaceEntrySnapshot(Base):
    __tablename__ = "plugin_marketplace_entry_snapshots"
    __table_args__ = (
        UniqueConstraint("source_id", "plugin_id", name="uq_plugin_marketplace_entry_snapshots_source_plugin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_repo: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_path: Mapped[str] = mapped_column(Text, nullable=False)
    readme_url: Mapped[str] = mapped_column(Text, nullable=False)
    publisher_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    permissions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    maintainers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    versions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    install_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    repository_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_entry_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    latest_version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sync_error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class PluginMarketplaceInstallTask(Base):
    __tablename__ = "plugin_marketplace_install_tasks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    installed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    install_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    failure_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    plugin_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class PluginMarketplaceInstance(Base):
    __tablename__ = "plugin_marketplace_instances"
    __table_args__ = (
        UniqueConstraint("household_id", "plugin_id", name="uq_plugin_marketplace_instances_household_plugin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    installed_version: Mapped[str] = mapped_column(String(50), nullable=False)
    install_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unconfigured")
    source_repo: Mapped[str] = mapped_column(Text, nullable=False)
    market_repo: Mapped[str] = mapped_column(Text, nullable=False)
    plugin_root: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_path: Mapped[str] = mapped_column(Text, nullable=False)
    python_path: Mapped[str] = mapped_column(Text, nullable=False)
    working_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    installed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
