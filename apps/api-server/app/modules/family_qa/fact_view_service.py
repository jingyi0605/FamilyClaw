from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import load_json
from app.modules.agent.service import build_agent_runtime_context
from app.modules.context.service import get_context_overview
from app.modules.device.models import Device
from app.modules.member import service as member_service
from app.modules.member.prompt_context_service import MemberPromptProfile, list_member_prompt_profiles
from app.modules.family_qa.schemas import (
    QaFactReference,
    QaFactDeviceState,
    QaFactMemberProfile,
    QaFactMemberRelationship,
    QaFactViewRead,
    QaMemorySummary,
    QaPermissionScope,
    QaReminderFactItem,
    QaReminderSummary,
    QaSceneFactItem,
    QaSceneSummary,
)
from app.modules.memory.context_engine import build_memory_context_bundle
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.permission.models import MemberPermission
from app.modules.reminder.models import ReminderAckEvent, ReminderRun, ReminderTask
from app.modules.room.models import Room
from app.modules.scene.models import SceneExecution, SceneTemplate


def build_qa_fact_view(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    agent_id: str | None = None,
    actor: ActorContext | None = None,
    question: str | None = None,
) -> QaFactViewRead:
    if db.get(Household, household_id) is None:
        raise ValueError("household not found")

    overview = get_context_overview(db, household_id)
    display_name_map = member_service.build_member_display_name_map(db, household_id=household_id)
    active_member = (
        overview.active_member.model_copy(
            update={
                "name": display_name_map.get(
                    overview.active_member.member_id,
                    overview.active_member.name,
                )
            }
        )
        if overview.active_member is not None
        else None
    )
    member_states = [
        member_state.model_copy(
            update={"name": display_name_map.get(member_state.member_id, member_state.name)}
        )
        for member_state in overview.member_states
    ]
    member_profiles = [
        _to_qa_fact_member_profile(profile)
        for profile in list_member_prompt_profiles(
            db,
            household_id=household_id,
            status_value="active",
        )
    ]
    room_occupancy = [
        room.model_copy(
            update={
                "occupants": [
                    occupant.model_copy(
                        update={"name": display_name_map.get(occupant.member_id, occupant.name)}
                    )
                    for occupant in room.occupants
                ]
            }
        )
        for room in overview.room_occupancy
    ]
    rooms = list(
        db.scalars(
            select(Room)
            .where(Room.household_id == household_id)
            .order_by(Room.created_at.asc(), Room.id.asc())
        ).all()
    )
    room_by_id = {room.id: room for room in rooms}
    devices = list(
        db.scalars(
            select(Device)
            .where(Device.household_id == household_id)
            .order_by(Device.updated_at.desc(), Device.id.desc())
        ).all()
    )
    tasks = list(
        db.scalars(
            select(ReminderTask)
            .where(ReminderTask.household_id == household_id)
            .order_by(ReminderTask.updated_at.desc(), ReminderTask.id.desc())
        ).all()
    )
    runs = list(
        db.scalars(
            select(ReminderRun)
            .where(ReminderRun.household_id == household_id)
            .order_by(ReminderRun.planned_at.desc(), ReminderRun.id.desc())
        ).all()
    )
    templates = list(
        db.scalars(
            select(SceneTemplate)
            .where(SceneTemplate.household_id == household_id)
            .order_by(SceneTemplate.priority.desc(), SceneTemplate.updated_at.desc())
        ).all()
    )
    executions = list(
        db.scalars(
            select(SceneExecution)
            .where(SceneExecution.household_id == household_id)
            .order_by(SceneExecution.started_at.desc(), SceneExecution.id.desc())
        ).all()
    )

    run_by_task_id: dict[str, ReminderRun] = {}
    for run in runs:
        if run.task_id not in run_by_task_id:
            run_by_task_id[run.task_id] = run

    ack_rows = list(
        db.scalars(
            select(ReminderAckEvent)
            .where(ReminderAckEvent.run_id.in_([run.id for run in runs]))
            .order_by(ReminderAckEvent.created_at.desc(), ReminderAckEvent.id.desc())
        ).all()
    ) if runs else []
    ack_by_run_id: dict[str, ReminderAckEvent] = {}
    for ack_row in ack_rows:
        if ack_row.run_id not in ack_by_run_id:
            ack_by_run_id[ack_row.run_id] = ack_row

    latest_execution_by_template_id: dict[str, SceneExecution] = {}
    for execution in executions:
        if execution.template_id not in latest_execution_by_template_id:
            latest_execution_by_template_id[execution.template_id] = execution

    permission_scope = _build_permission_scope(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        room_ids=[room.id for room in rooms],
        member_ids=[member_state.member_id for member_state in overview.member_states],
        room_privacy_map={room.id: room.privacy_level for room in rooms},
    )

    reminder_items = [
        QaReminderFactItem(
            task_id=task.id,
            title=task.title,
            reminder_type=task.reminder_type,
            target_member_ids=load_json(task.target_member_ids_json) or [],
            enabled=task.enabled,
            last_run_status=run_by_task_id.get(task.id).status if task.id in run_by_task_id else None,
            last_run_planned_at=run_by_task_id.get(task.id).planned_at if task.id in run_by_task_id else None,
            last_ack_action=ack_by_run_id.get(run_by_task_id[task.id].id).action
            if task.id in run_by_task_id and run_by_task_id[task.id].id in ack_by_run_id
            else None,
        )
        for task in tasks
    ]
    scene_items = [
        QaSceneFactItem(
            template_id=template.id,
            template_code=template.template_code,
            name=template.name,
            enabled=template.enabled,
            last_execution_status=latest_execution_by_template_id.get(template.id).status
            if template.id in latest_execution_by_template_id
            else None,
            last_execution_started_at=latest_execution_by_template_id.get(template.id).started_at
            if template.id in latest_execution_by_template_id
            else None,
        )
        for template in templates
    ]
    fact_view = QaFactViewRead(
        household_id=household_id,
        generated_at=overview.generated_at,
        requester_member_id=requester_member_id,
        active_member=active_member,
        member_states=member_states,
        member_profiles=member_profiles,
        room_occupancy=room_occupancy,
        device_summary=overview.device_summary,
        device_states=[
            QaFactDeviceState(
                device_id=device.id,
                name=device.name,
                device_type=device.device_type,
                room_id=device.room_id,
                room_name=room_by_id.get(device.room_id).name if device.room_id and device.room_id in room_by_id else None,
                status=device.status,
                controllable=bool(device.controllable),
            )
            for device in devices
        ],
        reminder_summary=QaReminderSummary(
            total_tasks=len(reminder_items),
            enabled_tasks=sum(1 for item in reminder_items if item.enabled),
            pending_runs=sum(1 for run in runs if run.status in {"pending", "delivering"}),
            recent_items=reminder_items,
        ),
        scene_summary=QaSceneSummary(
            total_templates=len(scene_items),
            enabled_templates=sum(1 for item in scene_items if item.enabled),
            running_executions=sum(1 for execution in executions if execution.status in {"planned", "running"}),
            recent_items=scene_items,
        ),
        memory_summary=_build_memory_summary(
            db,
            household_id=household_id,
            requester_member_id=requester_member_id,
            agent_id=agent_id,
            actor=actor,
            question=question,
        ),
        permission_scope=permission_scope,
    )
    return trim_qa_fact_view(fact_view)


