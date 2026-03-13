from __future__ import annotations

from dataclasses import dataclass


PLUGIN_RUNNER_NOT_CONFIGURED = "plugin_runner_not_configured"
PLUGIN_RUNNER_START_FAILED = "plugin_runner_start_failed"
PLUGIN_RUNNER_TIMEOUT = "plugin_runner_timeout"
PLUGIN_RUNNER_INVALID_OUTPUT = "plugin_runner_invalid_output"
PLUGIN_RUNNER_DEPENDENCY_MISSING = "plugin_runner_dependency_missing"
PLUGIN_EXECUTION_FAILED = "plugin_execution_failed"


@dataclass(slots=True)
class PluginRunnerError(RuntimeError):
    error_code: str
    message: str

    def __str__(self) -> str:
        return self.message
