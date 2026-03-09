from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.household.models import Household
from app.modules.household.schemas import HouseholdCreate


def create_household(db: Session, payload: HouseholdCreate) -> Household:
    household = Household(
        id=new_uuid(),
        name=payload.name,
        timezone=payload.timezone,
        locale=payload.locale,
        status="active",
    )
    db.add(household)
    return household


def get_household_or_404(db: Session, household_id: str) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )
    return household

