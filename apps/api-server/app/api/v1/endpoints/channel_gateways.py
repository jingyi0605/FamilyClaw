from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.modules.channel.gateway_service import (
    ChannelGatewayServiceError,
    handle_channel_webhook,
    process_channel_inbound_event,
)
from app.modules.channel.schemas import ChannelGatewayHttpResponse, ChannelGatewayWebhookAck
from app.modules.plugin.service import PluginExecutionError


router = APIRouter(prefix="/channel-gateways", tags=["channel-gateways"])
logger = logging.getLogger(__name__)


@router.api_route("/accounts/{account_id}/webhook", methods=["GET", "POST"], response_model=ChannelGatewayWebhookAck)
async def channel_gateway_webhook_endpoint(
    account_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ChannelGatewayWebhookAck | Response:
    try:
        result = handle_channel_webhook(
            db,
            account_id=account_id,
            method=request.method,
            headers={key: value for key, value in request.headers.items()},
            query_params={key: value for key, value in request.query_params.items()},
            body=await request.body(),
        )
        if (
            result.http_response is not None
            and result.http_response.defer_processing
            and result.ack.event_recorded
            and not result.ack.duplicate
            and result.ack.inbound_event_id is not None
        ):
            session_factory = sessionmaker(
                bind=db.get_bind(),
                autoflush=False,
                autocommit=False,
                future=True,
                class_=Session,
            )
            background_tasks.add_task(
                _process_channel_inbound_event_in_background,
                session_factory,
                account_id,
                result.ack.inbound_event_id,
            )
        db.commit()
        if result.http_response is not None:
            return _build_http_response(result.http_response)
        return result.ack
    except ChannelGatewayServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PluginExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _build_http_response(http_response: ChannelGatewayHttpResponse) -> Response:
    if http_response.body_json is not None:
        return JSONResponse(
            content=http_response.body_json,
            status_code=http_response.status_code,
            headers=http_response.headers,
        )
    return Response(
        content=http_response.body_text or "",
        status_code=http_response.status_code,
        headers=http_response.headers,
        media_type=http_response.media_type or "text/plain",
    )


def _process_channel_inbound_event_in_background(session_factory, account_id: str, inbound_event_id: str) -> None:
    db = session_factory()
    try:
        process_channel_inbound_event(
            db,
            account_id=account_id,
            inbound_event_id=inbound_event_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "channel gateway background processing failed account_id=%s inbound_event_id=%s",
            account_id,
            inbound_event_id,
        )
    finally:
        db.close()
