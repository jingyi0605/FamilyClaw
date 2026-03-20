import logging
from collections.abc import Mapping
from typing import cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.ai_gateway import repository
from app.modules.ai_gateway.models import AiProviderProfile
from app.modules.ai_gateway.provider_driver import resolve_ai_provider_driver_for_profile
from app.modules.ai_gateway.provider_runtime import (
    ProviderRuntimeError,
    build_template_fallback_output,
)
from app.modules.ai_gateway.schemas import (
    AiApiFamily,
    AiCapability,
    AiGatewayAttemptResult,
    AiGatewayInvokeRequest,
    AiGatewayInvokeResponse,
    AiInvocationPlan,
    AiModelCallLogCreate,
    AiModelCallStatus,
    AiPreparedPayload,
    AiPrivacyLevel,
    AiProviderCandidate,
    AiRoutingMode,
    AiTransportType,
)
from app.modules.ai_gateway.service import (
    get_household_ai_provider_plugin_for_profile,
    log_model_call,
    resolve_capability_route,
)

logger = logging.getLogger(__name__)


def build_invocation_plan(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None = None,
    requester_member_id: str | None = None,
    agent_id: str | None = None,
    plugin_id: str | None = None,
    request_payload: Mapping[str, object] | None = None,
    trace_id: str | None = None,
    timeout_ms_override: int | None = None,
) -> AiInvocationPlan:
    resolved_agent_id, resolved_plugin_id = _resolve_binding_context(
        agent_id=agent_id,
        plugin_id=plugin_id,
        request_payload=request_payload,
    )
    direct_provider_profile_id = _resolve_direct_binding_provider_profile_id(
        db,
        capability=capability,
        household_id=household_id,
        agent_id=resolved_agent_id,
        plugin_id=resolved_plugin_id,
    )
    if direct_provider_profile_id is not None:
        return _build_direct_binding_plan(
            db,
            capability=capability,
            household_id=household_id,
            requester_member_id=requester_member_id,
            direct_provider_profile_id=direct_provider_profile_id,
            trace_id=trace_id,
            timeout_ms_override=timeout_ms_override,
        )

    route = resolve_capability_route(
        db,
        capability=capability,
        household_id=household_id,
    )
    if route is None:
        return _build_runtime_default_plan(
            db,
            capability=capability,
            household_id=household_id,
            requester_member_id=requester_member_id,
            trace_id=trace_id,
        )

    provider_candidates, blocked_plugin_id = _build_provider_candidates(
        db,
        provider_profile_ids=[
            provider_id
            for provider_id in [route.primary_provider_profile_id, *route.fallback_provider_profile_ids]
            if provider_id is not None
        ],
        routing_mode=route.routing_mode,
        household_id=household_id,
    )
    primary_provider = provider_candidates[0] if provider_candidates else None
    fallback_providers = provider_candidates[1:] if len(provider_candidates) > 1 else []
    blocked_reason = None
    blocked_error_code = None

    if route.routing_mode != "template_only" and primary_provider is None and blocked_plugin_id is not None and household_id is not None:
        blocked_reason = "当前家庭绑定的 AI 供应商插件已禁用，不能继续调用。"
        blocked_error_code = "plugin_disabled"

    if not route.enabled:
        blocked_reason = "当前能力路由已禁用"
        blocked_error_code = None
        blocked_plugin_id = None

    if route.routing_mode != "template_only" and primary_provider is None:
        blocked_reason = blocked_reason or "当前能力没有可用主供应商"

    return AiInvocationPlan(
        capability=capability,
        household_id=household_id,
        requester_member_id=requester_member_id,
        trace_id=trace_id or _new_trace_id(),
        routing_mode=route.routing_mode,
        timeout_ms=timeout_ms_override or route.timeout_ms,
        max_retry_count=route.max_retry_count,
        allow_remote=route.allow_remote,
        prompt_policy=route.prompt_policy,
        response_policy=route.response_policy,
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        template_fallback_enabled=bool(route.response_policy.get("template_fallback_enabled", True)),
        blocked_reason=blocked_reason,
        blocked_error_code=blocked_error_code,
        blocked_plugin_id=blocked_plugin_id,
    )


