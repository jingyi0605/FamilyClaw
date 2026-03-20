from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.plugin.schemas import (
    PluginConfigState,
    PluginVersionCompatibilityStatus,
    PluginVersionGovernanceRead,
)
from app.modules.plugin.versioning import compare_plugin_versions


MarketplaceRepoProvider = Literal["github", "gitlab", "gitee", "gitea"]
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
PluginVersionOperationType = Literal["upgrade", "rollback"]
MarketplaceVersionOptionAction = Literal["install", "upgrade", "rollback", "current", "unavailable"]


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


def validate_http_url(value: str, *, field_name: str) -> str:
    normalized = _normalize_text(value, field_name=field_name)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} 必须是合法的 http/https 地址")
    path = parsed.path.rstrip("/")
    if not path:
        raise ValueError(f"{field_name} 必须包含路径")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def validate_repository_url(value: str, *, field_name: str) -> str:
    normalized = validate_http_url(value, field_name=field_name)
    parsed = urlparse(normalized)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        raise ValueError(f"{field_name} 必须包含仓库路径")
    return normalized


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
    artifact_url: str | None = Field(default=None, max_length=1000)
    checksum: str | None = Field(default=None, max_length=255)
    published_at: str | None = None
    min_app_version: str | None = Field(default=None, max_length=50)

    @field_validator("version", "git_ref", "artifact_url", "checksum", "published_at", "min_app_version")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="version")

    @model_validator(mode="after")
    def validate_artifact_fields(self) -> "MarketplaceVersionEntry":
        if self.artifact_type == "release_asset" and self.artifact_url is None:
            raise ValueError("release_asset 必须提供 artifact_url")
        if self.checksum is not None:
            normalized_checksum = self.checksum.lower()
            if normalized_checksum.startswith("sha256:"):
                normalized_checksum = normalized_checksum.removeprefix("sha256:")
            if len(normalized_checksum) != 64 or any(char not in "0123456789abcdef" for char in normalized_checksum):
                raise ValueError("checksum 目前只支持 sha256 十六进制摘要")
        return self


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
        return validate_repository_url(value, field_name="source_repo")

    @field_validator("categories", "permissions")
    @classmethod
    def validate_text_list(cls, value: list[str], info) -> list[str]:
        return _normalize_text_list(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_versions(self) -> "MarketplaceEntry":
        if not self.versions:
            raise ValueError("versions 至少要有一个可安装版本")
        version_map: dict[str, MarketplaceVersionEntry] = {}
        for item in self.versions:
            if item.version in version_map:
                raise ValueError(f"versions 里不能重复声明版本 {item.version}")
            version_map[item.version] = item
        if self.latest_version not in version_map:
            raise ValueError("latest_version 必须能在 versions 里找到")
        if len(self.versions) > 1:
            for item in self.versions:
                if not item.git_ref.startswith("refs/tags/"):
                    raise ValueError("多版本市场条目只能引用 tag，git_ref 必须写成 refs/tags/<tag>")
        highest_version = self.versions[0].version
        try:
            for item in self.versions[1:]:
                if compare_plugin_versions(item.version, highest_version) > 0:
                    highest_version = item.version
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if self.latest_version != highest_version:
            raise ValueError(f"latest_version 必须指向当前最高版本 {highest_version}")
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
    trusted_level: str | None = Field(default=None, exclude=True)

    @field_validator("market_id", "name", "owner", "default_branch", "entry_root")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_text(value, field_name="market")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        return validate_repository_url(value, field_name="repo_url")


class MarketplaceSourceCreateRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=255)
    branch: str | None = Field(default=None, max_length=100)
    entry_root: str | None = Field(default=None, max_length=255)
    repo_provider: MarketplaceRepoProvider | None = None
    api_base_url: str | None = Field(default=None, max_length=1000)
    mirror_repo_url: str | None = Field(default=None, max_length=255)
    mirror_repo_provider: MarketplaceRepoProvider | None = None
    mirror_api_base_url: str | None = Field(default=None, max_length=1000)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        return validate_repository_url(value, field_name="repo_url")

    @field_validator("api_base_url", "mirror_api_base_url")
    @classmethod
    def validate_optional_http_url(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field_name=info.field_name)

    @field_validator("mirror_repo_url")
    @classmethod
    def validate_optional_repo_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_repository_url(value, field_name="mirror_repo_url")

    @field_validator("branch", "entry_root")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_text(value, field_name="source")

    @model_validator(mode="after")
    def validate_mirror_fields(self) -> "MarketplaceSourceCreateRequest":
        if self.mirror_repo_url is None and (self.mirror_repo_provider is not None or self.mirror_api_base_url is not None):
            raise ValueError("只有提供 mirror_repo_url 时才能声明镜像源配置")
        return self


class MarketplaceSourceRead(BaseModel):
    source_id: str
    market_id: str | None = None
    name: str
    owner: str | None = None
    repo_url: str
    repo_provider: MarketplaceRepoProvider
    api_base_url: str | None = None
    mirror_repo_url: str | None = None
    mirror_repo_provider: MarketplaceRepoProvider | None = None
    mirror_api_base_url: str | None = None
    effective_repo_url: str
    branch: str
    entry_root: str
    is_system: bool
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
    is_system: bool
    sync_status: MarketplaceEntrySyncStatus
    sync_error: dict[str, Any] | None = None
    categories: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    repository_metrics: MarketplaceRepositoryMetrics | None = None
    source_name: str
    install_state: MarketplaceInstallStateRead = Field(default_factory=MarketplaceInstallStateRead)
    version_governance: PluginVersionGovernanceRead | None = None


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


class MarketplaceVersionOptionRead(BaseModel):
    version: str
    git_ref: str
    artifact_type: MarketplaceArtifactType
    artifact_url: str | None = None
    checksum: str | None = None
    published_at: str | None = None
    min_app_version: str | None = None
    is_latest: bool = False
    is_latest_compatible: bool = False
    is_installed: bool = False
    compatibility_status: PluginVersionCompatibilityStatus
    blocked_reason: str | None = None
    action: MarketplaceVersionOptionAction
    can_install: bool = False
    can_switch: bool = False


class MarketplaceVersionOptionsRead(BaseModel):
    source_id: str
    plugin_id: str
    installed_version: str | None = None
    latest_version: str
    latest_compatible_version: str | None = None
    items: list[MarketplaceVersionOptionRead] = Field(default_factory=list)


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


class PluginVersionOperationRequest(BaseModel):
    household_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1, max_length=64)
    target_version: str = Field(min_length=1, max_length=50)
    operation: PluginVersionOperationType

    @field_validator("household_id", "source_id", "plugin_id", "target_version")
    @classmethod
    def validate_operation_text(cls, value: str) -> str:
        return _normalize_text(value, field_name="version_operation")


class PluginVersionOperationResultRead(BaseModel):
    instance: MarketplaceInstanceRead
    governance: PluginVersionGovernanceRead
    previous_version: str
    target_version: str
    state_changed: bool
    state_change_reason: str | None = None


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
