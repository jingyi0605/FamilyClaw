from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, get_actor_context, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.memory.schemas import (
    MemoryCardCorrectionPayload,
    MemoryContextBundleRead,
    MemoryContextPreviewRequest,
    MemoryHotSummaryRead,
    MemoryQueryRequest,
    MemoryQueryResponse,
    EventRecordCreate,
    EventRecordListResponse,
    EventRecordWriteResponse,
    MemoryCardListResponse,
    MemoryCardManualCreate,
    MemoryCardRead,
    MemoryCardRevisionListResponse,
    MemoryDebugOverviewRead,
)
from app.modules.memory.context_engine import build_memory_context_bundle
from app.modules.memory.query_service import (
    ensure_can_mutate_memory_card,
    get_memory_hot_summary,
    get_visible_memory_card_or_404,
    query_memory_cards,
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
    member_id: str | None = None,
    memory_type: str | None = None,
    status: str | None = None,
    visibility: str | None = None,
    query: str | None = None,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryCardListResponse:
    page, page_size = pagination
    query_result = query_memory_cards(
        db,
        payload=MemoryQueryRequest(
            household_id=household_id,
            requester_member_id=actor.actor_id if actor.role != "admin" else None,
            member_id=member_id,
            memory_type=memory_type,
            status=status,
            visibility=visibility,
            query=query,
            limit=500,
        ),
        actor=actor,
    )
    start = (page - 1) * page_size
    sliced_items = query_result.items[start : start + page_size]
    return MemoryCardListResponse(
        items=[item.card for item in sliced_items],
        page=page,
        page_size=page_size,
        total=query_result.total,
    )


@router.get("/cards/{memory_id}", response_model=MemoryCardRead)
def get_memory_card_detail_endpoint(
    memory_id: str,
    requester_member_id: str | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryCardRead:
    return get_visible_memory_card_or_404(
        db,
        memory_id=memory_id,
        actor=actor,
        requester_member_id=requester_member_id,
    )


@router.post("/cards/manual", response_model=MemoryCardRead)
def create_manual_memory_card_endpoint(
    payload: MemoryCardManualCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryCardRead:
    if actor.role != "admin":
        if actor.actor_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor required")
        if payload.subject_member_id is not None and payload.subject_member_id != actor.actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor cannot create memory for another member")
        if payload.visibility == "sensitive":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor cannot create sensitive memory")
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
    requester_member_id: str | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryCardRevisionListResponse:
    get_visible_memory_card_or_404(
        db,
        memory_id=memory_id,
        actor=actor,
        requester_member_id=requester_member_id,
    )
    return list_memory_card_revisions(db, memory_id=memory_id)


@router.get("/hot-summary", response_model=MemoryHotSummaryRead)
def get_memory_hot_summary_endpoint(
    household_id: str,
    requester_member_id: str | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryHotSummaryRead:
    return get_memory_hot_summary(
        db,
        household_id=household_id,
        actor=actor,
        requester_member_id=requester_member_id,
    )


@router.post("/query", response_model=MemoryQueryResponse)
def query_memory_cards_endpoint(
    payload: MemoryQueryRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryQueryResponse:
    normalized_payload = payload
    if actor.role != "admin":
        normalized_payload = payload.model_copy(update={"requester_member_id": actor.actor_id})
    return query_memory_cards(db, payload=normalized_payload, actor=actor)


@router.post("/context-bundle/preview", response_model=MemoryContextBundleRead)
def preview_memory_context_bundle_endpoint(
    payload: MemoryContextPreviewRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryContextBundleRead:
    normalized_requester_member_id = payload.requester_member_id
    if actor.role != "admin":
        normalized_requester_member_id = actor.actor_id
    return build_memory_context_bundle(
        db,
        household_id=payload.household_id,
        actor=actor,
        requester_member_id=normalized_requester_member_id,
        question=payload.question,
        capability=payload.capability,
    )


@router.post("/cards/{memory_id}/corrections", response_model=MemoryCardRead)
def correct_memory_card_endpoint(
    memory_id: str,
    payload: MemoryCardCorrectionPayload,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
) -> MemoryCardRead:
    ensure_can_mutate_memory_card(
        db,
        memory_id=memory_id,
        actor=actor,
        action=payload.action,
        requester_member_id=actor.actor_id if actor.role != "admin" else None,
    )
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
