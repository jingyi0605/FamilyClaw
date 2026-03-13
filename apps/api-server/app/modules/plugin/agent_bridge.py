from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.service import resolve_effective_agent
from app.modules.audit.service import write_audit_log
from app.modules.household.service import get_household_or_404
from app.modules.plugin.schemas import AgentPluginInvokeRequest, AgentPluginInvokeResult, PluginExecutionRequest, PluginExecutionResult
from app.modules.plugin.service import execute_plugin, list_registered_plugins


def invoke_agent_plugin(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    request: AgentPluginInvokeRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> AgentPluginInvokeResult:
    get_household_or_404(db, household_id)
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)

    execution = _execute_agent_plugin_request(
        request,
        root_dir=root_dir,
        state_file=state_file,
    )

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.invoke",
        target_type="plugin",
        target_id=request.plugin_id,
        result="success" if execution.success else "fail",
        details={
            "agent_id": agent.id,
            "agent_name": agent.display_name,
            "plugin_id": execution.plugin_id,
            "plugin_type": execution.plugin_type,
            "run_id": execution.run_id,
            "trigger": execution.trigger,
            "error_code": execution.error_code,
            "error_message": execution.error_message,
        },
    )
    db.flush()

    return AgentPluginInvokeResult(
        agent_id=agent.id,
        agent_name=agent.display_name,
        plugin_id=execution.plugin_id,
        plugin_type=request.plugin_type,
        run_id=execution.run_id,
        success=execution.success,
        trigger=execution.trigger,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        output=execution.output,
        error_code=execution.error_code,
        error_message=execution.error_message,
    )


def _execute_agent_plugin_request(
    request: AgentPluginInvokeRequest,
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
            raise ValueError(f"插件不存在: {request.plugin_id}")
        if not plugin.enabled:
            raise ValueError(f"插件已禁用: {request.plugin_id}")
        if request.plugin_type not in plugin.types:
            raise ValueError(f"插件 {request.plugin_id} 没有声明 {request.plugin_type} 能力")
        if request.plugin_type not in {"connector", "agent-skill"}:
            raise ValueError("Agent 统一入口当前只允许 connector 或 agent-skill")

        return execute_plugin(
            PluginExecutionRequest(
                plugin_id=request.plugin_id,
                plugin_type=request.plugin_type,
                payload=request.payload,
                trigger=request.trigger,
            ),
            root_dir=root_dir,
            state_file=state_file,
        )
    except ValueError as exc:
        return PluginExecutionResult(
            run_id=run_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            error_code="agent_plugin_invoke_failed",
            error_message=str(exc),
        )
