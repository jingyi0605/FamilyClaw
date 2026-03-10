from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.context.schemas import ContextConfigRead, ContextConfigUpsert, ContextOverviewRead
from app.modules.context.service import get_context_config, get_context_overview, upsert_context_config
from app.modules.presence.schemas import PresenceEventCreate, PresenceEventWriteResponse
from app.modules.presence.service import ingest_presence_event

router = APIRouter(prefix="/context", tags=["context"])


@router.post("/presence-events", response_model=PresenceEventWriteResponse)
def ingest_presence_event_endpoint(
    payload: PresenceEventCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> PresenceEventWriteResponse:
    event, snapshot, snapshot_updated, cache_refreshed = ingest_presence_event(db, payload)
    write_audit_log(
        db,
        household_id=payload.household_id,
        actor=actor,
        action="presence_event.ingest",
        target_type="presence_event",
        target_id=event.id,
        result="success",
        details={
            **payload.model_dump(mode="json"),
            "snapshot_updated": snapshot_updated,
            "cache_refreshed": cache_refreshed,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    return PresenceEventWriteResponse(
        event_id=event.id,
        accepted=True,
        snapshot_updated=snapshot_updated,
        cache_refreshed=cache_refreshed,
        member_id=snapshot.member_id if snapshot is not None else payload.member_id,
        household_id=payload.household_id,
        status=snapshot.status if snapshot is not None else None,
        current_room_id=snapshot.current_room_id if snapshot is not None else None,
        confidence=(
            int(round(snapshot.confidence * 100))
            if snapshot is not None and snapshot.confidence <= 1
            else int(round(snapshot.confidence))
            if snapshot is not None
            else None
        ),
    )


@router.get("/overview", response_model=ContextOverviewRead)
def get_context_overview_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> ContextOverviewRead:
    return get_context_overview(db, household_id)


@router.get("/configs/{household_id}", response_model=ContextConfigRead)
def get_context_config_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> ContextConfigRead:
    return get_context_config(db, household_id)


@router.put("/configs/{household_id}", response_model=ContextConfigRead)
def upsert_context_config_endpoint(
    household_id: str,
    payload: ContextConfigUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ContextConfigRead:
    context_config = upsert_context_config(
        db,
        household_id=household_id,
        payload=payload,
        actor=actor,
    )
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="context_config.upsert",
        target_type="context_config",
        target_id=household_id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    return context_config
