from collections import defaultdict
from typing import Any
from typing import cast

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.service import get_household_or_404
from app.modules.member.models import Member
from app.modules.memory import repository
from app.modules.memory.models import EventRecord, MemoryCard, MemoryCardMember, MemoryCardRevision
from app.modules.memory.schemas import (
    EventRecordCreate,
    EventRecordRead,
    MemoryEventProcessingStatus,
    MemoryCardCorrectionPayload,
    MemoryCardManualCreate,
    MemoryCardMemberRead,
    MemoryCardRead,
    MemoryCardRevisionListResponse,
    MemoryCardRevisionRead,
    MemoryDebugOverviewRead,
    MemoryStatus,
    MemoryType,
    MemoryVisibility,
)
from app.modules.room.models import Room

VALID_MEMORY_TYPES = {"fact", "event", "preference", "relation", "growth", "observation"}
VALID_MEMORY_STATUS = {"active", "pending_review", "invalidated", "deleted"}
VALID_MEMORY_VISIBILITY = {"public", "family", "private", "sensitive"}
SUPPORTED_EVENT_MEMORY_TYPES = {
    "memory_manual_created": "fact",
    "member_fact_observed": "fact",
    "member_preference_observed": "preference",
    "family_relation_observed": "relation",
    "family_event_occurred": "event",
    "presence_changed": "event",
    "reminder_acknowledged": "event",
    "scene_executed": "event",
}


def _invalidate_hot_summary_cache(household_id: str) -> None:
    from app.modules.memory.query_service import invalidate_memory_hot_summary

    invalidate_memory_hot_summary(household_id)


def _get_member_in_household_or_400(db: Session, member_id: str, household_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="member not found")
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member must belong to the same household",
        )
    return member


def _get_room_in_household_or_400(db: Session, room_id: str, household_id: str) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="room not found")
    if room.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room must belong to the same household",
        )
    return room


def _normalize_memory_type(value: Any, default: str) -> str:
    if isinstance(value, str) and value in VALID_MEMORY_TYPES:
        return value
    return default


def _normalize_memory_status(value: Any, default: str = "active") -> str:
    if isinstance(value, str) and value in VALID_MEMORY_STATUS:
        return value
    return default


def _normalize_memory_visibility(value: Any, default: str = "family") -> str:
    if isinstance(value, str) and value in VALID_MEMORY_VISIBILITY:
        return value
    return default


def _normalize_confidence(value: Any, default: float = 0.8) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return default


def _normalize_importance(value: Any, default: int = 3) -> int:
    if isinstance(value, int):
        return max(1, min(5, value))
    return default


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().lower().split())


def _build_memory_dedupe_key(*, household_id: str, memory_type: str, subject_member_id: str | None, title: str, summary: str) -> str:
    subject_key = subject_member_id or "global"
    text_key = _normalize_text(title) or _normalize_text(summary) or "untitled"
    return f"{household_id}:{memory_type}:{subject_key}:{text_key}"


def _to_event_record_read(row: EventRecord) -> EventRecordRead:
    return EventRecordRead(
        id=row.id,
        household_id=row.household_id,
        event_type=row.event_type,
        source_type=row.source_type,
        source_ref=row.source_ref,
        subject_member_id=row.subject_member_id,
        room_id=row.room_id,
        payload=load_json(row.payload_json),
        dedupe_key=row.dedupe_key,
        processing_status=cast(MemoryEventProcessingStatus, row.processing_status),
        generate_memory_card=row.generate_memory_card,
        failure_reason=row.failure_reason,
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        processed_at=row.processed_at,
    )


