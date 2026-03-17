from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
import hashlib
from typing import cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.account.models import Account, AccountMemberBinding
from app.modules.account.service import AuthenticatedActor
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.plugin.service import PluginExecutionError, require_available_household_plugin
from app.modules.scheduler.models import ScheduledTaskDefinition, ScheduledTaskRun
from app.modules.scheduler.rules import evaluate_heartbeat_rule
from app.modules.scheduler.runtime import finalize_task_run
from app.modules.scheduler.schemas import (
    OwnerScope,
    RuleType,
    RunStatus,
    ScheduleType,
    ScheduledTaskDefinitionCreate,
    ScheduledTaskDefinitionRead,
    ScheduledTaskDefinitionUpdate,
    ScheduledTaskRunCreate,
    ScheduledTaskRunRead,
    TargetType,
    TaskStatus,
    TriggerSource,
    TriggerType,
)


def create_task_definition(
    db: Session,
    *,
    actor: AuthenticatedActor,
    payload: ScheduledTaskDefinitionCreate,
    now_iso: str | None = None,
) -> ScheduledTaskDefinitionRead:
    household = _get_household_or_404(db, payload.household_id)
    _ensure_actor_can_access_household(actor, household.id)
    _ensure_account_exists(db, actor.account_id)
    owner_scope, owner_member_id = _validate_ownership(
        db,
        actor=actor,
        household_id=household.id,
        owner_scope=payload.owner_scope,
        owner_member_id=payload.owner_member_id,
    )
    normalized_timezone = payload.timezone or household.timezone
    _ensure_target_is_valid(payload.enabled, payload.target_ref_id)
    _validate_target_dependency(
        db,
        household_id=household.id,
        target_type=payload.target_type,
        target_ref_id=payload.target_ref_id,
    )
    if _get_task_by_code(db, household_id=household.id, code=payload.code) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="scheduled task code already exists")

    reference_now = _parse_iso_datetime(now_iso or utc_now_iso())
    row = ScheduledTaskDefinition(
        id=new_uuid(),
        household_id=household.id,
        owner_scope=owner_scope,
        owner_member_id=owner_member_id,
        created_by_account_id=actor.account_id,
        last_modified_by_account_id=actor.account_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        trigger_type=payload.trigger_type,
        schedule_type=payload.schedule_type,
        schedule_expr=payload.schedule_expr,
        heartbeat_interval_seconds=payload.heartbeat_interval_seconds,
        timezone=normalized_timezone,
        target_type=payload.target_type,
        target_ref_id=payload.target_ref_id,
        rule_type=payload.rule_type,
        rule_config_json=dump_json(payload.rule_config),
        payload_template_json=dump_json(payload.payload_template),
        cooldown_seconds=payload.cooldown_seconds,
        quiet_hours_policy=payload.quiet_hours_policy,
        enabled=payload.enabled,
        status="active" if payload.enabled else "paused",
        consecutive_failures=0,
        next_run_at=None,
        next_heartbeat_at=None,
    )
    row.next_run_at = calculate_next_run_at(row, reference_now=reference_now)
    row.next_heartbeat_at = calculate_next_heartbeat_at(row, reference_now=reference_now)
    db.add(row)
    db.flush()
    return _to_definition_read(row)


