from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid
from app.modules.context.cache_service import ContextCacheUnavailableError, refresh_household_context_cache
from app.modules.context.service import get_context_overview
from app.modules.household.service import get_household_or_404
from app.modules.memory.schemas import EventRecordCreate
from app.modules.memory.service import ingest_event_record_best_effort
from app.modules.member.models import Member
from app.modules.presence.models import MemberPresenceState, PresenceEvent
from app.modules.presence.schemas import PresenceEventCreate
from app.modules.room.models import Room

HOME_EVENT_KEYWORDS = {
    "home",
    "arrive",
    "arrived",
    "enter",
    "entered",
    "unlock",
    "detected",
    "seen",
    "present",
    "active",
}
AWAY_EVENT_KEYWORDS = {
    "away",
    "leave",
    "left",
    "exit",
    "depart",
    "departed",
    "locked",
    "offline",
    "absent",
}


def _parse_occurred_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="occurred_at must be a valid ISO8601 datetime",
        ) from exc


def _get_member_in_household_or_404(db: Session, member_id: str, household_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member must belong to the same household",
        )
    return member


def _get_room_in_household_or_404(db: Session, room_id: str, household_id: str) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="room not found",
        )
    if room.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room must belong to the same household",
        )
    return room


def _extract_keyword(payload: Any, *keys: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _infer_presence_status(payload: Any, source_type: str, member_id: str | None) -> str:
    explicit_status = _extract_keyword(payload, "presence_status", "status")
    if explicit_status in {"home", "away", "unknown"}:
        return explicit_status

    event_keyword = _extract_keyword(payload, "event", "action", "state", "result")
    if event_keyword in HOME_EVENT_KEYWORDS:
        return "home"
    if event_keyword in AWAY_EVENT_KEYWORDS:
        return "away"

    if source_type == "voice" and member_id is not None:
        return "home"
    if source_type in {"camera", "bluetooth", "sensor"} and member_id is not None:
        return "home"

    return "unknown"


def _parse_snapshot_updated_at(snapshot: MemberPresenceState) -> datetime | None:
    try:
        return datetime.fromisoformat(snapshot.updated_at.replace("Z", "+00:00")).astimezone(
            timezone.utc,
        )
    except ValueError:
        return None


def _should_replace_snapshot(
    current_snapshot: MemberPresenceState,
    *,
    next_status: str,
    next_confidence: float,
    occurred_at: datetime,
) -> bool:
    current_updated_at = _parse_snapshot_updated_at(current_snapshot)
    if current_updated_at is None:
        return True

    if next_status == current_snapshot.status:
        return occurred_at >= current_updated_at or next_confidence >= current_snapshot.confidence

    if current_snapshot.status == "unknown":
        return occurred_at >= current_updated_at or next_confidence >= current_snapshot.confidence

    if next_status == "unknown":
        return occurred_at >= current_updated_at and next_confidence >= current_snapshot.confidence

    if occurred_at >= current_updated_at:
        return True

    current_age_minutes = max(0, int((datetime.now(timezone.utc) - current_updated_at).total_seconds() // 60))
    confidence_gap = next_confidence - current_snapshot.confidence
    return current_age_minutes >= 30 and confidence_gap >= 0.15


def _build_source_summary(
    payload: Any,
    *,
    status: str,
    source_type: str,
    source_ref: str,
    confidence: float,
    occurred_at: str,
) -> str:
    return dump_json(
        {
            "status": status,
            "source_type": source_type,
            "source_ref": source_ref,
            "confidence": confidence,
            "occurred_at": occurred_at,
            "payload": payload,
        }
    ) or "{}"


def _refresh_context_cache_best_effort(db: Session, household_id: str) -> bool:
    try:
        overview = get_context_overview(db, household_id)
        return refresh_household_context_cache(household_id, overview.model_dump(mode="json"))
    except ContextCacheUnavailableError:
        return False


def ingest_presence_event(
    db: Session,
    payload: PresenceEventCreate,
) -> tuple[PresenceEvent, MemberPresenceState | None, bool, bool]:
    get_household_or_404(db, payload.household_id)
    member = (
        _get_member_in_household_or_404(db, payload.member_id, payload.household_id)
        if payload.member_id is not None
        else None
    )
    if payload.room_id is not None:
        _get_room_in_household_or_404(db, payload.room_id, payload.household_id)

    occurred_at = _parse_occurred_at(payload.occurred_at)
    normalized_payload = jsonable_encoder(payload.payload)
    event = PresenceEvent(
        id=new_uuid(),
        household_id=payload.household_id,
        member_id=payload.member_id,
        room_id=payload.room_id,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        confidence=payload.confidence,
        payload=dump_json(normalized_payload),
        occurred_at=occurred_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    db.add(event)
    db.flush()

    snapshot_updated = False
    snapshot: MemberPresenceState | None = None
    if member is not None:
        next_status = _infer_presence_status(normalized_payload, payload.source_type, member.id)
        current_snapshot = db.get(MemberPresenceState, member.id)
        summary = _build_source_summary(
            normalized_payload,
            status=next_status,
            source_type=payload.source_type,
            source_ref=payload.source_ref,
            confidence=payload.confidence,
            occurred_at=event.occurred_at,
        )
        next_room_id = payload.room_id if next_status == "home" else None

        if current_snapshot is None:
            snapshot = MemberPresenceState(
                member_id=member.id,
                household_id=payload.household_id,
                status=next_status,
                current_room_id=next_room_id,
                confidence=payload.confidence,
                source_summary=summary,
                updated_at=event.occurred_at,
            )
            db.add(snapshot)
            snapshot_updated = True
        else:
            if _should_replace_snapshot(
                current_snapshot,
                next_status=next_status,
                next_confidence=payload.confidence,
                occurred_at=occurred_at,
            ):
                current_snapshot.status = next_status
                current_snapshot.current_room_id = (
                    next_room_id or current_snapshot.current_room_id
                    if next_status == "home"
                    else None
                )
                current_snapshot.confidence = payload.confidence
                current_snapshot.source_summary = summary
                current_snapshot.updated_at = event.occurred_at
                db.add(current_snapshot)
                snapshot_updated = True
            elif (
                current_snapshot.status == next_status
                and next_status == "home"
                and current_snapshot.current_room_id is None
                and payload.room_id is not None
            ):
                current_snapshot.current_room_id = payload.room_id
                current_snapshot.source_summary = summary
                current_snapshot.updated_at = event.occurred_at
                db.add(current_snapshot)
                snapshot_updated = True
            snapshot = current_snapshot

        db.flush()

    cache_refreshed = _refresh_context_cache_best_effort(db, payload.household_id)
    if member is not None and snapshot is not None and snapshot_updated:
        room_name = None
        if snapshot.current_room_id is not None:
            room = db.get(Room, snapshot.current_room_id)
            room_name = room.name if room is not None else None
        summary_text = f"{member.name} 当前状态变为 {snapshot.status}"
        if room_name:
            summary_text += f"，位置是 {room_name}"
        ingest_event_record_best_effort(
            db,
            EventRecordCreate(
                household_id=payload.household_id,
                event_type="presence_changed",
                source_type="presence",
                source_ref=event.id,
                subject_member_id=member.id,
                room_id=snapshot.current_room_id,
                payload={
                    "memory_type": "event",
                    "title": f"{member.name} 在家状态变化",
                    "summary": summary_text,
                    "visibility": "family",
                    "importance": 3,
                    "confidence": max(0.5, min(1.0, payload.confidence)),
                    "content": {
                        "status": snapshot.status,
                        "room_name": room_name,
                        "source_type": payload.source_type,
                    },
                    "card_dedupe_key": f"presence:{member.id}:{snapshot.status}",
                },
                dedupe_key=f"presence-event:{event.id}",
                generate_memory_card=snapshot.status in {"home", "away"},
                occurred_at=event.occurred_at,
            ),
        )
    return event, snapshot, snapshot_updated, cache_refreshed
