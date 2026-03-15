from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.service import resolve_effective_agent
from app.modules.audit.models import AuditLog
from app.modules.audit.service import write_audit_log
from app.modules.household.service import get_household_or_404
from app.modules.permission.models import MemberPermission
from app.modules.device_control.protocol import device_control_protocol_registry
from app.modules.plugin.schemas import (
    AgentActionConfirmationRead,
    AgentActionPluginInvokeRequest,
    AgentActionPluginInvokeResult,
    AgentPluginInvokeRequest,
    AgentPluginInvokeResult,
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginJobRead,
    PluginRegistryItem,
    RiskLevel,
)
from app.modules.plugin.service import (
    aexecute_household_plugin,
    enqueue_household_plugin_job,
    execute_household_plugin,
    get_household_plugin,
    require_available_household_plugin,
)


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

    try:
        queued = _enqueue_agent_plugin_request(
            db,
            request=request,
            household_id=household_id,
            root_dir=root_dir,
            state_file=state_file,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="agent.plugin.invoke",
            target_type="plugin",
            target_id=request.plugin_id,
            result="fail",
            details={
                "agent_id": agent.id,
                "agent_name": agent.display_name,
                "plugin_id": request.plugin_id,
                "plugin_type": request.plugin_type,
                "trigger": request.trigger,
                "error_message": str(exc),
            },
        )
        db.flush()
        return AgentPluginInvokeResult(
            agent_id=agent.id,
            agent_name=agent.display_name,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            run_id=new_uuid(),
            success=False,
            trigger=request.trigger,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=None,
            error_code="agent_plugin_invoke_failed",
            error_message=str(exc),
            queued=False,
        )

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.invoke",
        target_type="plugin",
        target_id=request.plugin_id,
        result="success",
        details={
            "agent_id": agent.id,
            "agent_name": agent.display_name,
            "plugin_id": queued.plugin_id,
            "plugin_type": request.plugin_type,
            "job_id": queued.id,
            "trigger": request.trigger,
            "job_status": queued.status,
        },
    )
    db.flush()

    return AgentPluginInvokeResult(
        agent_id=agent.id,
        agent_name=agent.display_name,
        plugin_id=queued.plugin_id,
        plugin_type=request.plugin_type,
        run_id=queued.id,
        success=True,
        trigger=request.trigger,
        started_at=queued.created_at,
        finished_at=queued.created_at,
        output=None,
        error_code=None,
        error_message=None,
        queued=True,
        job_id=queued.id,
        job_status=queued.status,
    )


async def ainvoke_agent_plugin(
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
    try:
        queued = _enqueue_agent_plugin_request(
            db,
            request=request,
            household_id=household_id,
            root_dir=root_dir,
            state_file=state_file,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=request.plugin_id, plugin_type=request.plugin_type, run_id=new_uuid(), success=False, trigger=request.trigger, started_at=started_at, finished_at=utc_now_iso(), output=None, error_code="agent_plugin_invoke_failed", error_message=str(exc), queued=False)

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.invoke",
        target_type="plugin",
        target_id=request.plugin_id,
        result="success",
        details={"agent_id": agent.id, "agent_name": agent.display_name, "plugin_id": queued.plugin_id, "plugin_type": request.plugin_type, "job_id": queued.id, "trigger": request.trigger, "job_status": queued.status},
    )
    db.flush()
    return AgentPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=queued.plugin_id, plugin_type=request.plugin_type, run_id=queued.id, success=True, trigger=request.trigger, started_at=queued.created_at, finished_at=queued.created_at, output=None, error_code=None, error_message=None, queued=True, job_id=queued.id, job_status=queued.status)