def update_task_definition(
    db: Session,
    *,
    actor: AuthenticatedActor,
    task_id: str,
    payload: ScheduledTaskDefinitionUpdate,
    now_iso: str | None = None,
) -> ScheduledTaskDefinitionRead:
    row = _get_task_or_404(db, task_id)
    _ensure_actor_can_access_household(actor, row.household_id)
    _ensure_can_manage_task(actor, row)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _to_definition_read(row)

    owner_scope = data.get("owner_scope", row.owner_scope)
    owner_member_id = data.get("owner_member_id", row.owner_member_id)
    owner_scope, owner_member_id = _validate_ownership(
        db,
        actor=actor,
        household_id=row.household_id,
        owner_scope=owner_scope,
        owner_member_id=owner_member_id,
    )
    row.owner_scope = owner_scope
    row.owner_member_id = owner_member_id

    for field_name in [
        "name",
        "description",
        "trigger_type",
        "schedule_type",
        "schedule_expr",
        "heartbeat_interval_seconds",
        "timezone",
        "target_type",
        "target_ref_id",
        "rule_type",
        "cooldown_seconds",
        "quiet_hours_policy",
        "enabled",
        "status",
    ]:
        if field_name in data:
            setattr(row, field_name, data[field_name])

    if "rule_config" in data:
        row.rule_config_json = dump_json(data["rule_config"])
    if "payload_template" in data:
        row.payload_template_json = dump_json(data["payload_template"])

    _ensure_target_is_valid(row.enabled, row.target_ref_id)
    _validate_definition_snapshot(row)
    _validate_target_dependency(
        db,
        household_id=row.household_id,
        target_type=row.target_type,
        target_ref_id=row.target_ref_id,
    )
    if not row.enabled:
        row.status = "paused"
    elif row.status == "paused":
        row.status = "active"

    reference_now = _parse_iso_datetime(now_iso or utc_now_iso())
    if row.trigger_type == "schedule":
        row.next_run_at = calculate_next_run_at(row, reference_now=reference_now)
        row.next_heartbeat_at = None
    else:
        row.next_run_at = None
        row.next_heartbeat_at = calculate_next_heartbeat_at(row, reference_now=reference_now)
    row.last_modified_by_account_id = actor.account_id
    row.updated_at = utc_now_iso()
    db.add(row)
    db.flush()
    return _to_definition_read(row)


def set_task_enabled(
    db: Session,
    *,
    actor: AuthenticatedActor,
    task_id: str,
    enabled: bool,
    now_iso: str | None = None,
) -> ScheduledTaskDefinitionRead:
    update = ScheduledTaskDefinitionUpdate(enabled=enabled, status="active" if enabled else "paused")
    return update_task_definition(db, actor=actor, task_id=task_id, payload=update, now_iso=now_iso)


def delete_task_definition(
    db: Session,
    *,
    actor: AuthenticatedActor,
    task_id: str,
) -> None:
    row = _get_task_or_404(db, task_id)
    _ensure_actor_can_access_household(actor, row.household_id)
    _ensure_can_manage_task(actor, row)
    db.delete(row)
    db.flush()


def list_task_definitions(
    db: Session,
    *,
    actor: AuthenticatedActor,
    household_id: str,
    owner_scope: str | None = None,
    owner_member_id: str | None = None,
    enabled: bool | None = None,
    trigger_type: str | None = None,
    target_type: str | None = None,
    status_value: str | None = None,
) -> list[ScheduledTaskDefinitionRead]:
    _ensure_actor_can_access_household(actor, household_id)
    stmt: Select[tuple[ScheduledTaskDefinition]] = select(ScheduledTaskDefinition).where(
        ScheduledTaskDefinition.household_id == household_id
    )
    if owner_scope is not None:
        stmt = stmt.where(ScheduledTaskDefinition.owner_scope == owner_scope)
    if owner_member_id is not None:
        stmt = stmt.where(ScheduledTaskDefinition.owner_member_id == owner_member_id)
    if enabled is not None:
        stmt = stmt.where(ScheduledTaskDefinition.enabled.is_(enabled))
    if trigger_type is not None:
        stmt = stmt.where(ScheduledTaskDefinition.trigger_type == trigger_type)
    if target_type is not None:
        stmt = stmt.where(ScheduledTaskDefinition.target_type == target_type)
    if status_value is not None:
        stmt = stmt.where(ScheduledTaskDefinition.status == status_value)
    stmt = stmt.order_by(ScheduledTaskDefinition.updated_at.desc(), ScheduledTaskDefinition.id.desc())
    rows = list(db.scalars(stmt).all())
    return [_to_definition_read(row) for row in rows if _can_view_task(actor, row)]


