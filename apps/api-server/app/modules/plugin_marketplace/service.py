from __future__ import annotations

import json
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.plugin.models import PluginMount
from app.modules.plugin.schemas import (
    PluginConfigState,
    PluginMountCreate,
    PluginStateUpdateRequest,
    PluginVersionGovernanceRead,
)
from app.modules.plugin.versioning import (
    MarketplaceVersionFact,
    resolve_host_compatibility,
    resolve_marketplace_version_governance,
)
from app.modules.plugin.service import (
    PluginManifestValidationError,
    PluginServiceError,
    load_plugin_manifest,
    register_plugin_mount,
)
from app.modules.plugin_marketplace.github_client import (
    GitHubMarketplaceClient,
    GitHubMarketplaceClientError,
    build_github_marketplace_client,
)
from app.modules.plugin_marketplace.models import (
    PluginMarketplaceEntrySnapshot,
    PluginMarketplaceInstallTask,
    PluginMarketplaceInstance,
    PluginMarketplaceSource,
)
from app.modules.plugin_marketplace import repository
from app.modules.plugin_marketplace.schemas import (
    MarketplaceCatalogItemRead,
    MarketplaceCatalogListRead,
    MarketplaceEntry,
    MarketplaceEntryDetailRead,
    MarketplaceEntryErrorRead,
    MarketplaceEntryInstallSpec,
    MarketplaceEntrySyncStatus,
    MarketplaceInstallStateRead,
    MarketplaceInstallTaskCreateRequest,
    MarketplaceInstallTaskRead,
    MarketplaceInstanceRead,
    MarketplaceManifest,
    MarketplaceRepositoryMetricAvailability,
    MarketplaceRepositoryMetrics,
    PluginVersionOperationRequest,
    PluginVersionOperationResultRead,
    PluginVersionOperationType,
    MarketplaceSourceCreateRequest,
    MarketplaceSourceRead,
    MarketplaceSourceSyncResultRead,
    MarketplaceSyncStatus,
)


BUILTIN_MARKETPLACE_SOURCE_ID = "builtin-official-marketplace"
MARKETPLACE_ENTRY_FILE_NAME = "entry.json"
MARKETPLACE_MANIFEST_FILE_NAME = "market.json"
MARKETPLACE_INVALID_SUMMARY = "插件市场条目校验失败"
PLUGIN_MARKETPLACE_UNCONFIGURED_ERROR_CODE = "plugin_marketplace_not_configured"