def prepare_payload_for_invocation(
    plan: AiInvocationPlan,
    payload: dict[str, object],
) -> AiPreparedPayload:
    prepared_payload = dict(payload)
    prepared_payload["request_context"] = _merge_request_context(
        payload.get("request_context"),
        trace_id=plan.trace_id,
    )
    masked_fields: list[str] = []
    blocked_reason = plan.blocked_reason

    mask_fields = plan.prompt_policy.get("mask_fields", [])
    for field_name in mask_fields:
        if field_name in prepared_payload:
            prepared_payload[field_name] = "***"
            masked_fields.append(field_name)

    if not plan.allow_remote and any(candidate.privacy_level != "local_only" for candidate in _iter_plan_candidates(plan)):
        blocked_reason = blocked_reason or "当前策略禁止把请求发送到远端模型"

    return AiPreparedPayload(
        payload=prepared_payload,
        masked_fields=masked_fields,
        blocked_reason=blocked_reason,
    )


def _merge_request_context(raw_context: object, *, trace_id: str) -> dict[str, object]:
    base: dict[str, object] = dict(raw_context) if isinstance(raw_context, dict) else {}
    base["trace_id"] = trace_id
    return base


def invoke_capability(
    db: Session,
    payload: AiGatewayInvokeRequest,
) -> AiGatewayInvokeResponse:
    plan = build_invocation_plan(
        db,
        capability=payload.capability,
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        agent_id=payload.agent_id,
        plugin_id=payload.plugin_id,
        request_payload=payload.payload,
        timeout_ms_override=payload.timeout_ms_override,
    )
    prepared_payload = prepare_payload_for_invocation(plan, payload.payload)
    attempts: list[AiGatewayAttemptResult] = []

    if prepared_payload.blocked_reason and not plan.template_fallback_enabled:
        _write_template_log(
            db,
            plan=plan,
            masked_fields=prepared_payload.masked_fields,
            status="blocked",
            error_code=plan.blocked_error_code or "policy_blocked",
        )
        if plan.blocked_error_code == "plugin_disabled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "detail": prepared_payload.blocked_reason,
                    "error_code": "plugin_disabled",
                    "field": "plugin_id",
                    "plugin_id": plan.blocked_plugin_id,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=prepared_payload.blocked_reason,
        )

    for index, candidate in enumerate(_iter_plan_candidates(plan)):
        provider_row = repository.get_provider_profile(db, candidate.provider_profile_id)
        if provider_row is None or not provider_row.enabled:
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="failed",
                    latency_ms=0,
                    error_code="provider_missing",
                    fallback_used=index > 0,
                )
            )
            continue

        if prepared_payload.blocked_reason and candidate.privacy_level != "local_only":
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="blocked",
                    latency_ms=0,
                    error_code="policy_blocked",
                    fallback_used=index > 0,
                )
            )
            continue

        driver = resolve_ai_provider_driver_for_profile(
            db,
            provider_profile=provider_row,
            household_id=plan.household_id,
        )
        if driver is None:
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="failed",
                    latency_ms=0,
                    error_code="driver_unavailable",
                    fallback_used=index > 0,
                )
            )
            continue

        try:
            result = driver.invoke(
                capability=plan.capability,
                provider_profile=provider_row,
                payload=prepared_payload.payload,
                timeout_ms=plan.timeout_ms,
                honor_timeout_override=payload.honor_timeout_override,
            )
        except ProviderRuntimeError as exc:
            logger.warning(
                "AI 调用失败 capability=%s trace_id=%s household_id=%s requester_member_id=%s provider=%s fallback_used=%s error_code=%s",
                plan.capability,
                plan.trace_id,
                plan.household_id or "-",
                plan.requester_member_id or "-",
                candidate.provider_code,
                index > 0,
                exc.error_code,
            )
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status=_map_error_code_to_status(exc.error_code),
                    latency_ms=0,
                    error_code=exc.error_code,
                    fallback_used=index > 0,
                )
            )
            continue

        attempt_status = "fallback_success" if index > 0 else "success"
        attempts.append(
            _write_attempt_log(
                db,
                plan=plan,
                candidate=candidate,
                masked_fields=prepared_payload.masked_fields,
                status=attempt_status,
                latency_ms=result.latency_ms,
                error_code=None,
                fallback_used=index > 0,
                model_name=result.model_name,
                usage={"transport_type": provider_row.transport_type},
            )
        )
        if index > 0:
            logger.info(
                "AI 回退成功 capability=%s trace_id=%s household_id=%s requester_member_id=%s provider=%s attempts=%s",
                plan.capability,
                plan.trace_id,
                plan.household_id or "-",
                plan.requester_member_id or "-",
                result.provider_code,
                _summarize_attempts(attempts),
            )
        return AiGatewayInvokeResponse(
            capability=plan.capability,
            household_id=plan.household_id,
            requester_member_id=plan.requester_member_id,
            trace_id=plan.trace_id,
            status="success",
            degraded=index > 0,
            provider_code=result.provider_code,
            model_name=result.model_name,
            finish_reason=result.finish_reason,
            normalized_output=result.normalized_output,
            raw_response_ref=result.raw_response_ref,
            attempts=attempts,
        )

    if not plan.template_fallback_enabled:
        logger.warning(
            "AI 调用耗尽且未启用模板降级 capability=%s trace_id=%s household_id=%s requester_member_id=%s attempts=%s",
            plan.capability,
            plan.trace_id,
            plan.household_id or "-",
            plan.requester_member_id or "-",
            _summarize_attempts(attempts),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="当前能力没有可用供应商，且未配置模板降级",
        )

    template_output = build_template_fallback_output(
        capability=plan.capability,
        payload=prepared_payload.payload,
    )
    attempts.append(
        _write_template_log(
            db,
            plan=plan,
            masked_fields=prepared_payload.masked_fields,
            status="fallback_success",
            error_code=None,
        )
    )
    logger.warning(
        "AI 调用降级到模板 capability=%s trace_id=%s household_id=%s requester_member_id=%s blocked_reason=%s attempts=%s",
        plan.capability,
        plan.trace_id,
        plan.household_id or "-",
        plan.requester_member_id or "-",
        prepared_payload.blocked_reason or "-",
        _summarize_attempts(attempts),
    )
    return AiGatewayInvokeResponse(
        capability=plan.capability,
        household_id=plan.household_id,
        requester_member_id=plan.requester_member_id,
        trace_id=plan.trace_id,
        status="success",
        degraded=True,
        provider_code="template",
        model_name="template-fallback",
        finish_reason="template_fallback",
        normalized_output=template_output,
        raw_response_ref="template://fallback",
        blocked_reason=prepared_payload.blocked_reason,
        attempts=attempts,
    )


