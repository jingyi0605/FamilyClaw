from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import cast

from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.models import FamilyAgent
from app.modules.ai_gateway.models import AiCapabilityRoute
from app.modules.household.models import Household
from app.modules.household.schemas import (
    HouseholdCoordinateUpsert,
    HouseholdRead,
    HouseholdCreate,
    HouseholdSetupStatusRead,
    HouseholdSetupStepCode,
    HouseholdUpdate,
)
from app.modules.member.models import Member
from app.modules.region.service import (
    RegionServiceError,
    get_household_coordinate_override,
    get_household_region_context,
    has_household_region_binding,
    upsert_household_region,
)

SETUP_REQUIRED_STEPS: tuple[HouseholdSetupStepCode, ...] = (
    "family_profile",
    "first_member",
    "provider_setup",
    "first_butler_agent",
)
SETUP_REQUIRED_PROVIDER_CAPABILITIES: tuple[str, ...] = ("text",)
HISTORICAL_REQUIRED_STEPS: tuple[HouseholdSetupStepCode, ...] = (
    "provider_setup",
    "first_butler_agent",
)


def create_household(db: Session, payload: HouseholdCreate) -> Household:
    household = Household(
        id=new_uuid(),
        name=payload.name,
        city=payload.city.strip() if isinstance(payload.city, str) and payload.city.strip() else None,
        timezone=payload.timezone,
        locale=payload.locale,
        status="active",
        setup_status="pending",
    )
    db.add(household)
    db.flush()
    if payload.region_selection is not None:
        upsert_household_region(
            db,
            household=household,
            selection=payload.region_selection,
            source="create",
        )
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


def get_household_setup_status(db: Session, household_id: str) -> HouseholdSetupStatusRead:
    household = get_household_or_404(db, household_id)
    is_new_household = household.setup_status == "pending"

    family_profile_completed = _is_family_profile_completed(
        db,
        household,
        require_formal_region=is_new_household,
    )
    first_member_completed, member_updated_at = _get_first_member_status(db, household_id)
    provider_setup_completed, provider_updated_at = _get_provider_setup_status(
        db,
        household_id=household_id,
        enforce_household_scope=is_new_household,
    )
    first_butler_agent_completed, agent_updated_at = _get_first_butler_agent_status(db, household_id)

    completion_by_step: dict[HouseholdSetupStepCode, bool] = {
        "family_profile": family_profile_completed,
        "first_member": first_member_completed,
        "provider_setup": provider_setup_completed,
        "first_butler_agent": first_butler_agent_completed,
    }
    completed_steps: list[HouseholdSetupStepCode] = [step for step in SETUP_REQUIRED_STEPS if completion_by_step[step]]
    missing_requirements: list[HouseholdSetupStepCode] = [step for step in SETUP_REQUIRED_STEPS if not completion_by_step[step]]
    required_steps: tuple[HouseholdSetupStepCode, ...] = (
        SETUP_REQUIRED_STEPS if is_new_household else HISTORICAL_REQUIRED_STEPS
    )
    blocking_missing_steps: list[HouseholdSetupStepCode] = [
        step for step in required_steps if not completion_by_step[step]
    ]
    all_required_completed = len(blocking_missing_steps) == 0
    has_progress = len(completed_steps) > 0

    if all_required_completed:
        current_step: HouseholdSetupStepCode = cast(HouseholdSetupStepCode, "finish")
        setup_status = "completed"
    else:
        current_step = blocking_missing_steps[0]
        setup_status = "in_progress" if has_progress else "pending"

    if not is_new_household and all_required_completed and missing_requirements:
        current_step = missing_requirements[0]

    is_required = len(blocking_missing_steps) > 0
    updated_at = max(
        item
        for item in [
            household.updated_at,
            member_updated_at,
            provider_updated_at,
            agent_updated_at,
        ]
        if item
    )

    return HouseholdSetupStatusRead(
        household_id=household.id,
        status=setup_status,
        current_step=current_step,
        completed_steps=completed_steps,
        missing_requirements=missing_requirements,
        is_required=is_required,
        resume_token=None,
        updated_at=updated_at,
    )


def _is_family_profile_completed(
    db: Session,
    household: Household,
    *,
    require_formal_region: bool,
) -> bool:
    has_basic_profile = all(
        isinstance(value, str) and value.strip()
        for value in [household.name, household.timezone, household.locale]
    )
    if not has_basic_profile:
        return False
    if require_formal_region:
        return has_household_region_binding(db, household.id)
    if has_household_region_binding(db, household.id):
        return True
    return isinstance(household.city, str) and household.city.strip() != ""