def _build_card_reads(db: Session, rows: list[MemoryCard]) -> list[MemoryCardRead]:
    members_by_memory_id: dict[str, list[MemoryCardMemberRead]] = defaultdict(list)
    memory_ids = [row.id for row in rows]
    for link in repository.list_memory_card_members(db, memory_ids=memory_ids):
        members_by_memory_id[link.memory_id].append(
            MemoryCardMemberRead(
                memory_id=link.memory_id,
                member_id=link.member_id,
                relation_role=link.relation_role,
            )
        )

    return [
        MemoryCardRead(
            id=row.id,
            household_id=row.household_id,
            memory_type=cast(MemoryType, row.memory_type),
            title=row.title,
            summary=row.summary,
            normalized_text=row.normalized_text,
            content=load_json(row.content_json),
            status=cast(MemoryStatus, row.status),
            visibility=cast(MemoryVisibility, row.visibility),
            importance=row.importance,
            confidence=row.confidence,
            subject_member_id=row.subject_member_id,
            source_event_id=row.source_event_id,
            source_plugin_id=row.source_plugin_id,
            source_raw_record_id=row.source_raw_record_id,
            dedupe_key=row.dedupe_key,
            effective_at=row.effective_at,
            last_observed_at=row.last_observed_at,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
            invalidated_at=row.invalidated_at,
            related_members=members_by_memory_id.get(row.id, []),
        )
        for row in rows
    ]


def _build_revision_reads(rows: list[MemoryCardRevision]) -> MemoryCardRevisionListResponse:
    return MemoryCardRevisionListResponse(
        items=[
            MemoryCardRevisionRead.model_validate(row, from_attributes=True)
            for row in rows
        ]
    )


