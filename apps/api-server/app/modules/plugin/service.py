from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import json
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor
import sys
from typing import Any, Literal, cast

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import ActorContext
from app.core.blocking import BlockingCallPolicy, run_blocking, run_blocking_db
from app.core.config import settings
from app.core.config import BASE_DIR
from app.db.engine import build_database_engine
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.audit.service import write_audit_log
# NOTE: get_household_or_404 延迟导入，避免循环依赖 (household → region → plugin → household)
from app.modules.memory.service import (
    upsert_knowledge_document_from_observation,
    upsert_plugin_observation_memory,
)
from app.modules.region.plugin_runtime import get_runtime_region_provider_spec, sync_household_plugin_region_providers
from app.modules.region.service import resolve_household_region_context
from app.modules.plugin.executors import get_executor, load_entrypoint_callable, resolve_execution_backend
from app.modules.plugin.private_migration_service import ensure_plugin_private_migrations
from . import repository
from app.modules.plugin.models import PluginMount, PluginRawRecord, PluginRun, PluginStateOverride
from app.modules.plugin.runner_errors import PLUGIN_EXECUTION_FAILED, PluginRunnerError
from app.modules.plugin.schemas import PluginManifest
from app.modules.plugin.schemas import (
    PluginRegistryItem,
    PluginRegistrySnapshot,
    PluginRegistryStateEntry,
    PluginVersionGovernanceRead,
)
from app.modules.plugin.schemas import (
    PluginExecutionBackend,
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginJobCreate,
    PluginJobRead,
    PluginManifestLocaleSpec,
    PluginLocaleListRead,
    PluginLocaleRead,
    PluginMountCreate,
    PluginMountRead,
    PluginMountUpdate,
    PluginStateUpdateRequest,
    PluginRawRecordCreate,
    PluginRawRecordRead,
    PluginRunnerConfig,
    PluginRunRead,
    PluginSourceType,
    PluginSyncPipelineResult,
    PluginThemeRegistryItemRead,
    PluginThemeRegistrySnapshotRead,
    PluginThemeResourceRead,
)
from app.modules.plugin.job_service import create_plugin_job
from app.modules.plugin.versioning import resolve_non_market_version_governance


BUILTIN_PLUGIN_ROOT = BASE_DIR / "app" / "plugins" / "builtin"
REGISTRY_STATE_PATH = BASE_DIR / "data" / "plugin_registry_state.json"
PLUGIN_EXECUTOR_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin-worker")
PLUGIN_SYSTEM_CONTEXT_KEY = "_system_context"
LOCALE_SOURCE_PRIORITY: dict[PluginSourceType, int] = {
    "builtin": 3,
    "official": 2,
    "third_party": 1,
}
PLUGIN_DISABLED_ERROR_CODE = "plugin_disabled"
PLUGIN_NOT_VISIBLE_ERROR_CODE = "plugin_not_visible_in_household"
PLUGIN_THEME_NOT_FOUND_ERROR_CODE = "plugin_theme_not_found"
PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE = "plugin_theme_resource_invalid"
PLUGIN_THEME_RESOURCE_UNAVAILABLE_ERROR_CODE = "plugin_theme_resource_unavailable"
PLUGIN_STATE_OVERRIDE_INVALID_ERROR_CODE = "plugin_state_override_invalid"
PLUGIN_EFFECTIVE_STATE_UNRESOLVED_ERROR_CODE = "plugin_effective_state_unresolved"
logger = logging.getLogger(__name__)
_REPORTED_PLUGIN_REGISTRY_ISSUES: set[str] = set()


@dataclass(slots=True)
class PluginExecutionContext:
    root_dir: str | Path | None
    source_type: PluginSourceType
    execution_backend: PluginExecutionBackend | None
    runner_config: PluginRunnerConfig | None


@dataclass(slots=True)
class PreparedHouseholdPluginExecution:
    plugin: PluginRegistryItem
    request: PluginExecutionRequest
    runtime_context: dict[str, object] | None


class PluginManifestValidationError(ValueError):
    pass


class PluginServiceError(ValueError):
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