def _enqueue_agent_plugin_request(
    db: Session,
    request: AgentPluginInvokeRequest,
    *,
    household_id: str,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> PluginJobRead:
    try:
        plugin = require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            trigger=request.trigger,
            root_dir=root_dir,
            state_file=state_file,
        )
        if request.plugin_type not in {"connector", "agent-skill"}:
            raise ValueError("Agent 统一入口当前只允许 connector 或 agent-skill")

        return enqueue_household_plugin_job(
            db,
            household_id=household_id,
            request=PluginExecutionRequest(
                plugin_id=request.plugin_id,
                plugin_type=request.plugin_type,
                payload=request.payload,
                trigger=request.trigger,
            ),
            payload_summary={"source": "agent_plugin_invoke"},
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def invoke_agent_action_plugin(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    request: AgentActionPluginInvokeRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> AgentActionPluginInvokeResult:
    get_household_or_404(db, household_id)
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)

    try:
        plugin = require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=request.plugin_id,
            plugin_type="action",
            trigger=request.trigger,
            root_dir=root_dir,
            state_file=state_file,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(
            agent_id=agent.id,
            agent_name=agent.display_name,
            plugin_id=request.plugin_id,
            run_id=new_uuid(),
            success=False,
            trigger=request.trigger,
            risk_level="high",
            authorization_status="denied",
            confirmation_request_id=None,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=None,
            error_code="agent_action_plugin_denied",
            error_message=str(exc),
            queued=False,
        )

    effective_risk_level = _resolve_agent_action_risk_level(plugin, request.payload)

    if effective_risk_level == "high":
        confirmation = request_agent_action_confirmation(
            db,
            household_id=household_id,
            agent_id=agent.id,
            request=request,
            actor=actor,
            plugin=plugin,
        )
        return AgentActionPluginInvokeResult(
            agent_id=agent.id,
            agent_name=agent.display_name,
            plugin_id=request.plugin_id,
            run_id=confirmation.confirmation_request_id,
            success=False,
            trigger=request.trigger,
            risk_level=effective_risk_level,
            authorization_status="confirmation_required",
            confirmation_request_id=confirmation.confirmation_request_id,
            started_at=confirmation.created_at,
            finished_at=confirmation.created_at,
            error_code="agent_action_confirmation_required",
            error_message="高风险动作需要人工确认后才能执行",
        )

    try:
        queued = _enqueue_agent_action_request(
            db,
            household_id=household_id,
            actor=actor,
            plugin=plugin,
            request=request,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(
            agent_id=agent.id,
            agent_name=agent.display_name,
            plugin_id=request.plugin_id,
            run_id=new_uuid(),
            success=False,
            trigger=request.trigger,
            risk_level=effective_risk_level,
            authorization_status="denied",
            confirmation_request_id=None,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=None,
            error_code="agent_action_plugin_denied",
            error_message=str(exc),
            queued=False,
        )
    authorization_status = "allowed"
    risk_level = effective_risk_level

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.invoke_action",
        target_type="plugin",
        target_id=request.plugin_id,
        result="success",
        details={
            "agent_id": agent.id,
            "agent_name": agent.display_name,
            "plugin_id": request.plugin_id,
            "plugin_type": "action",
            "job_id": queued.id,
            "trigger": request.trigger,
            "risk_level": risk_level,
            "authorization_status": authorization_status,
            "job_status": queued.status,
        },
    )
    db.flush()

    return AgentActionPluginInvokeResult(
        agent_id=agent.id,
        agent_name=agent.display_name,
        plugin_id=request.plugin_id,
        run_id=queued.id,
        success=True,
        trigger=request.trigger,
        risk_level=risk_level,
        authorization_status=authorization_status,
        confirmation_request_id=None,
        started_at=queued.created_at,
        finished_at=queued.created_at,
        output=None,
        error_code=None,
        error_message=None,
        queued=True,
        job_id=queued.id,
        job_status=queued.status,
    )


def _enqueue_agent_action_request(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext | None,
    plugin: PluginRegistryItem | None,
    request: AgentActionPluginInvokeRequest,
) -> PluginJobRead:
    try:
        if plugin is None:
            raise ValueError(f"插件不存在: {request.plugin_id}")
        if not plugin.enabled:
            raise ValueError(f"插件已禁用: {request.plugin_id}")
        if "action" not in plugin.types:
            raise ValueError(f"插件 {request.plugin_id} 不是动作插件")

        resource_type = _resolve_resource_type(request.payload)
        resource_scope = _resolve_resource_scope(request.payload)
        required_plugin_permission = _resolve_required_plugin_permission(resource_type)
        if required_plugin_permission not in plugin.permissions:
            raise ValueError(f"插件 {request.plugin_id} 没有声明所需权限: {required_plugin_permission}")
        if not _actor_has_action_permission(
            db,
            household_id=household_id,
            actor=actor,
            resource_type=resource_type,
            resource_scope=resource_scope,
        ):
            raise ValueError("当前成员没有动作执行权限")

        return enqueue_household_plugin_job(
            db,
            household_id=household_id,
            request=PluginExecutionRequest(
                plugin_id=request.plugin_id,
                plugin_type="action",
                payload=request.payload,
                trigger=request.trigger,
            ),
            payload_summary={"source": "agent_action_plugin_invoke"},
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def request_agent_action_confirmation(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    request: AgentActionPluginInvokeRequest,
    actor: ActorContext | None,
    plugin: PluginRegistryItem,
) -> AgentActionConfirmationRead:
    confirmation_log = write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.request_action_confirmation",
        target_type="plugin_action_confirmation",
        target_id=new_uuid(),
        result="pending",
        details={
            "agent_id": agent_id,
            "plugin_id": request.plugin_id,
            "plugin_type": "action",
            "risk_level": _resolve_agent_action_risk_level(plugin, request.payload),
            "trigger": request.trigger,
            "payload": request.payload,
        },
    )
    db.flush()
    return AgentActionConfirmationRead(
        confirmation_request_id=confirmation_log.target_id or confirmation_log.id,
        household_id=household_id,
        plugin_id=request.plugin_id,
        risk_level=_resolve_agent_action_risk_level(plugin, request.payload),
        status="pending",
        trigger=request.trigger,
        payload=request.payload,
        created_at=confirmation_log.created_at,
    )


def confirm_agent_action_plugin(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    confirmation_request_id: str,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> AgentActionPluginInvokeResult:
    get_household_or_404(db, household_id)
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)
    confirmation = _load_pending_action_confirmation(db, household_id=household_id, confirmation_request_id=confirmation_request_id)
    plugin = get_household_plugin(
        db,
        household_id=household_id,
        plugin_id=confirmation.plugin_id,
        root_dir=root_dir,
        state_file=state_file,
    )

    request = AgentActionPluginInvokeRequest(
        plugin_id=confirmation.plugin_id,
        payload=confirmation.payload,
        trigger=f"{confirmation.trigger}:confirmed",
    )
    try:
        queued = _enqueue_agent_action_request(
            db,
            household_id=household_id,
            actor=actor,
            plugin=plugin,
            request=request,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(
            agent_id=agent.id,
            agent_name=agent.display_name,
            plugin_id=confirmation.plugin_id,
            run_id=new_uuid(),
            success=False,
            trigger=request.trigger,
            risk_level=_resolve_agent_action_risk_level(plugin, confirmation.payload),
            authorization_status="denied",
            confirmation_request_id=confirmation_request_id,
            started_at=started_at,
            finished_at=utc_now_iso(),
            output=None,
            error_code="agent_action_plugin_denied",
            error_message=str(exc),
            queued=False,
        )
    authorization_status = "allowed"
    risk_level = _resolve_agent_action_risk_level(plugin, confirmation.payload)

    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.plugin.confirm_action",
        target_type="plugin_action_confirmation",
        target_id=confirmation_request_id,
        result="success",
        details={
            "agent_id": agent.id,
            "agent_name": agent.display_name,
            "plugin_id": confirmation.plugin_id,
            "plugin_type": "action",
            "risk_level": risk_level,
            "trigger": confirmation.trigger,
            "job_id": queued.id,
            "authorization_status": authorization_status,
            "job_status": queued.status,
        },
    )
    db.flush()

    return AgentActionPluginInvokeResult(
        agent_id=agent.id,
        agent_name=agent.display_name,
        plugin_id=confirmation.plugin_id,
        run_id=queued.id,
        success=True,
        trigger=request.trigger,
        risk_level=risk_level,
        authorization_status=authorization_status,
        confirmation_request_id=confirmation_request_id,
        started_at=queued.created_at,
        finished_at=queued.created_at,
        output=None,
        error_code=None,
        error_message=None,
        queued=True,
        job_id=queued.id,
        job_status=queued.status,
    )


async def ainvoke_agent_action_plugin(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    request: AgentActionPluginInvokeRequest,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> AgentActionPluginInvokeResult:
    get_household_or_404(db, household_id)
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)
    try:
        plugin = require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=request.plugin_id,
            plugin_type="action",
            trigger=request.trigger,
            root_dir=root_dir,
            state_file=state_file,
        )
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=request.plugin_id, run_id=new_uuid(), success=False, trigger=request.trigger, risk_level="high", authorization_status="denied", confirmation_request_id=None, started_at=started_at, finished_at=utc_now_iso(), output=None, error_code="agent_action_plugin_denied", error_message=str(exc), queued=False)

    effective_risk_level = _resolve_agent_action_risk_level(plugin, request.payload)
    if effective_risk_level == "high":
        confirmation = request_agent_action_confirmation(db, household_id=household_id, agent_id=agent.id, request=request, actor=actor, plugin=plugin)
        return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=request.plugin_id, run_id=confirmation.confirmation_request_id, success=False, trigger=request.trigger, risk_level=effective_risk_level, authorization_status="confirmation_required", confirmation_request_id=confirmation.confirmation_request_id, started_at=confirmation.created_at, finished_at=confirmation.created_at, error_code="agent_action_confirmation_required", error_message="高风险动作需要人工确认后才能执行")

    try:
        queued = _enqueue_agent_action_request(db, household_id=household_id, actor=actor, plugin=plugin, request=request)
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=request.plugin_id, run_id=new_uuid(), success=False, trigger=request.trigger, risk_level=effective_risk_level, authorization_status="denied", confirmation_request_id=None, started_at=started_at, finished_at=utc_now_iso(), output=None, error_code="agent_action_plugin_denied", error_message=str(exc), queued=False)
    authorization_status = "allowed"
    risk_level = effective_risk_level
    write_audit_log(db, household_id=household_id, actor=actor, action="agent.plugin.invoke_action", target_type="plugin", target_id=request.plugin_id, result="success", details={"agent_id": agent.id, "agent_name": agent.display_name, "plugin_id": request.plugin_id, "plugin_type": "action", "job_id": queued.id, "trigger": request.trigger, "risk_level": risk_level, "authorization_status": authorization_status, "job_status": queued.status})
    db.flush()
    return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=request.plugin_id, run_id=queued.id, success=True, trigger=request.trigger, risk_level=risk_level, authorization_status=authorization_status, confirmation_request_id=None, started_at=queued.created_at, finished_at=queued.created_at, output=None, error_code=None, error_message=None, queued=True, job_id=queued.id, job_status=queued.status)