class PluginMarketplaceServiceError(ValueError):
    def __init__(
        self,
        detail: str,
        *,
        error_code: str,
        field: str | None = None,
        field_errors: dict[str, str] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.field = field
        self.field_errors = field_errors or {}
        self.status_code = status_code

    def to_detail(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "detail": self.detail,
            "error_code": self.error_code,
            "timestamp": utc_now_iso(),
        }
        if self.field is not None:
            payload["field"] = self.field
        if self.field_errors:
            payload["field_errors"] = self.field_errors
        return payload


def _get_client(client: GitHubMarketplaceClient | None = None) -> GitHubMarketplaceClient:
    return client or build_github_marketplace_client()


def _normalize_relative_path(value: str, *, field_name: str) -> str:
    normalized = value.strip().strip("/")
    if not normalized:
        raise PluginMarketplaceServiceError(
            f"{field_name} 不能为空。",
            error_code="market_repo_structure_invalid",
            field=field_name,
        )
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise PluginMarketplaceServiceError(
            f"{field_name} 不能包含越界路径。",
            error_code="market_repo_structure_invalid",
            field=field_name,
        )
    return str(path)


def _resolve_child_path(base: Path, relative_path: str, *, field_name: str) -> Path:
    normalized = _normalize_relative_path(relative_path, field_name=field_name)
    candidate = (base / normalized).resolve()
    base_resolved = base.resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise PluginMarketplaceServiceError(
            f"{field_name} 超出了插件根目录。",
            error_code="install_target_invalid",
            field=field_name,
        )
    return candidate


def _load_json_or_default(payload: str | None, *, fallback: Any) -> Any:
    loaded = load_json(payload)
    return fallback if loaded is None else loaded


def _to_source_read(row: PluginMarketplaceSource) -> MarketplaceSourceRead:
    raw_error = _load_json_or_default(row.last_sync_error_json, fallback=None)
    return MarketplaceSourceRead(
        source_id=row.source_id,
        market_id=row.market_id,
        name=row.name,
        repo_url=row.repo_url,
        branch=row.branch,
        entry_root=row.entry_root,
        trusted_level=row.trusted_level,
        enabled=row.enabled,
        last_sync_status=row.last_sync_status,
        last_sync_error=raw_error if isinstance(raw_error, dict) else None,
        last_synced_at=row.last_synced_at,
    )


def _to_install_task_read(row: PluginMarketplaceInstallTask) -> MarketplaceInstallTaskRead:
    return MarketplaceInstallTaskRead(
        task_id=row.id,
        household_id=row.household_id,
        source_id=row.source_id,
        plugin_id=row.plugin_id,
        requested_version=row.requested_version,
        installed_version=row.installed_version,
        install_status=row.install_status,
        failure_stage=row.failure_stage,
        error_code=row.error_code,
        error_message=row.error_message,
        source_repo=row.source_repo,
        market_repo=row.market_repo,
        artifact_url=row.artifact_url,
        plugin_root=row.plugin_root,
        manifest_path=row.manifest_path,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _to_instance_read(row: PluginMarketplaceInstance) -> MarketplaceInstanceRead:
    return MarketplaceInstanceRead(
        instance_id=row.id,
        household_id=row.household_id,
        source_id=row.source_id,
        plugin_id=row.plugin_id,
        installed_version=row.installed_version,
        install_status=row.install_status,
        enabled=row.enabled,
        config_status=row.config_status,
        source_repo=row.source_repo,
        market_repo=row.market_repo,
        plugin_root=row.plugin_root,
        manifest_path=row.manifest_path,
        python_path=row.python_path,
        working_dir=row.working_dir,
        installed_at=row.installed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _load_marketplace_entry_from_snapshot(snapshot: PluginMarketplaceEntrySnapshot) -> MarketplaceEntry:
    raw_entry = _load_json_or_default(snapshot.raw_entry_json, fallback={})
    if not isinstance(raw_entry, dict):
        raise PluginMarketplaceServiceError(
            "市场条目原始数据损坏，不能继续解析。",
            error_code="marketplace_entry_invalid",
            status_code=409,
        )
    return MarketplaceEntry.model_validate(raw_entry)


def _build_marketplace_version_facts(entry: MarketplaceEntry) -> list[MarketplaceVersionFact]:
    return [
        MarketplaceVersionFact(version=item.version, min_app_version=item.min_app_version)
        for item in entry.versions
    ]


def _load_declared_version_from_manifest(manifest_path: str | None) -> str | None:
    if manifest_path is None:
        return None
    try:
        manifest = load_plugin_manifest(manifest_path)
    except (PluginManifestValidationError, FileNotFoundError, OSError):
        return None
    return manifest.version


def _resolve_marketplace_version_governance_from_rows(
    *,
    snapshot: PluginMarketplaceEntrySnapshot,
    instance: PluginMarketplaceInstance | None,
    declared_version: str | None = None,
) -> PluginVersionGovernanceRead:
    entry = _load_marketplace_entry_from_snapshot(snapshot)
    resolved_declared_version = declared_version
    if resolved_declared_version is None and instance is not None:
        resolved_declared_version = _load_declared_version_from_manifest(instance.manifest_path)
    return resolve_marketplace_version_governance(
        host_version=settings.app_version,
        declared_version=resolved_declared_version,
        installed_version=instance.installed_version if instance is not None else None,
        latest_version=entry.latest_version,
        versions=_build_marketplace_version_facts(entry),
    )


def resolve_marketplace_instance_version_governance(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    declared_version: str | None = None,
) -> PluginVersionGovernanceRead:
    instance = repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)
    if instance is None:
        raise PluginMarketplaceServiceError(
            "插件市场实例不存在，不能计算版本治理状态。",
            error_code="marketplace_instance_not_found",
            field="plugin_id",
            status_code=404,
        )
    snapshot = _require_snapshot(db, source_id=instance.source_id, plugin_id=plugin_id)
    return _resolve_marketplace_version_governance_from_rows(
        snapshot=snapshot,
        instance=instance,
        declared_version=declared_version,
    )


def get_marketplace_version_governance(
    db: Session,
    *,
    source_id: str,
    plugin_id: str,
    household_id: str | None = None,
) -> PluginVersionGovernanceRead:
    snapshot = _require_snapshot(db, source_id=source_id, plugin_id=plugin_id)
    if snapshot.sync_status != "ready":
        raise PluginMarketplaceServiceError(
            "这个插件市场条目当前不可用，不能计算版本治理状态。",
            error_code="marketplace_entry_invalid",
            status_code=409,
        )
    instance = None
    if household_id is not None:
        instance = repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)
        if instance is not None and instance.source_id != source_id:
            raise PluginMarketplaceServiceError(
                "当前家庭安装的插件来源和市场来源不一致。",
                error_code="plugin_source_mismatch",
                field="source_id",
                status_code=409,
            )
    return _resolve_marketplace_version_governance_from_rows(snapshot=snapshot, instance=instance)


def _build_repository_metrics(
    *,
    repo_url: str,
    client: GitHubMarketplaceClient,
) -> MarketplaceRepositoryMetrics:
    availability = MarketplaceRepositoryMetricAvailability()
    fetched_at = utc_now_iso()
    metadata = client.get_repository_metadata(repo_url=repo_url) or {}
    views = client.get_repository_views(repo_url=repo_url) or {}

    stargazers_count = metadata.get("stargazers_count") if isinstance(metadata, dict) else None
    forks_count = metadata.get("forks_count") if isinstance(metadata, dict) else None
    subscribers_count = metadata.get("subscribers_count") if isinstance(metadata, dict) else None
    open_issues_count = metadata.get("open_issues_count") if isinstance(metadata, dict) else None

    availability.stargazers_count = isinstance(stargazers_count, int)
    availability.forks_count = isinstance(forks_count, int)
    availability.subscribers_count = isinstance(subscribers_count, int)
    availability.open_issues_count = isinstance(open_issues_count, int)

    views_count = views.get("count") if isinstance(views, dict) else None
    availability.views_count = isinstance(views_count, int)

    return MarketplaceRepositoryMetrics(
        stargazers_count=stargazers_count if isinstance(stargazers_count, int) else None,
        forks_count=forks_count if isinstance(forks_count, int) else None,
        subscribers_count=subscribers_count if isinstance(subscribers_count, int) else None,
        open_issues_count=open_issues_count if isinstance(open_issues_count, int) else None,
        views_count=views_count if isinstance(views_count, int) else None,
        views_period_days=14 if availability.views_count else None,
        fetched_at=fetched_at,
        availability=availability,
    )


def _build_repository_metrics_or_none(
    *,
    repo_url: str,
    client: GitHubMarketplaceClient,
) -> MarketplaceRepositoryMetrics | None:
    try:
        return _build_repository_metrics(repo_url=repo_url, client=client)
    except GitHubMarketplaceClientError:
        return MarketplaceRepositoryMetrics(
            fetched_at=utc_now_iso(),
            availability=MarketplaceRepositoryMetricAvailability(),
        )


def _build_snapshot_row(
    *,
    source: PluginMarketplaceSource,
    plugin_id: str,
    entry: MarketplaceEntry | None,
    raw_entry: dict[str, Any],
    sync_status: MarketplaceEntrySyncStatus,
    sync_error: dict[str, Any] | None,
    synced_at: str,
) -> PluginMarketplaceEntrySnapshot:
    if entry is None:
        return PluginMarketplaceEntrySnapshot(
            id=new_uuid(),
            source_id=source.source_id,
            plugin_id=plugin_id,
            name=plugin_id,
            summary=MARKETPLACE_INVALID_SUMMARY,
            source_repo=source.repo_url,
            manifest_path="manifest.json",
            readme_url=source.repo_url,
            publisher_json="{}",
            categories_json="[]",
            permissions_json="[]",
            maintainers_json="[]",
            versions_json="[]",
            install_json=dump_json(MarketplaceEntryInstallSpec().model_dump(mode="json")) or "{}",
            repository_metrics_json=None,
            raw_entry_json=dump_json(raw_entry) or "{}",
            risk_level="high",
            latest_version="invalid",
            manifest_digest=None,
            sync_status=sync_status,
            sync_error_json=dump_json(sync_error) if sync_error is not None else None,
            synced_at=synced_at,
        )

    return PluginMarketplaceEntrySnapshot(
        id=new_uuid(),
        source_id=source.source_id,
        plugin_id=entry.plugin_id,
        name=entry.name,
        summary=entry.summary,
        source_repo=entry.source_repo,
        manifest_path=entry.manifest_path,
        readme_url=entry.readme_url,
        publisher_json=dump_json(entry.publisher.model_dump(mode="json")) or "{}",
        categories_json=dump_json(entry.categories) or "[]",
        permissions_json=dump_json(entry.permissions) or "[]",
        maintainers_json=dump_json([item.model_dump(mode="json") for item in entry.maintainers]) or "[]",
        versions_json=dump_json([item.model_dump(mode="json") for item in entry.versions]) or "[]",
        install_json=dump_json(entry.install.model_dump(mode="json")) or "{}",
        repository_metrics_json=(
            dump_json(entry.repository_metrics.model_dump(mode="json"))
            if entry.repository_metrics is not None
            else None
        ),
        raw_entry_json=dump_json(raw_entry) or "{}",
        risk_level=entry.risk_level,
        latest_version=entry.latest_version,
        manifest_digest=None,
        sync_status=sync_status,
        sync_error_json=dump_json(sync_error) if sync_error is not None else None,
        synced_at=synced_at,
    )


def _to_catalog_item(
    *,
    source: PluginMarketplaceSource,
    snapshot: PluginMarketplaceEntrySnapshot,
    install_state: MarketplaceInstallStateRead,
    version_governance: PluginVersionGovernanceRead | None = None,
) -> MarketplaceCatalogItemRead:
    categories = _load_json_or_default(snapshot.categories_json, fallback=[])
    permissions = _load_json_or_default(snapshot.permissions_json, fallback=[])
    metrics = _load_json_or_default(snapshot.repository_metrics_json, fallback=None)
    sync_error = _load_json_or_default(snapshot.sync_error_json, fallback=None)
    return MarketplaceCatalogItemRead(
        source_id=source.source_id,
        plugin_id=snapshot.plugin_id,
        name=snapshot.name,
        summary=snapshot.summary,
        source_repo=snapshot.source_repo,
        readme_url=snapshot.readme_url,
        risk_level=snapshot.risk_level,
        latest_version=snapshot.latest_version,
        trusted_level=source.trusted_level,
        sync_status=snapshot.sync_status,
        sync_error=sync_error if isinstance(sync_error, dict) else None,
        categories=categories if isinstance(categories, list) else [],
        permissions=permissions if isinstance(permissions, list) else [],
        repository_metrics=MarketplaceRepositoryMetrics.model_validate(metrics) if isinstance(metrics, dict) else None,
        source_name=source.name,
        install_state=install_state,
        version_governance=version_governance,
    )


def _resolve_install_state(db: Session, *, household_id: str | None, plugin_id: str) -> MarketplaceInstallStateRead:
    if household_id is None:
        return MarketplaceInstallStateRead()
    instance = repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)
    if instance is not None:
        return MarketplaceInstallStateRead(
            instance_id=instance.id,
            install_status=instance.install_status,
            enabled=instance.enabled,
            config_status=instance.config_status,
            installed_version=instance.installed_version,
        )
    latest_task = next(
        iter(repository.list_marketplace_install_tasks(db, household_id=household_id, plugin_id=plugin_id)),
        None,
    )
    if latest_task is None:
        return MarketplaceInstallStateRead()
    return MarketplaceInstallStateRead(
        install_status=latest_task.install_status,
        enabled=False,
        config_status=None,
        installed_version=latest_task.installed_version,
    )