class PluginExecutionError(PluginServiceError):
    def __init__(
        self,
        detail: str,
        *,
        error_code: str = PLUGIN_EXECUTION_FAILED,
        field: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(detail, error_code=error_code, field=field, status_code=status_code)


def _log_plugin_registry_issue_once(*, issue_key: str, message: str) -> None:
    if issue_key in _REPORTED_PLUGIN_REGISTRY_ISSUES:
        return
    _REPORTED_PLUGIN_REGISTRY_ISSUES.add(issue_key)
    logger.error(message)


def _load_mount_manifest_or_log(
    *,
    household_id: str,
    mount: PluginMount,
    operation: str,
) -> PluginManifest | None:
    try:
        manifest = load_plugin_manifest(mount.manifest_path)
    except PluginManifestValidationError as exc:
        _log_plugin_registry_issue_once(
            issue_key=(
                f"mounted-manifest-invalid:{operation}:{household_id}:{mount.plugin_id}:"
                f"{Path(mount.manifest_path).resolve()}:{exc}"
            ),
            message=(
                "家庭插件 manifest 无效，已跳过当前挂载记录。"
                f" operation={operation}"
                f" household_id={household_id}"
                f" plugin_id={mount.plugin_id}"
                f" manifest_path={mount.manifest_path}"
                f" error={exc}"
            ),
        )
        return None
    if manifest.id != mount.plugin_id:
        _log_plugin_registry_issue_once(
            issue_key=(
                f"mounted-manifest-id-mismatch:{operation}:{household_id}:{mount.plugin_id}:"
                f"{Path(mount.manifest_path).resolve()}:{manifest.id}"
            ),
            message=(
                "家庭插件 manifest 与挂载记录的 plugin_id 不一致，已跳过当前挂载记录。"
                f" operation={operation}"
                f" household_id={household_id}"
                f" mount_plugin_id={mount.plugin_id}"
                f" manifest_id={manifest.id}"
                f" manifest_path={mount.manifest_path}"
            ),
        )
        return None
    return manifest


def _load_locale_messages_or_log(
    *,
    plugin: PluginRegistryItem,
    locale_id: str,
    resource_path: Path,
) -> dict[str, str] | None:
    try:
        if not resource_path.exists() or not resource_path.is_file():
            raise PluginManifestValidationError(f"语言资源文件不存在: {resource_path}")
        raw_payload = json.loads(resource_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        error = PluginManifestValidationError(f"语言资源 JSON 解析失败: {resource_path}: {exc.msg}")
        _log_plugin_registry_issue_once(
            issue_key=f"plugin-locale-invalid:{plugin.id}:{locale_id}:{resource_path.resolve()}:{error}",
            message=(
                "插件语言资源无效，已跳过当前 locale。"
                f" plugin_id={plugin.id}"
                f" locale_id={locale_id}"
                f" resource_path={resource_path}"
                f" error={error}"
            ),
        )
        return None
    except PluginManifestValidationError as exc:
        _log_plugin_registry_issue_once(
            issue_key=f"plugin-locale-invalid:{plugin.id}:{locale_id}:{resource_path.resolve()}:{exc}",
            message=(
                "插件语言资源无效，已跳过当前 locale。"
                f" plugin_id={plugin.id}"
                f" locale_id={locale_id}"
                f" resource_path={resource_path}"
                f" error={exc}"
            ),
        )
        return None

    if not isinstance(raw_payload, dict):
        error = PluginManifestValidationError(f"语言资源顶层必须是对象: {resource_path}")
        _log_plugin_registry_issue_once(
            issue_key=f"plugin-locale-invalid:{plugin.id}:{locale_id}:{resource_path.resolve()}:{error}",
            message=(
                "插件语言资源无效，已跳过当前 locale。"
                f" plugin_id={plugin.id}"
                f" locale_id={locale_id}"
                f" resource_path={resource_path}"
                f" error={error}"
            ),
        )
        return None

    messages: dict[str, str] = {}
    for key, value in raw_payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            error = PluginManifestValidationError(f"语言资源必须是字符串 key-value: {resource_path}")
            _log_plugin_registry_issue_once(
                issue_key=f"plugin-locale-invalid:{plugin.id}:{locale_id}:{resource_path.resolve()}:{error}",
                message=(
                    "插件语言资源无效，已跳过当前 locale。"
                    f" plugin_id={plugin.id}"
                    f" locale_id={locale_id}"
                    f" resource_path={resource_path}"
                    f" error={error}"
                ),
            )
            return None
        messages[key] = value
    return messages


def load_plugin_manifest(manifest_path: str | Path) -> PluginManifest:
    path = Path(manifest_path)
    if not path.exists():
        raise PluginManifestValidationError(f"manifest 文件不存在: {path}")
    if not path.is_file():
        raise PluginManifestValidationError(f"manifest 路径不是文件: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PluginManifestValidationError(f"manifest JSON 解析失败: {path}: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise PluginManifestValidationError(f"manifest 顶层必须是对象: {path}")

    try:
        return PluginManifest.model_validate(payload)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        error_path = ".".join(str(part) for part in first_error.get("loc", ()))
        error_message = first_error.get("msg", "manifest 校验失败")
        if error_path:
            raise PluginManifestValidationError(f"manifest 校验失败: {path}: {error_path}: {error_message}") from exc
        raise PluginManifestValidationError(f"manifest 校验失败: {path}: {error_message}") from exc


def discover_plugin_manifests(root_dir: str | Path) -> list[PluginManifest]:
    return [manifest for _, manifest in _discover_manifest_entries(root_dir)]


def _build_registry_item_from_manifest(
    manifest_path: str | Path,
    manifest: PluginManifest,
    *,
    base_enabled: bool,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginRegistryItem:
    version_governance_source = "builtin" if source_type == "builtin" else "manual"
    version_governance = resolve_non_market_version_governance(
        source_type=version_governance_source,
        declared_version=manifest.version,
        installed_version=manifest.version,
    )
    item = PluginRegistryItem.model_validate(
        {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "installed_version": version_governance.installed_version,
            "compatibility": manifest.compatibility,
            "update_state": version_governance.update_state,
            "types": manifest.types,
            "permissions": manifest.permissions,
            "risk_level": manifest.risk_level,
            "triggers": manifest.triggers,
            "base_enabled": base_enabled,
            "household_enabled": None,
            "enabled": base_enabled,
            "disabled_reason": None,
            "manifest_path": str(manifest_path),
            "entrypoints": manifest.entrypoints.model_dump(mode="json"),
            "capabilities": manifest.capabilities.model_dump(mode="json"),
            "dashboard_cards": [item.model_dump(mode="json") for item in manifest.dashboard_cards],
            "config_specs": [item.model_dump(mode="json") for item in manifest.config_specs],
            "locales": [item.model_dump(mode="json") for item in manifest.locales],
            "schedule_templates": [item.model_dump(mode="json") for item in manifest.schedule_templates],
            "source_type": source_type,
            "execution_backend": execution_backend,
            "runner_config": runner_config.model_dump(mode="json") if runner_config is not None else None,
            "version_governance": version_governance.model_dump(mode="json"),
        }
    )
    if "ai-provider" in item.types and item.entrypoints.ai_provider is not None:
        from app.modules.ai_gateway.provider_driver import prime_ai_provider_driver_cache

        prime_ai_provider_driver_cache(item)
    return item


def list_registered_plugins(
    root_dir: str | Path | None = None,
    *,
    state_file: str | Path | None = None,
) -> PluginRegistrySnapshot:
    manifest_entries = _discover_registry_manifest_entries(root_dir or BUILTIN_PLUGIN_ROOT)
    state_map = _load_registry_state_map(state_file or REGISTRY_STATE_PATH)
    return PluginRegistrySnapshot(
        items=[
            _build_registry_item_from_manifest(
                manifest_path,
                manifest,
                base_enabled=state_map.get(manifest.id, PluginRegistryStateEntry()).enabled,
            )
            for manifest_path, manifest in manifest_entries
        ]
    )


def _build_runner_config_from_mount(mount: PluginMount) -> PluginRunnerConfig:
    return PluginRunnerConfig(
        plugin_root=mount.plugin_root,
        python_path=mount.python_path,
        working_dir=mount.working_dir,
        timeout_seconds=mount.timeout_seconds,
        stdout_limit_bytes=mount.stdout_limit_bytes,
        stderr_limit_bytes=mount.stderr_limit_bytes,
    )


def _build_registry_item_from_mount(mount: PluginMount, manifest: PluginManifest) -> PluginRegistryItem:
    return _build_registry_item_from_manifest(
        mount.manifest_path,
        manifest,
        base_enabled=mount.enabled,
        source_type=cast(PluginSourceType, mount.source_type),
        execution_backend=cast(PluginExecutionBackend, mount.execution_backend),
        runner_config=_build_runner_config_from_mount(mount),
    )


def _build_disabled_reason(*, base_enabled: bool, household_enabled: bool | None) -> str | None:
    if not base_enabled:
        return "插件基础状态已关闭，当前家庭不能继续启用。"
    if household_enabled is False:
        return "当前家庭已停用该插件。"
    return None


def _apply_marketplace_registry_state(
    item: PluginRegistryItem,
    *,
    instance_id: str,
    install_status: str,
    config_status: str,
    governance: PluginVersionGovernanceRead,
) -> PluginRegistryItem:
    return item.model_copy(
        update={
            "installed_version": governance.installed_version,
            "update_state": governance.update_state,
            "install_status": install_status,
            "config_status": config_status,
            "marketplace_instance_id": instance_id,
            "version_governance": governance,
        }
    )


def _merge_effective_plugin_state(
    item: PluginRegistryItem,
    override: PluginStateOverride | None,
) -> PluginRegistryItem:
    base_enabled = item.base_enabled
    household_enabled = override.enabled if override is not None else None
    enabled = base_enabled and (household_enabled if household_enabled is not None else True)
    disabled_reason = _build_disabled_reason(base_enabled=base_enabled, household_enabled=household_enabled)
    return item.model_copy(
        update={
            "base_enabled": base_enabled,
            "household_enabled": household_enabled,
            "enabled": enabled,
            "disabled_reason": disabled_reason,
        }
    )


def _list_plugin_state_override_map(db: Session, *, household_id: str) -> dict[str, PluginStateOverride]:
    return {
        row.plugin_id: row
        for row in repository.list_plugin_state_overrides(db, household_id=household_id)
    }


def _resolve_plugin_from_snapshot(snapshot: PluginRegistrySnapshot, *, plugin_id: str) -> PluginRegistryItem | None:
    return next((item for item in snapshot.items if item.id == plugin_id), None)


def _apply_execution_overrides(
    plugin: PluginRegistryItem,
    *,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginRegistryItem:
    if source_type == "builtin" and execution_backend is None and runner_config is None:
        return plugin
    return plugin.model_copy(
        update={
            "source_type": source_type,
            "execution_backend": execution_backend,
            "runner_config": runner_config,
        }
    )


def _to_plugin_mount_read(row: PluginMount, *, manifest: PluginManifest | None = None) -> PluginMountRead:
    current_manifest = manifest or load_plugin_manifest(row.manifest_path)
    return PluginMountRead.model_validate(
        {
            "id": row.id,
            "household_id": row.household_id,
            "plugin_id": row.plugin_id,
            "name": current_manifest.name,
            "version": current_manifest.version,
            "types": current_manifest.types,
            "permissions": current_manifest.permissions,
            "risk_level": current_manifest.risk_level,
            "triggers": current_manifest.triggers,
            "entrypoints": current_manifest.entrypoints.model_dump(mode="json"),
            "capabilities": current_manifest.capabilities.model_dump(mode="json"),
            "dashboard_cards": [item.model_dump(mode="json") for item in current_manifest.dashboard_cards],
            "config_specs": [item.model_dump(mode="json") for item in current_manifest.config_specs],
            "locales": [item.model_dump(mode="json") for item in current_manifest.locales],
            "schedule_templates": [item.model_dump(mode="json") for item in current_manifest.schedule_templates],
            "source_type": row.source_type,
            "execution_backend": row.execution_backend,
            "manifest_path": row.manifest_path,
            "plugin_root": row.plugin_root,
            "python_path": row.python_path,
            "working_dir": row.working_dir,
            "timeout_seconds": row.timeout_seconds,
            "stdout_limit_bytes": row.stdout_limit_bytes,
            "stderr_limit_bytes": row.stderr_limit_bytes,
            "enabled": row.enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


def _resolve_manifest_path(plugin_root: str, manifest_path: str | None) -> Path:
    if manifest_path is not None and manifest_path.strip():
        path = Path(manifest_path.strip()).resolve()
    else:
        path = (Path(plugin_root).resolve() / "manifest.json").resolve()
    return path


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _get_plugin_storage_root() -> Path:
    return Path(settings.plugin_storage_root).resolve()


def _copy_plugin_tree(*, source_root: Path, target_root: Path) -> None:
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, target_root)


def _resolve_managed_plugin_root(
    *,
    household_id: str,
    source_type: PluginSourceType,
    source_root: Path,
    manifest: PluginManifest,
) -> Path:
    storage_root = _get_plugin_storage_root()
    if _path_is_within(source_root, storage_root):
        return source_root
    if source_type == "official":
        return (storage_root / "official" / source_root.name).resolve()
    return (storage_root / "third_party" / "manual" / household_id / manifest.id).resolve()


def _map_managed_working_dir(
    *,
    source_root: Path,
    target_root: Path,
    working_dir: str | None,
) -> str | None:
    normalized = _normalize_optional_path(working_dir)
    if normalized is None:
        return None
    working_path = Path(normalized).resolve()
    if not _path_is_within(working_path, source_root):
        return normalized
    relative_working_dir = working_path.relative_to(source_root)
    return str((target_root / relative_working_dir).resolve())


def _prepare_managed_mount_paths(
    *,
    household_id: str,
    payload: PluginMountCreate,
    manifest: PluginManifest,
    manifest_path: Path,
) -> tuple[Path, Path, str | None]:
    source_root = Path(payload.plugin_root).resolve()
    source_manifest_path = manifest_path.resolve()
    target_root = _resolve_managed_plugin_root(
        household_id=household_id,
        source_type=payload.source_type,
        source_root=source_root,
        manifest=manifest,
    )
    if target_root == source_root:
        return source_root, source_manifest_path, _normalize_optional_path(payload.working_dir)
    if not _path_is_within(source_manifest_path, source_root):
        raise PluginManifestValidationError("manifest_path 必须位于 plugin_root 目录内，才能托管到 data/plugins。")
    _copy_plugin_tree(source_root=source_root, target_root=target_root)
    relative_manifest_path = source_manifest_path.relative_to(source_root)
    target_manifest_path = (target_root / relative_manifest_path).resolve()
    target_working_dir = _map_managed_working_dir(
        source_root=source_root,
        target_root=target_root,
        working_dir=payload.working_dir,
    )
    return target_root, target_manifest_path, target_working_dir


def _normalize_optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return str(Path(normalized).resolve())


def _validate_region_provider_mount_conflicts(
    db: Session,
    *,
    household_id: str,
    manifest: PluginManifest,
    skip_plugin_id: str | None,
) -> None:
    spec = get_runtime_region_provider_spec(manifest)
    if spec is None or spec.provider_code is None:
        return

    for mount in repository.list_plugin_mounts(db, household_id=household_id):
        if skip_plugin_id is not None and mount.plugin_id == skip_plugin_id:
            continue
        mounted_manifest = _load_mount_manifest_or_log(
            household_id=household_id,
            mount=mount,
            operation="validate_region_provider_mount_conflicts",
        )
        if mounted_manifest is None:
            continue
        mounted_spec = get_runtime_region_provider_spec(mounted_manifest)
        if mounted_spec is None or mounted_spec.provider_code is None:
            continue
        if mounted_spec.provider_code == spec.provider_code:
            raise PluginManifestValidationError(
                f"家庭 {household_id} 已经挂载地区 provider: {spec.provider_code}"
            )


def list_registered_plugins_for_household(
    db: Session,
    *,
    household_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistrySnapshot:
    from app.modules.plugin_marketplace.service import (
        get_marketplace_instance_for_household_plugin,
        resolve_marketplace_instance_version_governance,
    )

    builtin_snapshot = list_registered_plugins(root_dir=root_dir, state_file=state_file)
    builtin_by_id = {item.id: item for item in builtin_snapshot.items}
    override_map = _list_plugin_state_override_map(db, household_id=household_id)

    mounted_items: list[PluginRegistryItem] = []
    for mount in repository.list_plugin_mounts(db, household_id=household_id):
        manifest = _load_mount_manifest_or_log(
            household_id=household_id,
            mount=mount,
            operation="list_registered_plugins_for_household",
        )
        if manifest is None:
            continue
        if manifest.id in builtin_by_id:
            _log_plugin_registry_issue_once(
                issue_key=f"mounted-manifest-builtin-conflict:{household_id}:{mount.plugin_id}:{manifest.id}",
                message=(
                    "家庭插件 manifest 与内置插件 id 冲突，已跳过挂载插件。"
                    f" household_id={household_id}"
                    f" mount_plugin_id={mount.plugin_id}"
                    f" manifest_id={manifest.id}"
                    f" manifest_path={mount.manifest_path}"
                ),
            )
            continue
        mounted_item = _build_registry_item_from_mount(mount, manifest)
        marketplace_instance = get_marketplace_instance_for_household_plugin(
            db,
            household_id=household_id,
            plugin_id=manifest.id,
        )
        if marketplace_instance is not None:
            governance = resolve_marketplace_instance_version_governance(
                db,
                household_id=household_id,
                plugin_id=manifest.id,
                declared_version=manifest.version,
            )
            mounted_items.append(
                _apply_marketplace_registry_state(
                    mounted_item.model_copy(
                        update={
                            "base_enabled": mount.enabled,
                            "household_enabled": None,
                            "enabled": mount.enabled,
                            "disabled_reason": _build_disabled_reason(
                                base_enabled=mount.enabled,
                                household_enabled=None,
                            ),
                        }
                    ),
                    instance_id=marketplace_instance.id,
                    install_status=marketplace_instance.install_status,
                    config_status=marketplace_instance.config_status,
                    governance=governance,
                )
            )
            continue
        mounted_items.append(
            _merge_effective_plugin_state(
                mounted_item,
                override_map.get(manifest.id),
            )
        )

    builtin_items = [
        _merge_effective_plugin_state(item, override_map.get(item.id))
        for item in builtin_snapshot.items
    ]
    return PluginRegistrySnapshot(items=[*builtin_items, *mounted_items])


def get_household_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    snapshot = list_registered_plugins_for_household(
        db,
        household_id=household_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    plugin = _resolve_plugin_from_snapshot(snapshot, plugin_id=plugin_id)
    if plugin is None:
        raise PluginServiceError(
            f"当前家庭看不到插件 {plugin_id}。",
            error_code=PLUGIN_NOT_VISIBLE_ERROR_CODE,
            field="plugin_id",
            status_code=404,
        )
    return plugin


def require_available_household_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    plugin_type: str | None = None,
    trigger: str | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    plugin = get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    if not plugin.enabled:
        raise PluginExecutionError(
            f"插件 {plugin_id} 已在当前家庭停用，不能继续执行。",
            error_code=PLUGIN_DISABLED_ERROR_CODE,
            field="plugin_id",
            status_code=409,
        )
    if plugin.marketplace_instance_id is not None:
        if plugin.install_status != "installed":
            raise PluginExecutionError(
                f"插件 {plugin_id} 还没有安装完成，不能执行。",
                error_code="plugin_marketplace_not_installed",
                field="plugin_id",
                status_code=409,
            )
        if plugin.config_status != "configured":
            raise PluginExecutionError(
                f"插件 {plugin_id} 还没配置完成，不能执行。",
                error_code="plugin_marketplace_not_configured",
                field="plugin_id",
                status_code=409,
            )
    if plugin_type is not None and plugin_type not in plugin.types:
        raise PluginExecutionError(
            f"插件 {plugin_id} 没有声明 {plugin_type} 能力。",
            error_code="plugin_type_not_supported",
            field="plugin_type",
        )
    if trigger == "schedule" and "schedule" not in plugin.triggers:
        raise PluginExecutionError(
            f"插件 {plugin_id} 不支持计划触发。",
            error_code="plugin_trigger_not_supported",
            field="trigger",
        )
    return plugin


def set_household_plugin_enabled(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginStateUpdateRequest,
    updated_by: str | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    from app.modules.household.service import get_household_or_404
    from app.modules.plugin_marketplace.service import set_marketplace_instance_enabled

    get_household_or_404(db, household_id)
    current = get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    if current.marketplace_instance_id is not None:
        set_marketplace_instance_enabled(
            db,
            household_id=household_id,
            plugin_id=plugin_id,
            payload=payload,
        )
        sync_household_plugin_region_providers(db, household_id)
        return get_household_plugin(
            db,
            household_id=household_id,
            plugin_id=plugin_id,
            root_dir=root_dir,
            state_file=state_file,
        )
    now = utc_now_iso()
    row = repository.get_plugin_state_override(db, household_id=household_id, plugin_id=plugin_id)
    if row is None:
        row = PluginStateOverride(
            id=new_uuid(),
            household_id=household_id,
            plugin_id=plugin_id,
            enabled=payload.enabled,
            source_type=current.source_type,
            updated_by=updated_by,
            created_at=now,
            updated_at=now,
        )
        repository.add_plugin_state_override(db, row)
    else:
        row.enabled = payload.enabled
        row.source_type = current.source_type
        row.updated_by = updated_by
        row.updated_at = now
    db.flush()
    sync_household_plugin_region_providers(db, household_id)
    if payload.enabled:
        integration_capability = current.capabilities.integration
        if integration_capability is not None and integration_capability.auto_create_default_instance:
            from app.modules.integration.service import (
                ensure_default_integration_instance,
                sync_plugin_managed_integration_instance,
            )

            default_instance = ensure_default_integration_instance(
                db,
                household_id=household_id,
                plugin=current,
                updated_by=updated_by,
            )
            if default_instance is not None and not integration_capability.supports_discovery:
                sync_plugin_managed_integration_instance(
                    db,
                    plugin=current,
                    instance=default_instance,
                    sync_scope="device_sync",
                )
    return get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )


def list_plugin_mounts(db: Session, *, household_id: str) -> list[PluginMountRead]:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    items: list[PluginMountRead] = []
    for row in repository.list_plugin_mounts(db, household_id=household_id):
        manifest = _load_mount_manifest_or_log(
            household_id=household_id,
            mount=row,
            operation="list_plugin_mounts",
        )
        if manifest is None:
            continue
        items.append(_to_plugin_mount_read(row, manifest=manifest))
    return items


def list_registered_plugin_locales_for_household(
    db: Session,
    *,
    household_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginLocaleListRead:
    snapshot = list_registered_plugins_for_household(
        db,
        household_id=household_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    items_by_locale_id: dict[str, PluginLocaleRead] = {}

    contributions_by_locale_id: dict[
        str,
        list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]],
    ] = {}
    for plugin, locale_spec, messages in _iter_enabled_plugin_locale_contributions(snapshot):
        contributions_by_locale_id.setdefault(locale_spec.id, []).append((plugin, locale_spec, messages))

    for locale_id, contributions in contributions_by_locale_id.items():
        owner_plugin, owner_locale = _select_locale_owner(contributions)
        merged_messages = _merge_locale_messages(contributions)
        overridden_plugin_ids = _build_overridden_locale_plugin_ids(
            contributions,
            owner_plugin_id=owner_plugin.id,
        )
        items_by_locale_id[locale_id] = PluginLocaleRead(
            plugin_id=owner_plugin.id,
            locale_id=locale_id,
            label=owner_locale.label,
            native_label=owner_locale.native_label,
            fallback=owner_locale.fallback,
            source_type=owner_plugin.source_type,
            messages=merged_messages,
            overridden_plugin_ids=overridden_plugin_ids,
        )

    items = list(items_by_locale_id.values())
    items.sort(key=lambda item: (item.locale_id, -LOCALE_SOURCE_PRIORITY[item.source_type], item.plugin_id))
    return PluginLocaleListRead(household_id=household_id, items=items)


def _iter_enabled_plugin_locale_contributions(
    snapshot: PluginRegistrySnapshot,
) -> list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]]:
    items: list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]] = []
    for plugin in snapshot.items:
        if not plugin.enabled or not plugin.locales:
            continue

        manifest_dir = Path(plugin.manifest_path).resolve().parent
        for locale_spec in plugin.locales:
            resource_path = (manifest_dir / locale_spec.resource).resolve()
            messages = _load_locale_messages_or_log(
                plugin=plugin,
                locale_id=locale_spec.id,
                resource_path=resource_path,
            )
            if messages is None:
                continue
            items.append((plugin, locale_spec, messages))
    return items


def _select_locale_owner(
    contributions: list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]],
) -> tuple[PluginRegistryItem, PluginManifestLocaleSpec]:
    preferred = [item for item in contributions if "locale-pack" in item[0].types]
    candidates = preferred or contributions
    owner_plugin, owner_locale, _ = min(
        candidates,
        key=lambda item: (-LOCALE_SOURCE_PRIORITY[item[0].source_type], item[0].id),
    )
    return owner_plugin, owner_locale


def _merge_locale_messages(
    contributions: list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]],
) -> dict[str, str]:
    ordered = list(contributions)
    ordered.sort(key=lambda item: item[0].id, reverse=True)
    ordered.sort(key=lambda item: LOCALE_SOURCE_PRIORITY[item[0].source_type])

    merged: dict[str, str] = {}
    for _, _, messages in ordered:
        merged.update(messages)
    return merged