async def ainvoke_capability(
    db: Session,
    payload: AiGatewayInvokeRequest,
) -> AiGatewayInvokeResponse:
    plan = build_invocation_plan(
        db,
        capability=payload.capability,
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        agent_id=payload.agent_id,
        plugin_id=payload.plugin_id,
        request_payload=payload.payload,
        timeout_ms_override=payload.timeout_ms_override,
    )
    prepared_payload = prepare_payload_for_invocation(plan, payload.payload)
    attempts: list[AiGatewayAttemptResult] = []

    if prepared_payload.blocked_reason and not plan.template_fallback_enabled:
        _write_template_log(
            db,
            plan=plan,
            masked_fields=prepared_payload.masked_fields,
            status="blocked",
            error_code=plan.blocked_error_code or "policy_blocked",
        )
        if plan.blocked_error_code == "plugin_disabled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "detail": prepared_payload.blocked_reason,
                    "error_code": "plugin_disabled",
                    "field": "plugin_id",
                    "plugin_id": plan.blocked_plugin_id,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=prepared_payload.blocked_reason,
        )

    for index, candidate in enumerate(_iter_plan_candidates(plan)):
        provider_row = repository.get_provider_profile(db, candidate.provider_profile_id)
        if provider_row is None or not provider_row.enabled:
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="failed",
                    latency_ms=0,
                    error_code="provider_missing",
                    fallback_used=index > 0,
                )
            )
            continue

        if prepared_payload.blocked_reason and candidate.privacy_level != "local_only":
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="blocked",
                    latency_ms=0,
                    error_code="policy_blocked",
                    fallback_used=index > 0,
                )
            )
            continue

        driver = resolve_ai_provider_driver_for_profile(
            db,
            provider_profile=provider_row,
            household_id=plan.household_id,
        )
        if driver is None:
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status="failed",
                    latency_ms=0,
                    error_code="driver_unavailable",
                    fallback_used=index > 0,
                )
            )
            continue

        try:
            result = await driver.ainvoke(
                capability=plan.capability,
                provider_profile=provider_row,
                payload=prepared_payload.payload,
                timeout_ms=plan.timeout_ms,
                honor_timeout_override=payload.honor_timeout_override,
            )
        except ProviderRuntimeError as exc:
            logger.warning(
                "AI 异步调用失败 capability=%s trace_id=%s household_id=%s requester_member_id=%s provider=%s fallback_used=%s error_code=%s",
                plan.capability,
                plan.trace_id,
                plan.household_id or "-",
                plan.requester_member_id or "-",
                candidate.provider_code,
                index > 0,
                exc.error_code,
            )
            attempts.append(
                _write_attempt_log(
                    db,
                    plan=plan,
                    candidate=candidate,
                    masked_fields=prepared_payload.masked_fields,
                    status=_map_error_code_to_status(exc.error_code),
                    latency_ms=0,
                    error_code=exc.error_code,
                    fallback_used=index > 0,
                )
            )
            continue

        attempt_status = "fallback_success" if index > 0 else "success"
        attempts.append(
            _write_attempt_log(
                db,
                plan=plan,
                candidate=candidate,
                masked_fields=prepared_payload.masked_fields,
                status=attempt_status,
                latency_ms=result.latency_ms,
                error_code=None,
                fallback_used=index > 0,
                model_name=result.model_name,
                usage={"transport_type": provider_row.transport_type},
            )
        )
        if index > 0:
            logger.info(
                "AI 异步回退成功 capability=%s trace_id=%s household_id=%s requester_member_id=%s provider=%s attempts=%s",
                plan.capability,
                plan.trace_id,
                plan.household_id or "-",
                plan.requester_member_id or "-",
                result.provider_code,
                _summarize_attempts(attempts),
            )
        return AiGatewayInvokeResponse(
            capability=plan.capability,
            household_id=plan.household_id,
            requester_member_id=plan.requester_member_id,
            trace_id=plan.trace_id,
            status="success",
            degraded=index > 0,
            provider_code=result.provider_code,
            model_name=result.model_name,
            finish_reason=result.finish_reason,
            normalized_output=result.normalized_output,
            raw_response_ref=result.raw_response_ref,
            attempts=attempts,
        )

    if not plan.template_fallback_enabled:
        logger.warning(
            "AI 异步调用耗尽且未启用模板降级 capability=%s trace_id=%s household_id=%s requester_member_id=%s attempts=%s",
            plan.capability,
            plan.trace_id,
            plan.household_id or "-",
            plan.requester_member_id or "-",
            _summarize_attempts(attempts),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="当前能力没有可用供应商，且未配置模板降级",
        )

    template_output = build_template_fallback_output(
        capability=plan.capability,
        payload=prepared_payload.payload,
    )
    attempts.append(
        _write_template_log(
            db,
            plan=plan,
            masked_fields=prepared_payload.masked_fields,
            status="fallback_success",
            error_code=None,
        )
    )
    logger.warning(
        "AI 异步调用降级到模板 capability=%s trace_id=%s household_id=%s requester_member_id=%s blocked_reason=%s attempts=%s",
        plan.capability,
        plan.trace_id,
        plan.household_id or "-",
        plan.requester_member_id or "-",
        prepared_payload.blocked_reason or "-",
        _summarize_attempts(attempts),
    )
    return AiGatewayInvokeResponse(
        capability=plan.capability,
        household_id=plan.household_id,
        requester_member_id=plan.requester_member_id,
        trace_id=plan.trace_id,
        status="success",
        degraded=True,
        provider_code="template",
        model_name="template-fallback",
        finish_reason="template_fallback",
        normalized_output=template_output,
        raw_response_ref="template://fallback",
        blocked_reason=prepared_payload.blocked_reason,
        attempts=attempts,
    )


