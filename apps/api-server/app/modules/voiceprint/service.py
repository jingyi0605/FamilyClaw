from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device
from app.modules.member.models import Member
from app.modules.voiceprint.provider import (
    VoiceprintEmbedding,
    VoiceprintProfileCandidate,
    VoiceprintProvider,
    VoiceprintProviderError,
    get_default_voiceprint_provider,
)
from app.modules.voiceprint.models import MemberVoiceprintProfile, MemberVoiceprintSample, VoiceprintEnrollment
from app.modules.voiceprint.prompt_types import VoiceprintPromptEnrollmentSnapshot
from app.modules.voiceprint.schemas import (
    HouseholdVoiceprintMemberSummaryRead,
    HouseholdVoiceprintSummaryRead,
    MemberVoiceprintDeleteResponse,
    MemberVoiceprintDetailRead,
    MemberVoiceprintProfileRead,
    MemberVoiceprintSampleRead,
    PendingVoiceprintEnrollmentRead,
    VoiceprintEnrollmentCreate,
    VoiceprintEnrollmentRead,
)

_PENDING_ENROLLMENT_STATUSES = ("pending", "recording", "processing")
_ENROLLMENT_EXPIRE_MINUTES = 30
_ENROLLMENT_SAMPLE_MIN_DURATION_MS = 1000
_ENROLLMENT_SAMPLE_MAX_DURATION_MS = 8000
_DEFAULT_ENROLLMENT_SAMPLE_GOAL = 6
_DEFAULT_ENROLLMENT_BASE_REPEAT = 4
_VOICEPRINT_IDENTIFICATION_LIMIT = 3
_VOICEPRINT_CONFLICT_SCORE_MARGIN = 0.05
_VOICEPRINT_ENROLLMENT_EXPIRED_MESSAGE = "这次声纹录入任务已过期，请重新开始。"
_DEFAULT_ENROLLMENT_PHRASES = (
    "春眠不觉晓",
    "明月松间照",
    "海内存知己",
    "清风徐徐来",
    "山高水更长",
    "此心安处是吾乡",
)


@dataclass(slots=True)
class VoiceprintEnrollmentProcessResult:
    outcome: str
    enrollment: VoiceprintEnrollment
    prompt_enrollment: VoiceprintPromptEnrollmentSnapshot | None = None
    sample: MemberVoiceprintSample | None = None
    profile: MemberVoiceprintProfile | None = None
    sample_id: str | None = None
    profile_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class HouseholdVoiceprintSearchRead:
    provider: str
    status: str
    threshold: float
    profile_id: str | None
    member_id: str | None
    score: float | None
    candidate_count: int


@dataclass(slots=True)
class MemberVoiceprintVerifyRead:
    provider: str
    status: str
    threshold: float
    member_id: str
    profile_id: str | None
    matched: bool
    score: float | None


@dataclass(slots=True)
class VoiceprintIdentificationCandidateRead:
    member_id: str
    profile_id: str
    score: float


@dataclass(slots=True)
class VoiceprintIdentificationRead:
    provider: str
    status: str
    threshold: float
    reason: str
    profile_id: str | None = None
    member_id: str | None = None
    score: float | None = None
    candidate_count: int = 0
    candidates: list[VoiceprintIdentificationCandidateRead] = field(default_factory=list)


def _is_enrollment_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline.astimezone(timezone.utc) <= datetime.now(timezone.utc)


def _expire_enrollment_if_needed(db: Session, enrollment: VoiceprintEnrollment) -> bool:
    if enrollment.status not in _PENDING_ENROLLMENT_STATUSES:
        return False
    if not _is_enrollment_expired(enrollment.expires_at):
        return False
    enrollment.status = "cancelled"
    enrollment.error_code = "voiceprint_enrollment_expired"
    enrollment.error_message = _VOICEPRINT_ENROLLMENT_EXPIRED_MESSAGE
    enrollment.updated_at = utc_now_iso()
    db.add(enrollment)
    return True


def expire_stale_voiceprint_enrollments(
    db: Session,
    *,
    household_id: str | None = None,
    terminal_id: str | None = None,
    member_id: str | None = None,
    enrollment_id: str | None = None,
) -> int:
    filters = [VoiceprintEnrollment.status.in_(_PENDING_ENROLLMENT_STATUSES)]
    if household_id:
        filters.append(VoiceprintEnrollment.household_id == household_id)
    if terminal_id:
        filters.append(VoiceprintEnrollment.terminal_id == terminal_id)
    if member_id:
        filters.append(VoiceprintEnrollment.member_id == member_id)
    if enrollment_id:
        filters.append(VoiceprintEnrollment.id == enrollment_id)
    enrollments = list(db.scalars(select(VoiceprintEnrollment).where(*filters)).all())
    expired_count = 0
    for enrollment in enrollments:
        if _expire_enrollment_if_needed(db, enrollment):
            expired_count += 1
    return expired_count


