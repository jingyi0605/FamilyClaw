from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

from pydantic import ValidationError

from app.core.config import BASE_DIR
from app.db.utils import utc_now_iso
from app.modules.plugin.schemas import PluginManifest
from app.modules.plugin.schemas import PluginType
from app.modules.plugin.schemas import PluginRegistryItem, PluginRegistrySnapshot, PluginRegistryStateEntry
from app.modules.plugin.schemas import PluginExecutionRequest, PluginExecutionResult


BUILTIN_PLUGIN_ROOT = BASE_DIR / "app" / "plugins" / "builtin"
REGISTRY_STATE_PATH = BASE_DIR / "data" / "plugin_registry_state.json"


class PluginManifestValidationError(ValueError):
    pass


class PluginExecutionError(RuntimeError):
    pass


def load_plugin_manifest(manifest_path: str | Path) -> PluginManifest:
    path = Path(manifest_path)
    if not path.exists():
        raise PluginManifestValidationError(f"manifest 文件不存在: {path}")
    if not path.is_file():
        raise PluginManifestValidationError(f"manifest 路径不是文件: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def list_registered_plugins(
    root_dir: str | Path | None = None,
    *,
    state_file: str | Path | None = None,
) -> PluginRegistrySnapshot:
    manifest_entries = _discover_manifest_entries(root_dir or BUILTIN_PLUGIN_ROOT)
    state_map = _load_registry_state_map(state_file or REGISTRY_STATE_PATH)
    return PluginRegistrySnapshot(
        items=[
            PluginRegistryItem(
                id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                types=manifest.types,
                permissions=manifest.permissions,
                risk_level=manifest.risk_level,
                triggers=manifest.triggers,
                enabled=state_map.get(manifest.id, PluginRegistryStateEntry()).enabled,
                manifest_path=str(manifest_path),
                entrypoints=manifest.entrypoints,
            )
            for manifest_path, manifest in manifest_entries
        ]
    )


def _discover_manifest_entries(root_dir: str | Path) -> list[tuple[Path, PluginManifest]]:
    root = Path(root_dir)
    if not root.exists():
        raise PluginManifestValidationError(f"插件目录不存在: {root}")
    if not root.is_dir():
        raise PluginManifestValidationError(f"插件目录路径不是目录: {root}")

    manifest_entries: list[tuple[Path, PluginManifest]] = []
    seen_ids: set[str] = set()
    for manifest_path in sorted(root.glob("**/manifest.json")):
        manifest = load_plugin_manifest(manifest_path)
        if manifest.id in seen_ids:
            raise PluginManifestValidationError(f"发现重复插件 id: {manifest.id}")
        seen_ids.add(manifest.id)
        manifest_entries.append((manifest_path, manifest))
    return manifest_entries


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
) -> PluginExecutionResult:
    started_at = utc_now_iso()
    try:
        registry = list_registered_plugins(root_dir=root_dir, state_file=state_file)
        plugin = next((item for item in registry.items if item.id == request.plugin_id), None)
        if plugin is None:
            raise PluginExecutionError(f"插件不存在: {request.plugin_id}")
        if not plugin.enabled:
            raise PluginExecutionError(f"插件已禁用: {request.plugin_id}")

        entrypoint_path = _get_entrypoint_path(plugin, request.plugin_type)
        handler = _load_entrypoint_callable(entrypoint_path)
        output = handler(request.payload)
        return PluginExecutionResult(
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            success=True,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=output,
        )
    except (PluginManifestValidationError, PluginExecutionError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        return PluginExecutionResult(
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code="plugin_execution_failed",
            error_message=str(exc),
        )
    except Exception as exc:
        return PluginExecutionResult(
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code="plugin_execution_failed",
            error_message=str(exc),
        )


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


def _get_entrypoint_path(plugin: PluginRegistryItem, plugin_type: PluginType) -> str:
    if plugin_type == "connector":
        entrypoint_key = "connector"
    elif plugin_type == "memory-ingestor":
        entrypoint_key = "memory_ingestor"
    elif plugin_type == "action":
        entrypoint_key = "action"
    else:
        entrypoint_key = "agent_skill"
    entrypoint_path = getattr(plugin.entrypoints, entrypoint_key)
    if entrypoint_path is None:
        raise PluginExecutionError(f"插件 {plugin.id} 没有声明 {plugin_type} 入口")
    return entrypoint_path


def _load_entrypoint_callable(entrypoint_path: str):
    module_path, separator, function_name = entrypoint_path.rpartition(".")
    if not separator or not module_path or not function_name:
        raise PluginExecutionError(f"插件入口格式不合法: {entrypoint_path}")

    module = import_module(module_path)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise PluginExecutionError(f"插件入口不可调用: {entrypoint_path}")
    return handler


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