def _require_source(db: Session, *, source_id: str) -> PluginMarketplaceSource:
    source = repository.get_marketplace_source(db, source_id)
    if source is None:
        raise PluginMarketplaceServiceError(
            "插件市场源不存在。",
            error_code="marketplace_source_not_found",
            field="source_id",
            status_code=404,
        )
    return source


def _require_snapshot(
    db: Session,
    *,
    source_id: str,
    plugin_id: str,
) -> PluginMarketplaceEntrySnapshot:
    snapshot = repository.get_marketplace_entry_snapshot(db, source_id=source_id, plugin_id=plugin_id)
    if snapshot is None:
        raise PluginMarketplaceServiceError(
            "插件市场条目不存在。",
            error_code="marketplace_entry_not_found",
            field="plugin_id",
            status_code=404,
        )
    return snapshot


def _load_marketplace_manifest(
    *,
    client: GitHubMarketplaceClient,
    repo_url: str,
    branch: str,
) -> MarketplaceManifest:
    try:
        payload = client.get_file_json(repo_url=repo_url, path=MARKETPLACE_MANIFEST_FILE_NAME, ref=branch)
        return MarketplaceManifest.model_validate(payload)
    except GitHubMarketplaceClientError as exc:
        raise PluginMarketplaceServiceError(
            exc.detail,
            error_code=exc.error_code,
            status_code=exc.status_code,
        ) from exc
    except ValueError as exc:
        raise PluginMarketplaceServiceError(
            f"市场仓库 {MARKETPLACE_MANIFEST_FILE_NAME} 不合法：{exc}",
            error_code="market_repo_structure_invalid",
            status_code=400,
        ) from exc