def create_voiceprint_enrollment(db: Session, payload: VoiceprintEnrollmentCreate) -> VoiceprintEnrollment:
    member = _get_member_or_404(db, payload.member_id)
    terminal = _get_terminal_or_404(db, payload.terminal_id)
    if member.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="member must belong to the same household")
    if terminal.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="terminal must belong to the same household")
    expired_count = expire_stale_voiceprint_enrollments(
        db,
        household_id=payload.household_id,
        terminal_id=payload.terminal_id,
    )
    if expired_count > 0:
        db.flush()

    conflict = db.scalar(
        select(VoiceprintEnrollment).where(
            VoiceprintEnrollment.household_id == payload.household_id,
            VoiceprintEnrollment.terminal_id == payload.terminal_id,
            VoiceprintEnrollment.status.in_(_PENDING_ENROLLMENT_STATUSES),
        )
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="voiceprint enrollment conflict",
        )

    enrollment = VoiceprintEnrollment(
        id=new_uuid(),
        household_id=payload.household_id,
        member_id=payload.member_id,
        terminal_id=payload.terminal_id,
        status="pending",
        base_phrase=_resolve_base_phrase(
            expected_phrase=payload.expected_phrase,
            member_id=payload.member_id,
            terminal_id=payload.terminal_id,
        ),
        expected_phrase=None,
        sample_goal=payload.sample_goal,
        sample_count=0,
        expires_at=_build_enrollment_expires_at(),
    )
    _sync_enrollment_phrase_state(enrollment)
    db.add(enrollment)
    return enrollment