async def aconfirm_agent_action_plugin(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    confirmation_request_id: str,
    actor: ActorContext | None = None,
    root_dir: str | Path | None = None,
    state_file: str | Path | None = None,
) -> AgentActionPluginInvokeResult:
    get_household_or_404(db, household_id)
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)
    confirmation = _load_pending_action_confirmation(db, household_id=household_id, confirmation_request_id=confirmation_request_id)
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=confirmation.plugin_id, root_dir=root_dir, state_file=state_file)
    request = AgentActionPluginInvokeRequest(plugin_id=confirmation.plugin_id, payload=confirmation.payload, trigger=f"{confirmation.trigger}:confirmed")
    try:
        queued = _enqueue_agent_action_request(db, household_id=household_id, actor=actor, plugin=plugin, request=request)
    except ValueError as exc:
        started_at = utc_now_iso()
        return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=confirmation.plugin_id, run_id=new_uuid(), success=False, trigger=request.trigger, risk_level=_resolve_agent_action_risk_level(plugin, confirmation.payload), authorization_status="denied", confirmation_request_id=confirmation_request_id, started_at=started_at, finished_at=utc_now_iso(), output=None, error_code="agent_action_plugin_denied", error_message=str(exc), queued=False)
    authorization_status = "allowed"
    risk_level = _resolve_agent_action_risk_level(plugin, confirmation.payload)
    write_audit_log(db, household_id=household_id, actor=actor, action="agent.plugin.confirm_action", target_type="plugin_action_confirmation", target_id=confirmation_request_id, result="success", details={"agent_id": agent.id, "agent_name": agent.display_name, "plugin_id": confirmation.plugin_id, "plugin_type": "action", "risk_level": risk_level, "trigger": confirmation.trigger, "job_id": queued.id, "authorization_status": authorization_status, "job_status": queued.status})
    db.flush()
    return AgentActionPluginInvokeResult(agent_id=agent.id, agent_name=agent.display_name, plugin_id=confirmation.plugin_id, run_id=queued.id, success=True, trigger=request.trigger, risk_level=risk_level, authorization_status=authorization_status, confirmation_request_id=confirmation_request_id, started_at=queued.created_at, finished_at=queued.created_at, output=None, error_code=None, error_message=None, queued=True, job_id=queued.id, job_status=queued.status)


