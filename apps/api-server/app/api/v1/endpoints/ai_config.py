from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailRead,
    AgentListResponse,
    AgentMemberCognitionRead,
    AgentMemberCognitionsUpsert,
    AgentRuntimePolicyRead,
    AgentRuntimePolicyUpsert,
    AgentSoulProfileRead,
    AgentSoulProfileUpsert,
)
from app.modules.agent.service import (
    AgentNotFoundError,
    create_agent,
    get_agent_detail,
    list_ai_config_agents,
    upsert_agent_member_cognitions,
    upsert_agent_runtime_policy,
    upsert_agent_soul,
)
from app.modules.audit.service import write_audit_log


router = APIRouter(prefix="/ai-config", tags=["ai-config"])


@router.get("/{household_id}", response_model=AgentListResponse)
def list_ai_config_agents_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> AgentListResponse:
    return list_ai_config_agents(db, household_id=household_id)


@router.post("/{household_id}/agents", response_model=AgentDetailRead, status_code=status.HTTP_201_CREATED)
def create_ai_config_agent_endpoint(
    household_id: str,
    payload: AgentCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentDetailRead:
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
    _actor: ActorContext = Depends(require_admin_actor),
) -> AgentDetailRead:
    try:
        return get_agent_detail(db, household_id=household_id, agent_id=agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{household_id}/agents/{agent_id}/soul", response_model=AgentSoulProfileRead)
def upsert_ai_config_agent_soul_endpoint(
    household_id: str,
    agent_id: str,
    payload: AgentSoulProfileUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AgentSoulProfileRead:
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
