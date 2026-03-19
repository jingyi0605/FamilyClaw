from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.household.models import Household
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin.models import PluginMount
from app.modules.plugin.service import (
    PluginManifestValidationError,
    _validate_region_provider_mount_conflicts,
    list_registered_plugins,
    load_plugin_manifest,
)
from app.modules.plugin_marketplace import repository as marketplace_repository
from app.modules.plugin_marketplace.models import (
    PluginMarketplaceEntrySnapshot,
    PluginMarketplaceInstance,
    PluginMarketplaceInstallTask,
    PluginMarketplaceSource,
)
from app.modules.plugin_marketplace.service import (
    BUILTIN_MARKETPLACE_SOURCE_ID,
    resolve_marketplace_plugin_config_status,
)
from app.modules.region.plugin_runtime import sync_household_plugin_region_providers

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PluginStartupSyncResult:
    official_created: int = 0
    official_updated: int = 0
    manual_created: int = 0
    manual_updated: int = 0
    marketplace_mount_created: int = 0
    marketplace_mount_updated: int = 0
    marketplace_instance_created: int = 0
    marketplace_instance_updated: int = 0
    theme_pack_registry_refresh: int = 0
    skipped: int = 0


@dataclass(slots=True)
class _MarketplaceRestoreContext:
    source: PluginMarketplaceSource
    snapshot: PluginMarketplaceEntrySnapshot
    source_repo: str
    market_repo: str


def sync_persisted_plugins_on_startup(db: Session) -> PluginStartupSyncResult:
    result = PluginStartupSyncResult()
    household_ids = set(db.scalars(select(Household.id)).all())
    builtin_plugin_ids = {item.id for item in list_registered_plugins().items}
    changed_household_ids: set[str] = set()
    theme_pack_registry_household_ids: set[str] = set()

    result.official_created, result.official_updated, official_skipped = _sync_official_plugin_mounts(
        db,
        household_ids=household_ids,
        builtin_plugin_ids=builtin_plugin_ids,
        changed_household_ids=changed_household_ids,
        theme_pack_registry_household_ids=theme_pack_registry_household_ids,
    )
    result.skipped += official_skipped

    result.manual_created, result.manual_updated, manual_skipped = _sync_manual_plugin_mounts(
        db,
        household_ids=household_ids,
        builtin_plugin_ids=builtin_plugin_ids,
        changed_household_ids=changed_household_ids,
        theme_pack_registry_household_ids=theme_pack_registry_household_ids,
    )
    result.skipped += manual_skipped

    (
        result.marketplace_mount_created,
        result.marketplace_mount_updated,
        result.marketplace_instance_created,
        result.marketplace_instance_updated,
        marketplace_skipped,
    ) = _sync_marketplace_plugins(
        db,
        household_ids=household_ids,
        builtin_plugin_ids=builtin_plugin_ids,
        changed_household_ids=changed_household_ids,
        theme_pack_registry_household_ids=theme_pack_registry_household_ids,
    )
    result.skipped += marketplace_skipped

    for household_id in sorted(changed_household_ids):
        sync_household_plugin_region_providers(db, household_id)
    result.theme_pack_registry_refresh = len(theme_pack_registry_household_ids)

    logger.info(
        "Startup plugin sync finished official(created=%s updated=%s) "
        "manual(created=%s updated=%s) marketplace(mount_created=%s mount_updated=%s instance_created=%s instance_updated=%s) "
        "theme_pack_registry_refresh=%s skipped=%s",
        result.official_created,
        result.official_updated,
        result.manual_created,
        result.manual_updated,
        result.marketplace_mount_created,
        result.marketplace_mount_updated,
        result.marketplace_instance_created,
        result.marketplace_instance_updated,
        result.theme_pack_registry_refresh,
        result.skipped,
    )
    return result


def _sync_official_plugin_mounts(
    db: Session,
    *,
    household_ids: set[str],
    builtin_plugin_ids: set[str],
    changed_household_ids: set[str],
    theme_pack_registry_household_ids: set[str],
) -> tuple[int, int, int]:
    official_root = Path(settings.plugin_storage_root).resolve() / "official"
    if not official_root.exists():
        return 0, 0, 0

    created = 0
    updated = 0
    skipped = 0
    for manifest_path in sorted(official_root.glob("*/manifest.json")):
        plugin_root = manifest_path.parent.resolve()
        for household_id in sorted(household_ids):
            status = _upsert_plugin_mount_from_disk(
                db,
                household_id=household_id,
                source_type="official",
                plugin_root=plugin_root,
                manifest_path=manifest_path.resolve(),
                builtin_plugin_ids=builtin_plugin_ids,
                enabled_on_create=True,
                changed_household_ids=changed_household_ids,
                theme_pack_registry_household_ids=theme_pack_registry_household_ids,
            )
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            elif status == "skipped":
                skipped += 1
    return created, updated, skipped


