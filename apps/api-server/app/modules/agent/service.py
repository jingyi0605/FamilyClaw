from fastapi import HTTPException, status

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository
from app.modules.agent.models import (
    FamilyAgent,
    FamilyAgentMemberCognition,
    FamilyAgentRuntimePolicy,
    FamilyAgentSoulProfile,
)
from app.modules.agent.schemas import (
    AgentDetailRead,
    AgentListResponse,
    AgentMemberCognitionRead,
    AgentMemberCognitionsUpsert,
    AgentRuntimePolicyRead,
    AgentRuntimePolicyUpsert,
    AgentSoulProfileRead,
    AgentSoulProfileUpsert,
    AgentSummaryRead,
)
from app.modules.member.models import Member
from sqlalchemy.orm import Session


class AgentNotFoundError(LookupError):
    pass


def list_ai_config_agents(db: Session, *, household_id: str) -> AgentListResponse:
    rows = repository.list_agents(db, household_id=household_id)
    return AgentListResponse(
        household_id=household_id,
        items=[_to_agent_summary_read(db, row) for row in rows],
    )


def get_agent_detail(db: Session, *, household_id: str, agent_id: str) -> AgentDetailRead:
    row = repository.get_agent_by_household_and_id(db, household_id=household_id, agent_id=agent_id)
    if row is None:
        raise AgentNotFoundError(f"agent {agent_id} not found in household {household_id}")
    return _to_agent_detail_read(db, row)


def resolve_effective_agent(
    db: Session,
    *,
    household_id: str,
    agent_id: str | None = None,
) -> FamilyAgent:
    if agent_id:
        row = repository.get_agent_by_household_and_id(db, household_id=household_id, agent_id=agent_id)
        if row is not None:
            return row
    primary = repository.get_primary_agent(db, household_id=household_id)
    if primary is not None:
        return primary
    rows = repository.list_agents(db, household_id=household_id, status="active")
    if rows:
        return rows[0]
    rows = repository.list_agents(db, household_id=household_id)
    if rows:
        return rows[0]
    raise AgentNotFoundError(f"no agent configured for household {household_id}")


def upsert_agent_soul(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    payload: AgentSoulProfileUpsert,
) -> AgentSoulProfileRead:
    agent = _get_agent_in_household_or_404(db, household_id=household_id, agent_id=agent_id)
    current = repository.get_active_soul_profile(db, agent_id=agent.id)
    if current is not None:
        current.is_active = False
    next_version = repository.get_next_soul_version(db, agent_id=agent.id)
    row = FamilyAgentSoulProfile(
        id=new_uuid(),
        agent_id=agent.id,
        version=next_version,
        self_identity=payload.self_identity,
        role_summary=payload.role_summary,
        intro_message=payload.intro_message,
        speaking_style=payload.speaking_style,
        personality_traits_json=dump_json(payload.personality_traits) or "[]",
        service_focus_json=dump_json(payload.service_focus) or "[]",
        service_boundaries_json=dump_json(payload.service_boundaries),
        is_active=True,
        created_by=payload.created_by,
        created_at=utc_now_iso(),
    )
    repository.add_soul_profile(db, row)
    return _to_soul_profile_read(row)


def upsert_agent_member_cognitions(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    payload: AgentMemberCognitionsUpsert,
) -> list[AgentMemberCognitionRead]:
    agent = _get_agent_in_household_or_404(db, household_id=household_id, agent_id=agent_id)
    updated_rows: list[FamilyAgentMemberCognition] = []
    for item in payload.items:
        _get_member_in_household_or_404(db, household_id=household_id, member_id=item.member_id)
        row = repository.get_member_cognition(db, agent_id=agent.id, member_id=item.member_id)
        if row is None:
            row = FamilyAgentMemberCognition(
                id=new_uuid(),
                agent_id=agent.id,
                member_id=item.member_id,
                version=1,
            )
            repository.add_member_cognition(db, row)
        else:
            row.version += 1
        row.display_address = item.display_address
        row.closeness_level = item.closeness_level
        row.service_priority = item.service_priority
        row.communication_style = item.communication_style
        row.care_notes_json = dump_json(item.care_notes)
        row.prompt_notes = item.prompt_notes
        row.updated_at = utc_now_iso()
        updated_rows.append(row)
    return [_to_member_cognition_read(row) for row in updated_rows]