def _build_overridden_locale_plugin_ids(
    contributions: list[tuple[PluginRegistryItem, PluginManifestLocaleSpec, dict[str, str]]],
    *,
    owner_plugin_id: str,
) -> list[str]:
    ordered = sorted(
        contributions,
        key=lambda item: (-LOCALE_SOURCE_PRIORITY[item[0].source_type], item[0].id),
    )
    overridden: list[str] = []
    for plugin, _, _ in ordered:
        if plugin.id == owner_plugin_id or plugin.id in overridden:
            continue
        overridden.append(plugin.id)
    return overridden


def list_registered_plugin_themes_for_household(
    db: Session,
    *,
    household_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginThemeRegistrySnapshotRead:
    snapshot = list_registered_plugins_for_household(
        db,
        household_id=household_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    items: list[PluginThemeRegistryItemRead] = []
    for plugin in snapshot.items:
        if "theme-pack" not in plugin.types:
            continue
        spec = plugin.capabilities.theme_pack
        if spec is None:
            continue

        state = "disabled" if not plugin.enabled else "ready"
        if plugin.enabled:
            try:
                _load_theme_resource_tokens(plugin)
            except PluginServiceError:
                state = "invalid"

        items.append(
            PluginThemeRegistryItemRead(
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                source_type=plugin.source_type,
                enabled=plugin.enabled,
                disabled_reason=plugin.disabled_reason,
                state=state,
                theme_id=spec.theme_id,
                display_name=spec.display_name,
                description=spec.description,
                resource_source=_resolve_theme_resource_source(plugin=plugin),
                tokens_resource=spec.tokens_resource,
                resource_version=spec.resource_version,
                theme_schema_version=spec.theme_schema_version,
                platform_targets=spec.platform_targets,
                preview=spec.preview,
                fallback_theme_id=spec.fallback_theme_id,
            )
        )

    items.sort(key=lambda item: (item.theme_id, item.plugin_id))
    return PluginThemeRegistrySnapshotRead(household_id=household_id, items=items)


def get_plugin_theme_resource_for_household(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    theme_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginThemeResourceRead:
    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    spec = plugin.capabilities.theme_pack
    if "theme-pack" not in plugin.types or spec is None:
        raise PluginServiceError(
            f"插件 {plugin_id} 不是主题插件。",
            error_code=PLUGIN_THEME_NOT_FOUND_ERROR_CODE,
            field="plugin_id",
            status_code=404,
        )
    if spec.theme_id != theme_id:
        raise PluginServiceError(
            f"插件 {plugin_id} 不包含主题 {theme_id}。",
            error_code=PLUGIN_THEME_NOT_FOUND_ERROR_CODE,
            field="theme_id",
            status_code=404,
        )
    payload = _load_theme_resource_payload(plugin)
    return PluginThemeResourceRead(
        household_id=household_id,
        plugin_id=plugin.id,
        theme_id=spec.theme_id,
        display_name=spec.display_name,
        description=spec.description,
        preview=spec.preview,
        source_type=plugin.source_type,
        resource_source=_resolve_theme_resource_source(plugin=plugin),
        resource_version=spec.resource_version,
        theme_schema_version=spec.theme_schema_version,
        platform_targets=spec.platform_targets,
        tokens=cast(dict[str, Any], payload["tokens"]),
    )


def _resolve_theme_resource_path(plugin: PluginRegistryItem) -> Path:
    spec = plugin.capabilities.theme_pack
    if spec is None:
        raise PluginServiceError(
            f"插件 {plugin.id} 缺少主题能力声明。",
            error_code=PLUGIN_THEME_RESOURCE_UNAVAILABLE_ERROR_CODE,
            field="plugin_id",
            status_code=404,
        )
    manifest_dir = Path(plugin.manifest_path).resolve().parent
    if spec.tokens_resource is None:
        raise PluginServiceError(
            f"插件 {plugin.id} 缺少 tokens_resource 资源路径。",
            error_code=PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE,
            field="tokens_resource",
            status_code=409,
        )
    resource_path = (manifest_dir / spec.tokens_resource).resolve()
    if not _path_is_within(resource_path, manifest_dir):
        raise PluginServiceError(
            f"插件 {plugin.id} 的主题资源路径越界。",
            error_code=PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE,
            field="tokens_resource",
            status_code=409,
        )
    return resource_path


def _resolve_theme_resource_source(
    *,
    plugin: PluginRegistryItem,
) -> Literal["builtin_bundle", "managed_plugin_dir"]:
    spec = plugin.capabilities.theme_pack
    if spec is not None and spec.resource_source is not None:
        return spec.resource_source
    if plugin.source_type == "builtin":
        return "builtin_bundle"
    return "managed_plugin_dir"


def _load_theme_resource_payload(plugin: PluginRegistryItem) -> dict[str, Any]:
    resource_path = _resolve_theme_resource_path(plugin)
    if not resource_path.exists() or not resource_path.is_file():
        raise PluginServiceError(
            f"插件 {plugin.id} 的主题资源不存在。",
            error_code=PLUGIN_THEME_RESOURCE_UNAVAILABLE_ERROR_CODE,
            field="tokens_resource",
            status_code=404,
        )

    try:
        payload = json.loads(resource_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginServiceError(
            f"插件 {plugin.id} 的主题资源 JSON 解析失败: {exc.msg}",
            error_code=PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE,
            field="tokens_resource",
            status_code=409,
        )

    if not isinstance(payload, dict):
        raise PluginServiceError(
            f"插件 {plugin.id} 的主题资源顶层必须是对象。",
            error_code=PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE,
            field="tokens_resource",
            status_code=409,
        )

    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise PluginServiceError(
            f"插件 {plugin.id} 的主题资源缺少 tokens 对象。",
            error_code=PLUGIN_THEME_RESOURCE_INVALID_ERROR_CODE,
            field="tokens",
            status_code=409,
        )
    return cast(dict[str, Any], payload)


def _load_theme_resource_tokens(plugin: PluginRegistryItem) -> dict[str, Any]:
    payload = _load_theme_resource_payload(plugin)
    return cast(dict[str, Any], payload["tokens"])


def register_plugin_mount(
    db: Session,
    *,
    household_id: str,
    payload: PluginMountCreate,
) -> PluginMountRead:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    manifest_path = _resolve_manifest_path(payload.plugin_root, payload.manifest_path)
    manifest = load_plugin_manifest(manifest_path)
    if manifest.id in {item.id for item in list_registered_plugins().items}:
        raise PluginManifestValidationError(f"插件 id 与内置插件冲突: {manifest.id}")
    if repository.get_plugin_mount(db, household_id=household_id, plugin_id=manifest.id) is not None:
        raise PluginManifestValidationError(f"插件已经挂载: {manifest.id}")
    _validate_region_provider_mount_conflicts(db, household_id=household_id, manifest=manifest, skip_plugin_id=None)
    managed_plugin_root, managed_manifest_path, managed_working_dir = _prepare_managed_mount_paths(
        household_id=household_id,
        payload=payload,
        manifest=manifest,
        manifest_path=manifest_path,
    )

    row = PluginMount(
        id=new_uuid(),
        household_id=household_id,
        plugin_id=manifest.id,
        source_type=payload.source_type,
        execution_backend=payload.execution_backend,
        manifest_path=str(managed_manifest_path),
        plugin_root=str(managed_plugin_root),
        python_path=payload.python_path.strip(),
        working_dir=managed_working_dir,
        timeout_seconds=payload.timeout_seconds,
        stdout_limit_bytes=payload.stdout_limit_bytes,
        stderr_limit_bytes=payload.stderr_limit_bytes,
        enabled=payload.enabled,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    repository.add_plugin_mount(db, row)
    db.flush()
    sync_household_plugin_region_providers(db, household_id)
    return _to_plugin_mount_read(row, manifest=manifest)


def update_plugin_mount(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginMountUpdate,
) -> PluginMountRead:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    row = repository.get_plugin_mount(db, household_id=household_id, plugin_id=plugin_id)
    if row is None:
        raise PluginManifestValidationError(f"插件挂载不存在: {plugin_id}")

    data = payload.model_dump(exclude_unset=True)
    if "source_type" in data and data["source_type"] is not None:
        row.source_type = cast(PluginSourceType, data["source_type"])
    if "python_path" in data and data["python_path"] is not None:
        row.python_path = data["python_path"].strip()
    if "working_dir" in data:
        row.working_dir = _normalize_optional_path(data["working_dir"])
    if "timeout_seconds" in data and data["timeout_seconds"] is not None:
        row.timeout_seconds = data["timeout_seconds"]
    if "stdout_limit_bytes" in data and data["stdout_limit_bytes"] is not None:
        row.stdout_limit_bytes = data["stdout_limit_bytes"]
    if "stderr_limit_bytes" in data and data["stderr_limit_bytes"] is not None:
        row.stderr_limit_bytes = data["stderr_limit_bytes"]
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = data["enabled"]
    row.updated_at = utc_now_iso()
    db.flush()
    manifest = load_plugin_manifest(row.manifest_path)
    _validate_region_provider_mount_conflicts(db, household_id=household_id, manifest=manifest, skip_plugin_id=plugin_id)
    sync_household_plugin_region_providers(db, household_id)
    return _to_plugin_mount_read(row)


def delete_plugin_mount(db: Session, *, household_id: str, plugin_id: str) -> None:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    row = repository.get_plugin_mount(db, household_id=household_id, plugin_id=plugin_id)
    if row is None:
        raise PluginManifestValidationError(f"插件挂载不存在: {plugin_id}")
    repository.delete_plugin_mount(db, row)
    db.flush()
    sync_household_plugin_region_providers(db, household_id)


def _discover_manifest_entries(root_dir: str | Path) -> list[tuple[Path, PluginManifest]]:
    root = Path(root_dir)
    if not root.exists():
        raise PluginManifestValidationError(f"插件目录不存在: {root}")
    if not root.is_dir():
        raise PluginManifestValidationError(f"插件目录路径不是目录: {root}")

    manifest_entries: list[tuple[Path, PluginManifest]] = []
    seen_ids: set[str] = set()
    for manifest_path in sorted(root.glob("**/manifest.json")):
        try:
            manifest = load_plugin_manifest(manifest_path)
        except PluginManifestValidationError as exc:
            _log_plugin_registry_issue_once(
                issue_key=f"builtin-manifest-invalid:{manifest_path.resolve()}:{exc}",
                message=(
                    "插件 manifest 无效，已从注册表发现结果中跳过。"
                    f" manifest_path={manifest_path}"
                    f" error={exc}"
                ),
            )
            continue
        if manifest.id in seen_ids:
            _log_plugin_registry_issue_once(
                issue_key=f"builtin-manifest-duplicate-id:{root.resolve()}:{manifest.id}",
                message=(
                    "发现重复插件 id，已跳过后续 manifest。"
                    f" plugin_id={manifest.id}"
                    f" manifest_path={manifest_path}"
                ),
            )
            continue
        seen_ids.add(manifest.id)
        manifest_entries.append((manifest_path, manifest))
    return manifest_entries


def _discover_registry_manifest_entries(root_dir: str | Path) -> list[tuple[Path, PluginManifest]]:
    return _discover_manifest_entries(root_dir)


def resolve_plugin_execution_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    root_dir: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginExecutionContext:
    if root_dir is not None or execution_backend is not None or runner_config is not None or source_type != "builtin":
        return PluginExecutionContext(
            root_dir=root_dir,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        )

    mount = repository.get_plugin_mount(db, household_id=household_id, plugin_id=plugin_id)
    if mount is None:
        return PluginExecutionContext(
            root_dir=root_dir,
            source_type="builtin",
            execution_backend=None,
            runner_config=None,
        )

    return PluginExecutionContext(
        root_dir=mount.plugin_root,
        source_type=cast(PluginSourceType, mount.source_type),
        execution_backend=cast(PluginExecutionBackend, mount.execution_backend),
        runner_config=_build_runner_config_from_mount(mount),
    )


def _execute_registered_plugin(
    plugin: PluginRegistryItem,
    request: PluginExecutionRequest,
    *,
    runtime_context: dict[str, object] | None = None,
) -> PluginExecutionResult:
    started_at = utc_now_iso()
    run_id = new_uuid()
    try:
        if not plugin.enabled:
            raise PluginExecutionError(
                f"插件 {request.plugin_id} 已在当前家庭停用，不能继续执行。",
                error_code=PLUGIN_DISABLED_ERROR_CODE,
                field="plugin_id",
                status_code=409,
            )

        execution_backend = resolve_execution_backend(plugin, request)
        executor = get_executor(execution_backend)
        runtime_request = PluginExecutionRequest.model_validate(
            {
                **request.model_dump(exclude={"payload", "execution_backend"}),
                "payload": _merge_plugin_payload_with_runtime_context(request.payload, runtime_context),
                "execution_backend": execution_backend,
            }
        )
        output = executor.execute(plugin, runtime_request)
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=execution_backend,
            success=True,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=output,
        )
    except PluginRunnerError as exc:
        execution_backend = request.execution_backend or plugin.execution_backend or "subprocess_runner"
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=exc.error_code,
            error_message=str(exc),
        )
    except PluginServiceError as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=request.execution_backend or plugin.execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=exc.error_code,
            error_message=str(exc),
        )
    except (PluginManifestValidationError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=request.execution_backend or plugin.execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=PLUGIN_EXECUTION_FAILED,
            error_message=str(exc),
        )
    except Exception as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=request.execution_backend or plugin.execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=PLUGIN_EXECUTION_FAILED,
            error_message=str(exc),
        )


def execute_household_plugin(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginExecutionResult:
    try:
        prepared = prepare_household_plugin_execution(
            db,
            household_id=household_id,
            request=request,
            root_dir=root_dir,
            state_file=state_file,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        )
    except PluginServiceError as exc:
        started_at = utc_now_iso()
        return PluginExecutionResult(
            run_id=new_uuid(),
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=exc.error_code,
            error_message=str(exc),
        )

    return execute_prepared_household_plugin(prepared)


def prepare_household_plugin_execution(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PreparedHouseholdPluginExecution:
    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=request.plugin_id,
        plugin_type=request.plugin_type,
        trigger=request.trigger,
        root_dir=root_dir,
        state_file=state_file,
    )
    plugin = _apply_execution_overrides(
        plugin,
        source_type=source_type,
        execution_backend=execution_backend,
        runner_config=runner_config,
    )
    ensure_plugin_private_migrations(db, plugin=plugin)
    return PreparedHouseholdPluginExecution(
        plugin=plugin,
        request=request,
        runtime_context=_build_plugin_runtime_context(
            db,
            household_id=household_id,
            plugin_id=request.plugin_id,
            root_dir=root_dir,
            state_file=state_file,
        ),
    )


def execute_prepared_household_plugin(prepared: PreparedHouseholdPluginExecution) -> PluginExecutionResult:
    return _execute_registered_plugin(
        prepared.plugin,
        prepared.request,
        runtime_context=prepared.runtime_context,
    )


def enqueue_household_plugin_job(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    idempotency_key: str | None = None,
    payload_summary: dict[str, object] | None = None,
    max_attempts: int | None = None,
    source_task_definition_id: str | None = None,
    source_task_run_id: str | None = None,
) -> PluginJobRead:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=request.plugin_id,
        plugin_type=request.plugin_type,
        trigger=request.trigger,
    )

    return create_plugin_job(
        db,
        payload=PluginJobCreate(
            household_id=household_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            trigger=request.trigger,
            request_payload=request.payload,
            payload_summary=payload_summary,
            idempotency_key=idempotency_key,
            source_task_definition_id=source_task_definition_id,
            source_task_run_id=source_task_run_id,
            max_attempts=max_attempts or (1 if request.plugin_type == "action" else max(settings.plugin_job_default_max_attempts, 1)),
        ),
    )


def _build_plugin_runtime_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    root_dir: str | Path | None,
    state_file: str | Path | None,
) -> dict[str, object] | None:
    runtime_context: dict[str, object] = {}
    region_context = resolve_plugin_household_region_context(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    if region_context is not None:
        runtime_context["region"] = {
            "household_context": region_context.model_dump(mode="json"),
            "entry": "region.resolve_household_context",
        }
    return runtime_context or None


def _merge_plugin_payload_with_runtime_context(
    payload: dict[str, object],
    runtime_context: dict[str, object] | None,
) -> dict[str, object]:
    merged_payload = dict(payload)
    if runtime_context is None:
        return merged_payload
    existing_context = merged_payload.get(PLUGIN_SYSTEM_CONTEXT_KEY)
    if isinstance(existing_context, dict):
        merged_payload[PLUGIN_SYSTEM_CONTEXT_KEY] = {
            **existing_context,
            **runtime_context,
        }
    else:
        merged_payload[PLUGIN_SYSTEM_CONTEXT_KEY] = runtime_context
    return merged_payload


def resolve_plugin_household_region_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
):
    plugin = get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )
    if not plugin.capabilities.context_reads.household_region_context:
        return None
    return resolve_household_region_context(db, household_id)