def _resolve_agent_action_risk_level(plugin: PluginRegistryItem | None, payload: dict) -> RiskLevel:
    plugin_risk_level = plugin.risk_level if plugin is not None else "high"
    action_name = payload.get("action_name") if isinstance(payload, dict) else None
    if not isinstance(action_name, str) or not action_name.strip():
        return plugin_risk_level
    try:
        action_risk_level = device_control_protocol_registry.get_definition(action_name.strip()).risk_level
    except ValueError:
        return plugin_risk_level
    risk_order = {"low": 0, "medium": 1, "high": 2}
    return action_risk_level if risk_order[action_risk_level] > risk_order[plugin_risk_level] else plugin_risk_level


def _load_pending_action_confirmation(
    db: Session,
    *,
    household_id: str,
    confirmation_request_id: str,
) -> AgentActionConfirmationRead:
    request_stmt = select(AuditLog).where(
        AuditLog.household_id == household_id,
        AuditLog.action == "agent.plugin.request_action_confirmation",
        AuditLog.target_type == "plugin_action_confirmation",
        AuditLog.target_id == confirmation_request_id,
    )
    request_log = db.scalar(request_stmt)
    if request_log is None:
        raise ValueError("确认请求不存在")

    consumed_stmt = select(AuditLog).where(
        AuditLog.household_id == household_id,
        AuditLog.action == "agent.plugin.confirm_action",
        AuditLog.target_type == "plugin_action_confirmation",
        AuditLog.target_id == confirmation_request_id,
    )
    consumed_log = db.scalar(consumed_stmt)
    if consumed_log is not None:
        raise ValueError("确认请求已经使用，不能重复执行")

    details = json.loads(request_log.details or "{}")
    payload = details.get("payload") if isinstance(details.get("payload"), dict) else {}
    plugin_id = details.get("plugin_id") if isinstance(details.get("plugin_id"), str) else ""
    risk_level = details.get("risk_level") if isinstance(details.get("risk_level"), str) else "high"
    trigger = details.get("trigger") if isinstance(details.get("trigger"), str) else "agent-action"
    if not plugin_id:
        raise ValueError("确认请求缺少插件信息")
    return AgentActionConfirmationRead(
        confirmation_request_id=confirmation_request_id,
        household_id=household_id,
        plugin_id=plugin_id,
        risk_level=risk_level,
        status="pending",
        trigger=trigger,
        payload=payload,
        created_at=request_log.created_at,
    )


