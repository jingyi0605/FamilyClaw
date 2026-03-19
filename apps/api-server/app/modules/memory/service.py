from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from typing import cast

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
# NOTE: get_household_or_404 延迟导入，避免循环依赖
from app.modules.member.models import Member
from app.modules.memory import repository
from app.modules.memory.models import (
    EpisodicMemoryEntryRevision,
    EpisodicMemoryEntry,
    EventRecord,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    MemoryCard,
    MemoryCardMember,
    MemoryCardRevision,
)
from app.modules.memory.recall_projection import (
    MEMORY_RECALL_PROJECTION_VERSION,
    build_memory_card_search_text,
    build_text_embedding,
    to_vector_literal,
)
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
VALID_KNOWLEDGE_DOCUMENT_SOURCE_KINDS = {"plugin_raw_record", "doc", "rule"}
RECENT_EVENT_MEMORY_TYPES = {"event", "growth", "observation"}
PROMOTION_WINDOW_DAYS = 30
PROMOTION_THRESHOLD_BY_TYPE = {
    "fact": 1,
    "preference": 1,
    "relation": 1,
    "event": 2,
    "growth": 2,
    "observation": 2,
}
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


def _normalize_subject_member_id_for_household(
    db: Session,
    *,
    household_id: str,
    subject_member_id: str | None,
) -> str | None:
    if not isinstance(subject_member_id, str):
        return None
    normalized_subject_member_id = subject_member_id.strip()
    if not normalized_subject_member_id:
        return None
    return _get_member_in_household_or_400(db, normalized_subject_member_id, household_id).id


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


