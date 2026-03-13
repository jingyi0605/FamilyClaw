from fastapi import HTTPException, status
from typing import cast

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository
from app.modules.agent.models import (
    FamilyAgent,
    FamilyAgentMemberCognition,
    FamilyAgentRuntimePolicy,
    FamilyAgentSoulProfile,
)
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailRead,
    AgentListResponse,
    AgentMemoryInsightFact,
    AgentMemoryInsightRead,
    AgentStatus,
    AgentType,
    AgentPluginMemoryCheckpointRead,
    AgentPluginMemoryCheckpointRequest,
    AgentMemberCognitionRead,
    AgentMemberCognitionsUpsert,
    AgentRuntimePolicyRead,
    AgentRuntimePolicyUpsert,
    AgentSoulProfileRead,
    AgentSoulProfileUpsert,
    AgentSummaryRead,
    AgentUpdate,
)
from app.modules.member.models import Member
from app.modules.memory.schemas import MemoryCardRead
from app.modules.memory.service import list_memory_cards
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


def create_agent(
    db: Session,
    *,
    household_id: str,
    payload: AgentCreate,
) -> AgentDetailRead:
    existing_primary = repository.get_primary_agent(db, household_id=household_id)
    sort_order = len(repository.list_agents(db, household_id=household_id)) * 100 + 100
    display_name = payload.display_name.strip()
    code = _build_agent_code(display_name)

    if repository.get_agent_by_household_and_code(db, household_id=household_id, code=code) is not None:
        code = f"{code}-{new_uuid()[:8]}"

    row = FamilyAgent(
        id=new_uuid(),
        household_id=household_id,
        code=code,
        agent_type=payload.agent_type,
        display_name=display_name,
        status="active",
        is_primary=existing_primary is None,
        sort_order=sort_order,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    repository.add_agent(db, row)

    soul = FamilyAgentSoulProfile(
        id=new_uuid(),
        agent_id=row.id,
        version=1,
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
    repository.add_soul_profile(db, soul)

    runtime_policy = FamilyAgentRuntimePolicy(
        agent_id=row.id,
        conversation_enabled=payload.conversation_enabled,
        default_entry=payload.default_entry if existing_primary is None else False,
        routing_tags_json=dump_json(["setup", payload.agent_type]) or "[]",
        memory_scope_json=None,
        updated_at=utc_now_iso(),
    )
    repository.add_runtime_policy(db, runtime_policy)
    db.flush()
    return _to_agent_detail_read(db, row)


def update_agent(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    payload: AgentUpdate,
) -> AgentDetailRead:
    row = _get_agent_in_household_or_404(db, household_id=household_id, agent_id=agent_id)
    data = payload.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        display_name = data["display_name"].strip()
        if not display_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="display_name 不能为空")
        row.display_name = display_name
    if "status" in data and data["status"] is not None:
        row.status = data["status"]
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = data["sort_order"]
    row.updated_at = utc_now_iso()
    db.flush()
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


def build_agent_runtime_context(
    db: Session,
    *,
    household_id: str,
    agent_id: str | None = None,
    requester_member_id: str | None = None,
) -> dict[str, object]:
    effective_agent = resolve_effective_agent(
        db,
        household_id=household_id,
        agent_id=agent_id,
    )
    soul = repository.get_active_soul_profile(db, agent_id=effective_agent.id)
    runtime_policy = repository.get_runtime_policy(db, agent_id=effective_agent.id)
    requester_cognition = (
        repository.get_member_cognition(
            db,
            agent_id=effective_agent.id,
            member_id=requester_member_id,
        )
        if requester_member_id is not None
        else None
    )

    return {
        "agent": {
            "id": effective_agent.id,
            "type": effective_agent.agent_type,
            "name": effective_agent.display_name,
            "is_primary": effective_agent.is_primary,
            "status": effective_agent.status,
        },
        "identity": {
            "self_identity": soul.self_identity if soul is not None else None,
            "role_summary": soul.role_summary if soul is not None else None,
            "intro_message": soul.intro_message if soul is not None else None,
            "speaking_style": soul.speaking_style if soul is not None else None,
            "personality_traits": _load_json_list(soul.personality_traits_json) if soul is not None else [],
            "service_focus": _load_json_list(soul.service_focus_json) if soul is not None else [],
            "service_boundaries": _load_json_dict(soul.service_boundaries_json) if soul is not None else None,
        },
        "requester_member_cognition": {
            "member_id": requester_cognition.member_id,
            "display_address": requester_cognition.display_address,
            "closeness_level": requester_cognition.closeness_level,
            "service_priority": requester_cognition.service_priority,
            "communication_style": requester_cognition.communication_style,
            "care_notes": _load_json_dict(requester_cognition.care_notes_json),
            "prompt_notes": requester_cognition.prompt_notes,
        }
        if requester_cognition is not None
        else None,
        "runtime_policy": {
            "conversation_enabled": runtime_policy.conversation_enabled,
            "default_entry": runtime_policy.default_entry,
            "routing_tags": _load_json_list(runtime_policy.routing_tags_json),
            "memory_scope": _load_json_dict(runtime_policy.memory_scope_json),
        }
        if runtime_policy is not None
        else {
            "conversation_enabled": True,
            "default_entry": False,
            "routing_tags": [],
            "memory_scope": None,
        },
    }


def build_agent_memory_insight(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
) -> AgentMemoryInsightRead:
    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)
    cards, _total = list_memory_cards(
        db,
        household_id=household_id,
        page=1,
        page_size=100,
        memory_type="observation",
    )

    plugin_cards = [card for card in cards if card.source_plugin_id]
    if not plugin_cards:
        return AgentMemoryInsightRead(
            agent_id=agent.id,
            agent_name=agent.display_name,
            household_id=household_id,
            summary="当前还没有可用的插件记忆，暂时不能生成摘要或提醒。",
            suggestions=["先运行健康或智能家居样板插件"],
            used_plugins=[],
            facts=[],
        )

    latest_by_category: dict[str, MemoryCardRead] = {}
    for card in plugin_cards:
        content = card.content if isinstance(card.content, dict) else {}
        category = content.get("category") if isinstance(content.get("category"), str) else None
        if not category:
            continue
        current = latest_by_category.get(category)
        current_ts = _resolve_card_observed_at(current) if current is not None else ""
        candidate_ts = _resolve_card_observed_at(card)
        if current is None or candidate_ts >= current_ts:
            latest_by_category[category] = card

    facts: list[AgentMemoryInsightFact] = []
    used_plugins: list[str] = []
    summary_parts: list[str] = []
    suggestions: list[str] = []

    for category in [
        "daily_steps",
        "sleep_duration",
        "heart_rate",
        "device_power_state",
        "room_temperature",
        "room_humidity",
    ]:
        card: MemoryCardRead | None = latest_by_category.get(category)
        if card is None:
            continue
        content = card.content if isinstance(card.content, dict) else {}
        value = content.get("value")
        unit = content.get("unit") if isinstance(content.get("unit"), str) else None
        source_plugin_id = card.source_plugin_id or ""
        observed_at = _resolve_card_observed_at(card) or None
        summary_parts.append(_build_observation_summary(category=category, value=value, unit=unit, content=content))
        if source_plugin_id and source_plugin_id not in used_plugins:
            used_plugins.append(source_plugin_id)
        facts.append(
            AgentMemoryInsightFact(
                memory_id=card.id,
                source_plugin_id=source_plugin_id,
                category=category,
                summary=card.summary,
                observed_at=observed_at,
            )
        )
        _append_observation_suggestion(suggestions, category=category, value=value, unit=unit, content=content)

    if not summary_parts:
        summary_text = "当前已有插件记忆，但还没有可用于摘要的 Observation。"
    else:
        summary_text = f"{agent.display_name} 已读取插件写入的家庭记忆：" + "；".join(summary_parts) + "。"

    return AgentMemoryInsightRead(
        agent_id=agent.id,
        agent_name=agent.display_name,
        household_id=household_id,
        summary=summary_text,
        suggestions=suggestions[:3],
        used_plugins=used_plugins,
        facts=facts,
    )