def list_voiceprint_enrollments(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    member_id: str | None = None,
    terminal_id: str | None = None,
    status_value: str | None = None,
) -> tuple[list[VoiceprintEnrollment], int]:
    filters = [VoiceprintEnrollment.household_id == household_id]
    if member_id:
        filters.append(VoiceprintEnrollment.member_id == member_id)
    if terminal_id:
        filters.append(VoiceprintEnrollment.terminal_id == terminal_id)
    if status_value:
        filters.append(VoiceprintEnrollment.status == status_value)

    total = db.scalar(select(func.count()).select_from(VoiceprintEnrollment).where(*filters)) or 0
    statement = (
        select(VoiceprintEnrollment)
        .where(*filters)
        .order_by(VoiceprintEnrollment.created_at.desc(), VoiceprintEnrollment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), total


def get_voiceprint_enrollment_or_404(db: Session, enrollment_id: str) -> VoiceprintEnrollment:
    enrollment = db.get(VoiceprintEnrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voiceprint enrollment not found")
    _sync_enrollment_phrase_state(enrollment)
    return enrollment


def cancel_voiceprint_enrollment(db: Session, enrollment: VoiceprintEnrollment) -> VoiceprintEnrollment:
    if enrollment.status in {"completed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="voiceprint enrollment cannot be cancelled",
    )
    enrollment.status = "cancelled"
    _sync_enrollment_phrase_state(enrollment)
    enrollment.updated_at = utc_now_iso()
    db.add(enrollment)
    return enrollment


def mark_voiceprint_enrollment_failed(
    db: Session,
    *,
    enrollment_id: str,
    error_code: str,
    error_message: str,
) -> VoiceprintEnrollment | None:
    enrollment = db.get(VoiceprintEnrollment, enrollment_id)
    if enrollment is None:
        return None
    if enrollment.status in {"completed", "cancelled"}:
        return enrollment
    enrollment.status = "failed"
    _sync_enrollment_phrase_state(enrollment)
    enrollment.error_code = error_code
    enrollment.error_message = error_message
    enrollment.updated_at = utc_now_iso()
    db.add(enrollment)
    return enrollment


def get_pending_voiceprint_enrollment_by_terminal(
    db: Session,
    *,
    household_id: str,
    terminal_id: str,
) -> PendingVoiceprintEnrollmentRead | None:
    statement = (
        select(VoiceprintEnrollment)
        .where(
            VoiceprintEnrollment.household_id == household_id,
            VoiceprintEnrollment.terminal_id == terminal_id,
            VoiceprintEnrollment.status.in_(_PENDING_ENROLLMENT_STATUSES),
        )
        .order_by(VoiceprintEnrollment.created_at.asc())
        .limit(1)
    )
    enrollment = db.scalar(statement)
    if enrollment is None:
        return None
    _sync_enrollment_phrase_state(enrollment)
    return PendingVoiceprintEnrollmentRead(
        enrollment_id=enrollment.id,
        target_member_id=enrollment.member_id,
        expected_phrase=enrollment.expected_phrase,
        sample_goal=enrollment.sample_goal,
        sample_count=enrollment.sample_count,
        expires_at=enrollment.expires_at,
    )


def get_member_voiceprint_detail(db: Session, *, member_id: str) -> MemberVoiceprintDetailRead:
    member = _get_member_or_404(db, member_id)
    active_profile = db.scalar(
        select(MemberVoiceprintProfile)
        .where(
            MemberVoiceprintProfile.household_id == member.household_id,
            MemberVoiceprintProfile.member_id == member.id,
            MemberVoiceprintProfile.status == "active",
        )
        .order_by(MemberVoiceprintProfile.version.desc(), MemberVoiceprintProfile.updated_at.desc())
        .limit(1)
    )
    samples = list(
        db.scalars(
            select(MemberVoiceprintSample)
            .where(
                MemberVoiceprintSample.household_id == member.household_id,
                MemberVoiceprintSample.member_id == member.id,
            )
            .order_by(MemberVoiceprintSample.created_at.desc(), MemberVoiceprintSample.id.desc())
        ).all()
    )
    pending_enrollments = list(
        db.scalars(
            select(VoiceprintEnrollment)
            .where(
                VoiceprintEnrollment.household_id == member.household_id,
                VoiceprintEnrollment.member_id == member.id,
                VoiceprintEnrollment.status.in_(_PENDING_ENROLLMENT_STATUSES),
            )
            .order_by(VoiceprintEnrollment.created_at.asc(), VoiceprintEnrollment.id.asc())
        ).all()
    )
    return MemberVoiceprintDetailRead(
        member_id=member.id,
        household_id=member.household_id,
        active_profile=(
            MemberVoiceprintProfileRead.model_validate(active_profile) if active_profile is not None else None
        ),
        samples=[MemberVoiceprintSampleRead.model_validate(sample) for sample in samples],
        pending_enrollments=[VoiceprintEnrollmentRead.model_validate(item) for item in pending_enrollments],
        recent_identification_status=None,
    )


def get_household_voiceprint_summary(
    db: Session,
    *,
    household_id: str,
    terminal_id: str,
) -> HouseholdVoiceprintSummaryRead:
    terminal = _get_terminal_or_404(db, terminal_id)
    if terminal.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="terminal must belong to the same household")

    members = list(
        db.scalars(
            select(Member)
            .where(Member.household_id == household_id)
            .order_by(Member.created_at.asc(), Member.id.asc())
        ).all()
    )
    member_ids = [member.id for member in members]
    if not member_ids:
        return HouseholdVoiceprintSummaryRead(
            household_id=household_id,
            terminal_id=terminal_id,
            voiceprint_identity_enabled=bool(terminal.voiceprint_identity_enabled),
            conversation_mode=("voiceprint_member" if terminal.voiceprint_identity_enabled else "public"),
            pending_enrollment=get_pending_voiceprint_enrollment_by_terminal(
                db,
                household_id=household_id,
                terminal_id=terminal_id,
            ),
            members=[],
        )

    profiles = list(
        db.scalars(
            select(MemberVoiceprintProfile)
            .where(
                MemberVoiceprintProfile.household_id == household_id,
                MemberVoiceprintProfile.member_id.in_(member_ids),
            )
            .order_by(MemberVoiceprintProfile.updated_at.desc(), MemberVoiceprintProfile.id.desc())
        ).all()
    )
    enrollments = list(
        db.scalars(
            select(VoiceprintEnrollment)
            .where(
                VoiceprintEnrollment.household_id == household_id,
                VoiceprintEnrollment.member_id.in_(member_ids),
            )
            .order_by(VoiceprintEnrollment.updated_at.desc(), VoiceprintEnrollment.id.desc())
        ).all()
    )

    latest_profile_by_member: dict[str, MemberVoiceprintProfile] = {}
    active_profile_by_member: dict[str, MemberVoiceprintProfile] = {}
    for profile in profiles:
        latest_profile_by_member.setdefault(profile.member_id, profile)
        if profile.status == "active":
            active_profile_by_member.setdefault(profile.member_id, profile)

    latest_enrollment_by_member: dict[str, VoiceprintEnrollment] = {}
    pending_enrollment_by_member: dict[str, VoiceprintEnrollment] = {}
    for enrollment in enrollments:
        latest_enrollment_by_member.setdefault(enrollment.member_id, enrollment)
        if enrollment.status in _PENDING_ENROLLMENT_STATUSES:
            pending_enrollment_by_member.setdefault(enrollment.member_id, enrollment)

    member_summaries = [
        _build_household_member_summary(
            member=member,
            active_profile=active_profile_by_member.get(member.id),
            latest_profile=latest_profile_by_member.get(member.id),
            pending_enrollment=pending_enrollment_by_member.get(member.id),
            latest_enrollment=latest_enrollment_by_member.get(member.id),
        )
        for member in members
    ]

    return HouseholdVoiceprintSummaryRead(
        household_id=household_id,
        terminal_id=terminal_id,
        voiceprint_identity_enabled=bool(terminal.voiceprint_identity_enabled),
        conversation_mode=("voiceprint_member" if terminal.voiceprint_identity_enabled else "public"),
        pending_enrollment=get_pending_voiceprint_enrollment_by_terminal(
            db,
            household_id=household_id,
            terminal_id=terminal_id,
        ),
        members=member_summaries,
    )


def _build_household_member_summary(
    *,
    member: Member,
    active_profile: MemberVoiceprintProfile | None,
    latest_profile: MemberVoiceprintProfile | None,
    pending_enrollment: VoiceprintEnrollment | None,
    latest_enrollment: VoiceprintEnrollment | None,
) -> HouseholdVoiceprintMemberSummaryRead:
    if pending_enrollment is not None:
        return HouseholdVoiceprintMemberSummaryRead(
            member_id=member.id,
            member_name=member.name,
            member_role=member.role,
            status="pending",
            sample_count=pending_enrollment.sample_count,
            updated_at=pending_enrollment.updated_at,
            pending_enrollment_id=pending_enrollment.id,
            active_profile_id=active_profile.id if active_profile is not None else None,
            error_message=None,
        )

    if active_profile is not None:
        return HouseholdVoiceprintMemberSummaryRead(
            member_id=member.id,
            member_name=member.name,
            member_role=member.role,
            status="active",
            sample_count=active_profile.sample_count,
            updated_at=active_profile.updated_at,
            pending_enrollment_id=None,
            active_profile_id=active_profile.id,
            error_message=None,
        )

    if latest_enrollment is not None and latest_enrollment.status == "failed":
        return HouseholdVoiceprintMemberSummaryRead(
            member_id=member.id,
            member_name=member.name,
            member_role=member.role,
            status="failed",
            sample_count=0,
            updated_at=latest_enrollment.updated_at,
            pending_enrollment_id=None,
            active_profile_id=None,
            error_message=latest_enrollment.error_message,
        )

    if latest_profile is not None and latest_profile.status in {"deleted", "superseded"}:
        return HouseholdVoiceprintMemberSummaryRead(
            member_id=member.id,
            member_name=member.name,
            member_role=member.role,
            status="disabled",
            sample_count=latest_profile.sample_count,
            updated_at=latest_profile.updated_at,
            pending_enrollment_id=None,
            active_profile_id=None,
            error_message=None,
        )

    if latest_profile is not None and latest_profile.status == "failed":
        return HouseholdVoiceprintMemberSummaryRead(
            member_id=member.id,
            member_name=member.name,
            member_role=member.role,
            status="failed",
            sample_count=latest_profile.sample_count,
            updated_at=latest_profile.updated_at,
            pending_enrollment_id=None,
            active_profile_id=None,
            error_message=None,
        )

    return HouseholdVoiceprintMemberSummaryRead(
        member_id=member.id,
        member_name=member.name,
        member_role=member.role,
        status="not_enrolled",
        sample_count=0,
        updated_at=None,
        pending_enrollment_id=None,
        active_profile_id=None,
        error_message=None,
    )


def delete_member_voiceprints(db: Session, *, member_id: str) -> MemberVoiceprintDeleteResponse:
    member = _get_member_or_404(db, member_id)
    now = utc_now_iso()

    profiles = list(
        db.scalars(
            select(MemberVoiceprintProfile).where(
                MemberVoiceprintProfile.household_id == member.household_id,
                MemberVoiceprintProfile.member_id == member.id,
                MemberVoiceprintProfile.status != "deleted",
            )
        ).all()
    )
    for profile in profiles:
        profile.status = "deleted"
        profile.updated_at = now
        db.add(profile)

    enrollments = list(
        db.scalars(
            select(VoiceprintEnrollment).where(
                VoiceprintEnrollment.household_id == member.household_id,
                VoiceprintEnrollment.member_id == member.id,
                VoiceprintEnrollment.status.in_(_PENDING_ENROLLMENT_STATUSES),
            )
        ).all()
    )
    for enrollment in enrollments:
        enrollment.status = "cancelled"
        enrollment.error_code = "voiceprint_profile_deleted"
        enrollment.error_message = "成员声纹档案已删除，当前建档任务已取消。"
        enrollment.updated_at = now
        db.add(enrollment)

    return MemberVoiceprintDeleteResponse(
        member_id=member.id,
        household_id=member.household_id,
        deleted_profile_count=len(profiles),
        cancelled_enrollment_count=len(enrollments),
    )


def process_voiceprint_enrollment_sample(
    db: Session,
    *,
    enrollment_id: str,
    transcript_text: str | None,
    artifact_id: str,
    artifact_path: str,
    artifact_sha256: str,
    sample_rate: int,
    channels: int,
    sample_width: int,
    duration_ms: int,
    provider: VoiceprintProvider | None = None,
) -> VoiceprintEnrollmentProcessResult:
    enrollment = get_voiceprint_enrollment_or_404(db, enrollment_id)
    _sync_enrollment_phrase_state(enrollment)
    if enrollment.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="voiceprint enrollment is not accepting samples")

    provider_instance = provider or get_voiceprint_provider()
    transcript_value = (transcript_text or "").strip()
    sample = _build_voiceprint_sample_record(
        enrollment=enrollment,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        duration_ms=duration_ms,
        transcript_text=transcript_value or None,
    )

    validation_error = _validate_enrollment_sample(enrollment=enrollment, sample=sample, transcript_text=transcript_value)
    if validation_error is not None:
        sample.status = "rejected"
        sample.sample_payload_json = dump_json({"rejection_reason": validation_error})
        db.add(sample)
        enrollment.status = "recording" if enrollment.sample_count > 0 else "pending"
        _sync_enrollment_phrase_state(enrollment)
        enrollment.error_code = "voiceprint_sample_invalid"
        enrollment.error_message = validation_error
        enrollment.updated_at = utc_now_iso()
        db.add(enrollment)
        return _build_enrollment_process_result(
            outcome="rejected",
            enrollment=enrollment,
            sample=sample,
            error_code="voiceprint_sample_invalid",
            error_message=validation_error,
        )

    try:
        embedding = provider_instance.extract_embedding(artifact_path)
    except VoiceprintProviderError as exc:
        sample.status = "rejected"
        sample.sample_payload_json = dump_json({"error_code": exc.code, "error_message": exc.message})
        db.add(sample)
        enrollment.status = "failed"
        enrollment.error_code = exc.code
        enrollment.error_message = exc.message
        enrollment.updated_at = utc_now_iso()
        db.add(enrollment)
        return _build_enrollment_process_result(
            outcome="failed",
            enrollment=enrollment,
            sample=sample,
            error_code=exc.code,
            error_message=exc.message,
        )

    sample.sample_payload_json = dump_json(_build_sample_payload(embedding=embedding))
    sample.status = "accepted"
    db.add(sample)
    db.flush()

    accepted_samples = _load_accepted_samples_for_enrollment(db, enrollment_id=enrollment.id)
    enrollment.sample_count = len(accepted_samples)
    enrollment.error_code = None
    enrollment.error_message = None
    _sync_enrollment_phrase_state(enrollment)
    enrollment.updated_at = utc_now_iso()

    if enrollment.sample_count < enrollment.sample_goal:
        enrollment.status = "recording"
        _sync_enrollment_phrase_state(enrollment)
        db.add(enrollment)
        return _build_enrollment_process_result(
            outcome="recorded",
            enrollment=enrollment,
            sample=sample,
        )

    enrollment.status = "processing"
    db.add(enrollment)

    profile_result = _build_or_update_profile_from_samples(
        db,
        enrollment=enrollment,
        provider=provider_instance,
        latest_sample=sample,
    )
    return profile_result