def _build_episodic_memory_entry_snapshot(row: EpisodicMemoryEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "household_id": row.household_id,
        "subject_member_id": row.subject_member_id,
        "source_kind": row.source_kind,
        "source_id": row.source_id,
        "title": row.title,
        "summary": row.summary,
        "content": load_json(row.content_json),
        "visibility": row.visibility,
        "importance": row.importance,
        "confidence": row.confidence,
        "promotion_key": row.promotion_key,
        "occurred_at": row.occurred_at,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _record_episodic_memory_entry_revision(
    db: Session,
    *,
    entry_id: str,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str | None,
    actor_type: str,
    actor_id: str | None,
) -> None:
    repository.add_episodic_memory_entry_revision(
        db,
        EpisodicMemoryEntryRevision(
            id=new_uuid(),
            entry_id=entry_id,
            revision_no=repository.get_next_episodic_memory_entry_revision_no(db, entry_id=entry_id),
            action=action,
            before_json=dump_json(jsonable_encoder(before)) if before is not None else None,
            after_json=dump_json(jsonable_encoder(after)) if after is not None else None,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=utc_now_iso(),
        ),
    )


def _build_knowledge_document_snapshot(row: KnowledgeDocument) -> dict[str, Any]:
    return {
        "id": row.id,
        "household_id": row.household_id,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "title": row.title,
        "summary": row.summary,
        "body_text": row.body_text,
        "visibility": row.visibility,
        "updated_at": row.updated_at,
        "status": row.status,
    }


def _record_knowledge_document_revision(
    db: Session,
    *,
    document_id: str,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str | None,
    actor_type: str,
    actor_id: str | None,
) -> None:
    repository.add_knowledge_document_revision(
        db,
        KnowledgeDocumentRevision(
            id=new_uuid(),
            document_id=document_id,
            revision_no=repository.get_next_knowledge_document_revision_no(db, document_id=document_id),
            action=action,
            before_json=dump_json(jsonable_encoder(before)) if before is not None else None,
            after_json=dump_json(jsonable_encoder(after)) if after is not None else None,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=utc_now_iso(),
        ),
    )
    db.flush()


def _refresh_memory_card_projection(db: Session, *, row: MemoryCard) -> None:
    search_text = build_memory_card_search_text(
        memory_type=row.memory_type,
        title=row.title,
        summary=row.summary,
        normalized_text=row.normalized_text,
        content_json=row.content_json,
    )
    embedding_literal = to_vector_literal(build_text_embedding(search_text))
    projection_updated_at = utc_now_iso()
    repository.refresh_memory_card_projection(
        db,
        memory_id=row.id,
        search_text=search_text,
        embedding_literal=embedding_literal,
        projection_version=MEMORY_RECALL_PROJECTION_VERSION,
        projection_updated_at=projection_updated_at,
    )
    row.search_text = search_text or None
    row.projection_version = MEMORY_RECALL_PROJECTION_VERSION
    row.projection_updated_at = projection_updated_at
    from app.modules.memory.recall_document_service import sync_memory_card_recall_document

    sync_memory_card_recall_document(db, row=row)
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


def _derive_promotion_key(*, candidate: dict[str, Any]) -> str | None:
    content = candidate.get("content")
    if isinstance(content, dict):
        raw_key = content.get("promotion_key")
        if isinstance(raw_key, str) and raw_key.strip():
            return raw_key.strip()
        category = content.get("category")
        if isinstance(category, str) and category.strip():
            subject_key = candidate.get("subject_member_id") or content.get("subject_id") or "global"
            return f"{candidate['memory_type']}:{subject_key}:{category.strip().lower()}"

    if candidate["memory_type"] in RECENT_EVENT_MEMORY_TYPES:
        return _build_memory_dedupe_key(
            household_id=candidate["household_id"],
            memory_type=candidate["memory_type"],
            subject_member_id=candidate.get("subject_member_id"),
            title=candidate["title"],
            summary=candidate["summary"],
        )
    return _build_memory_dedupe_key(
        household_id=candidate["household_id"],
        memory_type=candidate["memory_type"],
        subject_member_id=candidate.get("subject_member_id"),
        title=candidate["title"],
        summary=candidate["summary"],
    )


def _upsert_episodic_entry_from_event(
    db: Session,
    *,
    event: EventRecord,
    candidate: dict[str, Any],
) -> EpisodicMemoryEntry:
    subject_member_id = _normalize_subject_member_id_for_household(
        db,
        household_id=event.household_id,
        subject_member_id=candidate.get("subject_member_id"),
    )
    row = repository.get_episodic_memory_entry_by_source(
        db,
        household_id=event.household_id,
        source_kind="event",
        source_id=event.id,
    )
    content = dict(candidate.get("content") or {})
    content["memory_type"] = candidate["memory_type"]
    content["related_members"] = candidate.get("related_members", [])
    now = utc_now_iso()
    if row is None:
        row = EpisodicMemoryEntry(
            id=new_uuid(),
            household_id=event.household_id,
            subject_member_id=subject_member_id,
            source_kind="event",
            source_id=event.id,
            title=candidate["title"],
            summary=candidate["summary"],
            content_json=dump_json(jsonable_encoder(content)) or "{}",
            visibility=candidate["visibility"],
            importance=candidate["importance"],
            confidence=candidate["confidence"],
            promotion_key=_derive_promotion_key(candidate=candidate),
            occurred_at=event.occurred_at,
            status="active",
            created_at=now,
            updated_at=now,
        )
        repository.add_episodic_memory_entry(db, row)
        db.flush()
        _record_episodic_memory_entry_revision(
            db,
            entry_id=row.id,
            action="create",
            before=None,
            after=_build_episodic_memory_entry_snapshot(row),
            reason="由事件记录沉淀为 L2 情节记忆",
            actor_type="system",
            actor_id=event.source_type,
        )
    else:
        before = _build_episodic_memory_entry_snapshot(row)
        row.subject_member_id = subject_member_id
        row.title = candidate["title"]
        row.summary = candidate["summary"]
        row.content_json = dump_json(jsonable_encoder(content)) or "{}"
        row.visibility = candidate["visibility"]
        row.importance = candidate["importance"]
        row.confidence = candidate["confidence"]
        row.promotion_key = _derive_promotion_key(candidate=candidate)
        row.occurred_at = event.occurred_at
        row.status = "active"
        row.updated_at = now
        db.add(row)
        db.flush()
        _record_episodic_memory_entry_revision(
            db,
            entry_id=row.id,
            action="update",
            before=before,
            after=_build_episodic_memory_entry_snapshot(row),
            reason="事件链路刷新 L2 情节记忆",
            actor_type="system",
            actor_id=event.source_type,
        )
    db.flush()
    from app.modules.memory.recall_document_service import sync_episodic_memory_recall_document

    sync_episodic_memory_recall_document(db, row=row)
    db.flush()
    return row


def upsert_episodic_memory_from_session_summary(
    db: Session,
    *,
    summary_id: str,
    household_id: str,
    requester_member_id: str | None,
    summary: str,
    open_topics: list[str],
    recent_confirmations: list[str],
    generated_at: str,
    updated_at: str,
) -> EpisodicMemoryEntry:
    normalized_requester_member_id = _normalize_subject_member_id_for_household(
        db,
        household_id=household_id,
        subject_member_id=requester_member_id,
    )
    row = repository.get_episodic_memory_entry_by_source(
        db,
        household_id=household_id,
        source_kind="session_summary",
        source_id=summary_id,
    )
    content = {
        "memory_type": "event",
        "open_topics": open_topics,
        "recent_confirmations": recent_confirmations,
        "source_summary_id": summary_id,
    }
    title = "会话进展摘要"
    now = utc_now_iso()
    if row is None:
        row = EpisodicMemoryEntry(
            id=new_uuid(),
            household_id=household_id,
            subject_member_id=normalized_requester_member_id,
            source_kind="session_summary",
            source_id=summary_id,
            title=title,
            summary=summary,
            content_json=dump_json(content) or "{}",
            visibility="private",
            importance=2,
            confidence=0.75,
            promotion_key=None,
            occurred_at=generated_at,
            status="active",
            created_at=now,
            updated_at=updated_at,
        )
        repository.add_episodic_memory_entry(db, row)
        db.flush()
        _record_episodic_memory_entry_revision(
            db,
            entry_id=row.id,
            action="create",
            before=None,
            after=_build_episodic_memory_entry_snapshot(row),
            reason="由会话摘要沉淀为 L2 情节记忆",
            actor_type="system",
            actor_id="session_summary",
        )
    else:
        before = _build_episodic_memory_entry_snapshot(row)
        row.subject_member_id = normalized_requester_member_id
        row.title = title
        row.summary = summary
        row.content_json = dump_json(content) or "{}"
        row.visibility = "private"
        row.importance = 2
        row.confidence = 0.75
        row.occurred_at = generated_at
        row.status = "active"
        row.updated_at = updated_at
        db.add(row)
        db.flush()
        _record_episodic_memory_entry_revision(
            db,
            entry_id=row.id,
            action="update",
            before=before,
            after=_build_episodic_memory_entry_snapshot(row),
            reason="会话摘要刷新 L2 情节记忆",
            actor_type="system",
            actor_id="session_summary",
        )
    db.flush()
    from app.modules.memory.recall_document_service import sync_episodic_memory_recall_document

    sync_episodic_memory_recall_document(db, row=row)
    db.flush()
    return row


def _build_promoted_memory_candidate(entries: list[EpisodicMemoryEntry]) -> dict[str, Any]:
    ordered_entries = sorted(entries, key=lambda item: (item.occurred_at, item.updated_at, item.id))
    latest = ordered_entries[-1]
    latest_content = load_json(latest.content_json)
    memory_type = latest_content.get("memory_type") if isinstance(latest_content, dict) else None
    normalized_memory_type = (
        memory_type if isinstance(memory_type, str) and memory_type in VALID_MEMORY_TYPES else "fact"
    )
    source_pairs = [
        {"episodic_entry_id": item.id, "source_kind": item.source_kind, "source_id": item.source_id}
        for item in ordered_entries
    ]
    summary = latest.summary
    if len(ordered_entries) > 1:
        summary = f"{latest.summary}（近{PROMOTION_WINDOW_DAYS}天重复命中 {len(ordered_entries)} 次）"
    return {
        "household_id": latest.household_id,
        "memory_type": normalized_memory_type if normalized_memory_type not in RECENT_EVENT_MEMORY_TYPES else "fact",
        "title": latest.title,
        "summary": summary,
        "content": {
            "promoted_from": "episodic_memory_entries",
            "promotion_key": latest.promotion_key,
            "source_entries": source_pairs,
            "latest_summary": latest.summary,
        },
        "status": "active",
        "visibility": latest.visibility,
        "importance": max(item.importance for item in ordered_entries),
        "confidence": round(sum(item.confidence for item in ordered_entries) / len(ordered_entries), 6),
        "subject_member_id": latest.subject_member_id,
        "source_event_id": latest.source_id if latest.source_kind == "event" else None,
        "source_plugin_id": None,
        "source_raw_record_id": None,
        "dedupe_key": f"promotion:{latest.household_id}:{latest.promotion_key or latest.id}",
        "effective_at": ordered_entries[0].occurred_at,
        "last_observed_at": latest.occurred_at,
        "related_members": latest_content.get("related_members", []) if isinstance(latest_content, dict) else [],
        "reason": "由情节记忆重复命中提升为语义记忆",
    }


def promote_episodic_to_semantic(
    db: Session,
    *,
    household_id: str,
    promotion_key: str | None,
    threshold: int,
) -> MemoryCardRead | None:
    if not promotion_key:
        return None
    occurred_at_gte = (datetime.now(UTC) - timedelta(days=PROMOTION_WINDOW_DAYS)).isoformat().replace("+00:00", "Z")
    entries = list(
        repository.list_episodic_memory_entries_by_promotion_key(
            db,
            household_id=household_id,
            promotion_key=promotion_key,
            statuses=["active"],
            occurred_at_gte=occurred_at_gte,
        )
    )
    if len(entries) < max(threshold, 1):
        return None
    return _upsert_memory_card(
        db,
        candidate=_build_promoted_memory_candidate(entries),
        actor_type="system",
        actor_id=None,
        revision_action="update_observed",
    )


def _upsert_memory_card(
    db: Session,
    *,
    candidate: dict[str, Any],
    actor_type: str,
    actor_id: str | None,
    revision_action: str,
    forbid_existing: bool = False,
) -> MemoryCardRead:
    from app.modules.household.service import get_household_or_404
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
        _refresh_memory_card_projection(db, row=row)
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

    _refresh_memory_card_projection(db, row=existing)
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
    from app.modules.household.service import get_household_or_404
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
        episodic_entry = _upsert_episodic_entry_from_event(
            db,
            event=event,
            candidate=candidate,
        )
        threshold = PROMOTION_THRESHOLD_BY_TYPE.get(candidate["memory_type"], 2)
        promote_episodic_to_semantic(
            db,
            household_id=event.household_id,
            promotion_key=episodic_entry.promotion_key,
            threshold=threshold,
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
    from app.modules.household.service import get_household_or_404
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

    _refresh_memory_card_projection(db, row=row)
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
    from app.modules.household.service import get_household_or_404
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
    from app.modules.household.service import get_household_or_404
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


def upsert_knowledge_document_from_observation(
    db: Session,
    *,
    household_id: str,
    subject_member_id: str | None,
    source_plugin_id: str,
    source_raw_record_id: str,
    observation: dict[str, Any],
) -> KnowledgeDocument:
    normalized_subject_member_id = _normalize_subject_member_id_for_household(
        db,
        household_id=household_id,
        subject_member_id=subject_member_id,
    )
    subject_type = observation.get("subject_type") if isinstance(observation.get("subject_type"), str) else None
    subject_id = observation.get("subject_id") if isinstance(observation.get("subject_id"), str) else None
    category = observation.get("category") if isinstance(observation.get("category"), str) else None
    observed_at = observation.get("observed_at") if isinstance(observation.get("observed_at"), str) else utc_now_iso()
    unit = observation.get("unit") if isinstance(observation.get("unit"), str) else None
    value = observation.get("value")
    if not category or value is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="observation 缺少 category 或 value")

    from app.modules.plugin.models import PluginRawRecord

    raw_record = db.get(PluginRawRecord, source_raw_record_id)
    if raw_record is None or raw_record.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source raw record not found")

    title_subject = subject_id or normalized_subject_member_id or "未指定对象"
    title = f"{title_subject} 的 {category} 外部记录"
    summary_parts = [category, str(value)]
    if unit:
        summary_parts.append(unit)
    summary = " / ".join(summary_parts)
    body_text = " ".join(
        part
        for part in [
            title,
            summary,
            subject_type,
            subject_id,
            source_plugin_id,
            dump_json(load_json(raw_record.payload_json)) or "",
        ]
        if isinstance(part, str) and part.strip()
    )
    return upsert_knowledge_document(
        db,
        household_id=household_id,
        source_kind="plugin_raw_record",
        source_ref=source_raw_record_id,
        title=title,
        summary=summary,
        body_text=body_text,
        visibility="family",
        updated_at=observed_at,
        status="active",
        reason="由插件原始记录导入为 L4 外部知识",
        actor_type="plugin",
        actor_id=source_plugin_id,
    )


def upsert_knowledge_document(
    db: Session,
    *,
    household_id: str,
    source_kind: str,
    source_ref: str,
    title: str,
    summary: str,
    body_text: str,
    visibility: str = "family",
    updated_at: str | None = None,
    status: str = "active",
    reason: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> KnowledgeDocument:
    normalized_source_kind = source_kind.strip() if isinstance(source_kind, str) else ""
    if normalized_source_kind not in VALID_KNOWLEDGE_DOCUMENT_SOURCE_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported knowledge source kind")
    normalized_source_ref = source_ref.strip() if isinstance(source_ref, str) else ""
    if not normalized_source_ref:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="knowledge source ref is required")
    normalized_title = title.strip() if isinstance(title, str) else ""
    normalized_summary = summary.strip() if isinstance(summary, str) else ""
    normalized_body_text = body_text.strip() if isinstance(body_text, str) else ""
    if not normalized_title or not normalized_summary or not normalized_body_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="knowledge document title/summary/body_text is required")
    normalized_visibility = _normalize_memory_visibility(visibility, default="family")
    normalized_status = status.strip() if isinstance(status, str) and status.strip() else "active"
    row = repository.get_knowledge_document_by_source(
        db,
        household_id=household_id,
        source_kind=normalized_source_kind,
        source_ref=normalized_source_ref,
    )
    if row is None:
        row = KnowledgeDocument(
            id=new_uuid(),
            household_id=household_id,
            source_kind=normalized_source_kind,
            source_ref=normalized_source_ref,
            title=normalized_title,
            summary=normalized_summary,
            body_text=normalized_body_text,
            visibility=normalized_visibility,
            updated_at=updated_at or utc_now_iso(),
            status=normalized_status,
        )
        repository.add_knowledge_document(db, row)
        db.flush()
        _record_knowledge_document_revision(
            db,
            document_id=row.id,
            action="create",
            before=None,
            after=_build_knowledge_document_snapshot(row),
            reason=reason or "创建 L4 外部知识",
            actor_type=actor_type,
            actor_id=actor_id,
        )
    else:
        before = _build_knowledge_document_snapshot(row)
        row.title = normalized_title
        row.summary = normalized_summary
        row.body_text = normalized_body_text
        row.visibility = normalized_visibility
        row.updated_at = updated_at or utc_now_iso()
        row.status = normalized_status
        db.add(row)
        db.flush()
        _record_knowledge_document_revision(
            db,
            document_id=row.id,
            action="update",
            before=before,
            after=_build_knowledge_document_snapshot(row),
            reason=reason or "更新 L4 外部知识",
            actor_type=actor_type,
            actor_id=actor_id,
        )
    db.flush()
    from app.modules.memory.recall_document_service import sync_knowledge_document_recall_document

    sync_knowledge_document_recall_document(db, row=row)
    db.flush()
    return row


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