def _build_runtime_default_plan(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None,
    requester_member_id: str | None,
    trace_id: str | None,
) -> AiInvocationPlan:
    default_routing_mode = cast(AiRoutingMode, settings.ai_runtime.default_routing_mode)
    rows = _list_runtime_default_provider_rows(db)
    providers, blocked_plugin_id = _build_candidates_from_rows(
        db,
        rows=rows,
        routing_mode=default_routing_mode,
        household_id=household_id,
    )
    primary_provider = providers[0] if providers else None
    fallback_providers = providers[1:] if len(providers) > 1 else []
    blocked_reason = None
    blocked_error_code = None
    if primary_provider is None and default_routing_mode != "template_only":
        if household_id is not None and blocked_plugin_id is not None:
            blocked_reason = "当前家庭绑定的 AI 供应商插件已禁用，不能继续调用。"
            blocked_error_code = "plugin_disabled"
        else:
            blocked_reason = "运行时默认 AI 供应商未配置"

    return AiInvocationPlan(
        capability=capability,
        household_id=household_id,
        requester_member_id=requester_member_id,
        trace_id=trace_id or _new_trace_id(),
        routing_mode=default_routing_mode,
        timeout_ms=settings.ai_runtime.default_timeout_ms,
        max_retry_count=settings.ai_runtime.default_max_retry_count,
        allow_remote=settings.ai_runtime.default_allow_remote,
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        template_fallback_enabled=True,
        blocked_reason=blocked_reason,
        blocked_error_code=blocked_error_code,
        blocked_plugin_id=blocked_plugin_id,
    )