def _build_memory_summary(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None,
    agent_id: str | None,
    actor: ActorContext | None,
    question: str | None,
) -> QaMemorySummary:
    effective_actor = actor or ActorContext(role="admin", actor_type="admin", actor_id=None)
    agent_runtime_context = build_agent_runtime_context(
        db,
        household_id=household_id,
        agent_id=agent_id,
        requester_member_id=requester_member_id,
    )
    bundle = build_memory_context_bundle(
        db,
        household_id=household_id,
        actor=effective_actor,
        requester_member_id=requester_member_id,
        question=question,
        capability="family_qa",
    )
    raw_items = [
        QaFactReference(
            type=f"memory_{hit.card.memory_type}",
            label=hit.card.title,
            source="memory_cards",
            occurred_at=hit.card.updated_at,
            visibility=hit.card.visibility,
            inferred=False,
            extra={
                "memory_id": hit.card.id,
                "memory_type": hit.card.memory_type,
                "score": hit.score,
                "matched_terms": hit.matched_terms,
                "summary": hit.card.summary,
                "subject_member_id": hit.card.subject_member_id,
                "related_members": [
                    {
                        "member_id": related_member.member_id,
                        "relation_role": related_member.relation_role,
                    }
                    for related_member in hit.card.related_members
                ],
            },
        )
        for hit in bundle.query_result.items
    ]
    items, scope_applied = _apply_agent_memory_scope_to_fact_references(
        raw_items,
        agent_runtime_context=agent_runtime_context,
        requester_member_id=requester_member_id,
    )

    if items:
        summary = (
            f"已按当前 Agent 的记忆视角筛出 {len(items)} 条长期记忆，可用于补充回答。"
            if scope_applied
            else f"已命中 {len(items)} 条长期记忆，可用于补充回答。"
        )
        status = "available"
        last_updated_at = max((item.occurred_at for item in items if item.occurred_at), default=None)
    else:
        hot_items = [
            QaFactReference(
                type=f"memory_{item.memory_type}",
                label=item.title,
                source="memory_hot_summary",
                occurred_at=item.updated_at,
                visibility="family",
                inferred=True,
                extra={
                    "memory_id": item.memory_id,
                    "memory_type": item.memory_type,
                    "summary": item.summary,
                },
            )
            for item in bundle.hot_summary.top_memories
        ]
        hot_items, hot_scope_applied = _apply_agent_memory_scope_to_fact_references(
            hot_items,
            agent_runtime_context=agent_runtime_context,
            requester_member_id=requester_member_id,
        )
        if hot_items:
            items = hot_items
            summary = (
                f"当前没有直接命中的问题记忆，但按当前 Agent 的记忆视角仍有 {len(hot_items)} 条热记忆可参考。"
                if hot_scope_applied
                else f"当前没有直接命中的问题记忆，但已有 {len(hot_items)} 条热记忆可参考。"
            )
            status = "hot_summary_only"
            last_updated_at = bundle.hot_summary.generated_at
        else:
            summary = "当前没有可用的长期记忆命中。"
            status = "empty"
            last_updated_at = bundle.generated_at
    return QaMemorySummary(
        status=status,
        summary=summary,
        last_updated_at=last_updated_at,
        query=question,
        items=items,
        degraded=bundle.degraded,
    )