def get_task_definition_read_or_404(
    db: Session,
    *,
    actor: AuthenticatedActor,
    task_id: str,
) -> ScheduledTaskDefinitionRead:
    row = _get_task_or_404(db, task_id)
    _ensure_actor_can_access_household(actor, row.household_id)
    if not _can_view_task(actor, row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scheduled task not found")
    return _to_definition_read(row)


def list_task_runs(
    db: Session,
    *,
    actor: AuthenticatedActor,
    household_id: str,
    task_definition_id: str | None = None,
    owner_scope: str | None = None,
    owner_member_id: str | None = None,
    status_value: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    limit: int = 100,
) -> list[ScheduledTaskRunRead]:
    _ensure_actor_can_access_household(actor, household_id)
    stmt: Select[tuple[ScheduledTaskRun]] = select(ScheduledTaskRun).where(ScheduledTaskRun.household_id == household_id)
    if task_definition_id is not None:
        stmt = stmt.where(ScheduledTaskRun.task_definition_id == task_definition_id)
    if owner_scope is not None:
        stmt = stmt.where(ScheduledTaskRun.owner_scope == owner_scope)
    if owner_member_id is not None:
        stmt = stmt.where(ScheduledTaskRun.owner_member_id == owner_member_id)
    if status_value is not None:
        stmt = stmt.where(ScheduledTaskRun.status == status_value)
    if created_from is not None:
        stmt = stmt.where(ScheduledTaskRun.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(ScheduledTaskRun.created_at <= created_to)
    stmt = stmt.order_by(ScheduledTaskRun.created_at.desc(), ScheduledTaskRun.id.desc()).limit(max(limit, 1))
    rows = list(db.scalars(stmt).all())
    return [_to_run_read(row) for row in rows if _can_view_run(actor, row)]


def create_task_run(
    db: Session,
    *,
    payload: ScheduledTaskRunCreate,
) -> ScheduledTaskRunRead:
    definition = _get_task_or_404(db, payload.task_definition_id)
    scheduled_for = payload.scheduled_for or utc_now_iso()
    idempotency_key = build_run_idempotency_key(
        task_definition_id=definition.id,
        scheduled_for=scheduled_for,
        trigger_source=payload.trigger_source,
    )
    existing = _get_run_by_idempotency_key(db, idempotency_key=idempotency_key)
    if existing is not None:
        return _to_run_read(existing)

    row = ScheduledTaskRun(
        id=new_uuid(),
        task_definition_id=definition.id,
        household_id=definition.household_id,
        owner_scope=definition.owner_scope,
        owner_member_id=definition.owner_member_id,
        trigger_source=payload.trigger_source,
        scheduled_for=scheduled_for,
        status=payload.status,
        idempotency_key=idempotency_key,
        evaluation_snapshot_json=dump_json(payload.evaluation_snapshot),
        dispatch_payload_json=dump_json(payload.dispatch_payload),
        target_type=definition.target_type,
        target_ref_id=definition.target_ref_id,
        error_code=payload.error_code,
        error_message=payload.error_message,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
    )
    db.add(row)
    db.flush()
    return _to_run_read(row)


def process_due_schedule_tick(
    db: Session,
    *,
    now_iso: str | None = None,
    limit: int = 100,
) -> list[ScheduledTaskRunRead]:
    now_text = now_iso or utc_now_iso()
    due_tasks = list_due_schedule_tasks(db, now_iso=now_text, limit=limit)
    created_runs: list[ScheduledTaskRunRead] = []
    for definition in due_tasks:
        scheduled_for = definition.next_run_at or now_text
        run = create_task_run(
            db,
            payload=ScheduledTaskRunCreate(
                task_definition_id=definition.id,
                trigger_source="schedule",
                scheduled_for=scheduled_for,
                status="queued",
            ),
        )
        definition.last_run_at = scheduled_for
        definition.last_result = "queued"
        if definition.schedule_type == "once":
            definition.next_run_at = None
            definition.enabled = False
            definition.status = "paused"
        else:
            definition.next_run_at = calculate_next_run_at(definition, reference_now=_parse_iso_datetime(scheduled_for))
        definition.updated_at = utc_now_iso()
        db.add(definition)
        created_runs.append(run)
    db.flush()
    return created_runs


def process_due_heartbeat_tick(
    db: Session,
    *,
    now_iso: str | None = None,
    limit: int = 100,
) -> list[ScheduledTaskRunRead]:
    now_text = now_iso or utc_now_iso()
    due_tasks = list_due_heartbeat_tasks(db, now_iso=now_text, limit=limit)
    created_runs: list[ScheduledTaskRunRead] = []
    for definition in due_tasks:
        scheduled_for = definition.next_heartbeat_at or now_text
        evaluation = evaluate_heartbeat_rule(db, definition=definition, now_iso=scheduled_for)
        if evaluation.status == "matched":
            run = create_task_run(
                db,
                payload=ScheduledTaskRunCreate(
                    task_definition_id=definition.id,
                    trigger_source="heartbeat",
                    scheduled_for=scheduled_for,
                    status="queued",
                    evaluation_snapshot=evaluation.snapshot,
                ),
            )
            created_runs.append(run)
            definition.last_run_at = scheduled_for
            definition.last_result = "queued"
        elif evaluation.status == "suppressed":
            run = create_task_run(
                db,
                payload=ScheduledTaskRunCreate(
                    task_definition_id=definition.id,
                    trigger_source="heartbeat",
                    scheduled_for=scheduled_for,
                    status="suppressed",
                    evaluation_snapshot=evaluation.snapshot,
                    error_code=evaluation.suppressed_reason,
                    error_message=evaluation.summary,
                    finished_at=scheduled_for,
                ),
            )
            created_runs.append(run)
            run_row = db.get(ScheduledTaskRun, run.id)
            if run_row is not None:
                finalize_task_run(db, definition=definition, run=run_row)
        elif evaluation.status == "error":
            run = create_task_run(
                db,
                payload=ScheduledTaskRunCreate(
                    task_definition_id=definition.id,
                    trigger_source="heartbeat",
                    scheduled_for=scheduled_for,
                    status="failed",
                    evaluation_snapshot=evaluation.snapshot,
                    error_code=evaluation.error_code,
                    error_message=evaluation.error_message or evaluation.summary,
                    finished_at=scheduled_for,
                ),
            )
            created_runs.append(run)
            run_row = db.get(ScheduledTaskRun, run.id)
            if run_row is not None:
                finalize_task_run(db, definition=definition, run=run_row)
        else:
            definition.last_result = "skipped"
        definition.next_heartbeat_at = calculate_next_heartbeat_at(definition, reference_now=_parse_iso_datetime(scheduled_for))
        definition.updated_at = utc_now_iso()
        db.add(definition)
    db.flush()
    return created_runs


def list_due_schedule_tasks(db: Session, *, now_iso: str, limit: int = 100) -> list[ScheduledTaskDefinition]:
    stmt: Select[tuple[ScheduledTaskDefinition]] = (
        select(ScheduledTaskDefinition)
        .where(
            ScheduledTaskDefinition.enabled.is_(True),
            ScheduledTaskDefinition.status == "active",
            ScheduledTaskDefinition.trigger_type == "schedule",
            ScheduledTaskDefinition.next_run_at.is_not(None),
            ScheduledTaskDefinition.next_run_at <= now_iso,
        )
        .order_by(ScheduledTaskDefinition.next_run_at.asc(), ScheduledTaskDefinition.id.asc())
        .limit(max(limit, 1))
    )
    return list(db.scalars(stmt).all())


def list_due_heartbeat_tasks(db: Session, *, now_iso: str, limit: int = 100) -> list[ScheduledTaskDefinition]:
    stmt: Select[tuple[ScheduledTaskDefinition]] = (
        select(ScheduledTaskDefinition)
        .where(
            ScheduledTaskDefinition.enabled.is_(True),
            ScheduledTaskDefinition.status == "active",
            ScheduledTaskDefinition.trigger_type == "heartbeat",
            ScheduledTaskDefinition.next_heartbeat_at.is_not(None),
            ScheduledTaskDefinition.next_heartbeat_at <= now_iso,
        )
        .order_by(ScheduledTaskDefinition.next_heartbeat_at.asc(), ScheduledTaskDefinition.id.asc())
        .limit(max(limit, 1))
    )
    return list(db.scalars(stmt).all())


def build_run_idempotency_key(*, task_definition_id: str, scheduled_for: str, trigger_source: str) -> str:
    digest = hashlib.sha256(f"{task_definition_id}|{trigger_source}|{scheduled_for}".encode("utf-8")).hexdigest()[:24]
    return f"{task_definition_id}:{trigger_source}:{digest}"


def calculate_next_run_at(definition: ScheduledTaskDefinition | ScheduledTaskDefinitionCreate, *, reference_now: datetime) -> str | None:
    if definition.trigger_type != "schedule":
        return None
    timezone_name = definition.timezone or "UTC"
    if definition.schedule_type == "daily":
        return _calculate_next_daily_run(definition.schedule_expr or "", timezone_name=timezone_name, reference_now=reference_now)
    if definition.schedule_type == "interval":
        return _calculate_next_interval_run(definition.schedule_expr or "", reference_now=reference_now)
    if definition.schedule_type == "cron":
        return _calculate_next_cron_run(definition.schedule_expr or "", timezone_name=timezone_name, reference_now=reference_now)
    if definition.schedule_type == "once":
        return _calculate_next_once_run(definition.schedule_expr or "", timezone_name=timezone_name, reference_now=reference_now)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported schedule type")


def calculate_next_heartbeat_at(definition: ScheduledTaskDefinition | ScheduledTaskDefinitionCreate, *, reference_now: datetime) -> str | None:
    if definition.trigger_type != "heartbeat":
        return None
    interval_seconds = definition.heartbeat_interval_seconds
    if interval_seconds is None or interval_seconds <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="heartbeat interval must be positive")
    return _to_utc_iso(reference_now + timedelta(seconds=interval_seconds))


def _calculate_next_daily_run(schedule_expr: str, *, timezone_name: str, reference_now: datetime) -> str:
    try:
        hour_text, minute_text = schedule_expr.strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="daily schedule must use HH:MM") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="daily schedule time is invalid")
    zone = _get_zoneinfo(timezone_name)
    local_reference = reference_now.astimezone(zone)
    candidate = local_reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_reference:
        candidate = candidate + timedelta(days=1)
    return _to_utc_iso(candidate)