def _sync_manual_plugin_mounts(
    db: Session,
    *,
    household_ids: set[str],
    builtin_plugin_ids: set[str],
    changed_household_ids: set[str],
    theme_pack_registry_household_ids: set[str],
) -> tuple[int, int, int]:
    manual_root = Path(settings.plugin_storage_root).resolve() / "third_party" / "manual"
    if not manual_root.exists():
        return 0, 0, 0

    created = 0
    updated = 0
    skipped = 0
    for household_dir in sorted(path for path in manual_root.iterdir() if path.is_dir()):
        household_id = household_dir.name
        if household_id not in household_ids:
            logger.warning("Startup plugin sync skipped manual plugin because household does not exist household_id=%s", household_id)
            skipped += 1
            continue
        for plugin_dir in sorted(path for path in household_dir.iterdir() if path.is_dir()):
            manifest_path = (plugin_dir / "manifest.json").resolve()
            if not manifest_path.is_file():
                logger.warning("Startup plugin sync skipped manual plugin because manifest is missing plugin_root=%s", plugin_dir)
                skipped += 1
                continue
            try:
                manifest = load_plugin_manifest(manifest_path)
            except PluginManifestValidationError as exc:
                logger.warning(
                    "Startup plugin sync skipped manual plugin because manifest is invalid household_id=%s plugin_root=%s error=%s",
                    household_id,
                    plugin_dir,
                    exc,
                )
                skipped += 1
                continue
            if manifest.id != plugin_dir.name:
                logger.warning(
                    "Startup plugin sync skipped manual plugin because plugin_id does not match directory household_id=%s directory_plugin_id=%s manifest_plugin_id=%s",
                    household_id,
                    plugin_dir.name,
                    manifest.id,
                )
                skipped += 1
                continue
            status = _upsert_plugin_mount_from_disk(
                db,
                household_id=household_id,
                source_type="third_party",
                plugin_root=plugin_dir.resolve(),
                manifest_path=manifest_path,
                builtin_plugin_ids=builtin_plugin_ids,
                enabled_on_create=False,
                changed_household_ids=changed_household_ids,
                theme_pack_registry_household_ids=theme_pack_registry_household_ids,
                manifest=manifest,
            )
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            elif status == "skipped":
                skipped += 1
    return created, updated, skipped


