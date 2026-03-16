from __future__ import annotations

import logging
from http.cookies import SimpleCookie
from typing import Any, cast

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import ActorContext, ensure_actor_can_access_household
from app.core.blocking import BlockingCallPolicy, run_blocking_db
from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.account.service import resolve_authenticated_actor_by_session_token
from app.modules.agent import repository as agent_repository
from app.modules.agent.bootstrap_service import (
    arun_butler_bootstrap_realtime_turn,
    get_butler_bootstrap_session_snapshot,
)
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.service import (
    arun_conversation_realtime_turn,
    get_conversation_session_snapshot,
)
from app.modules.realtime.connection_manager import realtime_connection_manager
from app.modules.realtime.schemas import BootstrapRealtimeClientEvent, build_bootstrap_realtime_event
from app.modules.voice.realtime_service import voice_realtime_service

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)
REALTIME_ENDPOINT_DB_TIMEOUT_SECONDS = 15.0


@router.websocket("/realtime/voice")
async def realtime_voice_gateway_websocket(websocket: WebSocket) -> None:
    await voice_realtime_service.handle_gateway_websocket(websocket)


@router.websocket("/realtime/agent-bootstrap")
async def realtime_agent_bootstrap_websocket(websocket: WebSocket) -> None:
    household_id = (websocket.query_params.get("household_id") or "").strip()
    session_id = (websocket.query_params.get("session_id") or "").strip()
    session_factory = SessionLocal

    accepted = False
    try:
        actor = await _authenticate_websocket_actor(session_factory, websocket)
        ensure_actor_can_access_household(actor, household_id)

        snapshot = await _load_bootstrap_session_snapshot(
            session_factory,
            household_id=household_id,
            session_id=session_id,
        )
        if snapshot is None:
            await websocket.accept()
            accepted = True
            await _send_error_and_close(
                websocket,
                session_id=session_id or "unknown-session",
                detail="引导会话不存在",
                error_code="session_not_found",
            )
            return

        await websocket.accept()
        accepted = True
        realtime_connection_manager.register(household_id=household_id, session_id=session_id, websocket=websocket)

        await _send_event(
            session_factory,
            websocket,
            event_type="session.ready",
            session_id=session_id,
            payload={},
        )
        await _send_event(
            session_factory,
            websocket,
            event_type="session.snapshot",
            session_id=session_id,
            payload={"snapshot": snapshot.model_dump(mode="json")},
        )

        while True:
            client_event = BootstrapRealtimeClientEvent.model_validate(await websocket.receive_json())
            if client_event.session_id != session_id:
                await _send_event(
                    session_factory,
                    websocket,
                    event_type="agent.error",
                    session_id=session_id,
                    request_id=client_event.request_id,
                    payload={
                        "detail": "session_id 不匹配",
                        "error_code": "invalid_event_payload",
                    },
                )
                continue

            if client_event.type == "ping":
                ping_payload = cast(dict[str, Any], client_event.payload.model_dump(mode="json"))
                await _send_event(
                    session_factory,
                    websocket,
                    event_type="pong",
                    session_id=session_id,
                    payload={"nonce": ping_payload.get("nonce")},
                )
                continue

            if client_event.type == "user.message":
                message_payload = cast(dict[str, Any], client_event.payload.model_dump(mode="json"))
                turn_db = SessionLocal()
                try:
                    await arun_butler_bootstrap_realtime_turn(
                        turn_db,
                        household_id=household_id,
                        session_id=session_id,
                        request_id=client_event.request_id or "",
                        user_message=str(message_payload.get("text") or ""),
                        connection_manager=realtime_connection_manager,
                        session_factory=session_factory,
                    )
                finally:
                    turn_db.close()
                continue

            await _send_event(
                session_factory,
                websocket,
                event_type="agent.error",
                session_id=session_id,
                request_id=client_event.request_id,
                payload={
                    "detail": "未知的实时事件类型",
                    "error_code": "invalid_event_payload",
                },
            )
    except WebSocketDisconnect:
        return
    except Exception:
        await _log_and_close_websocket_on_error(
            websocket=websocket,
            accepted=accepted,
            route_name="realtime.agent-bootstrap",
            household_id=household_id,
            session_id=session_id,
        )
    finally:
        if accepted and household_id and session_id:
            realtime_connection_manager.unregister(household_id=household_id, session_id=session_id, websocket=websocket)