def _calculate_next_interval_run(schedule_expr: str, *, reference_now: datetime) -> str:
    try:
        interval_seconds = int(schedule_expr)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval schedule must use seconds") from exc
    if interval_seconds <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval schedule must be positive")
    return _to_utc_iso(reference_now + timedelta(seconds=interval_seconds))


def _calculate_next_cron_run(schedule_expr: str, *, timezone_name: str, reference_now: datetime) -> str:
    fields = schedule_expr.strip().split()
    if len(fields) != 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron schedule must use five fields")
    minute_values = _expand_cron_field(fields[0], 0, 59)
    hour_values = _expand_cron_field(fields[1], 0, 23)
    day_values = _expand_cron_field(fields[2], 1, 31)
    month_values = _expand_cron_field(fields[3], 1, 12)
    weekday_values = _expand_cron_field(fields[4], 0, 6)
    zone = _get_zoneinfo(timezone_name)
    candidate = reference_now.astimezone(zone).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minute_values
            and candidate.hour in hour_values
            and candidate.day in day_values
            and candidate.month in month_values
            and cron_weekday in weekday_values
        ):
            return _to_utc_iso(candidate)
        candidate = candidate + timedelta(minutes=1)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron schedule cannot find next run time")


def _calculate_next_once_run(schedule_expr: str, *, timezone_name: str, reference_now: datetime) -> str:
    try:
        naive = datetime.fromisoformat(schedule_expr.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="once schedule must use YYYY-MM-DDTHH:MM") from exc
    zone = _get_zoneinfo(timezone_name)
    local_value = naive.replace(tzinfo=zone)
    if local_value.astimezone(timezone.utc) <= reference_now.astimezone(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="once schedule must be in the future")
    return _to_utc_iso(local_value)