def _build_enrollment_process_result(
    *,
    outcome: str,
    enrollment: VoiceprintEnrollment,
    sample: MemberVoiceprintSample | None = None,
    profile: MemberVoiceprintProfile | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> VoiceprintEnrollmentProcessResult:
    return VoiceprintEnrollmentProcessResult(
        outcome=outcome,
        enrollment=enrollment,
        prompt_enrollment=VoiceprintPromptEnrollmentSnapshot.from_enrollment(enrollment),
        sample=sample,
        profile=profile,
        sample_id=sample.id if sample is not None else None,
        profile_id=profile.id if profile is not None else None,
        error_code=error_code,
        error_message=error_message,
    )


def search_voiceprint_profiles_in_household(
    db: Session,
    *,
    household_id: str,
    artifact_path: str,
    provider: VoiceprintProvider | None = None,
    limit: int = 3,
) -> HouseholdVoiceprintSearchRead:
    provider_instance = provider or get_voiceprint_provider()
    query_embedding = provider_instance.extract_embedding(artifact_path)
    candidates = _load_household_profile_candidates(db, household_id=household_id)
    result = provider_instance.search(
        query_embedding=query_embedding.vector,
        candidates=candidates,
        threshold=None,
        limit=limit,
    )
    top_hit = result.top_hit
    return HouseholdVoiceprintSearchRead(
        provider=result.provider,
        status=result.status,
        threshold=result.threshold,
        profile_id=top_hit.profile_id if top_hit is not None else None,
        member_id=top_hit.member_id if top_hit is not None else None,
        score=top_hit.score if top_hit is not None else None,
        candidate_count=len(result.hits),
    )


def verify_member_voiceprint(
    db: Session,
    *,
    household_id: str,
    member_id: str,
    artifact_path: str,
    provider: VoiceprintProvider | None = None,
) -> MemberVoiceprintVerifyRead:
    provider_instance = provider or get_voiceprint_provider()
    profile = db.scalar(
        select(MemberVoiceprintProfile).where(
            MemberVoiceprintProfile.household_id == household_id,
            MemberVoiceprintProfile.member_id == member_id,
            MemberVoiceprintProfile.status == "active",
        )
    )
    if profile is None:
        return MemberVoiceprintVerifyRead(
            provider=provider_instance.provider_code,
            status="no_profile",
            threshold=0,
            member_id=member_id,
            profile_id=None,
            matched=False,
            score=None,
        )

    query_embedding = provider_instance.extract_embedding(artifact_path)
    profile_embedding = _load_profile_embedding(profile)
    if profile_embedding is None:
        return MemberVoiceprintVerifyRead(
            provider=provider_instance.provider_code,
            status="profile_unavailable",
            threshold=0,
            member_id=member_id,
            profile_id=profile.id,
            matched=False,
            score=None,
        )

    result = provider_instance.verify(
        query_embedding=query_embedding.vector,
        profile_embedding=profile_embedding,
        threshold=None,
    )
    return MemberVoiceprintVerifyRead(
        provider=result.provider,
        status=result.status,
        threshold=result.threshold,
        member_id=member_id,
        profile_id=profile.id,
        matched=result.matched,
        score=result.score,
    )


def identify_household_member_by_voiceprint(
    db: Session,
    *,
    household_id: str,
    artifact_path: str | None,
    provider: VoiceprintProvider | None = None,
    limit: int = _VOICEPRINT_IDENTIFICATION_LIMIT,
    conflict_score_margin: float = _VOICEPRINT_CONFLICT_SCORE_MARGIN,
) -> VoiceprintIdentificationRead:
    provider_instance = provider or get_voiceprint_provider()
    if not artifact_path:
        return VoiceprintIdentificationRead(
            provider=provider_instance.provider_code,
            status="skipped",
            threshold=0,
            reason="当前会话没有可用音频产物，先跳过声纹识别。",
        )

    candidates = _load_household_profile_candidates(db, household_id=household_id)
    if not candidates:
        return VoiceprintIdentificationRead(
            provider=provider_instance.provider_code,
            status="no_profile",
            threshold=settings.voiceprint_search_score_threshold,
            reason="当前家庭还没有可用于识别的声纹档案，先按旧逻辑回退。",
        )

    try:
        query_embedding = provider_instance.extract_embedding(artifact_path)
    except VoiceprintProviderError as exc:
        return VoiceprintIdentificationRead(
            provider=provider_instance.provider_code,
            status="unavailable",
            threshold=settings.voiceprint_search_score_threshold,
            reason=f"声纹 provider 当前不可用：{exc.message}",
            candidate_count=len(candidates),
        )

    search_result = provider_instance.search(
        query_embedding=query_embedding.vector,
        candidates=candidates,
        threshold=None,
        limit=max(limit, 1),
    )
    readable_candidates = [
        VoiceprintIdentificationCandidateRead(
            member_id=item.member_id,
            profile_id=item.profile_id,
            score=item.score,
        )
        for item in search_result.hits
    ]
    top_hit = search_result.top_hit
    if top_hit is None:
        return VoiceprintIdentificationRead(
            provider=search_result.provider,
            status="no_profile",
            threshold=search_result.threshold,
            reason="当前家庭没有命中任何有效声纹候选，先按旧逻辑回退。",
            candidate_count=0,
            candidates=readable_candidates,
        )

    if top_hit.score < search_result.threshold:
        return VoiceprintIdentificationRead(
            provider=search_result.provider,
            status="low_confidence",
            threshold=search_result.threshold,
            reason="声纹候选分数不够，不能拿来直接认人。",
            profile_id=top_hit.profile_id,
            member_id=top_hit.member_id,
            score=top_hit.score,
            candidate_count=len(readable_candidates),
            candidates=readable_candidates,
        )

    second_hit = search_result.hits[1] if len(search_result.hits) > 1 else None
    if (
        second_hit is not None
        and second_hit.score >= search_result.threshold
        and (top_hit.score - second_hit.score) < conflict_score_margin
    ):
        return VoiceprintIdentificationRead(
            provider=search_result.provider,
            status="conflict",
            threshold=search_result.threshold,
            reason="多个家庭成员的声纹分数太接近，当前不能安全认人。",
            profile_id=top_hit.profile_id,
            member_id=top_hit.member_id,
            score=top_hit.score,
            candidate_count=len(readable_candidates),
            candidates=readable_candidates,
        )

    profile_embedding_map = {item.profile_id: item.embedding for item in candidates}
    profile_embedding = profile_embedding_map.get(top_hit.profile_id)
    if not profile_embedding:
        return VoiceprintIdentificationRead(
            provider=search_result.provider,
            status="unavailable",
            threshold=search_result.threshold,
            reason="命中了声纹档案，但档案 embedding 缺失，先按旧逻辑回退。",
            profile_id=top_hit.profile_id,
            member_id=top_hit.member_id,
            score=top_hit.score,
            candidate_count=len(readable_candidates),
            candidates=readable_candidates,
        )

    verify_result = provider_instance.verify(
        query_embedding=query_embedding.vector,
        profile_embedding=profile_embedding,
        threshold=None,
    )
    if not verify_result.matched:
        return VoiceprintIdentificationRead(
            provider=verify_result.provider,
            status="low_confidence",
            threshold=verify_result.threshold,
            reason="声纹搜索命中了候选，但二次校验没有通过。",
            profile_id=top_hit.profile_id,
            member_id=top_hit.member_id,
            score=verify_result.score,
            candidate_count=len(readable_candidates),
            candidates=readable_candidates,
        )

    return VoiceprintIdentificationRead(
        provider=verify_result.provider,
        status="matched",
        threshold=verify_result.threshold,
        reason="声纹搜索和二次校验都通过，优先使用声纹结果。",
        profile_id=top_hit.profile_id,
        member_id=top_hit.member_id,
        score=verify_result.score,
        candidate_count=len(readable_candidates),
        candidates=readable_candidates,
    )


def get_voiceprint_provider() -> VoiceprintProvider:
    return get_default_voiceprint_provider()


def _get_member_or_404(db: Session, member_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    return member


def _get_terminal_or_404(db: Session, terminal_id: str) -> Device:
    terminal = db.get(Device, terminal_id)
    if terminal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="terminal not found")
    return terminal


def _build_enrollment_expires_at() -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_ENROLLMENT_EXPIRE_MINUTES)
    return expires_at.astimezone().isoformat()


