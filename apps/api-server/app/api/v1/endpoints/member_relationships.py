from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.relationship.schemas import (
    MemberRelationshipCreate,
    MemberRelationshipListResponse,
    MemberRelationshipRead,
    RelationType,
)
from app.modules.relationship.service import create_relationship, delete_relationship, list_relationships

router = APIRouter(prefix="/member-relationships", tags=["member-relationships"])


@router.post("", response_model=MemberRelationshipRead, status_code=status.HTTP_201_CREATED)
def create_member_relationship_endpoint(
    payload: MemberRelationshipCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberRelationshipRead:
    relationship = create_relationship(db, payload)
    db.flush()
    write_audit_log(
        db,
        household_id=relationship.household_id,
        actor=actor,
        action="member_relationship.create",
        target_type="member_relationship",
        target_id=relationship.id,
        result="success",
        details=payload.model_dump(),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(relationship)
    return MemberRelationshipRead.model_validate(relationship)


@router.get("", response_model=MemberRelationshipListResponse)
def list_member_relationships_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    source_member_id: str | None = None,
    target_member_id: str | None = None,
    relation_type: Annotated[RelationType | None, Query()] = None,
    db: Session = Depends(get_db),
) -> MemberRelationshipListResponse:
    page, page_size = pagination
    items, total = list_relationships(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        source_member_id=source_member_id,
        target_member_id=target_member_id,
        relation_type=relation_type,
    )
    return MemberRelationshipListResponse(
        items=[MemberRelationshipRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_relationship_endpoint(
    relationship_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    try:
        relationship = delete_relationship(db, relationship_id)
        write_audit_log(
            db,
            household_id=relationship.household_id,
            actor=actor,
            action="member_relationship.delete",
            target_type="member_relationship",
            target_id=relationship_id,
            result="success",
            details={"relationship_id": relationship_id},
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
