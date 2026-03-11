from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, get_actor_context, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.family_qa.schemas import (
    FamilyQaQueryRequest,
    FamilyQaQueryResponse,
    FamilyQaSuggestionsResponse,
)
from app.modules.family_qa.service import list_family_qa_suggestions, query_family_qa

router = APIRouter(prefix="/family-qa", tags=["family-qa"])


@router.post("/query", response_model=FamilyQaQueryResponse)
def query_family_qa_endpoint(
    payload: FamilyQaQueryRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> FamilyQaQueryResponse:
    ensure_actor_can_access_household(actor, payload.household_id)
    payload = _normalize_query_payload(payload, actor)
    try:
        result = query_family_qa(db, payload, actor)
        if payload.requester_member_id is not None:
            write_audit_log(
                db,
                household_id=payload.household_id,
                actor=actor,
                action="family_qa.query",
                target_type="family_qa",
                target_id=payload.requester_member_id,
                result="success",
                details={
                    "question": payload.question,
                    "answer_type": result.answer_type,
                    "degraded": result.degraded,
                    "ai_provider_code": result.ai_provider_code,
                },
            )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/suggestions", response_model=FamilyQaSuggestionsResponse)
def list_family_qa_suggestions_endpoint(
    household_id: str,
    agent_id: str | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> FamilyQaSuggestionsResponse:
    ensure_actor_can_access_household(actor, household_id)
    payload_requester_id = actor.member_id if actor.role != "admin" else None
    return list_family_qa_suggestions(
        db,
        household_id=household_id,
        requester_member_id=payload_requester_id,
        agent_id=agent_id,
        actor=actor,
    )


def _normalize_query_payload(payload: FamilyQaQueryRequest, actor: ActorContext) -> FamilyQaQueryRequest:
    if actor.role == "admin":
        return payload
    if actor.member_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor required")
    if payload.requester_member_id is not None and payload.requester_member_id != actor.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member actor cannot query as another member",
        )
    return payload.model_copy(update={"requester_member_id": actor.member_id})