def _apply_agent_memory_scope_to_fact_references(
    items: list[QaFactReference],
    *,
    agent_runtime_context: dict[str, object],
    requester_member_id: str | None,
) -> tuple[list[QaFactReference], bool]:
    runtime_policy = agent_runtime_context.get("runtime_policy")
    if not isinstance(runtime_policy, dict):
        return items, False

    memory_scope = runtime_policy.get("memory_scope")
    if not isinstance(memory_scope, dict) or not memory_scope:
        return items, False

    preferred_memory_types = {
        str(item).strip()
        for item in memory_scope.get("preferred_memory_types", [])
        if str(item).strip()
    } if isinstance(memory_scope.get("preferred_memory_types"), list) else set()
    focus_member_ids = {
        str(item).strip()
        for item in memory_scope.get("focus_member_ids", [])
        if str(item).strip()
    } if isinstance(memory_scope.get("focus_member_ids"), list) else set()
    requester_only = bool(memory_scope.get("requester_only"))
    max_items = memory_scope.get("max_items")
    normalized_max_items = max(1, int(max_items)) if isinstance(max_items, int) and max_items > 0 else None

    filtered = items

    if preferred_memory_types:
        filtered = [
            item
            for item in filtered
            if str(item.extra.get("memory_type") or "").strip() in preferred_memory_types
        ]

    if requester_only and requester_member_id:
        filtered = [
            item
            for item in filtered
            if _matches_memory_member(item, {requester_member_id})
        ]
    elif focus_member_ids:
        filtered = [
            item
            for item in filtered
            if _matches_memory_member(item, focus_member_ids)
        ]

    if normalized_max_items is not None:
        filtered = filtered[:normalized_max_items]

    return filtered, True


