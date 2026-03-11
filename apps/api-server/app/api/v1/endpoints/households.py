from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    ActorContext,
    ensure_actor_can_access_household,
    pagination_params,
    require_admin_actor,
    require_authenticated_actor,
)
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.household.schemas import (
    HouseholdCreate,
    HouseholdListResponse,
    HouseholdRead,
    HouseholdSetupStatusRead,
    HouseholdUpdate,
)
from app.modules.household.service import (
    create_household,
    get_household_or_404,
    get_household_setup_status,
    list_households,
    update_household,
)

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
    actor: ActorContext = Depends(require_authenticated_actor),
) -> HouseholdListResponse:
    page, page_size = pagination
    if actor.account_type == "system":
        households, total = list_households(
            db,
            page=page,
            page_size=page_size,
            status_value=status_value,
        )
    else:
        if actor.household_id is None:
            return HouseholdListResponse(items=[], page=page, page_size=page_size, total=0)
        household = get_household_or_404(db, actor.household_id)
        households = [household]
        if status_value and household.status != status_value:
            households = []
        total = len(households)
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
    actor: ActorContext = Depends(require_authenticated_actor),
) -> HouseholdRead:
    ensure_actor_can_access_household(actor, household_id)
    household = get_household_or_404(db, household_id)
    return HouseholdRead.model_validate(household)


@router.get("/{household_id}/setup-status", response_model=HouseholdSetupStatusRead)
def get_household_setup_status_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_authenticated_actor),
) -> HouseholdSetupStatusRead:
    ensure_actor_can_access_household(actor, household_id)
    return get_household_setup_status(db, household_id)


@router.patch("/{household_id}", response_model=HouseholdRead)
def update_household_endpoint(
    household_id: str,
    payload: HouseholdUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HouseholdRead:
    household = get_household_or_404(db, household_id)
    household, changed_fields = update_household(db, household, payload)
    if changed_fields:
        write_audit_log(
            db,
            household_id=household.id,
            actor=actor,
            action="household.update",
            target_type="household",
            target_id=household.id,
            result="success",
            details={"changed_fields": changed_fields},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(household)
    return HouseholdRead.model_validate(household)