def ensure_builtin_marketplace_source(
    db: Session,
    *,
    client: GitHubMarketplaceClient | None = None,
) -> PluginMarketplaceSource:
    existing = repository.get_marketplace_source(db, BUILTIN_MARKETPLACE_SOURCE_ID)
    if existing is not None:
        return existing

    branch = settings.plugin_marketplace_official_branch.strip() or "main"
    entry_root = settings.plugin_marketplace_official_entry_root.strip() or "plugins"
    now = utc_now_iso()
    row = PluginMarketplaceSource(
        source_id=BUILTIN_MARKETPLACE_SOURCE_ID,
        market_id=None,
        name="官方插件市场",
        repo_url=settings.plugin_marketplace_official_repo_url.strip(),
        branch=branch,
        entry_root=entry_root,
        trusted_level="official",
        enabled=True,
        last_sync_status="idle",
        last_sync_error_json=None,
        last_synced_at=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_marketplace_source(db, row)

    marketplace_client = _get_client(client)
    try:
        manifest = _load_marketplace_manifest(client=marketplace_client, repo_url=row.repo_url, branch=row.branch)
    except PluginMarketplaceServiceError:
        db.flush()
        return row

    row.market_id = manifest.market_id
    row.name = manifest.name
    row.entry_root = manifest.entry_root
    row.updated_at = utc_now_iso()
    db.flush()
    return row


def list_marketplace_sources(
    db: Session,
    *,
    enabled_only: bool = False,
    client: GitHubMarketplaceClient | None = None,
) -> list[MarketplaceSourceRead]:
    ensure_builtin_marketplace_source(db, client=client)
    return [_to_source_read(row) for row in repository.list_marketplace_sources(db, enabled_only=enabled_only)]


def add_marketplace_source(
    db: Session,
    *,
    payload: MarketplaceSourceCreateRequest,
    client: GitHubMarketplaceClient | None = None,
) -> MarketplaceSourceRead:
    marketplace_client = _get_client(client)
    try:
        metadata = marketplace_client.get_repository_metadata(repo_url=payload.repo_url)
    except GitHubMarketplaceClientError as exc:
        raise PluginMarketplaceServiceError(
            exc.detail,
            error_code=exc.error_code,
            field="repo_url",
            status_code=exc.status_code,
        ) from exc

    branch = (payload.branch or (metadata or {}).get("default_branch") or "main").strip()
    manifest = _load_marketplace_manifest(client=marketplace_client, repo_url=payload.repo_url, branch=branch)
    entry_root = payload.entry_root or manifest.entry_root

    existing = repository.get_marketplace_source_by_repo(
        db,
        repo_url=payload.repo_url,
        branch=branch,
        entry_root=entry_root,
    )
    if existing is not None:
        raise PluginMarketplaceServiceError(
            "这个插件市场源已经添加过了。",
            error_code="marketplace_source_conflict",
            field="repo_url",
            status_code=409,
        )

    now = utc_now_iso()
    row = PluginMarketplaceSource(
        source_id=new_uuid(),
        market_id=manifest.market_id,
        name=manifest.name,
        repo_url=payload.repo_url,
        branch=branch,
        entry_root=entry_root,
        trusted_level="third_party",
        enabled=True,
        last_sync_status="idle",
        last_sync_error_json=None,
        last_synced_at=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_marketplace_source(db, row)
    db.flush()
    return _to_source_read(row)


def sync_marketplace_source(
    db: Session,
    *,
    source_id: str,
    client: GitHubMarketplaceClient | None = None,
) -> MarketplaceSourceSyncResultRead:
    source = _require_source(db, source_id=source_id)
    marketplace_client = _get_client(client)
    source.last_sync_status = "syncing"
    source.last_sync_error_json = None
    source.updated_at = utc_now_iso()
    db.flush()

    try:
        manifest = _load_marketplace_manifest(client=marketplace_client, repo_url=source.repo_url, branch=source.branch)
        if manifest.repo_url != source.repo_url:
            raise PluginMarketplaceServiceError(
                "市场仓库 market.json 里的 repo_url 和当前源地址不一致。",
                error_code="market_repo_structure_invalid",
                status_code=400,
            )
        if manifest.entry_root != source.entry_root:
            raise PluginMarketplaceServiceError(
                "市场仓库 market.json 里的 entry_root 和当前源配置不一致。",
                error_code="market_repo_structure_invalid",
                status_code=400,
            )

        directory_items = marketplace_client.list_directory(
            repo_url=source.repo_url,
            path=source.entry_root,
            ref=source.branch,
        )
    except GitHubMarketplaceClientError as exc:
        source.last_sync_status = "failed"
        source.last_sync_error_json = dump_json({"error_code": exc.error_code, "detail": exc.detail})
        source.updated_at = utc_now_iso()
        db.flush()
        raise PluginMarketplaceServiceError(
            exc.detail,
            error_code=exc.error_code,
            status_code=exc.status_code,
        ) from exc
    except PluginMarketplaceServiceError as exc:
        source.last_sync_status = "failed"
        source.last_sync_error_json = dump_json({"error_code": exc.error_code, "detail": exc.detail})
        source.updated_at = utc_now_iso()
        db.flush()
        raise

    synced_at = utc_now_iso()
    next_rows: list[PluginMarketplaceEntrySnapshot] = []
    errors: list[MarketplaceEntryErrorRead] = []
    seen_plugin_ids: set[str] = set()

    for item in directory_items:
        if item.get("type") != "dir":
            continue
        plugin_id = str(item.get("name") or "").strip()
        if not plugin_id:
            continue
        if plugin_id in seen_plugin_ids:
            errors.append(
                MarketplaceEntryErrorRead(
                    plugin_id=plugin_id,
                    error_code="market_repo_structure_invalid",
                    detail=f"市场仓库里出现了重复插件目录：{plugin_id}",
                )
            )
            continue
        seen_plugin_ids.add(plugin_id)
        entry_path = f"{source.entry_root}/{plugin_id}/{MARKETPLACE_ENTRY_FILE_NAME}"
        raw_entry: dict[str, Any] = {}
        entry_model: MarketplaceEntry | None = None
        sync_error: dict[str, Any] | None = None
        sync_status: MarketplaceEntrySyncStatus = "ready"

        try:
            raw_entry = marketplace_client.get_file_json(repo_url=source.repo_url, path=entry_path, ref=source.branch)
            entry_model = MarketplaceEntry.model_validate(raw_entry)
            if entry_model.plugin_id != plugin_id:
                raise PluginMarketplaceServiceError(
                    f"目录名 {plugin_id} 和 entry.json 里的 plugin_id 不一致。",
                    error_code="market_repo_structure_invalid",
                )
            entry_model = entry_model.model_copy(
                update={
                    "repository_metrics": _build_repository_metrics_or_none(
                        repo_url=entry_model.source_repo,
                        client=marketplace_client,
                    )
                }
            )
        except GitHubMarketplaceClientError as exc:
            sync_status = "invalid"
            sync_error = {"error_code": exc.error_code, "detail": exc.detail}
            errors.append(MarketplaceEntryErrorRead(plugin_id=plugin_id, error_code=exc.error_code, detail=exc.detail))
        except (PluginMarketplaceServiceError, ValueError) as exc:
            sync_status = "invalid"
            error_code = getattr(exc, "error_code", "market_repo_structure_invalid")
            detail = str(getattr(exc, "detail", exc))
            sync_error = {"error_code": error_code, "detail": detail}
            errors.append(MarketplaceEntryErrorRead(plugin_id=plugin_id, error_code=error_code, detail=detail))

        next_rows.append(
            _build_snapshot_row(
                source=source,
                plugin_id=plugin_id,
                entry=entry_model,
                raw_entry=raw_entry,
                sync_status=sync_status,
                sync_error=sync_error,
                synced_at=synced_at,
            )
        )

    repository.delete_marketplace_entry_snapshots_for_source(db, source_id=source.source_id)
    for row in next_rows:
        repository.add_marketplace_entry_snapshot(db, row)

    source.market_id = manifest.market_id
    source.name = manifest.name
    source.last_sync_status = "success"
    source.last_sync_error_json = None
    source.last_synced_at = synced_at
    source.updated_at = synced_at
    db.flush()

    ready_entries = sum(1 for row in next_rows if row.sync_status == "ready")
    invalid_entries = len(next_rows) - ready_entries
    return MarketplaceSourceSyncResultRead(
        source=_to_source_read(source),
        total_entries=len(next_rows),
        ready_entries=ready_entries,
        invalid_entries=invalid_entries,
        errors=errors,
    )


def list_marketplace_catalog(
    db: Session,
    *,
    household_id: str | None = None,
) -> MarketplaceCatalogListRead:
    ensure_builtin_marketplace_source(db)
    sources = {
        row.source_id: row
        for row in repository.list_marketplace_sources(db, enabled_only=True)
    }
    items: list[MarketplaceCatalogItemRead] = []
    for source_id, source in sources.items():
        for snapshot in repository.list_marketplace_entry_snapshots(db, source_id=source_id, sync_status="ready"):
            version_governance = None
            if household_id is not None:
                try:
                    version_governance = get_marketplace_version_governance(
                        db,
                        source_id=source_id,
                        plugin_id=snapshot.plugin_id,
                        household_id=household_id,
                    )
                except (PluginMarketplaceServiceError, PluginManifestValidationError, ValueError):
                    version_governance = None
            items.append(
                _to_catalog_item(
                    source=source,
                    snapshot=snapshot,
                    install_state=_resolve_install_state(db, household_id=household_id, plugin_id=snapshot.plugin_id),
                    version_governance=version_governance,
                )
            )

    items.sort(
        key=lambda item: (
            0 if item.trusted_level == "official" else 1,
            item.name.lower(),
            item.plugin_id,
            item.source_id,
        )
    )
    return MarketplaceCatalogListRead(items=items)


def get_marketplace_entry_detail(
    db: Session,
    *,
    source_id: str,
    plugin_id: str,
    household_id: str | None = None,
) -> MarketplaceEntryDetailRead:
    source = _require_source(db, source_id=source_id)
    snapshot = _require_snapshot(db, source_id=source_id, plugin_id=plugin_id)
    if snapshot.sync_status != "ready":
        raise PluginMarketplaceServiceError(
            "这个插件市场条目当前不可安装，请先修复市场仓库错误。",
            error_code="marketplace_entry_invalid",
            status_code=409,
        )

    raw_entry = _load_json_or_default(snapshot.raw_entry_json, fallback={})
    entry = MarketplaceEntry.model_validate(raw_entry)
    version_governance = None
    if household_id is not None:
        version_governance = get_marketplace_version_governance(
            db,
            source_id=source_id,
            plugin_id=plugin_id,
            household_id=household_id,
        )
    return MarketplaceEntryDetailRead(
        source=_to_source_read(source),
        plugin=_to_catalog_item(
            source=source,
            snapshot=snapshot,
            install_state=_resolve_install_state(db, household_id=household_id, plugin_id=plugin_id),
            version_governance=version_governance,
        ),
        manifest_path=snapshot.manifest_path,
        publisher=entry.publisher,
        versions=entry.versions,
        install=entry.install,
        maintainers=entry.maintainers,
        raw_entry=raw_entry if isinstance(raw_entry, dict) else {},
    )


def _set_install_task_stage(
    task: PluginMarketplaceInstallTask,
    *,
    stage: str,
    installed_version: str | None = None,
    source_repo: str | None = None,
    market_repo: str | None = None,
    artifact_url: str | None = None,
    plugin_root: str | None = None,
    manifest_path: str | None = None,
) -> None:
    task.install_status = stage
    task.installed_version = installed_version or task.installed_version
    task.source_repo = source_repo or task.source_repo
    task.market_repo = market_repo or task.market_repo
    task.artifact_url = artifact_url or task.artifact_url
    task.plugin_root = plugin_root or task.plugin_root
    task.manifest_path = manifest_path or task.manifest_path
    task.updated_at = utc_now_iso()


def _mark_install_failed(
    *,
    task: PluginMarketplaceInstallTask,
    stage: str,
    exc: Exception,
) -> None:
    task.install_status = "install_failed"
    task.failure_stage = stage
    task.error_code = getattr(exc, "error_code", "plugin_marketplace_install_failed")
    task.error_message = str(getattr(exc, "detail", exc))
    task.finished_at = utc_now_iso()
    task.updated_at = task.finished_at


def _extract_archive_bytes(*, content: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(content)
        archive_path = Path(temp_file.name)
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.namelist():
                    _ensure_archive_member_safe(destination=destination, member_path=member)
                archive.extractall(destination)
            return
        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path) as archive:
                for member in archive.getmembers():
                    _ensure_archive_member_safe(destination=destination, member_path=member.name)
                archive.extractall(destination)
            return
    finally:
        archive_path.unlink(missing_ok=True)
    raise PluginMarketplaceServiceError(
        "下载到的插件产物不是受支持的压缩包格式。",
        error_code="artifact_format_unsupported",
        status_code=400,
    )


def _ensure_archive_member_safe(*, destination: Path, member_path: str) -> None:
    normalized = PurePosixPath(member_path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise PluginMarketplaceServiceError(
            "插件产物压缩包包含非法路径，已拒绝安装。",
            error_code="artifact_format_unsupported",
            status_code=409,
        )
    candidate = (destination / Path(*normalized.parts)).resolve()
    destination_resolved = destination.resolve()
    if candidate != destination_resolved and destination_resolved not in candidate.parents:
        raise PluginMarketplaceServiceError(
            "插件产物压缩包包含越界路径，已拒绝安装。",
            error_code="artifact_format_unsupported",
            status_code=409,
        )


def _resolve_extracted_package_root(
    *,
    extracted_root: Path,
    install_spec: MarketplaceEntryInstallSpec,
) -> Path:
    if install_spec.package_root:
        return _resolve_child_path(extracted_root, install_spec.package_root, field_name="install.package_root")

    manifest_candidates = sorted(extracted_root.glob("**/manifest.json"))
    if len(manifest_candidates) == 1:
        return manifest_candidates[0].parent.resolve()

    children = [item for item in extracted_root.iterdir() if item.is_dir()]
    if len(children) == 1:
        return children[0].resolve()

    raise PluginMarketplaceServiceError(
        "无法确定插件包根目录，请在注册表里显式声明 install.package_root。",
        error_code="install_target_invalid",
        field="install.package_root",
        status_code=400,
    )


def _validate_manifest_consistency(
    *,
    manifest_path: Path,
    entry: MarketplaceEntry,
    installed_version: str,
) -> tuple[Path, Path]:
    manifest = load_plugin_manifest(manifest_path)
    if manifest.id != entry.plugin_id:
        raise PluginMarketplaceServiceError(
            "manifest.json 里的插件 ID 和市场条目不一致。",
            error_code="manifest_mismatch",
            status_code=409,
        )
    if manifest.version != installed_version:
        raise PluginMarketplaceServiceError(
            "manifest.json 里的版本和市场条目目标版本不一致。",
            error_code="manifest_mismatch",
            status_code=409,
        )
    if manifest.risk_level != entry.risk_level:
        raise PluginMarketplaceServiceError(
            "manifest.json 里的风险等级和市场条目不一致。",
            error_code="manifest_mismatch",
            status_code=409,
        )


def _require_version_compatible(
    *,
    version: str,
    min_app_version: str | None,
) -> None:
    compatibility = resolve_host_compatibility(
        host_version=settings.app_version,
        min_app_version=min_app_version,
        target_version=version,
    )
    if compatibility.status == "compatible":
        return
    if compatibility.status == "host_too_old":
        raise PluginMarketplaceServiceError(
            compatibility.blocked_reason or "目标版本与当前宿主版本不兼容。",
            error_code="plugin_version_incompatible",
            field="target_version",
            status_code=409,
        )
    raise PluginMarketplaceServiceError(
        compatibility.blocked_reason or "目标版本缺少兼容性信息，当前不能安全安装。",
        error_code="plugin_version_governance_unavailable",
        field="target_version",
        status_code=409,
    )
    if sorted(manifest.permissions) != sorted(entry.permissions):
        raise PluginMarketplaceServiceError(
            "manifest.json 里的权限声明和市场条目不一致。",
            error_code="manifest_mismatch",
            status_code=409,
        )
    plugin_root = manifest_path.parent.resolve()
    readme_path = _resolve_child_path(plugin_root, entry.install.readme_path, field_name="install.readme_path")
    requirements_path = _resolve_child_path(
        plugin_root,
        entry.install.requirements_path,
        field_name="install.requirements_path",
    )
    if not readme_path.exists():
        raise PluginMarketplaceServiceError(
            "插件源码仓库缺少 README.md。",
            error_code="install_target_invalid",
            status_code=409,
        )
    if not requirements_path.exists():
        raise PluginMarketplaceServiceError(
            "插件源码仓库缺少 requirements.txt。",
            error_code="install_target_invalid",
            status_code=409,
        )
    return readme_path, requirements_path


def _get_install_root() -> Path:
    return Path(settings.plugin_marketplace_install_root).resolve()


def create_marketplace_install_task(
    db: Session,
    *,
    payload: MarketplaceInstallTaskCreateRequest,
    client: GitHubMarketplaceClient | None = None,
) -> MarketplaceInstallTaskRead:
    from app.modules.household.service import get_household_or_404

    get_household_or_404(db, payload.household_id)
    source = _require_source(db, source_id=payload.source_id)
    snapshot = _require_snapshot(db, source_id=payload.source_id, plugin_id=payload.plugin_id)
    if snapshot.sync_status != "ready":
        raise PluginMarketplaceServiceError(
            "这个市场条目当前不可安装，请先修复市场同步错误。",
            error_code="marketplace_entry_invalid",
            status_code=409,
        )

    existing_instance = repository.get_marketplace_instance_for_plugin(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
    )
    if existing_instance is not None and existing_instance.install_status == "installed":
        if existing_instance.source_id != payload.source_id:
            raise PluginMarketplaceServiceError(
                "同一个插件 ID 已经从另一个市场源安装过了，不能直接覆盖来源。",
                error_code="plugin_already_installed_from_other_source",
                status_code=409,
            )
        raise PluginMarketplaceServiceError(
            "这个插件已经安装过了。",
            error_code="plugin_already_installed",
            status_code=409,
        )

    raw_entry = _load_json_or_default(snapshot.raw_entry_json, fallback={})
    entry = MarketplaceEntry.model_validate(raw_entry)
    try:
        version_entry = entry.resolve_version(payload.version)
    except ValueError as exc:
        raise PluginMarketplaceServiceError(
            f"目标版本 {payload.version or entry.latest_version} 不在市场条目里。",
            error_code="plugin_version_not_found",
            field="version",
            status_code=409,
        ) from exc
    _require_version_compatible(
        version=version_entry.version,
        min_app_version=version_entry.min_app_version,
    )
    now = utc_now_iso()
    task = PluginMarketplaceInstallTask(
        id=new_uuid(),
        household_id=payload.household_id,
        source_id=payload.source_id,
        plugin_id=payload.plugin_id,
        requested_version=payload.version,
        installed_version=None,
        install_status="queued",
        failure_stage=None,
        error_code=None,
        error_message=None,
        source_repo=entry.source_repo,
        market_repo=source.repo_url,
        artifact_url=version_entry.artifact_url,
        plugin_root=None,
        manifest_path=None,
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=None,
    )
    repository.add_marketplace_install_task(db, task)
    db.flush()

    marketplace_client = _get_client(client)
    try:
        _set_install_task_stage(
            task,
            stage="resolving",
            installed_version=version_entry.version,
            source_repo=entry.source_repo,
            market_repo=source.repo_url,
            artifact_url=version_entry.artifact_url,
        )
        db.flush()

        _set_install_task_stage(task, stage="downloading")
        db.flush()
        content = marketplace_client.download_binary(version_entry.artifact_url)

        _set_install_task_stage(task, stage="validating")
        db.flush()
        with tempfile.TemporaryDirectory(prefix="plugin-marketplace-") as temp_dir:
            extracted_root = Path(temp_dir).resolve()
            _extract_archive_bytes(content=content, destination=extracted_root)
            package_root = _resolve_extracted_package_root(extracted_root=extracted_root, install_spec=entry.install)
            manifest_path = _resolve_child_path(package_root, entry.manifest_path, field_name="manifest_path")
            _validate_manifest_consistency(
                manifest_path=manifest_path,
                entry=entry,
                installed_version=version_entry.version,
            )

            _set_install_task_stage(task, stage="installing")
            db.flush()
            install_root = _get_install_root()
            target_root = install_root / payload.household_id / payload.plugin_id / version_entry.version
            if target_root.exists():
                shutil.rmtree(target_root)
            target_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(package_root, target_root)

        target_manifest_path = _resolve_child_path(target_root, entry.manifest_path, field_name="manifest_path")
        mount_row = _get_plugin_mount_row(db, household_id=payload.household_id, plugin_id=payload.plugin_id)
        if mount_row is None:
            register_plugin_mount(
                db,
                household_id=payload.household_id,
                payload=PluginMountCreate(
                    source_type=source.trusted_level,
                    plugin_root=str(target_root),
                    manifest_path=str(target_manifest_path),
                    python_path=sys.executable,
                    working_dir=str(target_root),
                    enabled=False,
                ),
            )
        else:
            mount_row.source_type = source.trusted_level
            mount_row.manifest_path = str(target_manifest_path)
            mount_row.plugin_root = str(target_root)
            mount_row.python_path = sys.executable
            mount_row.working_dir = str(target_root)
            mount_row.enabled = False
            mount_row.updated_at = utc_now_iso()
            db.flush()

        instance = existing_instance or repository.get_marketplace_instance_for_plugin(
            db,
            household_id=payload.household_id,
            plugin_id=payload.plugin_id,
        )
        if instance is None:
            instance = PluginMarketplaceInstance(
                id=new_uuid(),
                household_id=payload.household_id,
                source_id=source.source_id,
                plugin_id=payload.plugin_id,
                installed_version=version_entry.version,
                install_status="installed",
                enabled=False,
                config_status="unconfigured",
                source_repo=entry.source_repo,
                market_repo=source.repo_url,
                plugin_root=str(target_root),
                manifest_path=str(target_manifest_path),
                python_path=sys.executable,
                working_dir=str(target_root),
                installed_at=utc_now_iso(),
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            repository.add_marketplace_instance(db, instance)
        else:
            instance.source_id = source.source_id
            instance.installed_version = version_entry.version
            instance.install_status = "installed"
            instance.enabled = False
            instance.source_repo = entry.source_repo
            instance.market_repo = source.repo_url
            instance.plugin_root = str(target_root)
            instance.manifest_path = str(target_manifest_path)
            instance.python_path = sys.executable
            instance.working_dir = str(target_root)
            instance.installed_at = utc_now_iso()
            instance.updated_at = utc_now_iso()

        task.install_status = "installed"
        task.plugin_root = str(target_root)
        task.manifest_path = str(target_manifest_path)
        task.installed_version = version_entry.version
        task.failure_stage = None
        task.error_code = None
        task.error_message = None
        task.finished_at = utc_now_iso()
        task.updated_at = task.finished_at
        refresh_marketplace_plugin_instance_config_status(
            db,
            household_id=payload.household_id,
            plugin_id=payload.plugin_id,
        )
        db.flush()
        return _to_install_task_read(task)
    except (GitHubMarketplaceClientError, PluginMarketplaceServiceError, PluginManifestValidationError, PluginServiceError) as exc:
        _mark_install_failed(task=task, stage=task.install_status, exc=exc)
        if existing_instance is not None:
            existing_instance.install_status = "install_failed"
            existing_instance.updated_at = utc_now_iso()
        db.flush()
        raise PluginMarketplaceServiceError(
            task.error_message or "插件安装失败。",
            error_code=task.error_code or "plugin_marketplace_install_failed",
            status_code=getattr(exc, "status_code", 400),
        ) from exc


def _get_plugin_mount_row(db: Session, *, household_id: str, plugin_id: str) -> PluginMount | None:
    from app.modules.plugin import repository as plugin_repository

    return plugin_repository.get_plugin_mount(db, household_id=household_id, plugin_id=plugin_id)


def _snapshot_instance_runtime_state(instance: PluginMarketplaceInstance) -> dict[str, Any]:
    return {
        "source_id": instance.source_id,
        "installed_version": instance.installed_version,
        "install_status": instance.install_status,
        "enabled": instance.enabled,
        "config_status": instance.config_status,
        "source_repo": instance.source_repo,
        "market_repo": instance.market_repo,
        "plugin_root": instance.plugin_root,
        "manifest_path": instance.manifest_path,
        "python_path": instance.python_path,
        "working_dir": instance.working_dir,
        "installed_at": instance.installed_at,
        "updated_at": instance.updated_at,
    }


def _snapshot_mount_runtime_state(mount: PluginMount) -> dict[str, Any]:
    return {
        "source_type": mount.source_type,
        "manifest_path": mount.manifest_path,
        "plugin_root": mount.plugin_root,
        "python_path": mount.python_path,
        "working_dir": mount.working_dir,
        "enabled": mount.enabled,
        "updated_at": mount.updated_at,
    }


def _restore_runtime_state(target: Any, snapshot: dict[str, Any]) -> None:
    for field_name, value in snapshot.items():
        setattr(target, field_name, value)


def _switch_marketplace_instance_version(
    db: Session,
    *,
    instance: PluginMarketplaceInstance,
    entry: MarketplaceEntry,
    source: PluginMarketplaceSource,
    target_version_entry,
    operation: PluginVersionOperationType,
    client: GitHubMarketplaceClient | None = None,
) -> PluginVersionOperationResultRead:
    previous_version = instance.installed_version
    if previous_version == target_version_entry.version:
        governance = resolve_marketplace_instance_version_governance(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
            declared_version=_load_declared_version_from_manifest(instance.manifest_path),
        )
        return PluginVersionOperationResultRead(
            instance=_to_instance_read(instance),
            governance=governance,
            previous_version=previous_version,
            target_version=target_version_entry.version,
            state_changed=False,
            state_change_reason=None,
        )

    mount = _get_plugin_mount_row(db, household_id=instance.household_id, plugin_id=instance.plugin_id)
    if mount is None:
        raise PluginMarketplaceServiceError(
            "插件挂载记录不存在，不能切换版本。",
            error_code="plugin_mount_not_found",
            status_code=409,
        )

    previous_instance_state = _snapshot_instance_runtime_state(instance)
    previous_mount_state = _snapshot_mount_runtime_state(mount)
    previous_enabled = instance.enabled
    previous_config_status = instance.config_status
    target_root: Path | None = None
    target_manifest_path: Path | None = None
    marketplace_client = _get_client(client)

    try:
        content = marketplace_client.download_binary(target_version_entry.artifact_url)
        with tempfile.TemporaryDirectory(prefix="plugin-marketplace-version-switch-") as temp_dir:
            extracted_root = Path(temp_dir).resolve()
            _extract_archive_bytes(content=content, destination=extracted_root)
            package_root = _resolve_extracted_package_root(extracted_root=extracted_root, install_spec=entry.install)
            manifest_path = _resolve_child_path(package_root, entry.manifest_path, field_name="manifest_path")
            _validate_manifest_consistency(
                manifest_path=manifest_path,
                entry=entry,
                installed_version=target_version_entry.version,
            )

            install_root = _get_install_root()
            target_root = install_root / instance.household_id / instance.plugin_id / target_version_entry.version
            if target_root.exists():
                shutil.rmtree(target_root)
            target_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(package_root, target_root)

        target_manifest_path = _resolve_child_path(target_root, entry.manifest_path, field_name="manifest_path")
        instance.source_id = source.source_id
        instance.installed_version = target_version_entry.version
        instance.install_status = "installed"
        instance.enabled = previous_enabled
        instance.source_repo = entry.source_repo
        instance.market_repo = source.repo_url
        instance.plugin_root = str(target_root)
        instance.manifest_path = str(target_manifest_path)
        instance.python_path = sys.executable
        instance.working_dir = str(target_root)
        instance.installed_at = utc_now_iso()
        instance.updated_at = utc_now_iso()

        mount.source_type = source.trusted_level
        mount.manifest_path = str(target_manifest_path)
        mount.plugin_root = str(target_root)
        mount.python_path = sys.executable
        mount.working_dir = str(target_root)
        mount.enabled = previous_enabled
        mount.updated_at = utc_now_iso()

        refresh_marketplace_plugin_instance_config_status(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
        )

        state_changed = instance.config_status != previous_config_status
        state_change_reason = None
        if instance.config_status != "configured":
            if previous_enabled:
                instance.enabled = False
                mount.enabled = False
                state_changed = True
            state_change_reason = (
                f"{'升级' if operation == 'upgrade' else '回滚'}后配置状态变为 {instance.config_status}，"
                "当前已阻止继续执行，请先重新确认配置。"
            )

        governance = resolve_marketplace_instance_version_governance(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
            declared_version=target_version_entry.version,
        )
        db.flush()
        return PluginVersionOperationResultRead(
            instance=_to_instance_read(instance),
            governance=governance,
            previous_version=previous_version,
            target_version=target_version_entry.version,
            state_changed=state_changed,
            state_change_reason=state_change_reason,
        )
    except (GitHubMarketplaceClientError, PluginMarketplaceServiceError, PluginManifestValidationError, PluginServiceError) as exc:
        _restore_runtime_state(instance, previous_instance_state)
        _restore_runtime_state(mount, previous_mount_state)
        db.flush()
        raise PluginMarketplaceServiceError(
            getattr(exc, "detail", None) or "插件版本切换失败。",
            error_code=getattr(exc, "error_code", None) or "plugin_version_switch_failed",
            field=getattr(exc, "field", None),
            status_code=getattr(exc, "status_code", 409),
        ) from exc


def get_marketplace_instance(
    db: Session,
    *,
    instance_id: str,
) -> MarketplaceInstanceRead:
    instance = repository.get_marketplace_instance(db, instance_id)
    if instance is None:
        raise PluginMarketplaceServiceError(
            "插件市场实例不存在。",
            error_code="marketplace_instance_not_found",
            field="instance_id",
            status_code=404,
        )
    return _to_instance_read(instance)


def get_marketplace_instance_for_household_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginMarketplaceInstance | None:
    return repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)


def operate_marketplace_instance_version(
    db: Session,
    *,
    instance_id: str,
    payload: PluginVersionOperationRequest,
    client: GitHubMarketplaceClient | None = None,
) -> PluginVersionOperationResultRead:
    instance = repository.get_marketplace_instance(db, instance_id)
    if instance is None:
        raise PluginMarketplaceServiceError(
            "插件市场实例不存在。",
            error_code="marketplace_instance_not_found",
            field="instance_id",
            status_code=404,
        )
    if instance.household_id != payload.household_id or instance.plugin_id != payload.plugin_id:
        raise PluginMarketplaceServiceError(
            "版本切换请求和当前插件实例不匹配。",
            error_code="plugin_source_mismatch",
            status_code=409,
        )
    if instance.source_id != payload.source_id:
        raise PluginMarketplaceServiceError(
            "当前插件实例来源和目标市场来源不一致。",
            error_code="plugin_source_mismatch",
            field="source_id",
            status_code=409,
        )
    if instance.install_status != "installed":
        raise PluginMarketplaceServiceError(
            "插件还没有安装完成，不能切换版本。",
            error_code="plugin_marketplace_not_installed",
            status_code=409,
        )

    source = _require_source(db, source_id=payload.source_id)
    snapshot = _require_snapshot(db, source_id=payload.source_id, plugin_id=payload.plugin_id)
    entry = _load_marketplace_entry_from_snapshot(snapshot)
    try:
        target_version_entry = entry.resolve_version(payload.target_version)
    except ValueError as exc:
        raise PluginMarketplaceServiceError(
            f"目标版本 {payload.target_version} 不在市场条目里。",
            error_code="plugin_version_not_found",
            field="target_version",
            status_code=409,
        ) from exc

    _require_version_compatible(
        version=target_version_entry.version,
        min_app_version=target_version_entry.min_app_version,
    )
    return _switch_marketplace_instance_version(
        db,
        instance=instance,
        entry=entry,
        source=source,
        target_version_entry=target_version_entry,
        operation=payload.operation,
        client=client,
    )


def resolve_marketplace_plugin_config_status(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginConfigState:
    from app.modules.plugin.config_service import get_plugin_config_form, list_plugin_config_scopes

    scope_list = list_plugin_config_scopes(db, household_id=household_id, plugin_id=plugin_id)
    if not scope_list.items:
        return "configured"

    has_unconfigured = False
    for scope in scope_list.items:
        if not scope.instances:
            has_unconfigured = True
            continue
        for instance in scope.instances:
            form = get_plugin_config_form(
                db,
                household_id=household_id,
                plugin_id=plugin_id,
                scope_type=scope.scope_type,
                scope_key=instance.scope_key,
            )
            if form.view.state == "invalid":
                return "invalid"
            if form.view.state != "configured":
                has_unconfigured = True
    return "unconfigured" if has_unconfigured else "configured"


def refresh_marketplace_plugin_instance_config_status(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginMarketplaceInstance | None:
    instance = repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)
    if instance is None:
        return None
    instance.config_status = resolve_marketplace_plugin_config_status(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    instance.updated_at = utc_now_iso()
    db.flush()
    return instance


def set_marketplace_instance_enabled(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginStateUpdateRequest,
) -> MarketplaceInstanceRead:
    instance = repository.get_marketplace_instance_for_plugin(db, household_id=household_id, plugin_id=plugin_id)
    if instance is None:
        raise PluginMarketplaceServiceError(
            "插件市场实例不存在。",
            error_code="marketplace_instance_not_found",
            field="plugin_id",
            status_code=404,
        )

    refresh_marketplace_plugin_instance_config_status(db, household_id=household_id, plugin_id=plugin_id)
    if payload.enabled:
        if instance.install_status != "installed":
            raise PluginMarketplaceServiceError(
                "插件还没有安装完成，不能启用。",
                error_code="plugin_marketplace_not_installed",
                status_code=409,
            )
        if instance.config_status != "configured":
            raise PluginMarketplaceServiceError(
                "插件配置还没完成，不能启用。",
                error_code=PLUGIN_MARKETPLACE_UNCONFIGURED_ERROR_CODE,
                status_code=409,
            )

    mount = _get_plugin_mount_row(db, household_id=household_id, plugin_id=plugin_id)
    if mount is None:
        raise PluginMarketplaceServiceError(
            "插件挂载记录不存在，不能切换启用状态。",
            error_code="plugin_mount_not_found",
            status_code=409,
        )

    instance.enabled = payload.enabled
    instance.updated_at = utc_now_iso()
    mount.enabled = payload.enabled
    mount.updated_at = utc_now_iso()
    db.flush()
    return _to_instance_read(instance)