def _matches_memory_member(item: QaFactReference, member_ids: set[str]) -> bool:
    subject_member_id = str(item.extra.get("subject_member_id") or "").strip()
    if subject_member_id and subject_member_id in member_ids:
        return True
    related_members = item.extra.get("related_members")
    if isinstance(related_members, list):
        for related_member in related_members:
            if isinstance(related_member, dict):
                member_id = str(related_member.get("member_id") or "").strip()
                if member_id in member_ids:
                    return True
    return False


def trim_qa_fact_view(fact_view: QaFactViewRead) -> QaFactViewRead:
    trimmed = fact_view.model_copy(deep=True)
    scope = trimmed.permission_scope

    if not scope.can_view_member_details:
        trimmed.member_states = [
            item for item in trimmed.member_states if item.member_id in scope.visible_member_ids
        ]
        trimmed.member_profiles = [
            item for item in trimmed.member_profiles if item.member_id in scope.visible_member_ids
        ]
        if trimmed.active_member is not None and trimmed.active_member.member_id not in scope.visible_member_ids:
            trimmed.active_member = None
        if "member_states" not in scope.masked_sections:
            scope.masked_sections.append("member_states")
        if "member_profiles" not in scope.masked_sections:
            scope.masked_sections.append("member_profiles")

    visible_room_ids = set(scope.visible_room_ids)
    trimmed.room_occupancy = [
        room
        for room in trimmed.room_occupancy
        if room.room_id in visible_room_ids
    ]

    if not scope.can_view_device_states:
        trimmed.device_states = []
        if "device_states" not in scope.masked_sections:
            scope.masked_sections.append("device_states")
    else:
        trimmed.device_states = [
            item
            for item in trimmed.device_states
            if item.room_id is None or item.room_id in visible_room_ids
        ]

    visible_reminder_items = [
        item
        for item in trimmed.reminder_summary.recent_items
        if _is_reminder_item_visible(item, scope)
    ]
    if len(visible_reminder_items) != len(trimmed.reminder_summary.recent_items):
        if "reminder_summary" not in scope.masked_sections:
            scope.masked_sections.append("reminder_summary")
    trimmed.reminder_summary = QaReminderSummary(
        total_tasks=len(visible_reminder_items),
        enabled_tasks=sum(1 for item in visible_reminder_items if item.enabled),
        pending_runs=sum(
            1 for item in visible_reminder_items if item.last_run_status in {"pending", "delivering"}
        ),
        recent_items=visible_reminder_items[:5],
    )

    if not scope.can_view_scene_details:
        trimmed.scene_summary = QaSceneSummary(
            total_templates=trimmed.scene_summary.total_templates,
            enabled_templates=trimmed.scene_summary.enabled_templates,
            running_executions=0,
            recent_items=[],
        )
        if "scene_summary" not in scope.masked_sections:
            scope.masked_sections.append("scene_summary")
    else:
        trimmed.scene_summary = QaSceneSummary(
            total_templates=trimmed.scene_summary.total_templates,
            enabled_templates=trimmed.scene_summary.enabled_templates,
            running_executions=trimmed.scene_summary.running_executions,
            recent_items=trimmed.scene_summary.recent_items[:5],
        )

    trimmed.permission_scope = scope
    return trimmed


def _to_qa_fact_member_profile(profile: MemberPromptProfile) -> QaFactMemberProfile:
    return QaFactMemberProfile(
        member_id=profile.member_id,
        name=profile.display_name,
        aliases=list(profile.aliases),
        role=profile.role,
        gender=profile.gender,
        age_group=profile.age_group,
        age_group_label=profile.age_group_label,
        birthday=profile.birthday,
        age_years=profile.age_years,
        preferred_name=profile.preferred_name,
        guardian_member_id=profile.guardian_member_id,
        guardian_name=profile.guardian_name,
        relationships=[
            QaFactMemberRelationship(
                target_member_id=relationship.target_member_id,
                target_member_name=relationship.target_member_name,
                relation_type=relationship.relation_type,
                relation_label=relationship.relation_label,
            )
            for relationship in profile.relationships
        ],
    )


