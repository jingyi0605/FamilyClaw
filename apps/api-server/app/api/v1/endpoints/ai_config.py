from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.agent.bootstrap_service import (
    advance_butler_bootstrap_session,
    confirm_butler_bootstrap_session,
    get_latest_butler_bootstrap_session,
    restart_butler_bootstrap_session,
    start_butler_bootstrap_session,
)
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailRead,
    AgentListResponse,
    AgentMemoryInsightRead,
    AgentPluginMemoryCheckpointRead,
    AgentPluginMemoryCheckpointRequest,
    ButlerBootstrapConfirm,
    ButlerBootstrapMessageCreate,
    ButlerBootstrapSessionRead,
    AgentMemberCognitionRead,
    AgentMemberCognitionsUpsert,
    AgentRuntimePolicyRead,
    AgentRuntimePolicyUpsert,
    AgentSoulProfileRead,
    AgentSoulProfileUpsert,
    AgentUpdate,
)
from app.modules.agent.service import (
    AgentNotFoundError,
    build_agent_memory_insight,
    create_agent,
    get_agent_detail,
    list_ai_config_agents,
    run_agent_plugin_memory_checkpoint,
    update_agent,
    upsert_agent_member_cognitions,
    upsert_agent_runtime_policy,
    upsert_agent_soul,
)
from app.modules.ai_gateway.schemas import (
    AiCapability,
    AiCapabilityRouteRead,
    AiCapabilityRouteUpsert,
    AiProviderAdapterRead,
    AiProviderProfileCreate,
    AiProviderProfileRead,
    AiProviderProfileUpdate,
)
from app.modules.ai_gateway.provider_config_service import list_provider_adapters
from app.modules.ai_gateway.service import (
    AiGatewayConfigurationError,
    AiGatewayNotFoundError,
    create_provider_profile,
    delete_provider_profile,
    list_capability_routes,
    list_provider_profiles,
    update_provider_profile,
    upsert_capability_route,
)
from app.modules.audit.service import write_audit_log
from app.modules.plugin import AgentPluginInvokeRequest, AgentPluginInvokeResult, invoke_agent_plugin


router = APIRouter(prefix="/ai-config", tags=["ai-config"])


@router.get("/provider-adapters", response_model=list[AiProviderAdapterRead])
def list_ai_provider_adapters_endpoint(
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiProviderAdapterRead]:
    return list_provider_adapters()


@router.get("/{household_id}/provider-profiles", response_model=list[AiProviderProfileRead])
def list_ai_config_provider_profiles_endpoint(
    household_id: str,
    enabled: bool | None = Query(default=None),
    capability: AiCapability | None = Query(default=None),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiProviderProfileRead]:
    ensure_actor_can_access_household(_actor, household_id)
    return list_provider_profiles(db, enabled=enabled, capability=capability)


