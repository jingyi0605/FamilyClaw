from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.account.schemas import AccountRead, AccountMemberBindingRead, HouseholdAccountCreateRequest, HouseholdAccountCreateResponse
from app.modules.account.service import create_household_account_with_binding
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