def _expand_cron_field(field: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            values.update(range(minimum, maximum + 1))
            continue
        if part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron step must be positive")
            values.update(range(minimum, maximum + 1, step))
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron range is invalid")
            values.update(range(start, end + 1))
            continue
        values.add(int(part))
    if not values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron field is empty")
    if min(values) < minimum or max(values) > maximum:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron field is out of range")
    return values


def _validate_ownership(
    db: Session,
    *,
    actor: AuthenticatedActor,
    household_id: str,
    owner_scope: str,
    owner_member_id: str | None,
) -> tuple[str, str | None]:
    if owner_scope == "household":
        if actor.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only admin can manage household scheduled tasks")
        return "household", None

    effective_owner_member_id = owner_member_id or actor.member_id or _get_default_member_id(db, actor.account_id, household_id)
    if not effective_owner_member_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="member scheduled task requires owner member")
    member = db.get(Member, effective_owner_member_id)
    if member is None or member.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="owner member does not belong to household")
    if actor.role != "admin" and actor.member_id != effective_owner_member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage another member scheduled task")
    return "member", effective_owner_member_id


def _ensure_can_manage_task(actor: AuthenticatedActor, row: ScheduledTaskDefinition) -> None:
    if row.owner_scope == "household":
        if actor.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage household scheduled task")
        return
    if actor.role == "admin":
        return
    if actor.member_id != row.owner_member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage another member scheduled task")