@router.post("/{household_id}/provider-profiles", response_model=AiProviderProfileRead, status_code=status.HTTP_201_CREATED)
def create_ai_config_provider_profile_endpoint(
    household_id: str,
    payload: AiProviderProfileCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiProviderProfileRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = create_provider_profile(db, payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="ai_provider.create",
            target_type="ai_provider_profile",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.put("/{household_id}/provider-profiles/{profile_id}", response_model=AiProviderProfileRead)
def update_ai_config_provider_profile_endpoint(
    household_id: str,
    profile_id: str,
    payload: AiProviderProfileUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiProviderProfileRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = update_provider_profile(db, profile_id, payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="ai_provider.update",
            target_type="ai_provider_profile",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except AiGatewayNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.delete("/{household_id}/provider-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_config_provider_profile_endpoint(
    household_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    ensure_actor_can_access_household(actor, household_id)
    try:
        delete_provider_profile(db, profile_id)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="ai_provider.delete",
            target_type="ai_provider_profile",
            target_id=profile_id,
            result="success",
            details={"profile_id": profile_id},
        )
        db.commit()
    except AiGatewayNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{household_id}/provider-routes", response_model=list[AiCapabilityRouteRead])
def list_ai_config_provider_routes_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiCapabilityRouteRead]:
    ensure_actor_can_access_household(_actor, household_id)
    return list_capability_routes(db, household_id=household_id)


@router.put("/{household_id}/provider-routes/{capability}", response_model=AiCapabilityRouteRead)
def upsert_ai_config_provider_route_endpoint(
    household_id: str,
    capability: AiCapability,
    payload: AiCapabilityRouteUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiCapabilityRouteRead:
    ensure_actor_can_access_household(actor, household_id)
    if payload.capability != capability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path capability 与 payload capability 不一致",
        )
    if payload.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload household_id 与路径不一致",
        )
    try:
        result = upsert_capability_route(db, payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="ai_route.upsert",
            target_type="ai_capability_route",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/{household_id}/butler-bootstrap/sessions", response_model=ButlerBootstrapSessionRead, status_code=status.HTTP_201_CREATED)
def create_butler_bootstrap_session_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ButlerBootstrapSessionRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = start_butler_bootstrap_session(db, household_id=household_id)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/{household_id}/butler-bootstrap/sessions/latest", response_model=ButlerBootstrapSessionRead | None)
def get_latest_butler_bootstrap_session_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ButlerBootstrapSessionRead | None:
    ensure_actor_can_access_household(actor, household_id)
    return get_latest_butler_bootstrap_session(db, household_id=household_id)


@router.post("/{household_id}/butler-bootstrap/sessions/restart", response_model=ButlerBootstrapSessionRead, status_code=status.HTTP_201_CREATED)
def restart_butler_bootstrap_session_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ButlerBootstrapSessionRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = restart_butler_bootstrap_session(db, household_id=household_id)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/{household_id}/butler-bootstrap/sessions/{session_id}/messages", response_model=ButlerBootstrapSessionRead)
def append_butler_bootstrap_message_endpoint(
    household_id: str,
    session_id: str,
    payload: ButlerBootstrapMessageCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ButlerBootstrapSessionRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = advance_butler_bootstrap_session(
            db,
            household_id=household_id,
            session_id=session_id,
            payload=payload,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/{household_id}/butler-bootstrap/sessions/{session_id}/confirm", response_model=AgentDetailRead, status_code=status.HTTP_201_CREATED)
def confirm_butler_bootstrap_session_endpoint(
    household_id: str,
    session_id: str,
    payload: ButlerBootstrapConfirm,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    result = confirm_butler_bootstrap_session(
        db,
        household_id=household_id,
        session_id=session_id,
        payload=payload,
    )
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.bootstrap_create",
        target_type="family_agent",
        target_id=result.id,
        result="success",
        details={"session_id": session_id, **payload.model_dump(mode="json")},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.get("/{household_id}", response_model=AgentListResponse)
def list_ai_config_agents_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_bound_member_actor),
) -> AgentListResponse:
    ensure_actor_can_access_household(_actor, household_id)
    return list_ai_config_agents(db, household_id=household_id)


@router.post("/{household_id}/agents", response_model=AgentDetailRead, status_code=status.HTTP_201_CREATED)
def create_ai_config_agent_endpoint(
    household_id: str,
    payload: AgentCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    result = create_agent(db, household_id=household_id, payload=payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent.create",
        target_type="family_agent",
        target_id=result.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.get("/{household_id}/agents/{agent_id}", response_model=AgentDetailRead)
def get_ai_config_agent_detail_endpoint(
    household_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_bound_member_actor),
) -> AgentDetailRead:
    ensure_actor_can_access_household(_actor, household_id)
    try:
        return get_agent_detail(db, household_id=household_id, agent_id=agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{household_id}/agents/{agent_id}", response_model=AgentDetailRead)
def update_ai_config_agent_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = update_agent(db, household_id=household_id, agent_id=agent_id, payload=payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="agent.update",
            target_type="family_agent",
            target_id=agent_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except AgentNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.put("/{household_id}/agents/{agent_id}/soul", response_model=AgentSoulProfileRead)
def upsert_ai_config_agent_soul_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentSoulProfileUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentSoulProfileRead:
    ensure_actor_can_access_household(actor, household_id)
    result = upsert_agent_soul(db, household_id=household_id, agent_id=agent_id, payload=payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent_soul.upsert",
        target_type="family_agent_soul_profile",
        target_id=result.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.put("/{household_id}/agents/{agent_id}/member-cognitions", response_model=list[AgentMemberCognitionRead])
def upsert_ai_config_agent_member_cognitions_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentMemberCognitionsUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[AgentMemberCognitionRead]:
    ensure_actor_can_access_household(actor, household_id)
    result = upsert_agent_member_cognitions(db, household_id=household_id, agent_id=agent_id, payload=payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent_member_cognition.upsert",
        target_type="family_agent_member_cognition",
        target_id=agent_id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.put("/{household_id}/agents/{agent_id}/runtime-policy", response_model=AgentRuntimePolicyRead)
def upsert_ai_config_agent_runtime_policy_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentRuntimePolicyUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentRuntimePolicyRead:
    ensure_actor_can_access_household(actor, household_id)
    result = upsert_agent_runtime_policy(db, household_id=household_id, agent_id=agent_id, payload=payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="agent_runtime_policy.upsert",
        target_type="family_agent_runtime_policy",
        target_id=agent_id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.post("/{household_id}/agents/{agent_id}/plugin-invocations", response_model=AgentPluginInvokeResult)
def invoke_agent_plugin_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentPluginInvokeRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> AgentPluginInvokeResult:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = invoke_agent_plugin(
            db,
            household_id=household_id,
            agent_id=agent_id,
            request=payload,
            actor=actor,
        )
        db.commit()
        return result
    except AgentNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/{household_id}/agents/{agent_id}/memory-insight", response_model=AgentMemoryInsightRead)
def get_agent_memory_insight_endpoint(
    household_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> AgentMemoryInsightRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return build_agent_memory_insight(
            db,
            household_id=household_id,
            agent_id=agent_id,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{household_id}/agents/{agent_id}/plugin-memory-checkpoint", response_model=AgentPluginMemoryCheckpointRead)
def run_agent_plugin_memory_checkpoint_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentPluginMemoryCheckpointRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> AgentPluginMemoryCheckpointRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = run_agent_plugin_memory_checkpoint(
            db,
            household_id=household_id,
            agent_id=agent_id,
            payload=payload,
        )
        db.commit()
        return result
    except AgentNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