async def aexecute_household_plugin(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginExecutionResult:
    return await _run_plugin_with_isolated_thread_session(
        db,
        lambda thread_db: execute_household_plugin(
            thread_db,
            household_id=household_id,
            request=request,
            root_dir=root_dir,
            state_file=state_file,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        ),
        policy=_build_plugin_blocking_policy(
            label="plugin.aexecute_household_plugin",
            runner_config=runner_config,
        ),
        context={
            "household_id": household_id,
            "plugin_id": request.plugin_id,
            "trigger": request.trigger,
        },
    )


def enable_plugin(
    plugin_id: str,
    *,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    return set_plugin_enabled(plugin_id, enabled=True, root_dir=root_dir, state_file=state_file)


def disable_plugin(
    plugin_id: str,
    *,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    return set_plugin_enabled(plugin_id, enabled=False, root_dir=root_dir, state_file=state_file)


def execute_plugin(
    request: PluginExecutionRequest,
    *,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
    runtime_context: dict[str, object] | None = None,
) -> PluginExecutionResult:
    started_at = utc_now_iso()
    run_id = new_uuid()
    try:
        registry = list_registered_plugins(root_dir=root_dir, state_file=state_file)
        plugin = next((item for item in registry.items if item.id == request.plugin_id), None)
        if plugin is None:
            raise PluginExecutionError(f"插件不存在: {request.plugin_id}")
        plugin = PluginRegistryItem.model_validate(
            {
                **plugin.model_dump(mode="json"),
                "source_type": source_type,
                "execution_backend": execution_backend,
                "runner_config": runner_config.model_dump(mode="json") if runner_config is not None else None,
            }
        )
        if not plugin.enabled:
            raise PluginExecutionError(f"插件已禁用: {request.plugin_id}")

        execution_backend = resolve_execution_backend(plugin, request)
        executor = get_executor(execution_backend)
        runtime_request = PluginExecutionRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "payload": _merge_plugin_payload_with_runtime_context(request.payload, runtime_context),
                "execution_backend": execution_backend,
            }
        )
        output = executor.execute(plugin, runtime_request)
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=execution_backend,
            success=True,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=output,
        )
    except PluginRunnerError as exc:
        execution_backend = request.execution_backend or "subprocess_runner"
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=exc.error_code,
            error_message=str(exc),
        )
    except (PluginManifestValidationError, PluginExecutionError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=request.execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=PLUGIN_EXECUTION_FAILED,
            error_message=str(exc),
        )
    except Exception as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            execution_backend=request.execution_backend,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code=PLUGIN_EXECUTION_FAILED,
            error_message=str(exc),
        )