def update_household(db: Session, household: Household, payload: HouseholdUpdate) -> tuple[Household, dict]:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return household, {}

    normalized_data = dict(update_data)
    region_selection = normalized_data.pop("region_selection", None)
    has_region_binding = has_household_region_binding(db, household.id)
    if "city" in normalized_data:
        city = normalized_data["city"]
        normalized_city = city.strip() if isinstance(city, str) and city.strip() else None
        if has_region_binding and region_selection is None:
            normalized_data.pop("city")
        else:
            normalized_data["city"] = normalized_city

    changed_fields: dict[str, object] = {}
    for field_name, field_value in normalized_data.items():
        setattr(household, field_name, field_value)
        changed_fields[field_name] = field_value

    if payload.region_selection is not None:
        binding = upsert_household_region(
            db,
            household=household,
            selection=payload.region_selection,
            source="update",
        )
        changed_fields["region_selection"] = binding.region_code
        changed_fields["city"] = household.city

    db.add(household)
    return household, changed_fields


def upsert_household_coordinate(
    db: Session,
    *,
    household: Household,
    payload: HouseholdCoordinateUpsert,
) -> Household:
    if not payload.confirmed:
        raise RegionServiceError(
            detail="候选定位结果必须经用户确认后才能保存",
            error_code="coordinate_unconfirmed",
            field="confirmed",
        )
    household.latitude = payload.latitude
    household.longitude = payload.longitude
    household.coordinate_source = payload.coordinate_source
    household.coordinate_precision = "point"
    household.coordinate_updated_at = utc_now_iso()
    db.add(household)
    return household


def build_household_read(db: Session, household: Household) -> HouseholdRead:
    return HouseholdRead(
        id=household.id,
        name=household.name,
        city=household.city,
        timezone=household.timezone,
        locale=household.locale,
        status=household.status,
        region=get_household_region_context(db, household.id, household=household),
        coordinate_override=get_household_coordinate_override(household),
        created_at=household.created_at,
        updated_at=household.updated_at,
    )


def _get_first_member_status(db: Session, household_id: str) -> tuple[bool, str | None]:
    member_count = db.scalar(
        select(func.count())
        .select_from(Member)
        .where(Member.household_id == household_id, Member.status == "active")
    ) or 0
    updated_at = db.scalar(
        select(func.max(Member.updated_at)).where(Member.household_id == household_id)
    )
    return member_count > 0, updated_at


def _get_provider_setup_status(
    db: Session,
    *,
    household_id: str,
    enforce_household_scope: bool,
) -> tuple[bool, str | None]:
    household_route_count = db.scalar(
        select(func.count())
        .select_from(AiCapabilityRoute)
        .where(
            AiCapabilityRoute.household_id == household_id,
            AiCapabilityRoute.capability.in_(SETUP_REQUIRED_PROVIDER_CAPABILITIES),
            AiCapabilityRoute.enabled.is_(True),
            AiCapabilityRoute.primary_provider_profile_id.is_not(None),
        )
    ) or 0
    if household_route_count > 0:
        updated_at = db.scalar(
            select(func.max(AiCapabilityRoute.updated_at)).where(AiCapabilityRoute.household_id == household_id)
        )
        return True, updated_at

    global_updated_at = db.scalar(
        select(func.max(AiCapabilityRoute.updated_at)).where(AiCapabilityRoute.household_id.is_(None))
    )
    if enforce_household_scope:
        return False, global_updated_at

    global_route_count = db.scalar(
        select(func.count())
        .select_from(AiCapabilityRoute)
        .where(
            AiCapabilityRoute.household_id.is_(None),
            AiCapabilityRoute.capability.in_(SETUP_REQUIRED_PROVIDER_CAPABILITIES),
            AiCapabilityRoute.enabled.is_(True),
            AiCapabilityRoute.primary_provider_profile_id.is_not(None),
        )
    ) or 0
    return global_route_count > 0, global_updated_at


def _get_first_butler_agent_status(db: Session, household_id: str) -> tuple[bool, str | None]:
    agent_count = db.scalar(
        select(func.count())
        .select_from(FamilyAgent)
        .where(
            FamilyAgent.household_id == household_id,
            FamilyAgent.agent_type == "butler",
            FamilyAgent.status == "active",
        )
    ) or 0
    updated_at = db.scalar(
        select(func.max(FamilyAgent.updated_at)).where(FamilyAgent.household_id == household_id)
    )
    return agent_count > 0, updated_at
