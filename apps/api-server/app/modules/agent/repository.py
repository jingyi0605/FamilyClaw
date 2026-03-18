from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.agent.models import (
    FamilyAgent,
    FamilyAgentBootstrapMessage,
    FamilyAgentBootstrapRequest,
    FamilyAgentBootstrapSession,
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


def get_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    session_id: str,
) -> FamilyAgentBootstrapSession | None:
    stmt = select(FamilyAgentBootstrapSession).where(
        FamilyAgentBootstrapSession.id == session_id,
        FamilyAgentBootstrapSession.household_id == household_id,
    )
    return db.scalar(stmt)


def add_bootstrap_session(db: Session, row: FamilyAgentBootstrapSession) -> FamilyAgentBootstrapSession:
    db.add(row)
    return row


def claim_next_bootstrap_event_seq(db: Session, *, session: FamilyAgentBootstrapSession) -> int:
    session.last_event_seq += 1
    db.flush()
    return session.last_event_seq


def list_bootstrap_messages(
    db: Session,
    *,
    session_id: str,
) -> Sequence[FamilyAgentBootstrapMessage]:
    stmt = (
        select(FamilyAgentBootstrapMessage)
        .where(FamilyAgentBootstrapMessage.session_id == session_id)
        .order_by(FamilyAgentBootstrapMessage.seq.asc(), FamilyAgentBootstrapMessage.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def get_next_bootstrap_message_seq(db: Session, *, session_id: str) -> int:
    stmt = select(func.max(FamilyAgentBootstrapMessage.seq)).where(FamilyAgentBootstrapMessage.session_id == session_id)
    current = db.scalar(stmt)
    return (current or 0) + 1


def add_bootstrap_message(db: Session, row: FamilyAgentBootstrapMessage) -> FamilyAgentBootstrapMessage:
    db.add(row)
    return row


def add_bootstrap_request(db: Session, row: FamilyAgentBootstrapRequest) -> FamilyAgentBootstrapRequest:
    db.add(row)
    return row


def get_bootstrap_request(
    db: Session,
    *,
    request_id: str,
) -> FamilyAgentBootstrapRequest | None:
    return db.get(FamilyAgentBootstrapRequest, request_id)


def list_bootstrap_requests(
    db: Session,
    *,
    session_id: str,
) -> Sequence[FamilyAgentBootstrapRequest]:
    stmt = (
        select(FamilyAgentBootstrapRequest)
        .where(FamilyAgentBootstrapRequest.session_id == session_id)
        .order_by(FamilyAgentBootstrapRequest.started_at.asc(), FamilyAgentBootstrapRequest.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_latest_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    include_completed: bool = True,
) -> FamilyAgentBootstrapSession | None:
    stmt = (
        select(FamilyAgentBootstrapSession)
        .where(FamilyAgentBootstrapSession.household_id == household_id)
        .order_by(FamilyAgentBootstrapSession.updated_at.desc(), FamilyAgentBootstrapSession.created_at.desc())
    )
    if not include_completed:
        stmt = stmt.where(FamilyAgentBootstrapSession.status.not_in(["completed", "cancelled"]))
    return db.scalar(stmt)


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


def list_runtime_policies(
    db: Session,
    *,
    household_id: str | None = None,
) -> Sequence[FamilyAgentRuntimePolicy]:
    stmt = select(FamilyAgentRuntimePolicy)
    if household_id is not None:
        stmt = stmt.join(FamilyAgent, FamilyAgent.id == FamilyAgentRuntimePolicy.agent_id).where(FamilyAgent.household_id == household_id)
    stmt = stmt.order_by(FamilyAgentRuntimePolicy.updated_at.desc(), FamilyAgentRuntimePolicy.agent_id.asc())
    return list(db.scalars(stmt).all())


def add_runtime_policy(db: Session, row: FamilyAgentRuntimePolicy) -> FamilyAgentRuntimePolicy:
    db.add(row)
    return row
