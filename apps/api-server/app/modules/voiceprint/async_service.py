from __future__ import annotations

import logging

from app.core.blocking import BlockingCallPolicy, run_blocking_db
from app.db import session as db_session_module
from app.modules.voiceprint.provider import VoiceprintProvider
from app.modules.voiceprint.service import (
    VoiceprintEnrollmentProcessResult,
    VoiceprintIdentificationRead,
    identify_household_member_by_voiceprint,
    process_voiceprint_enrollment_sample,
)

logger = logging.getLogger(__name__)
VOICEPRINT_ENROLLMENT_TIMEOUT_SECONDS = 20.0
VOICEPRINT_IDENTIFICATION_TIMEOUT_SECONDS = 10.0


async def async_process_voiceprint_enrollment_sample(
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
    return await run_blocking_db(
        lambda db: process_voiceprint_enrollment_sample(
            db,
            enrollment_id=enrollment_id,
            transcript_text=transcript_text,
            artifact_id=artifact_id,
            artifact_path=artifact_path,
            artifact_sha256=artifact_sha256,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration_ms=duration_ms,
            provider=provider,
        ),
        session_factory=db_session_module.SessionLocal,
        policy=BlockingCallPolicy(
            label="voice.voiceprint.enrollment",
            kind="sync_db",
            timeout_seconds=VOICEPRINT_ENROLLMENT_TIMEOUT_SECONDS,
        ),
        commit=True,
        logger=logger,
        context={
            "enrollment_id": enrollment_id,
            "artifact_id": artifact_id,
            "artifact_path": artifact_path,
        },
    )


async def async_identify_household_member_by_voiceprint(
    *,
    household_id: str,
    artifact_path: str | None,
    provider: VoiceprintProvider | None = None,
    limit: int = 3,
    conflict_score_margin: float = 0.05,
) -> VoiceprintIdentificationRead:
    return await run_blocking_db(
        lambda db: identify_household_member_by_voiceprint(
            db,
            household_id=household_id,
            artifact_path=artifact_path,
            provider=provider,
            limit=limit,
            conflict_score_margin=conflict_score_margin,
        ),
        session_factory=db_session_module.SessionLocal,
        policy=BlockingCallPolicy(
            label="voice.voiceprint.identify",
            kind="sync_db",
            timeout_seconds=VOICEPRINT_IDENTIFICATION_TIMEOUT_SECONDS,
        ),
        commit=False,
        logger=logger,
        context={
            "household_id": household_id,
            "artifact_path": artifact_path,
            "limit": limit,
        },
    )
