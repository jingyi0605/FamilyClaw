from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from importlib import import_module
from pathlib import Path
from typing import cast

from app.core.config import BASE_DIR
from app.modules.plugin.runner_errors import (
    PLUGIN_RUNNER_DEPENDENCY_MISSING,
    PLUGIN_RUNNER_INVALID_OUTPUT,
    PLUGIN_RUNNER_NOT_CONFIGURED,
    PLUGIN_RUNNER_START_FAILED,
    PLUGIN_RUNNER_TIMEOUT,
    PluginRunnerError,
)
from app.modules.plugin.runner_protocol import RunnerExecutionRequest
from app.modules.plugin.schemas import ENTRYPOINT_KEY_BY_TYPE
from app.modules.plugin.schemas import PluginExecutionBackend, PluginExecutionRequest, PluginRegistryItem, PluginType


RUNNER_MODULE = "app.modules.plugin.runner_protocol"


class PluginExecutor(ABC):
    backend: PluginExecutionBackend

    @abstractmethod
    def execute(self, plugin: PluginRegistryItem, request: PluginExecutionRequest):
        raise NotImplementedError


class InProcessPluginExecutor(PluginExecutor):
    backend: PluginExecutionBackend = "in_process"

    def execute(self, plugin: PluginRegistryItem, request: PluginExecutionRequest):
        entrypoint_path = get_entrypoint_path(plugin, request.plugin_type)
        handler = load_entrypoint_callable(entrypoint_path)
        return handler(request.payload)


class SubprocessRunnerPluginExecutor(PluginExecutor):
    backend: PluginExecutionBackend = "subprocess_runner"

    def execute(self, plugin: PluginRegistryItem, request: PluginExecutionRequest):
        runner_config = plugin.runner_config
        if runner_config is None:
            raise PluginRunnerError(PLUGIN_RUNNER_NOT_CONFIGURED, f"插件 {plugin.id} 没有配置 runner")
        if not runner_config.python_path:
            raise PluginRunnerError(PLUGIN_RUNNER_NOT_CONFIGURED, f"插件 {plugin.id} 缺少 runner Python 路径")
        if not runner_config.plugin_root:
            raise PluginRunnerError(PLUGIN_RUNNER_NOT_CONFIGURED, f"插件 {plugin.id} 缺少第三方插件目录")

        entrypoint_path = get_entrypoint_path(plugin, request.plugin_type)
        runner_request = RunnerExecutionRequest(
            plugin_id=plugin.id,
            plugin_type=request.plugin_type,
            entrypoint=entrypoint_path,
            payload=request.payload,
            trigger=request.trigger,
            plugin_root=runner_config.plugin_root,
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = _build_pythonpath(runner_config.plugin_root)
        command = [runner_config.python_path, "-m", RUNNER_MODULE]
        cwd = runner_config.working_dir or runner_config.plugin_root

        try:
            completed = subprocess.run(
                command,
                input=runner_request.model_dump_json(),
                text=True,
                capture_output=True,
                timeout=runner_config.timeout_seconds,
                cwd=cwd,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            raise PluginRunnerError(PLUGIN_RUNNER_START_FAILED, f"runner 启动失败: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise PluginRunnerError(PLUGIN_RUNNER_TIMEOUT, f"runner 执行超时: {plugin.id}") from exc
        except OSError as exc:
            raise PluginRunnerError(PLUGIN_RUNNER_START_FAILED, f"runner 启动失败: {exc}") from exc

        stdout = _trim_output(completed.stdout, runner_config.stdout_limit_bytes)
        stderr = _trim_output(completed.stderr, runner_config.stderr_limit_bytes)
        if completed.returncode != 0:
            error_code = PLUGIN_RUNNER_START_FAILED
            if "ModuleNotFoundError" in stderr or "No module named" in stderr:
                error_code = PLUGIN_RUNNER_DEPENDENCY_MISSING
            message = stderr or stdout or f"runner 执行失败，退出码: {completed.returncode}"
            raise PluginRunnerError(error_code, message)

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise PluginRunnerError(PLUGIN_RUNNER_INVALID_OUTPUT, f"runner 返回了非法 JSON: {exc.msg}") from exc


def get_executor(backend: PluginExecutionBackend) -> PluginExecutor:
    if backend == "in_process":
        return InProcessPluginExecutor()
    return SubprocessRunnerPluginExecutor()


def resolve_execution_backend(plugin: PluginRegistryItem, request: PluginExecutionRequest) -> PluginExecutionBackend:
    if request.execution_backend is not None:
        return request.execution_backend
    if plugin.execution_backend is not None:
        return plugin.execution_backend
    if plugin.source_type == "builtin":
        return "in_process"
    return "subprocess_runner"


def get_entrypoint_path(plugin: PluginRegistryItem, plugin_type: PluginType) -> str:
    entrypoint_key = ENTRYPOINT_KEY_BY_TYPE[cast(PluginType, plugin_type)]
    entrypoint_path = getattr(plugin.entrypoints, entrypoint_key)
    if entrypoint_path is None:
        raise ValueError(f"插件 {plugin.id} 没有声明 {plugin_type} 入口")
    return entrypoint_path


def load_entrypoint_callable(entrypoint_path: str):
    module_path, separator, function_name = entrypoint_path.rpartition(".")
    if not separator or not module_path or not function_name:
        raise ValueError(f"插件入口格式不合法: {entrypoint_path}")

    module = import_module(module_path)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise ValueError(f"插件入口不可调用: {entrypoint_path}")
    return handler


def _build_pythonpath(plugin_root: str) -> str:
    path_items = [str(BASE_DIR), str(Path(plugin_root).resolve())]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        path_items.append(existing)
    return os.pathsep.join(path_items)


def _trim_output(content: str, byte_limit: int) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= byte_limit:
        return content
    return encoded[:byte_limit].decode("utf-8", errors="ignore")