def save_plugin_raw_records(
    db: Session,
    *,
    household_id: str,
    execution_result: PluginExecutionResult,
    raw_records: list[dict],
) -> list[PluginRawRecordRead]:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    saved_rows: list[PluginRawRecordRead] = []

    for raw_record in raw_records:
        payload = raw_record if isinstance(raw_record, dict) else {"value": raw_record}
        create_payload = PluginRawRecordCreate(
            household_id=household_id,
            plugin_id=execution_result.plugin_id,
            run_id=execution_result.run_id,
            trigger=execution_result.trigger,
            record_type=_resolve_record_type(payload),
            source_ref=_resolve_source_ref(payload),
            payload=payload,
            captured_at=_resolve_captured_at(payload),
        )
        row = PluginRawRecord(
            id=new_uuid(),
            household_id=create_payload.household_id,
            plugin_id=create_payload.plugin_id,
            run_id=create_payload.run_id,
            trigger=create_payload.trigger,
            record_type=create_payload.record_type,
            source_ref=create_payload.source_ref,
            payload_json=dump_json(create_payload.payload) or "{}",
            captured_at=create_payload.captured_at or utc_now_iso(),
            created_at=utc_now_iso(),
        )
        repository.add_plugin_raw_record(db, row)
        db.flush()
        saved_rows.append(_to_plugin_raw_record_read(row))

    return saved_rows