def _build_direct_binding_plan(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None,
    requester_member_id: str | None,
    direct_provider_profile_id: str,
    trace_id: str | None,
    timeout_ms_override: int | None,
) -> AiInvocationPlan:
    route = resolve_capability_route(
        db,
        capability=capability,
        household_id=household_id,
    )
    use_route_fallback = route is not None and route.enabled
    fallback_provider_profile_ids = (
        _collect_route_provider_profile_ids(route)
        if use_route_fallback
        else _list_runtime_default_provider_profile_ids(db)
    )
    provider_profile_ids = list(
        dict.fromkeys(
            [
                direct_provider_profile_id,
                *fallback_provider_profile_ids,
            ]
        )
    )

    routing_mode: AiRoutingMode
    if use_route_fallback:
        routing_mode = cast(AiRoutingMode, "primary_then_fallback" if route.routing_mode == "template_only" else route.routing_mode)
        timeout_ms = timeout_ms_override or route.timeout_ms
        max_retry_count = route.max_retry_count
        allow_remote = route.allow_remote
        prompt_policy = route.prompt_policy
        response_policy = route.response_policy
    else:
        routing_mode = cast(AiRoutingMode, "primary_then_fallback" if settings.ai_runtime.default_routing_mode == "template_only" else settings.ai_runtime.default_routing_mode)
        timeout_ms = timeout_ms_override or settings.ai_runtime.default_timeout_ms
        max_retry_count = settings.ai_runtime.default_max_retry_count
        allow_remote = settings.ai_runtime.default_allow_remote
        prompt_policy = {}
        response_policy = {}

    providers, blocked_plugin_id = _build_provider_candidates(
        db,
        provider_profile_ids=provider_profile_ids,
        routing_mode=routing_mode,
        household_id=household_id,
    )
    primary_provider = providers[0] if providers else None
    fallback_providers = providers[1:] if len(providers) > 1 else []
    blocked_reason = None
    blocked_error_code = None
    if primary_provider is None and household_id is not None and blocked_plugin_id is not None:
        blocked_reason = "当前家庭绑定的 AI 提供商插件已禁用，不能继续调用。"
        blocked_error_code = "plugin_disabled"
    elif primary_provider is None:
        blocked_reason = "当前 Agent 模型绑定没有可用提供商"

    return AiInvocationPlan(
        capability=capability,
        household_id=household_id,
        requester_member_id=requester_member_id,
        trace_id=trace_id or _new_trace_id(),
        routing_mode=routing_mode,
        timeout_ms=timeout_ms,
        max_retry_count=max_retry_count,
        allow_remote=allow_remote,
        prompt_policy=prompt_policy,
        response_policy=response_policy,
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        template_fallback_enabled=bool(response_policy.get("template_fallback_enabled", True)),
        blocked_reason=blocked_reason,
        blocked_error_code=blocked_error_code,
        blocked_plugin_id=blocked_plugin_id,
    )


