from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.core.config import BASE_DIR
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.audit.service import write_audit_log
from app.modules.household.service import get_household_or_404
from app.modules.memory.service import upsert_plugin_observation_memory
from app.modules.plugin import repository
from app.modules.plugin.models import PluginRawRecord, PluginRun
from app.modules.plugin.schemas import PluginManifest
from app.modules.plugin.schemas import PluginType
from app.modules.plugin.schemas import PluginRegistryItem, PluginRegistrySnapshot, PluginRegistryStateEntry
from app.modules.plugin.schemas import (
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginRawRecordCreate,
    PluginRawRecordRead,
    PluginRunRead,
    PluginSyncPipelineResult,
)


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
    run_id = new_uuid()
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
            run_id=run_id,
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
            run_id=run_id,
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
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code="plugin_execution_failed",
            error_message=str(exc),
        )


def save_plugin_raw_records(
    db: Session,
    *,
    household_id: str,
    execution_result: PluginExecutionResult,
    raw_records: list[dict],
) -> list[PluginRawRecordRead]:
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
) -> list[dict]:
    get_household_or_404(db, household_id)
    raw_records = list_saved_plugin_raw_records(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        run_id=run_id,
    )
    if not raw_records:
        return []

    registry = list_registered_plugins(root_dir=root_dir, state_file=state_file)
    plugin = next((item for item in registry.items if item.id == plugin_id), None)
    if plugin is None:
        raise PluginExecutionError(f"插件不存在: {plugin_id}")
    if not plugin.enabled:
        raise PluginExecutionError(f"插件已禁用: {plugin_id}")

    entrypoint_path = _get_entrypoint_path(plugin, "memory-ingestor")
    handler = _load_entrypoint_callable(entrypoint_path)
    observation_candidates = handler(
        {
            "records": [item.model_dump(mode="json") for item in raw_records],
        }
    )
    if not isinstance(observation_candidates, list):
        raise PluginExecutionError("memory-ingestor 必须返回列表")

    written_cards = []
    for observation in observation_candidates:
        if not isinstance(observation, dict):
            raise PluginExecutionError("memory-ingestor 返回项必须是对象")
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
        written_cards.append(card.model_dump(mode="json"))
    return written_cards


def run_plugin_sync_pipeline(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginSyncPipelineResult:
    get_household_or_404(db, household_id)

    execution = execute_plugin(request, root_dir=root_dir, state_file=state_file)
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
        )
        run_row.status = "success"
        run_row.raw_record_count = len(raw_records)
        run_row.memory_card_count = len(written_memory_cards)
        run_row.error_code = None
        run_row.error_message = None
    else:
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
    return PluginRunRead(
        id=row.id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        plugin_type=row.plugin_type,
        trigger=row.trigger,
        status=row.status,
        raw_record_count=row.raw_record_count,
        memory_card_count=row.memory_card_count,
        error_code=row.error_code,
        error_message=row.error_message,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
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
