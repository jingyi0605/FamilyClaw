from __future__ import annotations

import base64

from fastapi import Depends, FastAPI, Header, HTTPException, status

from voice_runtime.schemas import (
    AppendAudioRequest,
    AppendAudioResponse,
    CommitSessionRequest,
    CommitSessionResponse,
    ErrorResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from voice_runtime.service import build_transcript, session_store
from voice_runtime.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title="FamilyClaw Voice Runtime", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/voice/sessions/start",
        response_model=StartSessionResponse,
        responses={401: {"model": ErrorResponse}},
    )
    async def start_session(
        payload: StartSessionRequest,
        _: None = Depends(require_api_key),
    ) -> StartSessionResponse:
        session = await session_store.start_session(
            session_id=payload.session_id,
            terminal_id=payload.terminal_id,
            household_id=payload.household_id,
            room_id=payload.room_id,
            sample_rate=payload.sample_rate,
            codec=payload.codec,
            channels=payload.channels,
            session_purpose=payload.session_purpose,
            enrollment_id=payload.enrollment_id,
        )
        return StartSessionResponse(runtime_session_id=session.session_id)

    @app.post(
        "/v1/voice/sessions/append",
        response_model=AppendAudioResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def append_audio(
        payload: AppendAudioRequest,
        _: None = Depends(require_api_key),
    ) -> AppendAudioResponse:
        session = await session_store.append_audio(
            session_id=payload.session_id,
            terminal_id=payload.terminal_id,
            chunk_base64=payload.chunk_base64,
            chunk_bytes=payload.chunk_bytes,
        )
        if session is None:
            raise not_found("voice_session_not_found", "voice session not found")

        return AppendAudioResponse(
            runtime_session_id=session.session_id,
            buffered_chunk_count=session.chunk_count,
            received_bytes=session.received_bytes,
        )

    @app.post(
        "/v1/voice/sessions/commit",
        response_model=CommitSessionResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def commit_session(
        payload: CommitSessionRequest,
        _: None = Depends(require_api_key),
        x_debug_transcript: str | None = Header(default=None, alias="X-Debug-Transcript"),
        x_debug_transcript_b64: str | None = Header(default=None, alias="X-Debug-Transcript-B64"),
    ) -> CommitSessionResponse:
        commit_result = await session_store.commit_session(
            session_id=payload.session_id,
            terminal_id=payload.terminal_id,
            household_id=payload.household_id,
        )
        if commit_result is None:
            raise not_found("voice_session_not_found", "voice session not found")

        debug_transcript = decode_debug_transcript(x_debug_transcript, x_debug_transcript_b64)
        transcript_text = build_transcript(commit_result.session, debug_transcript)
        response = CommitSessionResponse(
            runtime_session_id=commit_result.session.session_id,
            transcript_text=transcript_text,
            buffered_chunk_count=commit_result.session.chunk_count,
            received_bytes=commit_result.session.received_bytes,
            degraded=commit_result.audio_artifact is None,
        )
        if commit_result.audio_artifact is not None:
            response.audio_artifact_id = commit_result.audio_artifact.artifact_id
            response.audio_file_path = commit_result.audio_artifact.file_path
            response.sample_rate = commit_result.audio_artifact.sample_rate
            response.channels = commit_result.audio_artifact.channels
            response.sample_width = commit_result.audio_artifact.sample_width
            response.duration_ms = commit_result.audio_artifact.duration_ms
            response.audio_sha256 = commit_result.audio_artifact.sha256
        return response

    return app


def require_api_key(authorization: str | None = Header(default=None, alias="Authorization")) -> None:
    expected_api_key = settings.api_key
    if not expected_api_key:
        return

    expected_header = f"Bearer {expected_api_key}"
    if authorization != expected_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error_code="voice_runtime_unauthorized", detail="invalid runtime api key").model_dump(),
        )


def not_found(error_code: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse(error_code=error_code, detail=detail).model_dump(),
    )


def decode_debug_transcript(raw_text: str | None, encoded_text: str | None) -> str | None:
    if encoded_text:
        try:
            return base64.b64decode(encoded_text.encode("ascii")).decode("utf-8").strip() or None
        except (ValueError, UnicodeDecodeError):
            return None
    return raw_text.strip() if raw_text and raw_text.strip() else None


app = create_app()
