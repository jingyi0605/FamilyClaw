from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.household.schemas import HouseholdCreate, HouseholdListResponse, HouseholdRead
from app.modules.household.service import create_household, get_household_or_404, list_households

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household_endpoint(
    payload: HouseholdCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HouseholdRead:
    household = create_household(db, payload)
    db.flush()
    write_audit_log(
        db,
        household_id=household.id,
        actor=actor,
        action="household.create",
        target_type="household",
        target_id=household.id,
        result="success",
        details=payload.model_dump(),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(household)
    return HouseholdRead.model_validate(household)


@router.get("", response_model=HouseholdListResponse)
def list_households_endpoint(
    pagination: tuple[int, int] = Depends(pagination_params),
    status_value: Annotated[str | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
) -> HouseholdListResponse:
    page, page_size = pagination
    households, total = list_households(
        db,
        page=page,
        page_size=page_size,
        status_value=status_value,
    )
    return HouseholdListResponse(
        items=[HouseholdRead.model_validate(household) for household in households],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{household_id}", response_model=HouseholdRead)
def get_household_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
) -> HouseholdRead:
    household = get_household_or_404(db, household_id)
    return HouseholdRead.model_validate(household)