def _ensure_actor_can_access_household(actor: AuthenticatedActor, household_id: str) -> None:
    if actor.account_type == "system":
        return
    if actor.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot access another household")


def _get_task_or_404(db: Session, task_id: str) -> ScheduledTaskDefinition:
    row = db.get(ScheduledTaskDefinition, task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scheduled task not found")
    return row


def _get_household_or_404(db: Session, household_id: str) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")
    return household


def _ensure_account_exists(db: Session, account_id: str) -> None:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account not found")


def _get_default_member_id(db: Session, account_id: str, household_id: str) -> str | None:
    binding = db.scalar(
        select(AccountMemberBinding).where(
            AccountMemberBinding.account_id == account_id,
            AccountMemberBinding.household_id == household_id,
            AccountMemberBinding.binding_status == "active",
        )
    )
    return binding.member_id if binding is not None else None


def _get_task_by_code(db: Session, *, household_id: str, code: str) -> ScheduledTaskDefinition | None:
    return db.scalar(
        select(ScheduledTaskDefinition).where(
            ScheduledTaskDefinition.household_id == household_id,
            ScheduledTaskDefinition.code == code,
        )
    )


def _get_run_by_idempotency_key(db: Session, *, idempotency_key: str) -> ScheduledTaskRun | None:
    return db.scalar(select(ScheduledTaskRun).where(ScheduledTaskRun.idempotency_key == idempotency_key))


def _ensure_target_is_valid(enabled: bool, target_ref_id: str | None) -> None:
    if enabled and (target_ref_id is None or not target_ref_id.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="enabled scheduled task requires target_ref_id")


def _validate_target_dependency(db: Session, *, household_id: str, target_type: str, target_ref_id: str | None) -> None:
    if target_ref_id is None:
        return
    if target_type != "plugin_job":
        return
    try:
        plugin = require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=target_ref_id,
            trigger="schedule",
        )
    except PluginExecutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    if plugin.risk_level == "high":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled task plugin target is high risk and cannot be scheduled by default")