def list_saved_plugin_raw_records(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    run_id: str | None = None,
) -> list[PluginRawRecordRead]:
    rows = repository.list_plugin_raw_records(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        run_id=run_id,
    )
    return [_to_plugin_raw_record_read(row) for row in rows]


def ingest_plugin_raw_records_to_memory(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    run_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> list[dict]:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    raw_records = list_saved_plugin_raw_records(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        run_id=run_id,
    )
    if not raw_records:
        return []

    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        plugin_type="integration",
        root_dir=root_dir,
        state_file=state_file,
    )
    plugin = _apply_execution_overrides(
        plugin,
        source_type=source_type,
        execution_backend=execution_backend,
        runner_config=runner_config,
    )

    transform = _load_plugin_observation_transform(plugin)
    if transform is None:
        return []

    try:
        observation_candidates = transform(
            {
                "records": [item.model_dump(mode="json") for item in raw_records],
            }
        )
    except (ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        raise PluginExecutionError(str(exc)) from exc

    if not isinstance(observation_candidates, list):
        raise PluginExecutionError("observation transform 必须返回列表")

    written_cards = []
    for observation in observation_candidates:
        if not isinstance(observation, dict):
            raise PluginExecutionError("observation transform 返回项必须是对象")
        source_raw_record_id = observation.get("source_record_ref")
        if not isinstance(source_raw_record_id, str) or not source_raw_record_id.strip():
            raise PluginExecutionError("Observation 缺少 source_record_ref")
        subject_member_id = observation.get("subject_id") if observation.get("subject_type") == "Person" else None
        card = upsert_plugin_observation_memory(
            db,
            household_id=household_id,
            subject_member_id=subject_member_id if isinstance(subject_member_id, str) else None,
            source_plugin_id=plugin_id,
            source_raw_record_id=source_raw_record_id,
            observation=observation,
        )
        knowledge_document = upsert_knowledge_document_from_observation(
            db,
            household_id=household_id,
            subject_member_id=subject_member_id if isinstance(subject_member_id, str) else None,
            source_plugin_id=plugin_id,
            source_raw_record_id=source_raw_record_id,
            observation=observation,
        )
        payload = card.model_dump(mode="json")
        payload["knowledge_document_id"] = knowledge_document.id
        written_cards.append(payload)
    return written_cards


def _load_plugin_observation_transform(plugin: PluginRegistryItem):
    integration_entrypoint = plugin.entrypoints.integration
    if integration_entrypoint is None:
        return None
    module_path, separator, _ = integration_entrypoint.rpartition(".")
    if not separator or not module_path:
        return None
    package_path, package_separator, _ = module_path.rpartition(".")
    if not package_separator or not package_path:
        return None
    try:
        with _plugin_runtime_import_path(plugin):
            return load_entrypoint_callable(f"{package_path}.ingestor.transform")
    except (ModuleNotFoundError, AttributeError, TypeError, ValueError):
        return None


@contextmanager
def _plugin_runtime_import_path(plugin: PluginRegistryItem):
    plugin_root = plugin.runner_config.plugin_root if plugin.runner_config is not None else None
    if not plugin_root:
        yield
        return

    resolved_root = Path(plugin_root).resolve()
    candidate_paths = [str(resolved_root.parent), str(resolved_root)]
    inserted_paths: list[str] = []
    for candidate in candidate_paths:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            inserted_paths.append(candidate)
    try:
        yield
    finally:
        for candidate in reversed(inserted_paths):
            try:
                sys.path.remove(candidate)
            except ValueError:
                continue


def _sync_plugin_dashboard_cards(
    db: Session,
    *,
    household_id: str,
    execution: PluginExecutionResult,
) -> int:
    from .dashboard_service import (
        record_plugin_dashboard_card_snapshot_error,
        upsert_plugin_dashboard_card_snapshot,
    )
    from .schemas import (
        PluginDashboardCardSnapshotErrorUpsert,
        PluginDashboardCardSnapshotUpsert,
    )

    try:
        plugin = get_household_plugin(db, household_id=household_id, plugin_id=execution.plugin_id)
    except PluginServiceError:
        return 0
    if not plugin.dashboard_cards:
        return 0

    output = execution.output if isinstance(execution.output, dict) else {}
    raw_snapshots = output.get("dashboard_snapshots")
    if raw_snapshots is None:
        return 0

    if not isinstance(raw_snapshots, list):
        for card_spec in plugin.dashboard_cards:
            record_plugin_dashboard_card_snapshot_error(
                db,
                household_id=household_id,
                plugin_id=execution.plugin_id,
                payload=PluginDashboardCardSnapshotErrorUpsert(
                    card_key=card_spec.card_key,
                    error_code="plugin_dashboard_snapshot_invalid",
                    error_message="插件返回的 dashboard_snapshots 不是数组，首页卡片已降级。",
                ),
            )
        return 0

    written_count = 0
    for raw_item in raw_snapshots:
        if not isinstance(raw_item, dict):
            continue

        raw_card_key = raw_item.get("card_key")
        if not isinstance(raw_card_key, str) or not raw_card_key.strip():
            continue

        try:
            snapshot_payload = PluginDashboardCardSnapshotUpsert.model_validate(raw_item)
            upsert_plugin_dashboard_card_snapshot(
                db,
                household_id=household_id,
                plugin_id=execution.plugin_id,
                payload=snapshot_payload,
            )
            written_count += 1
        except (ValidationError, PluginServiceError) as exc:
            record_plugin_dashboard_card_snapshot_error(
                db,
                household_id=household_id,
                plugin_id=execution.plugin_id,
                payload=PluginDashboardCardSnapshotErrorUpsert(
                    card_key=raw_card_key,
                    error_code="plugin_dashboard_snapshot_invalid",
                    error_message=str(exc),
                ),
            )

    return written_count


def _record_plugin_dashboard_cards_execution_error(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    error_code: str,
    error_message: str,
) -> None:
    from .dashboard_service import record_plugin_dashboard_card_snapshot_error
    from .schemas import PluginDashboardCardSnapshotErrorUpsert

    try:
        plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    except PluginServiceError:
        return
    if not plugin.dashboard_cards:
        return

    for card_spec in plugin.dashboard_cards:
        record_plugin_dashboard_card_snapshot_error(
            db,
            household_id=household_id,
            plugin_id=plugin_id,
            payload=PluginDashboardCardSnapshotErrorUpsert(
                card_key=card_spec.card_key,
                error_code=error_code,
                error_message=error_message,
            ),
        )


def run_plugin_sync_pipeline(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginSyncPipelineResult:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=request,
        root_dir=root_dir,
        state_file=state_file,
        source_type=source_type,
        execution_backend=execution_backend,
        runner_config=runner_config,
    )
    run_row = PluginRun(
        id=execution.run_id,
        household_id=household_id,
        plugin_id=execution.plugin_id,
        plugin_type=request.plugin_type,
        trigger=execution.trigger,
        status="running" if execution.success else "failed",
        raw_record_count=0,
        memory_card_count=0,
        error_code=execution.error_code,
        error_message=execution.error_message,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        created_at=utc_now_iso(),
    )
    repository.add_plugin_run(db, run_row)
    db.flush()

    raw_records: list[PluginRawRecordRead] = []
    written_memory_cards: list[dict] = []
    dashboard_card_count = 0

    if execution.success:
        output = execution.output if isinstance(execution.output, dict) else {}
        raw_records = save_plugin_raw_records(
            db,
            household_id=household_id,
            execution_result=execution,
            raw_records=output.get("records", []),
        )
        written_memory_cards = ingest_plugin_raw_records_to_memory(
            db,
            household_id=household_id,
            plugin_id=execution.plugin_id,
            run_id=execution.run_id,
            root_dir=root_dir,
            state_file=state_file,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        )
        dashboard_card_count = _sync_plugin_dashboard_cards(
            db,
            household_id=household_id,
            execution=execution,
        )
        run_row.status = "success"
        run_row.raw_record_count = len(raw_records)
        run_row.memory_card_count = len(written_memory_cards)
        run_row.error_code = None
        run_row.error_message = None
    else:
        _record_plugin_dashboard_cards_execution_error(
            db,
            household_id=household_id,
            plugin_id=execution.plugin_id,
            error_code=execution.error_code or "plugin_execution_failed",
            error_message=execution.error_message or "插件执行失败，首页卡片已降级。",
        )
        run_row.status = "failed"

    run_row.finished_at = execution.finished_at
    db.add(run_row)

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="plugin.run_sync_pipeline",
        target_type="plugin_run",
        target_id=run_row.id,
        result="success" if run_row.status == "success" else "fail",
        details={
            "plugin_id": execution.plugin_id,
            "plugin_type": request.plugin_type,
            "trigger": execution.trigger,
            "raw_record_count": run_row.raw_record_count,
            "memory_card_count": run_row.memory_card_count,
            "dashboard_card_count": dashboard_card_count,
            "error_code": run_row.error_code,
            "error_message": run_row.error_message,
        },
    )
    db.flush()

    return PluginSyncPipelineResult(
        run=_to_plugin_run_read(run_row),
        execution=execution,
        raw_records=raw_records,
        written_memory_cards=written_memory_cards,
    )