def _resolve_base_phrase(*, expected_phrase: str | None, member_id: str, terminal_id: str) -> str:
    normalized_phrase = _normalize_optional_text(expected_phrase)
    if normalized_phrase:
        return normalized_phrase
    return _select_default_expected_phrase(member_id=member_id, terminal_id=terminal_id)


def _select_default_expected_phrase(*, member_id: str, terminal_id: str) -> str:
    return _select_default_expected_phrase_by_offset(member_id=member_id, terminal_id=terminal_id, offset=0)


def _select_default_expected_phrase_by_offset(*, member_id: str, terminal_id: str, offset: int) -> str:
    stable_seed = f"{member_id}:{terminal_id}:{offset}"
    phrase_index = sum(ord(char) for char in stable_seed) % len(_DEFAULT_ENROLLMENT_PHRASES)
    return _DEFAULT_ENROLLMENT_PHRASES[phrase_index]


def _resolve_sample_goal(sample_goal: int | None) -> int:
    goal = int(sample_goal or _DEFAULT_ENROLLMENT_SAMPLE_GOAL)
    return max(goal, 1)


def _build_enrollment_phrase_plan(
    *,
    member_id: str,
    terminal_id: str,
    base_phrase: str,
    sample_goal: int,
) -> list[str]:
    goal = _resolve_sample_goal(sample_goal)
    repeated_rounds = min(goal, _DEFAULT_ENROLLMENT_BASE_REPEAT)
    plan = [base_phrase] * repeated_rounds
    remaining = goal - len(plan)
    if remaining <= 0:
        return plan

    normalized_base = _normalize_phrase(base_phrase)
    alternates: list[str] = []
    offset = 1
    while len(alternates) < remaining:
        candidate = _select_default_expected_phrase_by_offset(
            member_id=member_id,
            terminal_id=terminal_id,
            offset=offset,
        )
        offset += 1
        if _normalize_phrase(candidate) == normalized_base:
            continue
        if any(_normalize_phrase(item) == _normalize_phrase(candidate) for item in alternates):
            continue
        alternates.append(candidate)
    return plan + alternates