def _sync_marketplace_plugins(
    db: Session,
    *,
    household_ids: set[str],
    builtin_plugin_ids: set[str],
    changed_household_ids: set[str],
    theme_pack_registry_household_ids: set[str],
) -> tuple[int, int, int, int, int]:
    install_root = Path(settings.plugin_marketplace_install_root).resolve()
    if not install_root.exists():
        return 0, 0, 0, 0, 0

    _ensure_builtin_marketplace_source_row(db)
    mount_created = 0
    mount_updated = 0
    instance_created = 0
    instance_updated = 0
    skipped = 0

    for trusted_root in sorted(path for path in install_root.iterdir() if path.is_dir()):
        trusted_level = trusted_root.name
        if trusted_level not in {"official", "third_party"}:
            logger.warning(
                "Startup plugin sync skipped marketplace trusted level because it is unsupported trusted_level=%s",
                trusted_level,
            )
            skipped += 1
            continue
        marketplace_root = trusted_root / "marketplace"
        if not marketplace_root.is_dir():
            continue
        for household_dir in sorted(path for path in marketplace_root.iterdir() if path.is_dir()):
            household_id = household_dir.name
            if household_id not in household_ids:
                logger.warning(
                    "Startup plugin sync skipped marketplace plugin because household does not exist household_id=%s trusted_level=%s",
                    household_id,
                    trusted_level,
                )
                skipped += 1
                continue
            for plugin_dir in sorted(path for path in household_dir.iterdir() if path.is_dir()):
                for version_dir in sorted(path for path in plugin_dir.iterdir() if path.is_dir()):
                    manifest_path = (version_dir / "manifest.json").resolve()
                    if not manifest_path.is_file():
                        logger.warning(
                            "Startup plugin sync skipped marketplace plugin because manifest is missing household_id=%s plugin_root=%s",
                            household_id,
                            version_dir,
                        )
                        skipped += 1
                        continue
                    try:
                        manifest = load_plugin_manifest(manifest_path)
                    except PluginManifestValidationError as exc:
                        logger.warning(
                            "Startup plugin sync skipped marketplace plugin because manifest is invalid household_id=%s plugin_root=%s error=%s",
                            household_id,
                            version_dir,
                            exc,
                        )
                        skipped += 1
                        continue
                    if manifest.id != plugin_dir.name:
                        logger.warning(
                            "Startup plugin sync skipped marketplace plugin because plugin_id does not match directory household_id=%s directory_plugin_id=%s manifest_plugin_id=%s",
                            household_id,
                            plugin_dir.name,
                            manifest.id,
                        )
                        skipped += 1
                        continue
                    if manifest.version != version_dir.name:
                        logger.warning(
                            "Startup plugin sync skipped marketplace plugin because version does not match directory household_id=%s plugin_id=%s directory_version=%s manifest_version=%s",
                            household_id,
                            manifest.id,
                            version_dir.name,
                            manifest.version,
                        )
                        skipped += 1
                        continue

                    mount_status = _upsert_plugin_mount_from_disk(
                        db,
                        household_id=household_id,
                        source_type=trusted_level,
                        plugin_root=version_dir.resolve(),
                        manifest_path=manifest_path,
                        builtin_plugin_ids=builtin_plugin_ids,
                        enabled_on_create=False,
                        changed_household_ids=changed_household_ids,
                        theme_pack_registry_household_ids=theme_pack_registry_household_ids,
                        manifest=manifest,
                    )
                    if mount_status == "created":
                        mount_created += 1
                    elif mount_status == "updated":
                        mount_updated += 1
                    elif mount_status == "skipped":
                        skipped += 1
                        continue

                    restore_context = _resolve_marketplace_restore_context(
                        db,
                        household_id=household_id,
                        plugin_id=manifest.id,
                        trusted_level=trusted_level,
                        installed_version=manifest.version,
                        plugin_root=version_dir.resolve(),
                        manifest_path=manifest_path,
                    )
                    if restore_context is None:
                        skipped += 1
                        continue

                    instance_status = _upsert_marketplace_instance_from_disk(
                        db,
                        household_id=household_id,
                        plugin_root=version_dir.resolve(),
                        manifest_path=manifest_path,
                        manifest_version=manifest.version,
                        plugin_id=manifest.id,
                        restore_context=restore_context,
                    )
                    if instance_status == "created":
                        instance_created += 1
                    elif instance_status == "updated":
                        instance_updated += 1
    return mount_created, mount_updated, instance_created, instance_updated, skipped


def _ensure_builtin_marketplace_source_row(db: Session) -> PluginMarketplaceSource:
    existing = marketplace_repository.get_marketplace_source(db, BUILTIN_MARKETPLACE_SOURCE_ID)
    if existing is not None:
        return existing

    now = utc_now_iso()
    row = PluginMarketplaceSource(
        source_id=BUILTIN_MARKETPLACE_SOURCE_ID,
        market_id=None,
        name="官方插件市场",
        owner=None,
        repo_url=settings.plugin_marketplace_official_repo_url.strip(),
        repo_provider=_infer_repo_provider(settings.plugin_marketplace_official_repo_url),
        api_base_url=None,
        mirror_repo_url=None,
        mirror_repo_provider=None,
        mirror_api_base_url=None,
        branch=settings.plugin_marketplace_official_branch.strip() or "main",
        entry_root=settings.plugin_marketplace_official_entry_root.strip() or "plugins",
        trusted_level="official",
        enabled=True,
        last_sync_status="idle",
        last_sync_error_json=None,
        last_synced_at=None,
        created_at=now,
        updated_at=now,
    )
    marketplace_repository.add_marketplace_source(db, row)
    db.flush()
    return row


def _infer_repo_provider(repo_url: str) -> str:
    host = urlparse(repo_url).netloc.lower()
    if host == "gitlab.com":
        return "gitlab"
    if host == "gitee.com":
        return "gitee"
    if host.startswith("git.") or "gitea" in host:
        return "gitea"
    return "github"


