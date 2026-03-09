from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.household.schemas import HouseholdCreate, HouseholdRead
from app.modules.household.service import create_household, get_household_or_404

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


@router.get("/{household_id}", response_model=HouseholdRead)
def get_household_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
) -> HouseholdRead:
    household = get_household_or_404(db, household_id)
    return HouseholdRead.model_validate(household)
