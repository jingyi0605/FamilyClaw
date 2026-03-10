from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.memory.schemas import (
    MemoryCardCorrectionPayload,
    EventRecordCreate,
    EventRecordListResponse,
    EventRecordWriteResponse,
    MemoryCardListResponse,
    MemoryCardManualCreate,
    MemoryCardRead,
    MemoryCardRevisionListResponse,
    MemoryDebugOverviewRead,
)
from app.modules.memory.service import (
    correct_memory_card,
    create_manual_memory_card,
    get_memory_debug_overview,
    ingest_event_record,
    list_memory_card_revisions,
    list_event_records,
    list_memory_cards,
)

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/overview", response_model=MemoryDebugOverviewRead)
def get_memory_debug_overview_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> MemoryDebugOverviewRead:
    return get_memory_debug_overview(db, household_id=household_id)


@router.get("/events", response_model=EventRecordListResponse)
def list_event_records_endpoint(
    household_id: str,
    processing_status: str | None = None,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> EventRecordListResponse:
    page, page_size = pagination
    items, total = list_event_records(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        processing_status=processing_status,
    )
    return EventRecordListResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("/events", response_model=EventRecordWriteResponse)
def ingest_event_record_endpoint(
    payload: EventRecordCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> EventRecordWriteResponse:
    event, duplicate_detected = ingest_event_record(db, payload)
    write_audit_log(
        db,
        household_id=payload.household_id,
        actor=actor,
        action="memory_event.ingest",
        target_type="event_record",
        target_id=event.id,
        result="success",
        details={
            **payload.model_dump(mode="json"),
            "duplicate_detected": duplicate_detected,
            "processing_status": event.processing_status,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    return EventRecordWriteResponse(
        event_id=event.id,
        accepted=True,
        duplicate_detected=duplicate_detected,
        processing_status=event.processing_status,
    )


@router.get("/cards", response_model=MemoryCardListResponse)
def list_memory_cards_endpoint(
    household_id: str,
    memory_type: str | None = None,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> MemoryCardListResponse:
    page, page_size = pagination
    items, total = list_memory_cards(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        memory_type=memory_type,
    )
    return MemoryCardListResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("/cards/manual", response_model=MemoryCardRead)
def create_manual_memory_card_endpoint(
    payload: MemoryCardManualCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemoryCardRead:
    card = create_manual_memory_card(db, payload=payload, actor=actor)
    write_audit_log(
        db,
        household_id=payload.household_id,
        actor=actor,
        action="memory_card.create_manual",
        target_type="memory_card",
        target_id=card.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return card


@router.get("/cards/{memory_id}/revisions", response_model=MemoryCardRevisionListResponse)
def list_memory_card_revisions_endpoint(
    memory_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> MemoryCardRevisionListResponse:
    return list_memory_card_revisions(db, memory_id=memory_id)


@router.post("/cards/{memory_id}/corrections", response_model=MemoryCardRead)
def correct_memory_card_endpoint(
    memory_id: str,
    payload: MemoryCardCorrectionPayload,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemoryCardRead:
    card = correct_memory_card(
        db,
        memory_id=memory_id,
        payload=payload,
        actor=actor,
    )
    write_audit_log(
        db,
        household_id=card.household_id,
        actor=actor,
        action="memory_card.correct",
        target_type="memory_card",
        target_id=card.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return card