def _upsert_plugin_mount_from_disk(
    db: Session,
    *,
    household_id: str,
    source_type: str,
    plugin_root: Path,
    manifest_path: Path,
    builtin_plugin_ids: set[str],
    enabled_on_create: bool,
    changed_household_ids: set[str],
    theme_pack_registry_household_ids: set[str],
    manifest=None,
) -> str:
    current_manifest = manifest
    if current_manifest is None:
        try:
            current_manifest = load_plugin_manifest(manifest_path)
        except PluginManifestValidationError as exc:
            logger.warning(
                "Startup plugin sync skipped mount because manifest is invalid household_id=%s manifest_path=%s error=%s",
                household_id,
                manifest_path,
                exc,
            )
            return "skipped"

    if current_manifest.id in builtin_plugin_ids:
        logger.warning(
            "Startup plugin sync skipped mount because plugin_id conflicts with builtin registry household_id=%s plugin_id=%s",
            household_id,
            current_manifest.id,
        )
        return "skipped"

    existing = plugin_repository.get_plugin_mount(db, household_id=household_id, plugin_id=current_manifest.id)
    try:
        _validate_region_provider_mount_conflicts(
            db,
            household_id=household_id,
            manifest=current_manifest,
            skip_plugin_id=current_manifest.id if existing is not None else None,
        )
    except ValueError as exc:
        logger.warning(
            "Startup plugin sync skipped mount because region provider validation failed household_id=%s plugin_id=%s error=%s",
            household_id,
            current_manifest.id,
            exc,
        )
        return "skipped"

    plugin_root_value = str(plugin_root.resolve())
    manifest_path_value = str(manifest_path.resolve())
    working_dir_value = plugin_root_value
    python_path_value = sys.executable
    execution_backend_value = "in_process" if source_type == "official" else "subprocess_runner"
    now = utc_now_iso()

    if existing is None:
        row = PluginMount(
            id=new_uuid(),
            household_id=household_id,
            plugin_id=current_manifest.id,
            source_type=source_type,
            execution_backend=execution_backend_value,
            manifest_path=manifest_path_value,
            plugin_root=plugin_root_value,
            python_path=python_path_value,
            working_dir=working_dir_value,
            enabled=enabled_on_create,
            created_at=now,
            updated_at=now,
        )
        plugin_repository.add_plugin_mount(db, row)
        db.flush()
        changed_household_ids.add(household_id)
        if "theme-pack" in current_manifest.types:
            theme_pack_registry_household_ids.add(household_id)
        return "created"

    changed = False
    if existing.source_type != source_type:
        existing.source_type = source_type
        changed = True
    if existing.execution_backend != execution_backend_value:
        existing.execution_backend = execution_backend_value
        changed = True
    if existing.manifest_path != manifest_path_value:
        existing.manifest_path = manifest_path_value
        changed = True
    if existing.plugin_root != plugin_root_value:
        existing.plugin_root = plugin_root_value
        changed = True
    if existing.python_path != python_path_value:
        existing.python_path = python_path_value
        changed = True
    if existing.working_dir != working_dir_value:
        existing.working_dir = working_dir_value
        changed = True
    if changed:
        existing.updated_at = now
        db.flush()
        changed_household_ids.add(household_id)
        if "theme-pack" in current_manifest.types:
            theme_pack_registry_household_ids.add(household_id)
        return "updated"
    return "unchanged"


