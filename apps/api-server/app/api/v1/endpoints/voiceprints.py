import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    ActorContext,
    ensure_actor_can_access_household,
    pagination_params,
    require_admin_actor,
    require_bound_member_actor,
)
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.voice.binding_refresh_service import refresh_voice_terminal_binding_state
from app.modules.voiceprint.models import VoiceprintEnrollment
from app.modules.voiceprint.prompt_service import (
    VoiceprintPromptEnrollmentSnapshot,
    send_voiceprint_round_prompt,
)
from app.modules.voiceprint.schemas import (
    HouseholdVoiceprintSummaryRead,
    MemberVoiceprintDeleteResponse,
    MemberVoiceprintDetailRead,
    VoiceprintEnrollmentCreate,
    VoiceprintEnrollmentListResponse,
    VoiceprintEnrollmentRead,
)
from app.modules.voiceprint.service import (
    cancel_voiceprint_enrollment,
    create_voiceprint_enrollment,
    delete_member_voiceprints,
    expire_stale_voiceprint_enrollments,
    get_household_voiceprint_summary,
    get_member_voiceprint_detail,
    get_voiceprint_enrollment_or_404,
    list_voiceprint_enrollments,
)

router = APIRouter(prefix="/voiceprints", tags=["voiceprints"])
logger = logging.getLogger(__name__)


async def notify_voice_terminal_binding_refresh_best_effort(*, terminal_id: str, reason: str) -> None:
    if not terminal_id.strip():
        return
    try:
        refreshed = await refresh_voice_terminal_binding_state(
            terminal_id=terminal_id,
            reason=reason,
        )
        if refreshed:
            return
        logger.warning(
            "binding refresh was not delivered terminal_id=%s reason=%s",
            terminal_id,
            reason,
        )
    except Exception:
        logger.warning(
            "voice terminal binding refresh failed terminal_id=%s reason=%s",
            terminal_id,
            reason,
            exc_info=True,
        )        
async def notify_voiceprint_round_prompt_best_effort(
    *,
    enrollment: VoiceprintEnrollment | VoiceprintPromptEnrollmentSnapshot,
    prompt_key: str,
    retry: bool = False,
) -> None:
    try:
        prompted = await send_voiceprint_round_prompt(
            enrollment,
            prompt_key=prompt_key,
            retry=retry,
        )
        if prompted:
            return
        logger.warning(
            "voiceprint round prompt was not delivered enrollment_id=%s terminal_id=%s prompt_key=%s",
            enrollment.id,
            enrollment.terminal_id,
            prompt_key,
        )
    except Exception:
        logger.warning(
            "voiceprint round prompt failed enrollment_id=%s terminal_id=%s prompt_key=%s",
            enrollment.id,
            enrollment.terminal_id,
            prompt_key,
            exc_info=True,
        )


