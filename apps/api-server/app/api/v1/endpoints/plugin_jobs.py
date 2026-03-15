from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_bound_member_actor
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.plugin import PluginJobNotFoundError, PluginJobStateError, get_plugin_job_detail, list_plugin_jobs_page, record_plugin_job_response
from app.modules.plugin.job_notifier import publish_plugin_job_updates
from app.modules.plugin.schemas import PluginExecutionRequest, PluginJobDetailRead, PluginJobEnqueueRequest, PluginJobListRead, PluginJobResponseCreate, PluginJobStatus
from app.modules.plugin.service import PluginExecutionError, enqueue_household_plugin_job

router = APIRouter(prefix="/plugin-jobs", tags=["plugin-jobs"])


@router.post("", response_model=PluginJobDetailRead, status_code=status.HTTP_201_CREATED)
async def create_plugin_job_endpoint(
    payload: PluginJobEnqueueRequest,
    household_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> PluginJobDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        job = enqueue_household_plugin_job(
            db,
            household_id=household_id,
            request=PluginExecutionRequest(
                plugin_id=payload.plugin_id,
                plugin_type=payload.plugin_type,
                payload=payload.payload,
                trigger=payload.trigger,
            ),
            idempotency_key=payload.idempotency_key,
            payload_summary=payload.payload_summary,
            max_attempts=payload.max_attempts,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="plugin.job.create",
            target_type="plugin_job",
            target_id=job.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        await publish_plugin_job_updates(db, household_id=household_id, job_id=job.id)
        return get_plugin_job_detail(db, household_id=household_id, job_id=job.id)
    except PluginExecutionError as exc:
        db.rollback()
        detail = exc.to_detail() if hasattr(exc, "to_detail") else str(exc)
        status_code = exc.status_code if hasattr(exc, "status_code") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{job_id}", response_model=PluginJobDetailRead)
def get_plugin_job_detail_endpoint(
    job_id: str,
    household_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> PluginJobDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return get_plugin_job_detail(db, household_id=household_id, job_id=job_id)
    except PluginJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=PluginJobListRead)
def list_plugin_jobs_endpoint(
    household_id: str = Query(min_length=1),
    status_value: PluginJobStatus | None = Query(default=None, alias="status"),
    plugin_id: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> PluginJobListRead:
    ensure_actor_can_access_household(actor, household_id)
    return list_plugin_jobs_page(
        db,
        household_id=household_id,
        status=status_value,
        plugin_id=plugin_id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )


@router.post("/{job_id}/responses", response_model=PluginJobDetailRead)
async def respond_plugin_job_endpoint(
    job_id: str,
    household_id: str = Query(min_length=1),
    payload: PluginJobResponseCreate | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> PluginJobDetailRead:
    ensure_actor_can_access_household(actor, household_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="响应体不能为空")
    try:
        _, job = record_plugin_job_response(db, job_id=job_id, payload=payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="plugin.job.respond",
            target_type="plugin_job",
            target_id=job_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        await publish_plugin_job_updates(db, household_id=household_id, job_id=job.id)
        return get_plugin_job_detail(db, household_id=household_id, job_id=job.id)
    except PluginJobNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PluginJobStateError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": str(exc),
                "error_code": "job_invalid_response_action",
                "field": "action",
            },
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