def _resolve_resource_type(payload: dict) -> str:
    value = payload.get("resource_type")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "device"


def _resolve_resource_scope(payload: dict) -> str:
    value = payload.get("resource_scope")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "family"


def _resolve_required_plugin_permission(resource_type: str) -> str:
    if resource_type == "device":
        return "device.control"
    return f"{resource_type}.execute"


def _actor_has_action_permission(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext | None,
    resource_type: str,
    resource_scope: str,
) -> bool:
    if actor is None:
        return False
    if actor.account_type == "system":
        return True
    if actor.member_id is None:
        return False
    if actor.household_id != household_id:
        return False

    scope_candidates = _build_scope_candidates(resource_scope)
    stmt = select(MemberPermission).where(
        MemberPermission.member_id == actor.member_id,
        MemberPermission.household_id == household_id,
        MemberPermission.resource_type == resource_type,
        MemberPermission.action == "execute",
    )
    rows = list(db.scalars(stmt).all())
    if not rows:
        return False

    for row in rows:
        if row.resource_scope in scope_candidates and row.effect == "deny":
            return False
    for row in rows:
        if row.resource_scope in scope_candidates and row.effect == "allow":
            return True
    return False


def _build_scope_candidates(resource_scope: str) -> set[str]:
    if resource_scope == "self":
        return {"self", "family", "public"}
    if resource_scope == "children":
        return {"children", "family", "public"}
    if resource_scope == "family":
        return {"family", "public"}
    return {resource_scope}
