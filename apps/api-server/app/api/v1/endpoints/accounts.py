from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.account.schemas import (
    AccountMemberBindingRead,
    AccountRead,
    HouseholdAccountCreateRequest,
    HouseholdAccountCreateResponse,
    HouseholdAccountListResponse,
    HouseholdAccountResetPasswordRequest,
    HouseholdAccountUpdateRequest,
    AccountWithBindingRead,
)
from app.modules.account.service import (
    create_household_account_with_binding,
    delete_household_account,
    list_household_accounts,
    reset_household_account_password,
    update_household_account,
)
from app.modules.audit.service import write_audit_log

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/household", response_model=HouseholdAccountCreateResponse, status_code=status.HTTP_201_CREATED)
def create_household_account_endpoint(
    payload: HouseholdAccountCreateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HouseholdAccountCreateResponse:
    account, binding = create_household_account_with_binding(db, payload)
    db.flush()
    write_audit_log(
        db,
        household_id=binding.household_id,
        actor=actor,
        action="account.household.create",
        target_type="account",
        target_id=account.id,
        result="success",
        details={
            "member_id": binding.member_id,
            "username": account.username,
            "account_type": account.account_type,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(account)
    return HouseholdAccountCreateResponse(
        account=AccountRead.model_validate(account),
        binding=AccountMemberBindingRead.model_validate(binding),
    )


@router.get("/household/{household_id}", response_model=HouseholdAccountListResponse)
def list_household_accounts_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HouseholdAccountListResponse:
    """List all household accounts with their member bindings."""
    if actor.household_id != household_id:
        # System admin can access any household, household admin can only access their own
        if actor.account_type not in {"system", "bootstrap"}:
            from fastapi import HTTPException
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")

    items_data = list_household_accounts(db, household_id)
    items = [
        AccountWithBindingRead(
            account=AccountRead.model_validate(account),
            binding=AccountMemberBindingRead.model_validate(binding) if binding else None,
        )
        for account, binding in items_data
    ]
    return HouseholdAccountListResponse(items=items, total=len(items))


@router.patch("/household/{household_id}/{account_id}", response_model=AccountRead)
def update_household_account_endpoint(
    household_id: str,
    account_id: str,
    payload: HouseholdAccountUpdateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AccountRead:
    """Update a household account's status or must_change_password flag."""
    if actor.household_id != household_id:
        if actor.account_type not in {"system", "bootstrap"}:
            from fastapi import HTTPException
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")

    account = update_household_account(db, account_id, household_id, payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="account.update",
        target_type="account",
        target_id=account_id,
        result="success",
        details={"status": payload.status, "must_change_password": payload.must_change_password},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(account)
    return AccountRead.model_validate(account)


@router.post("/household/{household_id}/{account_id}/reset-password", response_model=AccountRead)
def reset_household_account_password_endpoint(
    household_id: str,
    account_id: str,
    payload: HouseholdAccountResetPasswordRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AccountRead:
    """Reset a household account's password."""
    if actor.household_id != household_id:
        if actor.account_type not in {"system", "bootstrap"}:
            from fastapi import HTTPException
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")

    account = reset_household_account_password(db, account_id, household_id, payload)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="account.reset_password",
        target_type="account",
        target_id=account_id,
        result="success",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(account)
    return AccountRead.model_validate(account)


@router.delete("/household/{household_id}/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household_account_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    """Delete a household account."""
    if actor.household_id != household_id:
        if actor.account_type not in {"system", "bootstrap"}:
            from fastapi import HTTPException
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")

    delete_household_account(db, account_id, household_id)
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="account.delete",
        target_type="account",
        target_id=account_id,
        result="success",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
