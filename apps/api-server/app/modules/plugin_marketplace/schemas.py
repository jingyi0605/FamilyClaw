from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.plugin.schemas import PluginConfigState


MarketplaceTrustedLevel = Literal["official", "third_party"]
MarketplaceSyncStatus = Literal["idle", "syncing", "success", "failed"]
MarketplaceEntrySyncStatus = Literal["ready", "invalid"]
MarketplaceInstallStatus = Literal[
    "not_installed",
    "queued",
    "resolving",
    "downloading",
    "validating",
    "installing",
    "installed",
    "install_failed",
    "uninstalled",
]
MarketplaceArtifactType = Literal["release_asset", "source_archive"]


def _normalize_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _normalize_text_list(values: list[str], *, field_name: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _normalize_text(value, field_name=field_name)
        if item in seen:
            raise ValueError(f"{field_name} 不能有重复值: {item}")
        seen.add(item)
        result.append(item)
    return result


def validate_github_repo_url(value: str) -> str:
    normalized = _normalize_text(value, field_name="repo_url")
    if not normalized.startswith("https://github.com/"):
        raise ValueError("repo_url 必须是 https://github.com/ 开头的 GitHub 仓库地址")
    segments = [segment for segment in normalized.removeprefix("https://github.com/").split("/") if segment]
    if len(segments) < 2:
        raise ValueError("repo_url 必须包含 owner 和 repo")
    return f"https://github.com/{segments[0]}/{segments[1]}"


class MarketplacePublisher(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    url: str | None = Field(default=None, max_length=255)

    @field_validator("name", "url")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="publisher")


class MarketplaceMaintainer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    url: str | None = Field(default=None, max_length=255)

    @field_validator("name", "url")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="maintainer")


class MarketplaceVersionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=50)
    git_ref: str = Field(min_length=1, max_length=255)
    artifact_type: MarketplaceArtifactType
    artifact_url: str = Field(min_length=1, max_length=1000)
    checksum: str | None = Field(default=None, max_length=255)
    published_at: str | None = None
    min_app_version: str | None = Field(default=None, max_length=50)

    @field_validator("version", "git_ref", "artifact_url", "checksum", "published_at", "min_app_version")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="version")


class MarketplaceEntryInstallSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_root: str | None = Field(default=None, max_length=255)
    requirements_path: str = Field(default="requirements.txt", max_length=255)
    readme_path: str = Field(default="README.md", max_length=255)

    @field_validator("package_root", "requirements_path", "readme_path")
    @classmethod
    def validate_optional_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="install")


class MarketplaceRepositoryMetricAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stargazers_count: bool = False
    forks_count: bool = False
    subscribers_count: bool = False
    open_issues_count: bool = False
    views_count: bool = False


class MarketplaceRepositoryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stargazers_count: int | None = Field(default=None, ge=0)
    forks_count: int | None = Field(default=None, ge=0)
    subscribers_count: int | None = Field(default=None, ge=0)
    open_issues_count: int | None = Field(default=None, ge=0)
    views_count: int | None = Field(default=None, ge=0)
    views_period_days: int | None = Field(default=None, ge=1)
    fetched_at: str
    availability: MarketplaceRepositoryMetricAvailability = Field(
        default_factory=MarketplaceRepositoryMetricAvailability
    )

    @field_validator("fetched_at")
    @classmethod
    def validate_fetched_at(cls, value: str) -> str:
        return _normalize_text(value, field_name="fetched_at")


class MarketplaceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    source_repo: str = Field(min_length=1, max_length=255)
    manifest_path: str = Field(default="manifest.json", min_length=1, max_length=255)
    readme_url: str = Field(min_length=1, max_length=1000)
    publisher: MarketplacePublisher
    categories: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"]
    permissions: list[str] = Field(default_factory=list)
    latest_version: str = Field(min_length=1, max_length=50)
    versions: list[MarketplaceVersionEntry] = Field(default_factory=list)
    install: MarketplaceEntryInstallSpec = Field(default_factory=MarketplaceEntryInstallSpec)
    repository_metrics: MarketplaceRepositoryMetrics | None = None
    maintainers: list[MarketplaceMaintainer] = Field(default_factory=list)

    @field_validator("plugin_id", "name", "summary", "manifest_path", "readme_url", "latest_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_text(value, field_name="entry")

    @field_validator("source_repo")
    @classmethod
    def validate_source_repo(cls, value: str) -> str:
        return validate_github_repo_url(value)

    @field_validator("categories", "permissions")
    @classmethod
    def validate_text_list(cls, value: list[str], info) -> list[str]:
        return _normalize_text_list(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_versions(self) -> "MarketplaceEntry":
        if not self.versions:
            raise ValueError("versions 至少要有一个可安装版本")
        version_map = {item.version: item for item in self.versions}
        if self.latest_version not in version_map:
            raise ValueError("latest_version 必须能在 versions 里找到")
        return self

    def resolve_version(self, version: str | None) -> MarketplaceVersionEntry:
        target_version = version or self.latest_version
        for item in self.versions:
            if item.version == target_version:
                return item
        raise ValueError(f"找不到版本 {target_version}")


class MarketplaceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=100)
    repo_url: str = Field(min_length=1, max_length=255)
    default_branch: str = Field(min_length=1, max_length=100)
    entry_root: str = Field(default="plugins", min_length=1, max_length=255)
    trusted_level: MarketplaceTrustedLevel

    @field_validator("market_id", "name", "owner", "default_branch", "entry_root")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_text(value, field_name="market")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        return validate_github_repo_url(value)


class MarketplaceSourceCreateRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=255)
    branch: str | None = Field(default=None, max_length=100)
    entry_root: str | None = Field(default=None, max_length=255)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        return validate_github_repo_url(value)

    @field_validator("branch", "entry_root")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="source")


class MarketplaceSourceRead(BaseModel):
    source_id: str
    market_id: str | None = None
    name: str
    repo_url: str
    branch: str
    entry_root: str
    trusted_level: MarketplaceTrustedLevel
    enabled: bool
    last_sync_status: MarketplaceSyncStatus | None = None
    last_sync_error: dict[str, Any] | None = None
    last_synced_at: str | None = None


class MarketplaceEntryErrorRead(BaseModel):
    plugin_id: str
    error_code: str
    detail: str


class MarketplaceSourceSyncResultRead(BaseModel):
    source: MarketplaceSourceRead
    total_entries: int = Field(ge=0)
    ready_entries: int = Field(ge=0)
    invalid_entries: int = Field(ge=0)
    errors: list[MarketplaceEntryErrorRead] = Field(default_factory=list)


class MarketplaceInstallStateRead(BaseModel):
    instance_id: str | None = None
    install_status: MarketplaceInstallStatus = "not_installed"
    enabled: bool = False
    config_status: PluginConfigState | None = None
    installed_version: str | None = None


class MarketplaceCatalogItemRead(BaseModel):
    source_id: str
    plugin_id: str
    name: str
    summary: str
    source_repo: str
    readme_url: str
    risk_level: Literal["low", "medium", "high"]
    latest_version: str
    trusted_level: MarketplaceTrustedLevel
    sync_status: MarketplaceEntrySyncStatus
    sync_error: dict[str, Any] | None = None
    categories: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    repository_metrics: MarketplaceRepositoryMetrics | None = None
    source_name: str
    install_state: MarketplaceInstallStateRead = Field(default_factory=MarketplaceInstallStateRead)


class MarketplaceCatalogListRead(BaseModel):
    items: list[MarketplaceCatalogItemRead] = Field(default_factory=list)


class MarketplaceEntryDetailRead(BaseModel):
    source: MarketplaceSourceRead
    plugin: MarketplaceCatalogItemRead
    manifest_path: str
    publisher: MarketplacePublisher
    versions: list[MarketplaceVersionEntry] = Field(default_factory=list)
    install: MarketplaceEntryInstallSpec
    maintainers: list[MarketplaceMaintainer] = Field(default_factory=list)
    raw_entry: dict[str, Any] = Field(default_factory=dict)


class MarketplaceInstallTaskCreateRequest(BaseModel):
    household_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1, max_length=64)
    version: str | None = Field(default=None, max_length=50)

    @field_validator("household_id", "source_id", "plugin_id", "version")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="install_task")


class MarketplaceInstallTaskRead(BaseModel):
    task_id: str
    household_id: str
    source_id: str
    plugin_id: str
    requested_version: str | None = None
    installed_version: str | None = None
    install_status: MarketplaceInstallStatus
    failure_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    source_repo: str | None = None
    market_repo: str | None = None
    artifact_url: str | None = None
    plugin_root: str | None = None
    manifest_path: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None


class MarketplaceInstanceRead(BaseModel):
    instance_id: str
    household_id: str
    source_id: str
    plugin_id: str
    installed_version: str
    install_status: MarketplaceInstallStatus
    enabled: bool
    config_status: PluginConfigState
    source_repo: str
    market_repo: str
    plugin_root: str
    manifest_path: str
    python_path: str
    working_dir: str | None = None
    installed_at: str | None = None
    created_at: str
    updated_at: str