@router.websocket("/realtime/conversation")
async def realtime_conversation_websocket(websocket: WebSocket) -> None:
    accepted = False
    household_id = ""
    session_id = ""
    session_factory = SessionLocal
    try:
        household_id = (websocket.query_params.get("household_id") or "").strip()
        session_id = (websocket.query_params.get("session_id") or "").strip()
        actor_context = await _authenticate_member_websocket_actor(session_factory, websocket)
        session_snapshot = await _load_conversation_session_snapshot(
            session_factory,
            session_id=session_id,
            actor=actor_context,
        )
        if not household_id:
            household_id = session_snapshot.household_id
        if household_id != session_snapshot.household_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot access another household conversation")

        await websocket.accept()
        accepted = True
        realtime_connection_manager.register(household_id=household_id, session_id=session_id, websocket=websocket)

        await _send_event(
            session_factory,
            websocket,
            event_type="session.ready",
            session_id=session_id,
            payload={},
        )
        await _send_event(
            session_factory,
            websocket,
            event_type="session.snapshot",
            session_id=session_id,
            payload={"snapshot": session_snapshot.model_dump(mode="json")},
        )

        while True:
            client_event = BootstrapRealtimeClientEvent.model_validate(await websocket.receive_json())
            if client_event.session_id != session_id:
                await _send_event(
                    session_factory,
                    websocket,
                    event_type="agent.error",
                    session_id=session_id,
                    request_id=client_event.request_id,
                    payload={
                        "detail": "session_id 不匹配",
                        "error_code": "invalid_event_payload",
                    },
                )
                continue

            if client_event.type == "ping":
                ping_payload = cast(dict[str, Any], client_event.payload.model_dump(mode="json"))
                await _send_event(
                    session_factory,
                    websocket,
                    event_type="pong",
                    session_id=session_id,
                    payload={"nonce": ping_payload.get("nonce")},
                )
                continue

            if client_event.type == "user.message":
                message_payload = cast(dict[str, Any], client_event.payload.model_dump(mode="json"))
                turn_db = SessionLocal()
                try:
                    await arun_conversation_realtime_turn(
                        turn_db,
                        session_id=session_id,
                        request_id=client_event.request_id or "",
                        user_message=str(message_payload.get("text") or ""),
                        actor=actor_context,
                        connection_manager=realtime_connection_manager,
                        session_factory=session_factory,
                    )
                finally:
                    turn_db.close()
                continue

            await _send_event(
                session_factory,
                websocket,
                event_type="agent.error",
                session_id=session_id,
                request_id=client_event.request_id,
                payload={
                    "detail": "未知的实时事件类型",
                    "error_code": "invalid_event_payload",
                },
            )
    except HTTPException as exc:
        if accepted:
            await _send_error_and_close(
                websocket,
                session_id=session_id,
                detail=str(exc.detail),
                error_code="session_not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "invalid_event_payload",
            )
        else:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        return
    except Exception:
        await _log_and_close_websocket_on_error(
            websocket=websocket,
            accepted=accepted,
            route_name="realtime.conversation",
            household_id=household_id,
            session_id=session_id,
        )
    finally:
        if accepted and household_id and session_id:
            realtime_connection_manager.unregister(household_id=household_id, session_id=session_id, websocket=websocket)


async def _authenticate_websocket_actor(
    session_factory: sessionmaker[Session],
    websocket: WebSocket,
) -> ActorContext:
    session_token = _extract_session_token(websocket)
    return await run_blocking_db(
        lambda db: _authenticate_websocket_actor_sync(db, session_token),
        session_factory=session_factory,
        policy=_build_realtime_policy(label="realtime.agent_bootstrap.authenticate"),
        logger=logger,
    )


async def _authenticate_member_websocket_actor(
    session_factory: sessionmaker[Session],
    websocket: WebSocket,
) -> ActorContext:
    session_token = _extract_session_token(websocket)
    return await run_blocking_db(
        lambda db: _authenticate_member_websocket_actor_sync(db, session_token),
        session_factory=session_factory,
        policy=_build_realtime_policy(label="realtime.conversation.authenticate"),
        logger=logger,
    )


def _authenticate_websocket_actor_sync(db: Session, session_token: str | None) -> ActorContext:
    actor = resolve_authenticated_actor_by_session_token(db, session_token)
    if actor is None:
        raise PermissionError("authentication required")

    actor_context = ActorContext.from_authenticated_actor(actor)
    if actor_context.role != "admin":
        raise PermissionError("admin role required")
    return actor_context


