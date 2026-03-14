from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.channel.gateway_service import ChannelGatewayServiceError, handle_channel_webhook
from app.modules.channel.schemas import ChannelGatewayWebhookAck
from app.modules.plugin.service import PluginExecutionError


router = APIRouter(prefix="/channel-gateways", tags=["channel-gateways"])


@router.post("/accounts/{account_id}/webhook", response_model=ChannelGatewayWebhookAck)
async def channel_gateway_webhook_endpoint(
    account_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ChannelGatewayWebhookAck:
    try:
        ack = handle_channel_webhook(
            db,
            account_id=account_id,
            method=request.method,
            headers={key: value for key, value in request.headers.items()},
            query_params={key: value for key, value in request.query_params.items()},
            body=await request.body(),
        )
        db.commit()
        return ack
    except ChannelGatewayServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PluginExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
