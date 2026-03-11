from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.agent.models import (
    FamilyAgent,
    FamilyAgentMemberCognition,
    FamilyAgentRuntimePolicy,
    FamilyAgentSoulProfile,
)


def get_agent(db: Session, agent_id: str) -> FamilyAgent | None:
    return db.get(FamilyAgent, agent_id)


def get_agent_by_household_and_id(db: Session, *, household_id: str, agent_id: str) -> FamilyAgent | None:
    stmt = select(FamilyAgent).where(FamilyAgent.id == agent_id, FamilyAgent.household_id == household_id)
    return db.scalar(stmt)


def get_agent_by_household_and_code(db: Session, *, household_id: str, code: str) -> FamilyAgent | None:
    stmt = select(FamilyAgent).where(FamilyAgent.household_id == household_id, FamilyAgent.code == code)
    return db.scalar(stmt)


def get_primary_agent(db: Session, *, household_id: str) -> FamilyAgent | None:
    stmt = select(FamilyAgent).where(FamilyAgent.household_id == household_id, FamilyAgent.is_primary.is_(True))
    return db.scalar(stmt)


def list_agents(
    db: Session,
    *,
    household_id: str,
    status: str | None = None,
) -> Sequence[FamilyAgent]:
    stmt: Select[tuple[FamilyAgent]] = (
        select(FamilyAgent)
        .where(FamilyAgent.household_id == household_id)
        .order_by(FamilyAgent.sort_order.asc(), FamilyAgent.created_at.asc())
    )
    if status is not None:
        stmt = stmt.where(FamilyAgent.status == status)
    return list(db.scalars(stmt).all())


def add_agent(db: Session, row: FamilyAgent) -> FamilyAgent:
    db.add(row)
    return row


def get_active_soul_profile(db: Session, *, agent_id: str) -> FamilyAgentSoulProfile | None:
    stmt = select(FamilyAgentSoulProfile).where(
        FamilyAgentSoulProfile.agent_id == agent_id,
        FamilyAgentSoulProfile.is_active.is_(True),
    )
    return db.scalar(stmt)


def list_soul_profiles(db: Session, *, agent_id: str) -> Sequence[FamilyAgentSoulProfile]:
    stmt = (
        select(FamilyAgentSoulProfile)
        .where(FamilyAgentSoulProfile.agent_id == agent_id)
        .order_by(FamilyAgentSoulProfile.version.desc())
    )
    return list(db.scalars(stmt).all())


def get_next_soul_version(db: Session, *, agent_id: str) -> int:
    stmt = select(func.max(FamilyAgentSoulProfile.version)).where(FamilyAgentSoulProfile.agent_id == agent_id)
    current = db.scalar(stmt)
    return (current or 0) + 1


def add_soul_profile(db: Session, row: FamilyAgentSoulProfile) -> FamilyAgentSoulProfile:
    db.add(row)
    return row


def list_member_cognitions(db: Session, *, agent_id: str) -> Sequence[FamilyAgentMemberCognition]:
    stmt = (
        select(FamilyAgentMemberCognition)
        .where(FamilyAgentMemberCognition.agent_id == agent_id)
        .order_by(
            FamilyAgentMemberCognition.service_priority.desc(),
            FamilyAgentMemberCognition.updated_at.desc(),
        )
    )
    return list(db.scalars(stmt).all())


def get_member_cognition(
    db: Session,
    *,
    agent_id: str,
    member_id: str,
) -> FamilyAgentMemberCognition | None:
    stmt = select(FamilyAgentMemberCognition).where(
        FamilyAgentMemberCognition.agent_id == agent_id,
        FamilyAgentMemberCognition.member_id == member_id,
    )
    return db.scalar(stmt)


def add_member_cognition(db: Session, row: FamilyAgentMemberCognition) -> FamilyAgentMemberCognition:
    db.add(row)
    return row


def get_runtime_policy(db: Session, *, agent_id: str) -> FamilyAgentRuntimePolicy | None:
    return db.get(FamilyAgentRuntimePolicy, agent_id)


def add_runtime_policy(db: Session, row: FamilyAgentRuntimePolicy) -> FamilyAgentRuntimePolicy:
    db.add(row)
    return row