def _build_provider_candidates(
    db: Session,
    *,
    provider_profile_ids: list[str],
    routing_mode: str,
    household_id: str | None = None,
) -> tuple[list[AiProviderCandidate], str | None]:
    rows = repository.list_provider_profiles_by_ids(db, provider_profile_ids)
    row_by_id = {row.id: row for row in rows}
    ordered_rows = [row_by_id.get(provider_profile_id) for provider_profile_id in provider_profile_ids]
    return _build_candidates_from_rows(
        db,
        rows=ordered_rows,
        routing_mode=routing_mode,
        household_id=household_id,
    )


def _collect_route_provider_profile_ids(route) -> list[str]:
    return [
        provider_id
        for provider_id in [route.primary_provider_profile_id, *route.fallback_provider_profile_ids]
        if provider_id is not None
    ]


def _list_runtime_default_provider_rows(db: Session) -> list[AiProviderProfile | None]:
    provider_codes = [
        code
        for code in [
            settings.ai_runtime.default_provider_code,
            *settings.ai_runtime.default_fallback_provider_codes,
        ]
        if code
    ]
    return [repository.get_provider_profile_by_code(db, provider_code) for provider_code in provider_codes]


def _list_runtime_default_provider_profile_ids(db: Session) -> list[str]:
    return [row.id for row in _list_runtime_default_provider_rows(db) if row is not None]


def _build_candidates_from_rows(
    db: Session,
    *,
    rows: list[AiProviderProfile | None],
    routing_mode: str,
    household_id: str | None,
) -> tuple[list[AiProviderCandidate], str | None]:
    candidates: list[AiProviderCandidate] = []
    blocked_plugin_id: str | None = None

    for index, row in enumerate(rows):
        if row is None or not row.enabled:
            continue
        if household_id is not None:
            plugin = get_household_ai_provider_plugin_for_profile(
                db,
                household_id=household_id,
                provider_profile=row,
            )
            if plugin is not None and not plugin.enabled:
                blocked_plugin_id = blocked_plugin_id or plugin.id
                continue
        candidates.append(
            AiProviderCandidate(
                provider_profile_id=row.id,
                provider_code=row.provider_code,
                display_name=row.display_name,
                privacy_level=cast(AiPrivacyLevel, row.privacy_level),
                transport_type=cast(AiTransportType, row.transport_type),
                api_family=cast(AiApiFamily, row.api_family),
                order=index,
            )
        )
    return _reorder_candidates(candidates, routing_mode=routing_mode), blocked_plugin_id


def _reorder_candidates(
    candidates: list[AiProviderCandidate],
    *,
    routing_mode: str,
) -> list[AiProviderCandidate]:
    if routing_mode != "local_preferred_then_cloud":
        return candidates
    return sorted(
        candidates,
        key=lambda item: (0 if item.privacy_level == "local_only" else 1, item.order),
    )