def _authenticate_member_websocket_actor_sync(db: Session, session_token: str | None) -> ActorContext:
    actor = resolve_authenticated_actor_by_session_token(db, session_token)
    if actor is None:
        raise PermissionError("authentication required")
    actor_context = ActorContext.from_authenticated_actor(actor)
    if actor_context.member_id is None and actor_context.account_type != "system":
        raise PermissionError("member role required")
    return actor_context


async def _load_bootstrap_session_snapshot(
    session_factory: sessionmaker[Session],
    *,
    household_id: str,
    session_id: str,
):
    return await run_blocking_db(
        lambda db: _load_bootstrap_session_snapshot_sync(
            db,
            household_id=household_id,
            session_id=session_id,
        ),
        session_factory=session_factory,
        policy=_build_realtime_policy(label="realtime.agent_bootstrap.snapshot"),
        logger=logger,
    )


def _load_bootstrap_session_snapshot_sync(
    db: Session,
    *,
    household_id: str,
    session_id: str,
):
    if agent_repository.get_bootstrap_session(db, household_id=household_id, session_id=session_id) is None:
        return None
    return get_butler_bootstrap_session_snapshot(db, household_id=household_id, session_id=session_id)


async def _load_conversation_session_snapshot(
    session_factory: sessionmaker[Session],
    *,
    session_id: str,
    actor: ActorContext,
):
    return await run_blocking_db(
        lambda db: get_conversation_session_snapshot(db, session_id=session_id, actor=actor),
        session_factory=session_factory,
        policy=_build_realtime_policy(label="realtime.conversation.snapshot"),
        logger=logger,
    )


def _extract_session_token(websocket: WebSocket) -> str | None:
    cookie_header = websocket.headers.get("cookie")
    if not cookie_header:
        return None
    parsed = SimpleCookie()
    parsed.load(cookie_header)
    morsel = parsed.get(settings.auth_session_cookie_name)
    if morsel is None:
        return None
    return morsel.value


async def _log_and_close_websocket_on_error(
    *,
    websocket: WebSocket,
    accepted: bool,
    route_name: str,
    household_id: str,
    session_id: str,
) -> None:
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    logger.exception(
        "WebSocket 异常 route=%s accepted=%s household_id=%s session_id=%s client=%s:%s",
        route_name,
        accepted,
        household_id or "-",
        session_id or "-",
        client_host,
        client_port,
    )
    if accepted:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


async def _send_event(
    session_factory: sessionmaker[Session],
    websocket: WebSocket,
    *,
    event_type: Any,
    session_id: str,
    payload: dict,
    request_id: str | None = None,
) -> None:
    household_id = (websocket.query_params.get("household_id") or "").strip()
    seq = await run_blocking_db(
        lambda db: _claim_realtime_event_seq_sync(
            db,
            household_id=household_id,
            session_id=session_id,
        ),
        session_factory=session_factory,
        policy=_build_realtime_policy(label="realtime.endpoint.event_seq"),
        commit=True,
        logger=logger,
        context={"household_id": household_id, "session_id": session_id, "event_type": str(event_type)},
    )
    event = build_bootstrap_realtime_event(
        event_type=event_type,
        session_id=session_id,
        request_id=request_id,
        seq=seq,
        payload=payload,
    )
    await realtime_connection_manager.send_event(websocket, event)


def _claim_realtime_event_seq_sync(
    db: Session,
    *,
    household_id: str,
    session_id: str,
) -> int:
    if household_id:
        bootstrap_session = agent_repository.get_bootstrap_session(db, household_id=household_id, session_id=session_id)
        if bootstrap_session is not None:
            return agent_repository.claim_next_bootstrap_event_seq(db, session=bootstrap_session)

    conversation_session = conversation_repository.get_session(db, session_id)
    if conversation_session is not None:
        return conversation_repository.claim_next_event_seq(db, session=conversation_session)
    return 0


async def _send_error_and_close(
    websocket: WebSocket,
    *,
    session_id: str,
    detail: str,
    error_code: str,
) -> None:
    event = build_bootstrap_realtime_event(
        event_type="agent.error",
        session_id=session_id,
        seq=0,
        payload={"detail": detail, "error_code": error_code},
    )
    await realtime_connection_manager.send_event(websocket, event)
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


def _build_realtime_policy(*, label: str) -> BlockingCallPolicy:
    return BlockingCallPolicy(
        label=label,
        kind="sync_db",
        timeout_seconds=REALTIME_ENDPOINT_DB_TIMEOUT_SECONDS,
    )
