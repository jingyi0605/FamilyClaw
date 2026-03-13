from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RunnerExecutionRequest(BaseModel):
    plugin_id: str
    plugin_type: str
    entrypoint: str
    payload: dict
    trigger: str
    plugin_root: str | None = None


class RunnerExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    output: dict | list | str | int | float | bool | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str
    finished_at: str


def load_entrypoint(entrypoint: str):
    module_path, separator, function_name = entrypoint.rpartition(".")
    if not separator or not module_path or not function_name:
        raise ValueError(f"插件入口格式不合法: {entrypoint}")

    module = import_module(module_path)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise ValueError(f"插件入口不可调用: {entrypoint}")
    return handler


def apply_plugin_root(plugin_root: str | None) -> None:
    if not plugin_root:
        return
    resolved = str(Path(plugin_root).resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def main() -> int:
    payload = json.load(sys.stdin)
    request = RunnerExecutionRequest.model_validate(payload)
    apply_plugin_root(request.plugin_root)
    handler = load_entrypoint(request.entrypoint)
    output = handler(request.payload)
    sys.stdout.write(json.dumps(output, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
