from fastapi import HTTPException, status
from sqlalchemy import func, select
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


def list_households(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_value: str | None = None,
) -> tuple[list[Household], int]:
    filters = []
    if status_value:
        filters.append(Household.status == status_value)

    total = db.scalar(select(func.count()).select_from(Household).where(*filters)) or 0
    statement = (
        select(Household)
        .where(*filters)
        .order_by(Household.created_at.desc(), Household.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    households = list(db.scalars(statement).all())
    return households, total