def run_agent_plugin_memory_checkpoint(
    db: Session,
    *,
    household_id: str,
    agent_id: str,
    payload: AgentPluginMemoryCheckpointRequest,
) -> AgentPluginMemoryCheckpointRead:
    from app.modules.plugin.schemas import PluginExecutionRequest
    from app.modules.plugin.service import run_plugin_sync_pipeline

    agent = resolve_effective_agent(db, household_id=household_id, agent_id=agent_id)
    pipeline_result = run_plugin_sync_pipeline(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=payload.plugin_id,
            plugin_type="connector",
            payload=payload.payload,
            trigger=payload.trigger,
        ),
    )
    insight = build_agent_memory_insight(
        db,
        household_id=household_id,
        agent_id=agent.id,
    )
    return AgentPluginMemoryCheckpointRead(
        agent_id=agent.id,
        agent_name=agent.display_name,
        household_id=household_id,
        plugin_id=payload.plugin_id,
        trigger=payload.trigger,
        pipeline_run_id=pipeline_result.run.id,
        pipeline_success=pipeline_result.run.status == "success",
        raw_record_count=pipeline_result.run.raw_record_count,
        memory_card_count=pipeline_result.run.memory_card_count,
        degraded=pipeline_result.run.status != "success",
        insight=insight,
    )


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
    if payload.default_entry:
        for item in repository.list_agents(db, household_id=household_id):
            if item.id == agent.id:
                continue
            runtime_policy = repository.get_runtime_policy(db, agent_id=item.id)
            if runtime_policy is None or not runtime_policy.default_entry:
                continue
            runtime_policy.default_entry = False
            runtime_policy.updated_at = utc_now_iso()
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
    agent_type: AgentType = cast(AgentType, row.agent_type)
    agent_status: AgentStatus = cast(AgentStatus, row.status)
    return AgentSummaryRead(
        id=row.id,
        household_id=row.household_id,
        code=row.code,
        agent_type=agent_type,
        display_name=row.display_name,
        status=agent_status,
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
    agent_type: AgentType = cast(AgentType, row.agent_type)
    agent_status: AgentStatus = cast(AgentStatus, row.status)
    return AgentDetailRead(
        id=row.id,
        household_id=row.household_id,
        code=row.code,
        agent_type=agent_type,
        display_name=row.display_name,
        status=agent_status,
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


def _resolve_card_observed_at(card: object) -> str:
    observed_at = getattr(card, "last_observed_at", None)
    if isinstance(observed_at, str) and observed_at:
        return observed_at
    effective_at = getattr(card, "effective_at", None)
    if isinstance(effective_at, str) and effective_at:
        return effective_at
    updated_at = getattr(card, "updated_at", None)
    if isinstance(updated_at, str) and updated_at:
        return updated_at
    return ""


def _build_observation_summary(*, category: str, value: object, unit: str | None, content: dict) -> str:
    if category == "daily_steps":
        return f"今日步数 {value}"
    if category == "sleep_duration":
        return f"最近睡眠时长 {value} {unit or 'hour'}"
    if category == "heart_rate":
        return f"最近心率 {value} {unit or 'bpm'}"
    if category == "device_power_state":
        subject_id = content.get("subject_id") if isinstance(content.get("subject_id"), str) else "设备"
        return f"{subject_id} 当前状态 {value}"
    if category == "room_temperature":
        return f"房间温度 {value} {unit or 'celsius'}"
    if category == "room_humidity":
        return f"房间湿度 {value} {unit or 'percent'}"
    return f"{category} {value} {unit or ''}".strip()


def _append_observation_suggestion(
    suggestions: list[str],
    *,
    category: str,
    value: object,
    unit: str | None,
    content: dict,
) -> None:
    if category == "sleep_duration" and isinstance(value, (int, float)) and float(value) < 7:
        suggestions.append("最近睡眠时长偏少，先作为提醒处理，建议今晚尽量早点休息。")
        return
    if category == "heart_rate" and isinstance(value, (int, float)) and float(value) > 100:
        suggestions.append("最近心率偏高，先作为提醒处理，建议结合当时活动状态再确认一次。")
        return
    if category == "room_temperature" and isinstance(value, (int, float)) and float(value) >= 28:
        suggestions.append("房间温度偏高，先给建议，不自动控制设备；可以考虑手动开空调或通风。")
        return
    if category == "room_humidity" and isinstance(value, (int, float)) and float(value) <= 30:
        suggestions.append("房间湿度偏低，可以考虑手动开加湿设备。")
        return
    if category == "daily_steps" and isinstance(value, (int, float)) and float(value) < 3000:
        suggestions.append("今天步数偏少，如果方便可以安排一次轻量活动。")
        return


def _build_agent_code(display_name: str) -> str:
    normalized = "".join(
        character.lower()
        if character.isalnum()
        else "-"
        for character in display_name.strip()
    )
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact[:64] or f"agent-{new_uuid()[:8]}"
