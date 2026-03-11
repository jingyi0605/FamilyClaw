from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.ai_gateway.models import AiCapabilityRoute, AiModelCallLog, AiProviderProfile


def get_provider_profile(db: Session, provider_profile_id: str) -> AiProviderProfile | None:
    return db.get(AiProviderProfile, provider_profile_id)


def get_provider_profile_by_code(db: Session, provider_code: str) -> AiProviderProfile | None:
    stmt = select(AiProviderProfile).where(AiProviderProfile.provider_code == provider_code)
    return db.scalar(stmt)


def list_provider_profiles(
    db: Session,
    *,
    enabled: bool | None = None,
) -> Sequence[AiProviderProfile]:
    stmt: Select[tuple[AiProviderProfile]] = select(AiProviderProfile).order_by(AiProviderProfile.provider_code.asc())
    if enabled is not None:
        stmt = stmt.where(AiProviderProfile.enabled == enabled)
    return list(db.scalars(stmt).all())


def list_provider_profiles_by_ids(db: Session, provider_profile_ids: list[str]) -> Sequence[AiProviderProfile]:
    if not provider_profile_ids:
        return []
    stmt = select(AiProviderProfile).where(AiProviderProfile.id.in_(provider_profile_ids))
    return list(db.scalars(stmt).all())


def add_provider_profile(db: Session, row: AiProviderProfile) -> AiProviderProfile:
    db.add(row)
    return row


def delete_provider_profile(db: Session, row: AiProviderProfile) -> None:
    db.delete(row)


def get_capability_route(
    db: Session,
    *,
    capability: str,
    household_id: str | None,
) -> AiCapabilityRoute | None:
    stmt = (
        select(AiCapabilityRoute)
        .where(AiCapabilityRoute.capability == capability)
        .where(AiCapabilityRoute.household_id == household_id)
    )
    return db.scalar(stmt)


def list_capability_routes(
    db: Session,
    *,
    household_id: str | None = None,
) -> Sequence[AiCapabilityRoute]:
    stmt: Select[tuple[AiCapabilityRoute]] = select(AiCapabilityRoute).order_by(
        AiCapabilityRoute.capability.asc(),
        AiCapabilityRoute.household_id.asc().nullsfirst(),
    )
    if household_id is None:
        stmt = stmt.where(AiCapabilityRoute.household_id.is_(None))
    else:
        stmt = stmt.where(AiCapabilityRoute.household_id == household_id)
    return list(db.scalars(stmt).all())


def list_all_capability_routes(db: Session) -> Sequence[AiCapabilityRoute]:
    stmt: Select[tuple[AiCapabilityRoute]] = select(AiCapabilityRoute).order_by(
        AiCapabilityRoute.capability.asc(),
        AiCapabilityRoute.household_id.asc().nullsfirst(),
    )
    return list(db.scalars(stmt).all())


def add_capability_route(db: Session, row: AiCapabilityRoute) -> AiCapabilityRoute:
    db.add(row)
    return row


def add_model_call_log(db: Session, row: AiModelCallLog) -> AiModelCallLog:
    db.add(row)
    return row


def list_model_call_logs(
    db: Session,
    *,
    household_id: str | None = None,
    capability: str | None = None,
    limit: int = 50,
) -> Sequence[AiModelCallLog]:
    stmt: Select[tuple[AiModelCallLog]] = select(AiModelCallLog).order_by(AiModelCallLog.created_at.desc()).limit(limit)
    if household_id is not None:
        stmt = stmt.where(AiModelCallLog.household_id == household_id)
    if capability is not None:
        stmt = stmt.where(AiModelCallLog.capability == capability)
    return list(db.scalars(stmt).all())