def _get_enrollment_base_phrase(enrollment: VoiceprintEnrollment) -> str:
    base_phrase = _normalize_optional_text(getattr(enrollment, "base_phrase", None))
    if base_phrase:
        return base_phrase
    fallback = _normalize_optional_text(enrollment.expected_phrase)
    if fallback:
        return fallback
    return _select_default_expected_phrase(member_id=enrollment.member_id, terminal_id=enrollment.terminal_id)


def _get_current_enrollment_phrase(enrollment: VoiceprintEnrollment) -> str | None:
    plan = _build_enrollment_phrase_plan(
        member_id=enrollment.member_id,
        terminal_id=enrollment.terminal_id,
        base_phrase=_get_enrollment_base_phrase(enrollment),
        sample_goal=enrollment.sample_goal,
    )
    if not plan:
        return None
    next_index = min(max(enrollment.sample_count, 0), len(plan) - 1)
    return plan[next_index]


def _sync_enrollment_phrase_state(enrollment: VoiceprintEnrollment) -> None:
    enrollment.base_phrase = _get_enrollment_base_phrase(enrollment)
    enrollment.sample_goal = _resolve_sample_goal(enrollment.sample_goal)
    enrollment.expected_phrase = _get_current_enrollment_phrase(enrollment)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _validate_enrollment_sample(
    *,
    enrollment: VoiceprintEnrollment,
    sample: MemberVoiceprintSample,
    transcript_text: str,
) -> str | None:
    _sync_enrollment_phrase_state(enrollment)
    sample_path = Path(sample.artifact_path).expanduser()
    if not sample_path.is_file():
        return "样本文件不存在，无法继续建档"
    if sample.duration_ms < _ENROLLMENT_SAMPLE_MIN_DURATION_MS:
        return f"样本时长过短，至少需要 {_ENROLLMENT_SAMPLE_MIN_DURATION_MS}ms"
    if sample.duration_ms > _ENROLLMENT_SAMPLE_MAX_DURATION_MS:
        return f"样本时长过长，当前上限是 {_ENROLLMENT_SAMPLE_MAX_DURATION_MS}ms"
    if not transcript_text:
        return "样本文本为空，无法确认本轮采样内容"
    if sample.channels != 1:
        return "当前首版只接受单声道样本"
    if sample.sample_width != 2:
        return "当前首版只接受 16-bit PCM 样本"
    if enrollment.expected_phrase and not _phrases_match(enrollment.expected_phrase, transcript_text):
        return "样本文本与预期采样短语不一致"
    return None