async def arun_plugin_sync_pipeline(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
    source_type: PluginSourceType = "builtin",
    execution_backend: PluginExecutionBackend | None = None,
    runner_config: PluginRunnerConfig | None = None,
) -> PluginSyncPipelineResult:
    from app.modules.household.service import get_household_or_404
    get_household_or_404(db, household_id)
    execution = await _run_plugin_with_isolated_thread_session(
        db,
        lambda thread_db: execute_household_plugin(
            thread_db,
            household_id=household_id,
            request=request,
            root_dir=root_dir,
            state_file=state_file,
            source_type=source_type,
            execution_backend=execution_backend,
            runner_config=runner_config,
        ),
        policy=_build_plugin_blocking_policy(
            label="plugin.arun_plugin_sync_pipeline",
            runner_config=runner_config,
        ),
        context={
            "household_id": household_id,
            "plugin_id": request.plugin_id,
            "trigger": request.trigger,
        },
    )
    run_row = PluginRun(
        id=execution.run_id,
        household_id=household_id,
        plugin_id=execution.plugin_id,
        plugin_type=request.plugin_type,
        trigger=execution.trigger,
        status="running" if execution.success else "failed",
        raw_record_count=0,
        memory_card_count=0,
        error_code=execution.error_code,
        error_message=execution.error_message,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        created_at=utc_now_iso(),
    )
    repository.add_plugin_run(db, run_row)
    db.flush()
    raw_records: list[PluginRawRecordRead] = []
    written_memory_cards: list[dict] = []
    dashboard_card_count = 0
    if execution.success:
        output = execution.output if isinstance(execution.output, dict) else {}
        raw_records = save_plugin_raw_records(db, household_id=household_id, execution_result=execution, raw_records=output.get("records", []))
        if raw_records:
            written_memory_cards = ingest_plugin_raw_records_to_memory(
                db,
                household_id=household_id,
                plugin_id=execution.plugin_id,
                run_id=execution.run_id,
                root_dir=root_dir,
                state_file=state_file,
                source_type=source_type,
                execution_backend=execution_backend,
                runner_config=runner_config,
            )
        dashboard_card_count = _sync_plugin_dashboard_cards(
            db,
            household_id=household_id,
            execution=execution,
        )
        run_row.status = "success"
        run_row.raw_record_count = len(raw_records)
        run_row.memory_card_count = len(written_memory_cards)
        run_row.error_code = None
        run_row.error_message = None
    else:
        _record_plugin_dashboard_cards_execution_error(
            db,
            household_id=household_id,
            plugin_id=execution.plugin_id,
            error_code=execution.error_code or "plugin_execution_failed",
            error_message=execution.error_message or "插件执行失败，首页卡片已降级。",
        )
        run_row.status = "failed"
    db.flush()
    if actor is not None:
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="plugin.sync_pipeline.run",
            target_type="plugin",
            target_id=request.plugin_id,
            result="success" if run_row.status == "success" else "fail",
            details={
                "run_id": run_row.id,
                "plugin_type": request.plugin_type,
                "raw_record_count": run_row.raw_record_count,
                "memory_card_count": run_row.memory_card_count,
                "dashboard_card_count": dashboard_card_count,
            },
        )
    return PluginSyncPipelineResult(run=_to_plugin_run_read(run_row), execution=execution, raw_records=raw_records, written_memory_cards=written_memory_cards)