def _resolve_marketplace_restore_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    trusted_level: str,
    installed_version: str,
    plugin_root: Path,
    manifest_path: Path,
) -> _MarketplaceRestoreContext | None:
    existing_instance = marketplace_repository.get_marketplace_instance_for_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    if existing_instance is not None:
        context = _build_marketplace_restore_context(
            db,
            source_id=existing_instance.source_id,
            plugin_id=plugin_id,
            trusted_level=trusted_level,
            source_repo=existing_instance.source_repo,
            market_repo=existing_instance.market_repo,
        )
        if context is not None:
            return context

    if trusted_level == "official":
        context = _build_marketplace_restore_context(
            db,
            source_id=BUILTIN_MARKETPLACE_SOURCE_ID,
            plugin_id=plugin_id,
            trusted_level=trusted_level,
            source_repo=None,
            market_repo=None,
        )
        if context is not None:
            return context

    install_tasks = marketplace_repository.list_marketplace_install_tasks(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    for task in install_tasks:
        if task.install_status != "installed":
            continue
        if not _install_task_matches_runtime_state(
            task,
            installed_version=installed_version,
            plugin_root=plugin_root,
            manifest_path=manifest_path,
        ):
            continue
        context = _build_marketplace_restore_context(
            db,
            source_id=task.source_id,
            plugin_id=plugin_id,
            trusted_level=trusted_level,
            source_repo=task.source_repo,
            market_repo=task.market_repo,
        )
        if context is not None:
            return context

    candidates: list[_MarketplaceRestoreContext] = []
    for source in marketplace_repository.list_marketplace_sources(db, enabled_only=False):
        if source.trusted_level != trusted_level:
            continue
        snapshot = marketplace_repository.get_marketplace_entry_snapshot(
            db,
            source_id=source.source_id,
            plugin_id=plugin_id,
        )
        if snapshot is None or snapshot.sync_status != "ready":
            continue
        candidates.append(
            _MarketplaceRestoreContext(
                source=source,
                snapshot=snapshot,
                source_repo=snapshot.source_repo,
                market_repo=source.repo_url,
            )
        )

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        logger.warning(
            "Startup plugin sync skipped marketplace instance because source resolution is ambiguous household_id=%s plugin_id=%s trusted_level=%s candidate_source_ids=%s",
            household_id,
            plugin_id,
            trusted_level,
            [item.source.source_id for item in candidates],
        )
        return None

    logger.warning(
        "Startup plugin sync skipped marketplace instance because no matching source snapshot was found household_id=%s plugin_id=%s trusted_level=%s",
        household_id,
        plugin_id,
        trusted_level,
    )
    return None


def _install_task_matches_runtime_state(
    task: PluginMarketplaceInstallTask,
    *,
    installed_version: str,
    plugin_root: Path,
    manifest_path: Path,
) -> bool:
    if task.installed_version == installed_version:
        return True
    if task.plugin_root and Path(task.plugin_root).resolve() == plugin_root.resolve():
        return True
    if task.manifest_path and Path(task.manifest_path).resolve() == manifest_path.resolve():
        return True
    return False


def _build_marketplace_restore_context(
    db: Session,
    *,
    source_id: str,
    plugin_id: str,
    trusted_level: str,
    source_repo: str | None,
    market_repo: str | None,
) -> _MarketplaceRestoreContext | None:
    source = marketplace_repository.get_marketplace_source(db, source_id)
    if source is None or source.trusted_level != trusted_level:
        return None
    snapshot = marketplace_repository.get_marketplace_entry_snapshot(db, source_id=source_id, plugin_id=plugin_id)
    if snapshot is None or snapshot.sync_status != "ready":
        return None
    return _MarketplaceRestoreContext(
        source=source,
        snapshot=snapshot,
        source_repo=source_repo or snapshot.source_repo,
        market_repo=market_repo or source.repo_url,
    )


def _upsert_marketplace_instance_from_disk(
    db: Session,
    *,
    household_id: str,
    plugin_root: Path,
    manifest_path: Path,
    manifest_version: str,
    plugin_id: str,
    restore_context: _MarketplaceRestoreContext,
) -> str:
    mount = plugin_repository.get_plugin_mount(db, household_id=household_id, plugin_id=plugin_id)
    enabled_on_create = mount.enabled if mount is not None else False
    config_status = resolve_marketplace_plugin_config_status(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    plugin_root_value = str(plugin_root.resolve())
    manifest_path_value = str(manifest_path.resolve())
    working_dir_value = plugin_root_value
    python_path_value = sys.executable
    now = utc_now_iso()

    existing = marketplace_repository.get_marketplace_instance_for_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )
    if existing is None:
        row = PluginMarketplaceInstance(
            id=new_uuid(),
            household_id=household_id,
            source_id=restore_context.source.source_id,
            plugin_id=plugin_id,
            installed_version=manifest_version,
            install_status="installed",
            enabled=enabled_on_create,
            config_status=config_status,
            source_repo=restore_context.source_repo,
            market_repo=restore_context.market_repo,
            plugin_root=plugin_root_value,
            manifest_path=manifest_path_value,
            python_path=python_path_value,
            working_dir=working_dir_value,
            installed_at=now,
            created_at=now,
            updated_at=now,
        )
        marketplace_repository.add_marketplace_instance(db, row)
        db.flush()
        return "created"

    changed = False
    if existing.source_id != restore_context.source.source_id:
        existing.source_id = restore_context.source.source_id
        changed = True
    if existing.installed_version != manifest_version:
        existing.installed_version = manifest_version
        changed = True
    if existing.install_status != "installed":
        existing.install_status = "installed"
        changed = True
    if existing.source_repo != restore_context.source_repo:
        existing.source_repo = restore_context.source_repo
        changed = True
    if existing.market_repo != restore_context.market_repo:
        existing.market_repo = restore_context.market_repo
        changed = True
    if existing.plugin_root != plugin_root_value:
        existing.plugin_root = plugin_root_value
        changed = True
    if existing.manifest_path != manifest_path_value:
        existing.manifest_path = manifest_path_value
        changed = True
    if existing.python_path != python_path_value:
        existing.python_path = python_path_value
        changed = True
    if existing.working_dir != working_dir_value:
        existing.working_dir = working_dir_value
        changed = True
    if existing.config_status != config_status:
        existing.config_status = config_status
        changed = True
    if existing.installed_at is None:
        existing.installed_at = now
        changed = True
    if changed:
        existing.updated_at = now
        db.flush()
        return "updated"
    return "unchanged"