def _validate_definition_snapshot(row: ScheduledTaskDefinition) -> None:
    ScheduledTaskDefinitionCreate.model_validate(
        {
            "household_id": row.household_id,
            "owner_scope": row.owner_scope,
            "owner_member_id": row.owner_member_id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "trigger_type": row.trigger_type,
            "schedule_type": row.schedule_type,
            "schedule_expr": row.schedule_expr,
            "heartbeat_interval_seconds": row.heartbeat_interval_seconds,
            "timezone": row.timezone,
            "target_type": row.target_type,
            "target_ref_id": row.target_ref_id,
            "rule_type": row.rule_type or "none",
            "rule_config": load_json(row.rule_config_json) or {},
            "payload_template": load_json(row.payload_template_json) or {},
            "cooldown_seconds": row.cooldown_seconds,
            "quiet_hours_policy": row.quiet_hours_policy,
            "enabled": row.enabled,
        }
    )


def _can_view_task(actor: AuthenticatedActor, row: ScheduledTaskDefinition) -> bool:
    if row.owner_scope == "household":
        return True
    if actor.role == "admin":
        return True
    return actor.member_id == row.owner_member_id


def _can_view_run(actor: AuthenticatedActor, row: ScheduledTaskRun) -> bool:
    if row.owner_scope == "household":
        return True
    if actor.role == "admin":
        return True
    return actor.member_id == row.owner_member_id


def _to_definition_read(row: ScheduledTaskDefinition) -> ScheduledTaskDefinitionRead:
    return ScheduledTaskDefinitionRead.model_validate(
        {
            "id": row.id,
            "household_id": row.household_id,
            "owner_scope": row.owner_scope,
            "owner_member_id": row.owner_member_id,
            "created_by_account_id": row.created_by_account_id,
            "last_modified_by_account_id": row.last_modified_by_account_id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "trigger_type": row.trigger_type,
            "schedule_type": row.schedule_type,
            "schedule_expr": row.schedule_expr,
            "heartbeat_interval_seconds": row.heartbeat_interval_seconds,
            "timezone": row.timezone,
            "target_type": row.target_type,
            "target_ref_id": row.target_ref_id,
            "rule_type": row.rule_type or "none",
            "rule_config": load_json(row.rule_config_json) or {},
            "payload_template": load_json(row.payload_template_json) or {},
            "cooldown_seconds": row.cooldown_seconds,
            "quiet_hours_policy": row.quiet_hours_policy,
            "enabled": row.enabled,
            "status": row.status,
            "last_run_at": row.last_run_at,
            "last_result": row.last_result,
            "consecutive_failures": row.consecutive_failures,
            "next_run_at": row.next_run_at,
            "next_heartbeat_at": row.next_heartbeat_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


def _to_run_read(row: ScheduledTaskRun) -> ScheduledTaskRunRead:
    return ScheduledTaskRunRead.model_validate(
        {
            "id": row.id,
            "task_definition_id": row.task_definition_id,
            "household_id": row.household_id,
            "owner_scope": row.owner_scope,
            "owner_member_id": row.owner_member_id,
            "trigger_source": row.trigger_source,
            "scheduled_for": row.scheduled_for,
            "status": row.status,
            "idempotency_key": row.idempotency_key,
            "evaluation_snapshot": load_json(row.evaluation_snapshot_json) or {},
            "dispatch_payload": load_json(row.dispatch_payload_json) or {},
            "target_type": row.target_type,
            "target_ref_id": row.target_ref_id,
            "target_run_id": row.target_run_id,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "created_at": row.created_at,
        }
    )


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_zoneinfo(timezone_name: str) -> tzinfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        fallback_offsets = {
            "UTC": 0,
            "Asia/Shanghai": 8,
            "Asia/Taipei": 8,
            "Asia/Hong_Kong": 8,
            "Asia/Macau": 8,
            "Asia/Tokyo": 9,
        }
        if timezone_name in fallback_offsets:
            return timezone(timedelta(hours=fallback_offsets[timezone_name]), name=timezone_name)
    if timezone_name == "UTC":
        return timezone.utc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="timezone is invalid")