def _build_voiceprint_sample_record(
    *,
    enrollment: VoiceprintEnrollment,
    artifact_id: str,
    artifact_path: str,
    artifact_sha256: str,
    sample_rate: int,
    channels: int,
    sample_width: int,
    duration_ms: int,
    transcript_text: str | None,
) -> MemberVoiceprintSample:
    return MemberVoiceprintSample(
        id=new_uuid(),
        profile_id=None,
        enrollment_id=enrollment.id,
        household_id=enrollment.household_id,
        member_id=enrollment.member_id,
        terminal_id=enrollment.terminal_id,
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        duration_ms=duration_ms,
        transcript_text=transcript_text,
        status="accepted",
    )


def _build_sample_payload(*, embedding: VoiceprintEmbedding) -> dict[str, object]:
    return {
        "provider": embedding.provider,
        "embedding": embedding.vector,
        "dimension": embedding.dimension,
        "audio_path": embedding.audio_path,
        "metadata": embedding.metadata,
    }


def _build_or_update_profile_from_samples(
    db: Session,
    *,
    enrollment: VoiceprintEnrollment,
    provider: VoiceprintProvider,
    latest_sample: MemberVoiceprintSample,
) -> VoiceprintEnrollmentProcessResult:
    current_profile = db.scalar(
        select(MemberVoiceprintProfile)
        .where(
            MemberVoiceprintProfile.household_id == enrollment.household_id,
            MemberVoiceprintProfile.member_id == enrollment.member_id,
            MemberVoiceprintProfile.status == "active",
        )
        .order_by(MemberVoiceprintProfile.version.desc())
        .limit(1)
    )
    accepted_member_samples = _load_accepted_samples_for_member(
        db,
        household_id=enrollment.household_id,
        member_id=enrollment.member_id,
    )
    sample_embeddings = _load_embeddings_from_samples(accepted_member_samples)
    if not sample_embeddings:
        enrollment.status = "failed"
        _sync_enrollment_phrase_state(enrollment)
        enrollment.error_code = "voiceprint_embedding_missing"
        enrollment.error_message = "没有可聚合的 embedding，无法生成声纹档案"
        enrollment.updated_at = utc_now_iso()
        db.add(enrollment)
        return _build_enrollment_process_result(
            outcome="failed",
            enrollment=enrollment,
            sample=latest_sample,
            error_code=enrollment.error_code,
            error_message=enrollment.error_message,
        )

    try:
        profile_data = provider.build_profile(
            member_id=enrollment.member_id,
            embeddings=sample_embeddings,
            source_sample_ids=[item.id for item in accepted_member_samples],
            source_profile_id=current_profile.id if current_profile is not None else None,
        )
    except VoiceprintProviderError as exc:
        enrollment.status = "failed"
        _sync_enrollment_phrase_state(enrollment)
        enrollment.error_code = exc.code
        enrollment.error_message = exc.message
        enrollment.updated_at = utc_now_iso()
        db.add(enrollment)
        return _build_enrollment_process_result(
            outcome="failed",
            enrollment=enrollment,
            sample=latest_sample,
            error_code=exc.code,
            error_message=exc.message,
        )

    next_version = _next_profile_version(db, household_id=enrollment.household_id, member_id=enrollment.member_id)
    if current_profile is not None:
        current_profile.status = "superseded"
        current_profile.updated_at = utc_now_iso()
        db.add(current_profile)

    profile = MemberVoiceprintProfile(
        id=new_uuid(),
        household_id=enrollment.household_id,
        member_id=enrollment.member_id,
        provider=profile_data.provider,
        provider_profile_ref=profile_data.provider_profile_ref,
        profile_payload_json=dump_json(
            {
                "provider": profile_data.provider,
                "embedding": profile_data.embedding,
                "sample_count": profile_data.sample_count,
                "metadata": profile_data.metadata,
            }
        ),
        status="active",
        sample_count=profile_data.sample_count,
        version=next_version,
    )
    db.add(profile)
    db.flush()

    enrollment_samples = _load_accepted_samples_for_enrollment(db, enrollment_id=enrollment.id)
    for item in enrollment_samples:
        item.profile_id = profile.id
        db.add(item)

    enrollment.status = "completed"
    _sync_enrollment_phrase_state(enrollment)
    enrollment.error_code = None
    enrollment.error_message = None
    enrollment.updated_at = utc_now_iso()
    db.add(enrollment)
    return _build_enrollment_process_result(
        outcome="completed",
        enrollment=enrollment,
        sample=latest_sample,
        profile=profile,
    )