def set_plugin_enabled(
    plugin_id: str,
    *,
    enabled: bool,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginRegistryItem:
    normalized_plugin_id = plugin_id.strip()
    if not normalized_plugin_id:
        raise PluginManifestValidationError("plugin_id 不能为空")

    root = Path(root_dir or BUILTIN_PLUGIN_ROOT)
    registry = list_registered_plugins(root, state_file=state_file)
    target = next((item for item in registry.items if item.id == normalized_plugin_id), None)
    if target is None:
        raise PluginManifestValidationError(f"插件不存在，无法更新状态: {normalized_plugin_id}")

    state_path = Path(state_file or REGISTRY_STATE_PATH)
    state_map = _load_registry_state_map(state_path)
    state_map[normalized_plugin_id] = PluginRegistryStateEntry(enabled=enabled, updated_at=utc_now_iso())
    _save_registry_state_map(state_path, state_map)

    return target.model_copy(update={"enabled": enabled})


def _to_plugin_raw_record_read(row: PluginRawRecord) -> PluginRawRecordRead:
    return PluginRawRecordRead(
        id=row.id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        run_id=row.run_id,
        trigger=row.trigger,
        record_type=row.record_type,
        source_ref=row.source_ref,
        payload=load_json(row.payload_json),
        captured_at=row.captured_at,
        created_at=row.created_at,
    )


def _to_plugin_run_read(row: PluginRun) -> PluginRunRead:
    return PluginRunRead.model_validate(
        {
            "id": row.id,
            "household_id": row.household_id,
            "plugin_id": row.plugin_id,
            "plugin_type": row.plugin_type,
            "trigger": row.trigger,
            "status": row.status,
            "raw_record_count": row.raw_record_count,
            "memory_card_count": row.memory_card_count,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "created_at": row.created_at,
        }
    )


def _build_thread_session_factory(db: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        future=True,
        class_=Session,
    )


async def _run_plugin_with_isolated_thread_session(
    db: Session,
    callback: Any,
    *,
    policy: BlockingCallPolicy,
    context: dict[str, Any],
) -> Any:
    database_url = _build_thread_database_url(db)

    def _run_in_thread() -> Any:
        if database_url is None:
            with _build_thread_session_factory(db)() as thread_db:
                try:
                    return callback(thread_db)
                except Exception:
                    thread_db.rollback()
                    raise

        engine = build_database_engine(database_url)
        session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            future=True,
            class_=Session,
        )
        try:
            with session_factory() as thread_db:
                try:
                    return callback(thread_db)
                except Exception:
                    thread_db.rollback()
                    raise
        finally:
            engine.dispose()

    return await run_blocking(
        _run_in_thread,
        policy=policy,
        executor=PLUGIN_EXECUTOR_POOL,
        logger=logger,
        context=context,
    )


def _build_thread_database_url(db: Session) -> str | None:
    bind = db.get_bind()
    if hasattr(bind, "url"):
        return _render_database_url(bind.url)
    engine = getattr(bind, "engine", None)
    if engine is not None and hasattr(engine, "url"):
        return _render_database_url(engine.url)
    return None


def _render_database_url(url: Any) -> str:
    if hasattr(url, "render_as_string"):
        return url.render_as_string(hide_password=False)
    return str(url)


def _build_plugin_blocking_policy(
    *,
    label: str,
    runner_config: PluginRunnerConfig | None,
) -> BlockingCallPolicy:
    timeout_seconds = float(
        runner_config.timeout_seconds
        if runner_config is not None and runner_config.timeout_seconds is not None
        else settings.plugin_job_default_timeout_seconds
    )
    return BlockingCallPolicy(
        label=label,
        kind="plugin_code",
        timeout_seconds=timeout_seconds,
    )


def _resolve_record_type(payload: dict) -> str:
    for key in ("record_type", "type", "category"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "raw"


def _resolve_source_ref(payload: dict) -> str | None:
    for key in ("source_ref", "external_member_id", "external_device_id", "device", "member_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_captured_at(payload: dict) -> str | None:
    for key in ("captured_at", "observed_at", "occurred_at", "date"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _load_registry_state_map(state_file: str | Path) -> dict[str, PluginRegistryStateEntry]:
    path = Path(state_file)
    if not path.exists():
        return {}
    if not path.is_file():
        raise PluginManifestValidationError(f"插件状态路径不是文件: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginManifestValidationError(f"插件状态文件解析失败: {path}: {exc.msg}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise PluginManifestValidationError(f"插件状态文件顶层必须是对象: {path}")

    plugin_items = payload.get("plugins", {})
    if not isinstance(plugin_items, dict):
        raise PluginManifestValidationError(f"插件状态文件中的 plugins 字段必须是对象: {path}")

    state_map: dict[str, PluginRegistryStateEntry] = {}
    for plugin_id, raw_state in plugin_items.items():
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            raise PluginManifestValidationError(f"插件状态文件里存在非法插件 id: {path}")
        try:
            state_map[plugin_id.strip()] = PluginRegistryStateEntry.model_validate(raw_state)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            error_path = ".".join(str(part) for part in first_error.get("loc", ()))
            message = first_error.get("msg", "插件状态校验失败")
            raise PluginManifestValidationError(
                f"插件状态校验失败: {path}: {plugin_id}: {error_path}: {message}"
            ) from exc
    return state_map


def _save_registry_state_map(state_file: str | Path, state_map: dict[str, PluginRegistryStateEntry]) -> None:
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "plugins": {
            plugin_id: entry.model_dump(mode="json")
            for plugin_id, entry in sorted(state_map.items())
        }
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