def _resolve_binding_context(
    *,
    agent_id: str | None,
    plugin_id: str | None,
    request_payload: Mapping[str, object] | None,
) -> tuple[str | None, str | None]:
    request_context = request_payload.get("request_context") if isinstance(request_payload, Mapping) else None
    context = request_context if isinstance(request_context, Mapping) else {}

    resolved_agent_id = _first_non_empty_string(
        agent_id,
        context.get("effective_agent_id"),
        context.get("agent_id"),
    )
    resolved_plugin_id = _first_non_empty_string(
        plugin_id,
        context.get("plugin_id"),
    )
    return resolved_agent_id, resolved_plugin_id


def _resolve_direct_binding_provider_profile_id(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None,
    agent_id: str | None,
    plugin_id: str | None,
) -> str | None:
    if household_id is None or agent_id is None:
        return None
    from app.modules.agent.service import resolve_bound_provider_profile_id

    return resolve_bound_provider_profile_id(
        db,
        household_id=household_id,
        capability=capability,
        agent_id=agent_id,
        plugin_id=plugin_id,
    )


def _iter_plan_candidates(plan: AiInvocationPlan) -> list[AiProviderCandidate]:
    candidates: list[AiProviderCandidate] = []
    if plan.primary_provider is not None:
        candidates.append(plan.primary_provider)
    candidates.extend(plan.fallback_providers)
    return candidates


def _write_attempt_log(
    db: Session,
    *,
    plan: AiInvocationPlan,
    candidate: AiProviderCandidate,
    masked_fields: list[str],
    status: str,
    latency_ms: int,
    error_code: str | None,
    fallback_used: bool,
    model_name: str | None = None,
    usage: dict[str, object] | None = None,
) -> AiGatewayAttemptResult:
    attempt_status = cast(AiModelCallStatus, status)
    log_model_call(
        db,
        AiModelCallLogCreate(
            capability=plan.capability,
            provider_code=candidate.provider_code,
            model_name=model_name or f"{candidate.provider_code}-{plan.capability}",
            household_id=plan.household_id,
            requester_member_id=plan.requester_member_id,
            trace_id=plan.trace_id,
            input_policy="masked" if masked_fields else "default",
            masked_fields=masked_fields,
            latency_ms=latency_ms,
            usage=usage or {},
            status=attempt_status,
            fallback_used=fallback_used,
            error_code=error_code,
        ),
    )
    return AiGatewayAttemptResult(
        provider_code=candidate.provider_code,
        model_name=model_name or f"{candidate.provider_code}-{plan.capability}",
        status=attempt_status,
        latency_ms=latency_ms,
        error_code=error_code,
        fallback_used=fallback_used,
    )


def _write_template_log(
    db: Session,
    *,
    plan: AiInvocationPlan,
    masked_fields: list[str],
    status: str,
    error_code: str | None,
) -> AiGatewayAttemptResult:
    attempt_status = cast(AiModelCallStatus, status)
    log_model_call(
        db,
        AiModelCallLogCreate(
            capability=plan.capability,
            provider_code="template",
            model_name="template-fallback",
            household_id=plan.household_id,
            requester_member_id=plan.requester_member_id,
            trace_id=plan.trace_id,
            input_policy="masked" if masked_fields else "default",
            masked_fields=masked_fields,
            latency_ms=0,
            usage={},
            status=attempt_status,
            fallback_used=True,
            error_code=error_code,
        ),
    )
    return AiGatewayAttemptResult(
        provider_code="template",
        model_name="template-fallback",
        status=attempt_status,
        latency_ms=0,
        error_code=error_code,
        fallback_used=True,
    )


def _map_error_code_to_status(error_code: str) -> str:
    if error_code == "timeout":
        return "timeout"
    if error_code == "rate_limited":
        return "rate_limited"
    if error_code == "validation_error":
        return "validation_error"
    return "failed"


def _summarize_attempts(attempts: list[AiGatewayAttemptResult]) -> str:
    if not attempts:
        return "-"
    return ",".join(
        f"{attempt.provider_code}:{attempt.status}:{attempt.error_code or 'ok'}"
        for attempt in attempts
    )


def _new_trace_id() -> str:
    return uuid4().hex


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None