def _load_accepted_samples_for_enrollment(db: Session, *, enrollment_id: str) -> list[MemberVoiceprintSample]:
    return list(
        db.scalars(
            select(MemberVoiceprintSample)
            .where(
                MemberVoiceprintSample.enrollment_id == enrollment_id,
                MemberVoiceprintSample.status == "accepted",
            )
            .order_by(MemberVoiceprintSample.created_at.asc(), MemberVoiceprintSample.id.asc())
        ).all()
    )


def _load_accepted_samples_for_member(
    db: Session,
    *,
    household_id: str,
    member_id: str,
) -> list[MemberVoiceprintSample]:
    return list(
        db.scalars(
            select(MemberVoiceprintSample)
            .where(
                MemberVoiceprintSample.household_id == household_id,
                MemberVoiceprintSample.member_id == member_id,
                MemberVoiceprintSample.status == "accepted",
            )
            .order_by(MemberVoiceprintSample.created_at.asc(), MemberVoiceprintSample.id.asc())
        ).all()
    )


def _load_embeddings_from_samples(samples: list[MemberVoiceprintSample]) -> list[VoiceprintEmbedding]:
    embeddings: list[VoiceprintEmbedding] = []
    for sample in samples:
        payload = load_json(sample.sample_payload_json)
        if not isinstance(payload, dict):
            continue
        raw_embedding = payload.get("embedding")
        if not isinstance(raw_embedding, list) or not raw_embedding:
            continue
        embeddings.append(
            VoiceprintEmbedding(
                provider=str(payload.get("provider") or ""),
                vector=[float(item) for item in raw_embedding],
                dimension=len(raw_embedding),
                audio_path=str(payload.get("audio_path") or sample.artifact_path),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
        )
    return embeddings


def _load_household_profile_candidates(db: Session, *, household_id: str) -> list[VoiceprintProfileCandidate]:
    profiles = list(
        db.scalars(
            select(MemberVoiceprintProfile)
            .where(
                MemberVoiceprintProfile.household_id == household_id,
                MemberVoiceprintProfile.status == "active",
            )
            .order_by(MemberVoiceprintProfile.updated_at.desc(), MemberVoiceprintProfile.id.desc())
        ).all()
    )
    candidates: list[VoiceprintProfileCandidate] = []
    for profile in profiles:
        embedding = _load_profile_embedding(profile)
        if embedding is None:
            continue
        candidates.append(
            VoiceprintProfileCandidate(
                profile_id=profile.id,
                member_id=profile.member_id,
                embedding=embedding,
                metadata={"version": profile.version},
            )
        )
    return candidates


def _load_profile_embedding(profile: MemberVoiceprintProfile) -> list[float] | None:
    payload = load_json(profile.profile_payload_json)
    if not isinstance(payload, dict):
        return None
    raw_embedding = payload.get("embedding")
    if not isinstance(raw_embedding, list) or not raw_embedding:
        return None
    return [float(item) for item in raw_embedding]


def _next_profile_version(db: Session, *, household_id: str, member_id: str) -> int:
    current_max = db.scalar(
        select(func.max(MemberVoiceprintProfile.version)).where(
            MemberVoiceprintProfile.household_id == household_id,
            MemberVoiceprintProfile.member_id == member_id,
        )
    )
    return int(current_max or 0) + 1


def _phrases_match(expected_phrase: str, transcript_text: str) -> bool:
    expected = _normalize_phrase(expected_phrase)
    actual = _normalize_phrase(transcript_text)
    if not expected or not actual:
        return False
    return expected in actual or actual in expected


def _normalize_phrase(value: str) -> str:
    normalized = re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)
    return normalized.casefold()