def _build_permission_scope(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None,
    room_ids: list[str],
    member_ids: list[str],
    room_privacy_map: dict[str, str],
) -> QaPermissionScope:
    if requester_member_id is None:
        visible_room_ids = [room_id for room_id in room_ids if room_privacy_map.get(room_id) != "private"]
        return QaPermissionScope(
            requester_member_id=None,
            requester_role="guest",
            can_view_member_details=False,
            can_view_device_states=False,
            can_view_private_reminders=False,
            can_view_scene_details=False,
            visible_member_ids=[],
            visible_room_ids=visible_room_ids,
        )

    member = db.get(Member, requester_member_id)
    if member is None or member.household_id != household_id:
        raise ValueError("requester member not found")

    permissions = list(
        db.scalars(
            select(MemberPermission)
            .where(MemberPermission.member_id == requester_member_id)
            .order_by(MemberPermission.created_at.desc(), MemberPermission.id.desc())
        ).all()
    )
    allow_map: dict[str, bool] = defaultdict(bool)
    deny_map: dict[str, bool] = defaultdict(bool)
    for permission in permissions:
        key = _normalize_permission_key(permission.resource_type, permission.resource_scope)
        if permission.action != "read":
            continue
        if permission.effect == "allow":
            allow_map[key] = True
        if permission.effect == "deny":
            deny_map[key] = True

    default_flags = _default_scope_flags(member.role)
    can_view_member_details = _resolve_scope_flag(
        default_flags["can_view_member_details"],
        allow_map,
        deny_map,
        "member_details",
    )
    can_view_device_states = _resolve_scope_flag(
        default_flags["can_view_device_states"],
        allow_map,
        deny_map,
        "device_states",
    )
    can_view_private_reminders = _resolve_scope_flag(
        default_flags["can_view_private_reminders"],
        allow_map,
        deny_map,
        "private_reminders",
    )
    can_view_scene_details = _resolve_scope_flag(
        default_flags["can_view_scene_details"],
        allow_map,
        deny_map,
        "scene_details",
    )

    visible_member_ids = member_ids if can_view_member_details else [requester_member_id]
    visible_room_ids = room_ids if can_view_scene_details else [
        room_id for room_id in room_ids if room_privacy_map.get(room_id) != "private"
    ]
    return QaPermissionScope(
        requester_member_id=requester_member_id,
        requester_role=member.role,
        can_view_member_details=can_view_member_details,
        can_view_device_states=can_view_device_states,
        can_view_private_reminders=can_view_private_reminders,
        can_view_scene_details=can_view_scene_details,
        visible_member_ids=visible_member_ids,
        visible_room_ids=visible_room_ids,
    )


def _default_scope_flags(member_role: str) -> dict[str, bool]:
    normalized_role = member_role.lower()
    if normalized_role == "admin":
        return {
            "can_view_member_details": True,
            "can_view_device_states": True,
            "can_view_private_reminders": True,
            "can_view_scene_details": True,
        }
    if normalized_role in {"adult", "elder"}:
        return {
            "can_view_member_details": True,
            "can_view_device_states": True,
            "can_view_private_reminders": False,
            "can_view_scene_details": True,
        }
    return {
        "can_view_member_details": False,
        "can_view_device_states": False,
        "can_view_private_reminders": False,
        "can_view_scene_details": False,
    }


def _normalize_permission_key(resource_type: str, resource_scope: str) -> str:
    if resource_type == "qa_fact" and resource_scope:
        return resource_scope
    if resource_type == "member_state":
        return "member_details"
    if resource_type == "device":
        return "device_states"
    if resource_type == "reminder":
        return "private_reminders"
    if resource_type == "scene":
        return "scene_details"
    return resource_type


def _resolve_scope_flag(
    default_value: bool,
    allow_map: dict[str, bool],
    deny_map: dict[str, bool],
    key: str,
) -> bool:
    if deny_map.get(key):
        return False
    if allow_map.get(key):
        return True
    return default_value


def _is_reminder_item_visible(item: QaReminderFactItem, scope: QaPermissionScope) -> bool:
    if scope.can_view_private_reminders:
        return True
    if item.reminder_type in {"family", "announcement"}:
        return True
    if scope.requester_member_id is None:
        return False
    return scope.requester_member_id in item.target_member_ids