def upsert_agent_runtime_policy(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    payload: AgentRuntimePolicyUpsert,
) -> AgentRuntimePolicyRead:
    agent = _get_agent_in_household_or_404(db, household_id=household_id, agent_id=agent_id)
    row = repository.get_runtime_policy(db, agent_id=agent.id)
    if row is None:
        row = FamilyAgentRuntimePolicy(agent_id=agent.id)
        repository.add_runtime_policy(db, row)
    row.conversation_enabled = payload.conversation_enabled
    row.default_entry = payload.default_entry
    row.routing_tags_json = dump_json(payload.routing_tags) or "[]"
    row.memory_scope_json = dump_json(payload.memory_scope)
    row.updated_at = utc_now_iso()
    return _to_runtime_policy_read(row)


def _to_agent_summary_read(db: Session, row: FamilyAgent) -> AgentSummaryRead:
    soul = repository.get_active_soul_profile(db, agent_id=row.id)
    runtime_policy = repository.get_runtime_policy(db, agent_id=row.id)
    runtime_policy_read = _to_runtime_policy_read(runtime_policy) if runtime_policy is not None else _default_runtime_policy_read(row.id)
    return AgentSummaryRead(
        id=row.id,
        household_id=row.household_id,
        code=row.code,
        agent_type=row.agent_type,
        display_name=row.display_name,
        status=row.status,
        is_primary=row.is_primary,
        sort_order=row.sort_order,
        summary=soul.role_summary if soul is not None else None,
        conversation_enabled=runtime_policy_read.conversation_enabled,
        default_entry=runtime_policy_read.default_entry,
        updated_at=row.updated_at,
    )


def _to_agent_detail_read(db: Session, row: FamilyAgent) -> AgentDetailRead:
    soul = repository.get_active_soul_profile(db, agent_id=row.id)
    member_cognitions = repository.list_member_cognitions(db, agent_id=row.id)
    runtime_policy = repository.get_runtime_policy(db, agent_id=row.id)
    return AgentDetailRead(
        id=row.id,
        household_id=row.household_id,
        code=row.code,
        agent_type=row.agent_type,
        display_name=row.display_name,
        status=row.status,
        is_primary=row.is_primary,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
        soul=_to_soul_profile_read(soul) if soul is not None else None,
        member_cognitions=[_to_member_cognition_read(item) for item in member_cognitions],
        runtime_policy=_to_runtime_policy_read(runtime_policy) if runtime_policy is not None else _default_runtime_policy_read(row.id),
    )


def _to_soul_profile_read(row: FamilyAgentSoulProfile) -> AgentSoulProfileRead:
    return AgentSoulProfileRead(
        id=row.id,
        agent_id=row.agent_id,
        version=row.version,
        self_identity=row.self_identity,
        role_summary=row.role_summary,
        intro_message=row.intro_message,
        speaking_style=row.speaking_style,
        personality_traits=_load_json_list(row.personality_traits_json),
        service_focus=_load_json_list(row.service_focus_json),
        service_boundaries=_load_json_dict(row.service_boundaries_json),
        is_active=row.is_active,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _to_member_cognition_read(row: FamilyAgentMemberCognition) -> AgentMemberCognitionRead:
    return AgentMemberCognitionRead(
        id=row.id,
        agent_id=row.agent_id,
        member_id=row.member_id,
        display_address=row.display_address,
        closeness_level=row.closeness_level,
        service_priority=row.service_priority,
        communication_style=row.communication_style,
        care_notes=_load_json_dict(row.care_notes_json),
        prompt_notes=row.prompt_notes,
        version=row.version,
        updated_at=row.updated_at,
    )


def _to_runtime_policy_read(row: FamilyAgentRuntimePolicy) -> AgentRuntimePolicyRead:
    return AgentRuntimePolicyRead(
        agent_id=row.agent_id,
        conversation_enabled=row.conversation_enabled,
        default_entry=row.default_entry,
        routing_tags=_load_json_list(row.routing_tags_json),
        memory_scope=_load_json_dict(row.memory_scope_json),
        updated_at=row.updated_at,
    )


def _default_runtime_policy_read(agent_id: str) -> AgentRuntimePolicyRead:
    return AgentRuntimePolicyRead(
        agent_id=agent_id,
        conversation_enabled=True,
        default_entry=False,
        routing_tags=[],
        memory_scope=None,
        updated_at="",
    )


def _get_agent_in_household_or_404(db: Session, *, household_id: str, agent_id: str) -> FamilyAgent:
    row = repository.get_agent_by_household_and_id(db, household_id=household_id, agent_id=agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
    return row


def _get_member_in_household_or_404(db: Session, *, household_id: str, member_id: str) -> Member:
    row = db.get(Member, member_id)
    if row is None or row.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found in household")
    return row


def _load_json_list(value: str | None) -> list[str]:
    data = load_json(value)
    if isinstance(data, list):
        return [str(item) for item in data]
    return []


def _load_json_dict(value: str | None) -> dict | None:
    data = load_json(value)
    if isinstance(data, dict):
        return data
    return None