@router.post("/enrollments", response_model=VoiceprintEnrollmentRead, status_code=status.HTTP_201_CREATED)
def create_voiceprint_enrollment_endpoint(
    payload: VoiceprintEnrollmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> VoiceprintEnrollmentRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    enrollment = create_voiceprint_enrollment(db, payload)
    db.flush()
    write_audit_log(
        db,
        household_id=payload.household_id,
        actor=actor,
        action="voiceprint.enrollment.create",
        target_type="voiceprint_enrollment",
        target_id=enrollment.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(enrollment)
    enrollment_snapshot = VoiceprintPromptEnrollmentSnapshot.from_enrollment(enrollment)
    background_tasks.add_task(
        notify_voice_terminal_binding_refresh_best_effort,
        terminal_id=enrollment.terminal_id,
        reason="voiceprint_enrollment_created",
    )
    background_tasks.add_task(
        notify_voiceprint_round_prompt_best_effort,
        enrollment=enrollment_snapshot,
        prompt_key="created",
    )
    return VoiceprintEnrollmentRead.model_validate(enrollment)


@router.get("/enrollments", response_model=VoiceprintEnrollmentListResponse)
def list_voiceprint_enrollments_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    member_id: str | None = None,
    terminal_id: str | None = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> VoiceprintEnrollmentListResponse:
    ensure_actor_can_access_household(actor, household_id)
    expired_count = expire_stale_voiceprint_enrollments(
        db,
        household_id=household_id,
        terminal_id=terminal_id,
        member_id=member_id,
    )
    if expired_count > 0:
        db.commit()
    page, page_size = pagination
    items, total = list_voiceprint_enrollments(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        member_id=member_id,
        terminal_id=terminal_id,
        status_value=status_value,
    )
    return VoiceprintEnrollmentListResponse(
        items=[VoiceprintEnrollmentRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/enrollments/{enrollment_id}", response_model=VoiceprintEnrollmentRead)
def get_voiceprint_enrollment_endpoint(
    enrollment_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> VoiceprintEnrollmentRead:
    expired_count = expire_stale_voiceprint_enrollments(db, enrollment_id=enrollment_id)
    if expired_count > 0:
        db.commit()
    enrollment = get_voiceprint_enrollment_or_404(db, enrollment_id)
    ensure_actor_can_access_household(actor, enrollment.household_id)
    return VoiceprintEnrollmentRead.model_validate(enrollment)


@router.post("/enrollments/{enrollment_id}/cancel", response_model=VoiceprintEnrollmentRead)
def cancel_voiceprint_enrollment_endpoint(
    enrollment_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> VoiceprintEnrollmentRead:
    enrollment = get_voiceprint_enrollment_or_404(db, enrollment_id)
    ensure_actor_can_access_household(actor, enrollment.household_id)
    enrollment = cancel_voiceprint_enrollment(db, enrollment)
    write_audit_log(
        db,
        household_id=enrollment.household_id,
        actor=actor,
        action="voiceprint.enrollment.cancel",
        target_type="voiceprint_enrollment",
        target_id=enrollment.id,
        result="success",
        details={"member_id": enrollment.member_id, "terminal_id": enrollment.terminal_id},
    )
    db.commit()
    background_tasks.add_task(
        notify_voice_terminal_binding_refresh_best_effort,
        terminal_id=enrollment.terminal_id,
        reason="voiceprint_enrollment_cancelled",
    )
    db.refresh(enrollment)
    return VoiceprintEnrollmentRead.model_validate(enrollment)


@router.get("/members/{member_id}", response_model=MemberVoiceprintDetailRead)
def get_member_voiceprint_endpoint(
    member_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberVoiceprintDetailRead:
    expired_count = expire_stale_voiceprint_enrollments(db, member_id=member_id)
    if expired_count > 0:
        db.commit()
    detail = get_member_voiceprint_detail(db, member_id=member_id)
    ensure_actor_can_access_household(actor, detail.household_id)
    return detail


@router.get("/households/{household_id}/summary", response_model=HouseholdVoiceprintSummaryRead)
def get_household_voiceprint_summary_endpoint(
    household_id: str,
    terminal_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> HouseholdVoiceprintSummaryRead:
    ensure_actor_can_access_household(actor, household_id)
    expired_count = expire_stale_voiceprint_enrollments(
        db,
        household_id=household_id,
        terminal_id=terminal_id,
    )
    if expired_count > 0:
        db.commit()
    return get_household_voiceprint_summary(db, household_id=household_id, terminal_id=terminal_id)


@router.delete("/members/{member_id}", response_model=MemberVoiceprintDeleteResponse)
def delete_member_voiceprint_endpoint(
    member_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberVoiceprintDeleteResponse:
    result = delete_member_voiceprints(db, member_id=member_id)
    ensure_actor_can_access_household(actor, result.household_id)
    write_audit_log(
        db,
        household_id=result.household_id,
        actor=actor,
        action="voiceprint.member.delete",
        target_type="member_voiceprint",
        target_id=result.member_id,
        result="success",
        details={
            "deleted_profile_count": result.deleted_profile_count,
            "cancelled_enrollment_count": result.cancelled_enrollment_count,
        },
    )
    db.commit()
    return result
