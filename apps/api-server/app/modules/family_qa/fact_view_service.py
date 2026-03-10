from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.context.service import get_context_overview
from app.modules.device.models import Device
from app.modules.family_qa.schemas import (
    QaFactDeviceState,
    QaFactViewRead,
    QaMemorySummary,
    QaPermissionScope,
    QaReminderFactItem,
    QaReminderSummary,
    QaSceneFactItem,
    QaSceneSummary,
)
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
) -> QaFactViewRead:
    if db.get(Household, household_id) is None:
        raise ValueError("household not found")

    overview = get_context_overview(db, household_id)
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
        active_member=overview.active_member,
        member_states=overview.member_states,
        room_occupancy=overview.room_occupancy,
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
        memory_summary=QaMemorySummary(),
        permission_scope=permission_scope,
    )
    return trim_qa_fact_view(fact_view)


def trim_qa_fact_view(fact_view: QaFactViewRead) -> QaFactViewRead:
    trimmed = fact_view.model_copy(deep=True)
    scope = trimmed.permission_scope

    if not scope.can_view_member_details:
        trimmed.member_states = [
            item for item in trimmed.member_states if item.member_id in scope.visible_member_ids
        ]
        if trimmed.active_member is not None and trimmed.active_member.member_id not in scope.visible_member_ids:
            trimmed.active_member = None
        if "member_states" not in scope.masked_sections:
            scope.masked_sections.append("member_states")

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