def _collect_member_links(
    subject_member_id: str | None,
    related_members: list[dict[str, str]],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    if subject_member_id:
        pair = (subject_member_id, "subject")
        seen.add(pair)
        pairs.append(pair)

    for item in related_members:
        member_id = item.get("member_id")
        relation_role = item.get("relation_role", "participant")
        if not isinstance(member_id, str) or not member_id.strip():
            continue
        if relation_role not in {"subject", "participant", "mentioned", "owner"}:
            relation_role = "participant"
        pair = (member_id.strip(), relation_role)
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(pair)
    return pairs


def _replace_memory_links(
    db: Session,
    *,
    memory_id: str,
    household_id: str,
    subject_member_id: str | None,
    related_members: list[dict[str, str]],
) -> None:
    pairs = _collect_member_links(subject_member_id, related_members)
    links: list[MemoryCardMember] = []
    for member_id, relation_role in pairs:
        _get_member_in_household_or_400(db, member_id, household_id)
        links.append(
            MemoryCardMember(
                memory_id=memory_id,
                member_id=member_id,
                relation_role=relation_role,
            )
        )
    repository.replace_memory_card_members(db, memory_id=memory_id, links=links)


def _record_revision(
    db: Session,
    *,
    memory_id: str,
    action: str,
    before: MemoryCardRead | None,
    after: MemoryCardRead | None,
    reason: str | None,
    actor_type: str,
    actor_id: str | None,
) -> None:
    repository.add_memory_card_revision(
        db,
        MemoryCardRevision(
            id=new_uuid(),
            memory_id=memory_id,
            revision_no=repository.get_next_revision_no(db, memory_id=memory_id),
            action=action,
            before_json=dump_json(before.model_dump(mode="json")) if before is not None else None,
            after_json=dump_json(after.model_dump(mode="json")) if after is not None else None,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=utc_now_iso(),
        ),
    )
    db.flush()


def _derive_event_candidate(event: EventRecord) -> dict[str, Any] | None:
    payload = load_json(event.payload_json)
    if not isinstance(payload, dict):
        payload = {}

    default_memory_type = SUPPORTED_EVENT_MEMORY_TYPES.get(event.event_type)
    if default_memory_type is None:
        return None

    memory_type = _normalize_memory_type(payload.get("memory_type"), default_memory_type)
    subject_member_id = payload.get("subject_member_id") if isinstance(payload.get("subject_member_id"), str) else event.subject_member_id
    title = payload.get("title") if isinstance(payload.get("title"), str) else None
    summary = payload.get("summary") if isinstance(payload.get("summary"), str) else None

    if not title:
        if memory_type == "preference":
            title = "成员偏好观察"
        elif memory_type == "relation":
            title = "家庭关系观察"
        elif memory_type == "event":
            title = event.event_type.replace("_", " ")
        else:
            title = "成员事实观察"

    if not summary:
        summary_parts = []
        if isinstance(payload.get("fact"), str):
            summary_parts.append(payload["fact"])
        if isinstance(payload.get("preference"), str):
            summary_parts.append(payload["preference"])
        if isinstance(payload.get("description"), str):
            summary_parts.append(payload["description"])
        if isinstance(payload.get("note"), str):
            summary_parts.append(payload["note"])
        summary = "；".join(part.strip() for part in summary_parts if part.strip()) or f"来自事件 {event.event_type}"

    raw_related_members = payload.get("related_members")
    related_members = raw_related_members if isinstance(raw_related_members, list) else []
    normalized_related_members: list[dict[str, str]] = []
    for item in related_members:
        if not isinstance(item, dict):
            continue
        member_id = item.get("member_id")
        relation_role = item.get("relation_role", "participant")
        if isinstance(member_id, str) and member_id.strip():
            normalized_related_members.append(
                {
                    "member_id": member_id.strip(),
                    "relation_role": relation_role if isinstance(relation_role, str) else "participant",
                }
            )

    dedupe_key = None
    for candidate_key in ("card_dedupe_key", "memory_dedupe_key", "dedupe_key"):
        candidate_value = payload.get(candidate_key)
        if isinstance(candidate_value, str) and candidate_value.strip():
            dedupe_key = candidate_value.strip()
            break
    if dedupe_key is None:
        dedupe_key = _build_memory_dedupe_key(
            household_id=event.household_id,
            memory_type=memory_type,
            subject_member_id=subject_member_id,
            title=title,
            summary=summary,
        )

    content = payload.get("content") if isinstance(payload.get("content"), dict) else payload
    return {
        "household_id": event.household_id,
        "memory_type": memory_type,
        "title": title,
        "summary": summary,
        "content": content,
        "status": _normalize_memory_status(payload.get("status"), "active"),
        "visibility": _normalize_memory_visibility(payload.get("visibility"), "family"),
        "importance": _normalize_importance(payload.get("importance"), 3),
        "confidence": _normalize_confidence(payload.get("confidence"), 0.8),
        "subject_member_id": subject_member_id,
        "source_event_id": event.id,
        "dedupe_key": dedupe_key,
        "effective_at": payload.get("effective_at") if isinstance(payload.get("effective_at"), str) else event.occurred_at,
        "last_observed_at": event.occurred_at,
        "related_members": normalized_related_members,
        "reason": payload.get("reason") if isinstance(payload.get("reason"), str) else f"由事件 {event.event_type} 自动提炼",
    }


def _upsert_memory_card(
    db: Session,
    *,
    candidate: dict[str, Any],
    actor_type: str,
    actor_id: str | None,
    revision_action: str,
    forbid_existing: bool = False,
) -> MemoryCardRead:
    household_id = candidate["household_id"]
    get_household_or_404(db, household_id)

    subject_member_id = candidate.get("subject_member_id")
    if isinstance(subject_member_id, str) and subject_member_id:
        _get_member_in_household_or_400(db, subject_member_id, household_id)

    source_event_id = candidate.get("source_event_id")
    if isinstance(source_event_id, str) and source_event_id:
        source_event = repository.get_event_record(db, source_event_id)
        if source_event is None or source_event.household_id != household_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source event not found")

    source_plugin_id = candidate.get("source_plugin_id")
    if source_plugin_id is not None and (not isinstance(source_plugin_id, str) or not source_plugin_id.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source plugin id invalid")

    source_raw_record_id = candidate.get("source_raw_record_id")
    if isinstance(source_raw_record_id, str) and source_raw_record_id:
        from app.modules.plugin.models import PluginRawRecord
        source_raw_record = db.get(PluginRawRecord, source_raw_record_id)
        if source_raw_record is None or source_raw_record.household_id != household_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source raw record not found")

    dedupe_key = candidate.get("dedupe_key")
    existing = None
    if isinstance(dedupe_key, str) and dedupe_key:
        existing = repository.get_memory_card_by_dedupe_key(
            db,
            household_id=household_id,
            dedupe_key=dedupe_key,
        )

    if existing is not None and forbid_existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="memory card dedupe key already exists")

    now = utc_now_iso()
    if existing is None:
        row = MemoryCard(
            id=new_uuid(),
            household_id=household_id,
            memory_type=candidate["memory_type"],
            title=candidate["title"],
            summary=candidate["summary"],
            normalized_text=" ".join(
                part.strip()
                for part in [candidate["title"], candidate["summary"]]
                if isinstance(part, str) and part.strip()
            )
            or None,
            content_json=dump_json(jsonable_encoder(candidate.get("content"))) or "{}",
            status=candidate["status"],
            visibility=candidate["visibility"],
            importance=candidate["importance"],
            confidence=candidate["confidence"],
            subject_member_id=subject_member_id,
            source_event_id=source_event_id,
            source_plugin_id=source_plugin_id.strip() if isinstance(source_plugin_id, str) else None,
            source_raw_record_id=source_raw_record_id,
            dedupe_key=dedupe_key,
            effective_at=candidate.get("effective_at"),
            last_observed_at=candidate.get("last_observed_at"),
            created_by=actor_type,
            created_at=now,
            updated_at=now,
            invalidated_at=now if candidate["status"] in {"invalidated", "deleted"} else None,
        )
        repository.add_memory_card(db, row)
        db.flush()
        _replace_memory_links(
            db,
            memory_id=row.id,
            household_id=household_id,
            subject_member_id=subject_member_id,
            related_members=candidate.get("related_members", []),
        )
        db.flush()
        after = _build_card_reads(db, [row])[0]
        _record_revision(
            db,
            memory_id=row.id,
            action="create",
            before=None,
            after=after,
            reason=candidate.get("reason"),
            actor_type=actor_type,
            actor_id=actor_id,
        )
        _invalidate_hot_summary_cache(household_id)
        return after

    before = _build_card_reads(db, [existing])[0]
    existing.memory_type = candidate["memory_type"]
    existing.title = candidate["title"]
    existing.summary = candidate["summary"]
    existing.normalized_text = " ".join(
        part.strip()
        for part in [candidate["title"], candidate["summary"]]
        if isinstance(part, str) and part.strip()
    ) or None
    existing.content_json = dump_json(jsonable_encoder(candidate.get("content"))) or "{}"
    existing.status = candidate["status"]
    existing.visibility = candidate["visibility"]
    existing.importance = candidate["importance"]
    existing.confidence = candidate["confidence"]
    existing.subject_member_id = subject_member_id
    existing.source_event_id = source_event_id or existing.source_event_id
    existing.source_plugin_id = source_plugin_id.strip() if isinstance(source_plugin_id, str) else existing.source_plugin_id
    existing.source_raw_record_id = source_raw_record_id or existing.source_raw_record_id
    existing.dedupe_key = dedupe_key
    existing.effective_at = candidate.get("effective_at") or existing.effective_at
    existing.last_observed_at = candidate.get("last_observed_at") or existing.last_observed_at
    existing.updated_at = now
    existing.invalidated_at = now if candidate["status"] in {"invalidated", "deleted"} else None
    db.add(existing)
    db.flush()

    related_members = candidate.get("related_members")
    if isinstance(related_members, list):
        _replace_memory_links(
            db,
            memory_id=existing.id,
            household_id=household_id,
            subject_member_id=subject_member_id,
            related_members=related_members,
        )
        db.flush()

    after = _build_card_reads(db, [existing])[0]
    _record_revision(
        db,
        memory_id=existing.id,
        action=revision_action,
        before=before,
        after=after,
        reason=candidate.get("reason"),
        actor_type=actor_type,
        actor_id=actor_id,
    )
    _invalidate_hot_summary_cache(household_id)
    return after


def ingest_event_record(db: Session, payload: EventRecordCreate) -> tuple[EventRecord, bool]:
    get_household_or_404(db, payload.household_id)

    if payload.subject_member_id is not None:
        _get_member_in_household_or_400(db, payload.subject_member_id, payload.household_id)
    if payload.room_id is not None:
        _get_room_in_household_or_400(db, payload.room_id, payload.household_id)

    if payload.dedupe_key:
        existing = repository.get_event_record_by_dedupe_key(
            db,
            household_id=payload.household_id,
            dedupe_key=payload.dedupe_key,
        )
        if existing is not None:
            return existing, True

    event = EventRecord(
        id=new_uuid(),
        household_id=payload.household_id,
        event_type=payload.event_type,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        subject_member_id=payload.subject_member_id,
        room_id=payload.room_id,
        payload_json=dump_json(jsonable_encoder(payload.payload)) or "{}",
        dedupe_key=payload.dedupe_key,
        processing_status="pending" if payload.generate_memory_card else "ignored",
        generate_memory_card=payload.generate_memory_card,
        failure_reason=None,
        occurred_at=payload.occurred_at or utc_now_iso(),
        processed_at=None,
    )
    repository.add_event_record(db, event)
    db.flush()

    if not payload.generate_memory_card:
        event.processing_status = "ignored"
        event.processed_at = utc_now_iso()
        _invalidate_hot_summary_cache(event.household_id)
        return event, False

    try:
        candidate = _derive_event_candidate(event)
        if candidate is None:
            event.processing_status = "ignored"
            event.processed_at = utc_now_iso()
            return event, False
        _upsert_memory_card(
            db,
            candidate=candidate,
            actor_type="system",
            actor_id=None,
            revision_action="update_observed",
        )
        event.processing_status = "processed"
        event.failure_reason = None
        event.processed_at = utc_now_iso()
        _invalidate_hot_summary_cache(event.household_id)
    except HTTPException as exc:
        event.processing_status = "failed"
        event.failure_reason = str(exc.detail)
        event.processed_at = utc_now_iso()
    except Exception as exc:
        event.processing_status = "failed"
        event.failure_reason = str(exc)
        event.processed_at = utc_now_iso()
    return event, False


def list_event_records(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    processing_status: str | None = None,
) -> tuple[list[EventRecordRead], int]:
    get_household_or_404(db, household_id)
    rows, total = repository.list_event_records(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        processing_status=processing_status,
    )
    return [_to_event_record_read(row) for row in rows], total


def create_manual_memory_card(
    db: Session,
    *,
    payload: MemoryCardManualCreate,
    actor: ActorContext | None,
) -> MemoryCardRead:
    candidate = {
        "household_id": payload.household_id,
        "memory_type": payload.memory_type,
        "title": payload.title,
        "summary": payload.summary,
        "content": payload.content,
        "status": payload.status,
        "visibility": payload.visibility,
        "importance": payload.importance,
        "confidence": payload.confidence,
        "subject_member_id": payload.subject_member_id,
        "source_event_id": payload.source_event_id,
        "source_plugin_id": payload.source_plugin_id,
        "source_raw_record_id": payload.source_raw_record_id,
        "dedupe_key": payload.dedupe_key,
        "effective_at": payload.effective_at,
        "last_observed_at": payload.last_observed_at,
        "related_members": [item.model_dump(mode="json") for item in payload.related_members],
        "reason": payload.reason,
    }
    return _upsert_memory_card(
        db,
        candidate=candidate,
        actor_type=actor.actor_type if actor else "system",
        actor_id=actor.actor_id if actor else None,
        revision_action="create",
        forbid_existing=True,
    )


def correct_memory_card(
    db: Session,
    *,
    memory_id: str,
    payload: MemoryCardCorrectionPayload,
    actor: ActorContext | None,
) -> MemoryCardRead:
    row = repository.get_memory_card(db, memory_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory card not found")

    before = _build_card_reads(db, [row])[0]
    now = utc_now_iso()

    if payload.action == "invalidate":
        row.status = "invalidated"
        row.invalidated_at = now
    elif payload.action == "delete":
        row.status = "deleted"
        row.invalidated_at = now
    else:
        row.status = payload.status or row.status
        if row.status not in {"invalidated", "deleted"}:
            row.invalidated_at = None

    if payload.title is not None:
        row.title = payload.title
    if payload.summary is not None:
        row.summary = payload.summary
    if payload.content is not None:
        row.content_json = dump_json(jsonable_encoder(payload.content)) or "{}"
    if payload.visibility is not None:
        row.visibility = payload.visibility
    if payload.importance is not None:
        row.importance = payload.importance
    if payload.confidence is not None:
        row.confidence = payload.confidence

    row.normalized_text = " ".join(
        part.strip()
        for part in [row.title, row.summary]
        if isinstance(part, str) and part.strip()
    ) or None
    row.updated_at = now
    db.add(row)
    db.flush()

    after = _build_card_reads(db, [row])[0]
    _record_revision(
        db,
        memory_id=row.id,
        action=payload.action,
        before=before,
        after=after,
        reason=payload.reason,
        actor_type=actor.actor_type if actor else "system",
        actor_id=actor.actor_id if actor else None,
    )
    _invalidate_hot_summary_cache(row.household_id)
    return after


def list_memory_cards(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    memory_type: str | None = None,
) -> tuple[list[MemoryCardRead], int]:
    get_household_or_404(db, household_id)
    rows, total = repository.list_memory_cards(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        memory_type=memory_type,
    )
    return _build_card_reads(db, rows), total


def list_memory_card_revisions(
    db: Session,
    *,
    memory_id: str,
) -> MemoryCardRevisionListResponse:
    row = repository.get_memory_card(db, memory_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory card not found")
    revisions = list(repository.list_memory_card_revisions(db, memory_id=memory_id))
    return _build_revision_reads(revisions)


def get_memory_debug_overview(db: Session, *, household_id: str) -> MemoryDebugOverviewRead:
    get_household_or_404(db, household_id)
    event_counts = repository.count_event_records_by_status(db, household_id=household_id)
    card_counts = repository.count_memory_cards_by_status(db, household_id=household_id)
    return MemoryDebugOverviewRead(
        household_id=household_id,
        total_events=sum(event_counts.values()),
        pending_events=event_counts.get("pending", 0),
        processed_events=event_counts.get("processed", 0),
        failed_events=event_counts.get("failed", 0),
        ignored_events=event_counts.get("ignored", 0),
        total_cards=sum(card_counts.values()),
        active_cards=card_counts.get("active", 0),
        pending_cards=card_counts.get("pending_review", 0),
        invalidated_cards=card_counts.get("invalidated", 0),
        deleted_cards=card_counts.get("deleted", 0),
        latest_event_at=repository.get_latest_event_occurred_at(db, household_id=household_id),
        latest_card_at=repository.get_latest_memory_card_updated_at(db, household_id=household_id),
    )


def ingest_event_record_best_effort(db: Session, payload: EventRecordCreate) -> tuple[str | None, str | None]:
    try:
        with db.begin_nested():
            event, _duplicate = ingest_event_record(db, payload)
            return event.id, event.processing_status
    except Exception:
        return None, None


def upsert_plugin_observation_memory(
    db: Session,
    *,
    household_id: str,
    subject_member_id: str | None,
    source_plugin_id: str,
    source_raw_record_id: str,
    observation: dict[str, Any],
) -> MemoryCardRead:
    subject_type = observation.get("subject_type") if isinstance(observation.get("subject_type"), str) else None
    subject_id = observation.get("subject_id") if isinstance(observation.get("subject_id"), str) else None
    category = observation.get("category") if isinstance(observation.get("category"), str) else None
    observed_at = observation.get("observed_at") if isinstance(observation.get("observed_at"), str) else utc_now_iso()
    unit = observation.get("unit") if isinstance(observation.get("unit"), str) else None
    value = observation.get("value")

    if not category or value is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="observation 缺少 category 或 value")

    summary_parts = [category]
    if value is not None:
        summary_parts.append(str(value))
    if unit:
        summary_parts.append(unit)
    if subject_id:
        summary_parts.append(subject_id)

    title_subject = subject_id or subject_member_id or "未指定对象"
    title = f"{title_subject} 的 {category} 观察"
    summary = " / ".join(summary_parts)
    dedupe_key = f"plugin-raw-observation:{source_raw_record_id}"

    candidate = {
        "household_id": household_id,
        "memory_type": "observation",
        "title": title,
        "summary": summary,
        "content": {
            "type": "Observation",
            "subject_type": subject_type,
            "subject_id": subject_id,
            "category": category,
            "value": value,
            "unit": unit,
            "observed_at": observed_at,
            "source_plugin_id": source_plugin_id,
            "source_record_ref": source_raw_record_id,
        },
        "status": "active",
        "visibility": "family",
        "importance": 3,
        "confidence": 0.9,
        "subject_member_id": subject_member_id,
        "source_event_id": None,
        "source_plugin_id": source_plugin_id,
        "source_raw_record_id": source_raw_record_id,
        "dedupe_key": dedupe_key,
        "effective_at": observed_at,
        "last_observed_at": observed_at,
        "related_members": [],
        "reason": "由插件原始记录转换为 Observation",
    }
    return _upsert_memory_card(
        db,
        candidate=candidate,
        actor_type="plugin",
        actor_id=source_plugin_id,
        revision_action="update_observed",
    )
