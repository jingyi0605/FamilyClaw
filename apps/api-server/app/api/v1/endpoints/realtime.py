from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household
from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.account.service import resolve_authenticated_actor_by_session_token
from app.modules.agent import repository as agent_repository
from app.modules.agent.bootstrap_service import (
    get_butler_bootstrap_session_snapshot,
    run_butler_bootstrap_realtime_turn,
)
from app.modules.realtime.connection_manager import realtime_connection_manager
from app.modules.realtime.schemas import BootstrapRealtimeClientEvent, build_bootstrap_realtime_event

router = APIRouter(tags=["realtime"])


@router.websocket("/realtime/agent-bootstrap")
async def realtime_agent_bootstrap_websocket(websocket: WebSocket) -> None:
    household_id = (websocket.query_params.get("household_id") or "").strip()
    session_id = (websocket.query_params.get("session_id") or "").strip()

    db: Session = SessionLocal()
    accepted = False
    try:
        actor = _authenticate_websocket_actor(db, websocket)
        ensure_actor_can_access_household(actor, household_id)

        session = agent_repository.get_bootstrap_session(db, household_id=household_id, session_id=session_id)
        if session is None:
            await websocket.accept()
            accepted = True
            await _send_error_and_close(
                db,
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
            db,
            websocket,
            event_type="session.ready",
            session_id=session_id,
            payload={},
        )
        snapshot = get_butler_bootstrap_session_snapshot(db, household_id=household_id, session_id=session_id)
        await _send_event(
            db,
            websocket,
            event_type="session.snapshot",
            session_id=session_id,
            payload={"snapshot": snapshot.model_dump(mode="json")},
        )

        while True:
            client_event = BootstrapRealtimeClientEvent.model_validate(await websocket.receive_json())
            if client_event.session_id != session_id:
                await _send_event(
                    db,
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
                    db,
                    websocket,
                    event_type="pong",
                    session_id=session_id,
                    payload={"nonce": ping_payload.get("nonce")},
                )
                continue

            if client_event.type == "user.message":
                message_payload = cast(dict[str, Any], client_event.payload.model_dump(mode="json"))
                await run_butler_bootstrap_realtime_turn(
                    db,
                    household_id=household_id,
                    session_id=session_id,
                    request_id=client_event.request_id or "",
                    user_message=str(message_payload.get("text") or ""),
                    connection_manager=realtime_connection_manager,
                )
                continue

            await _send_event(
                db,
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
        if accepted:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        else:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    finally:
        if accepted and household_id and session_id:
            realtime_connection_manager.unregister(household_id=household_id, session_id=session_id, websocket=websocket)
        db.close()


def _authenticate_websocket_actor(db: Session, websocket: WebSocket) -> ActorContext:
    session_token = _extract_session_token(websocket)
    actor = resolve_authenticated_actor_by_session_token(db, session_token)
    if actor is None:
        raise PermissionError("authentication required")

    actor_context = ActorContext.from_authenticated_actor(actor)
    if actor_context.role != "admin":
        raise PermissionError("admin role required")
    return actor_context


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


async def _send_event(
    db: Session,
    websocket: WebSocket,
    *,
    event_type: Any,
    session_id: str,
    payload: dict,
    request_id: str | None = None,
) -> None:
    session = agent_repository.get_bootstrap_session(db, household_id=(websocket.query_params.get("household_id") or "").strip(), session_id=session_id)
    if session is None:
        seq = 0
    else:
        seq = agent_repository.claim_next_bootstrap_event_seq(db, session=session)
        db.commit()
    event = build_bootstrap_realtime_event(
        event_type=event_type,
        session_id=session_id,
        request_id=request_id,
        seq=seq,
        payload=payload,
    )
    await realtime_connection_manager.send_event(websocket, event)


async def _send_error_and_close(
    db: Session,
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
