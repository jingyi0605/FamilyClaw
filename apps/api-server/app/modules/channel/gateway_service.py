from __future__ import annotations

import base64
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.channel.conversation_bridge import (
    ChannelConversationBridgeError,
    handle_inbound_message,
)
from app.modules.channel.conversation_routing import resolve_channel_conversation_route
from app.modules.channel.delivery_service import send_reply
from app.modules.channel import repository
from app.modules.channel.schemas import (
    ChannelGatewayHandleResult,
    ChannelGatewayHttpResponse,
    ChannelGatewayInboundEvent,
    ChannelGatewayWebhookAck,
    ChannelInboundMessage,
    ChannelInboundEventCreate,
    ChannelInboundProcessingRead,
)
from app.modules.channel.service import record_channel_inbound_event
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginExecutionError,
    execute_household_plugin,
)


class ChannelGatewayServiceError(ValueError):
    pass


logger = logging.getLogger(__name__)


def handle_channel_webhook(
    db: Session,
    *,
    account_id: str,
    method: str,
    headers: dict[str, str],
    query_params: dict[str, str],
    body: bytes,
) -> ChannelGatewayHandleResult:
    account = repository.get_channel_plugin_account(db, account_id)
    if account is None:
        raise ChannelGatewayServiceError("channel account not found")
    if account.status == "disabled":
        raise ChannelGatewayServiceError("channel account is disabled")

    execution = execute_household_plugin(
        db,
        household_id=account.household_id,
        request=PluginExecutionRequest(
            plugin_id=account.plugin_id,
            plugin_type="channel",
            payload={
                "action": "webhook",
                "account": {
                    "id": account.id,
                    "household_id": account.household_id,
                    "plugin_id": account.plugin_id,
                    "platform_code": account.platform_code,
                    "account_code": account.account_code,
                    "connection_mode": account.connection_mode,
                    "config": account.config_json,
                },
                "request": {
                    "method": method,
                    "headers": headers,
                    "query_params": query_params,
                    "body_text": body.decode("utf-8", errors="ignore"),
                    "body_base64": base64.b64encode(body).decode("ascii"),
                },
            },
            trigger="channel-webhook",
        ),
    )
    if not execution.success:
        raise PluginExecutionError(execution.error_message or "channel plugin execution failed")
    if not isinstance(execution.output, dict):
        raise ChannelGatewayServiceError("channel plugin must return a JSON object")

    event_payload = execution.output.get("event")
    http_response = _parse_http_response(execution.output.get("http_response"))
    message = execution.output.get("message")
    ack_message = message if isinstance(message, str) and message.strip() else None
    if event_payload is None:
        return ChannelGatewayHandleResult(
            ack=ChannelGatewayWebhookAck(
                accepted=True,
                account_id=account.id,
                plugin_id=account.plugin_id,
                event_recorded=False,
                duplicate=False,
                inbound_event_id=None,
                external_event_id=None,
                status="accepted",
                message=ack_message,
            ),
            http_response=http_response,
        )
    if not isinstance(event_payload, dict):
        raise ChannelGatewayServiceError("channel plugin event payload must be an object")

    normalized_event = ChannelGatewayInboundEvent.model_validate(event_payload)
    inbound_event, created = record_channel_inbound_event(
        db,
        payload=ChannelInboundEventCreate(
            household_id=account.household_id,
            channel_account_id=account.id,
            external_event_id=normalized_event.external_event_id,
            event_type=normalized_event.event_type,
            external_user_id=normalized_event.external_user_id,
            external_conversation_key=normalized_event.external_conversation_key,
            normalized_payload=normalized_event.normalized_payload,
            status=normalized_event.status,
            conversation_session_id=normalized_event.conversation_session_id,
            error_code=normalized_event.error_code,
            error_message=normalized_event.error_message,
            received_at=normalized_event.received_at,
            processed_at=normalized_event.processed_at,
        ),
    )
    if not created:
        return ChannelGatewayHandleResult(
            ack=ChannelGatewayWebhookAck(
                accepted=True,
                account_id=account.id,
                plugin_id=account.plugin_id,
                event_recorded=True,
                duplicate=True,
                inbound_event_id=inbound_event.id,
                external_event_id=inbound_event.external_event_id,
                status="accepted",
                message=ack_message,
                processing_status=inbound_event.status,
                member_id=None,
                conversation_session_id=inbound_event.conversation_session_id,
                assistant_message_id=None,
                reply_text=None,
            ),
            http_response=http_response,
        )

    processing_status = "recorded"
    member_id: str | None = None
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    reply_text: str | None = None
    delivery_id: str | None = None
    delivery_status: str | None = None
    provider_message_ref: str | None = None
    if normalized_event.event_type == "message":
        if http_response is not None and http_response.defer_processing:
            processing_status = "queued"
        else:
            processing = process_channel_inbound_event(
                db,
                account_id=account.id,
                inbound_event_id=inbound_event.id,
            )
            processing_status = processing.processing_status
            member_id = processing.member_id
            conversation_session_id = processing.conversation_session_id
            assistant_message_id = processing.assistant_message_id
            reply_text = processing.reply_text
            delivery_id = processing.delivery_id
            delivery_status = processing.delivery_status
            provider_message_ref = processing.provider_message_ref
    return ChannelGatewayHandleResult(
        ack=ChannelGatewayWebhookAck(
            accepted=True,
            account_id=account.id,
            plugin_id=account.plugin_id,
            event_recorded=True,
            duplicate=not created,
            inbound_event_id=inbound_event.id,
            external_event_id=inbound_event.external_event_id,
            status="accepted",
            message=ack_message,
            processing_status=processing_status,
            member_id=member_id,
            conversation_session_id=conversation_session_id,
            assistant_message_id=assistant_message_id,
            reply_text=reply_text,
            delivery_id=delivery_id,
            delivery_status=delivery_status,
            provider_message_ref=provider_message_ref,
        ),
        http_response=http_response,
    )


def process_channel_inbound_event(
    db: Session,
    *,
    account_id: str,
    inbound_event_id: str,
) -> ChannelInboundProcessingRead:
    account = repository.get_channel_plugin_account(db, account_id)
    if account is None:
        raise ChannelGatewayServiceError("channel account not found")

    inbound_event = repository.get_channel_inbound_event(db, inbound_event_id)
    if inbound_event is None or inbound_event.channel_account_id != account.id:
        raise ChannelGatewayServiceError("channel inbound event not found")
    if inbound_event.event_type != "message":
        return ChannelInboundProcessingRead(
            processing_status=inbound_event.status,
            conversation_session_id=inbound_event.conversation_session_id,
        )
    if inbound_event.status in {"dispatched", "ignored", "failed"}:
        return ChannelInboundProcessingRead(
            processing_status=inbound_event.status,
            conversation_session_id=inbound_event.conversation_session_id,
        )

    try:
        bridge_result = handle_inbound_message(
            db,
            household_id=account.household_id,
            channel_account_id=account.id,
            inbound_event_id=inbound_event.id,
        )
        processing_status = bridge_result.disposition
        member_id = bridge_result.member_id
        conversation_session_id = bridge_result.conversation_session_id
        assistant_message_id = bridge_result.assistant_message_id
        reply_text = bridge_result.reply_text
    except (ChannelConversationBridgeError, ValueError) as exc:
        inbound_event_row = repository.get_channel_inbound_event(db, inbound_event.id)
        if inbound_event_row is not None:
            inbound_event_row.status = "failed"
            inbound_event_row.error_code = "channel_session_binding_failed"
            inbound_event_row.error_message = str(exc)
            inbound_event_row.processed_at = utc_now_iso()
        return ChannelInboundProcessingRead(processing_status="failed")

    delivery_id: str | None = None
    delivery_status: str | None = None
    provider_message_ref: str | None = None
    if reply_text is not None and reply_text.strip():
        try:
            normalized_message = _parse_channel_inbound_message(inbound_event)
            delivery_route = resolve_channel_conversation_route(
                inbound_event.external_conversation_key,
                external_user_id=inbound_event.external_user_id,
                chat_type=normalized_message.chat_type,
                thread_key=normalized_message.thread_key,
            )
            dispatch = send_reply(
                db,
                household_id=account.household_id,
                channel_account_id=account.id,
                external_conversation_key=delivery_route.delivery_conversation_key,
                text=reply_text,
                delivery_type="reply" if member_id is not None else "notice",
                conversation_session_id=conversation_session_id,
                assistant_message_id=assistant_message_id,
                metadata=_extract_delivery_metadata(inbound_event),
            )
            delivery_id = dispatch.delivery.id
            delivery_status = dispatch.delivery.status
            provider_message_ref = dispatch.provider_message_ref
        except ValueError as exc:
            inbound_event_row = repository.get_channel_inbound_event(db, inbound_event.id)
            if inbound_event_row is not None:
                inbound_event_row.status = "failed"
                inbound_event_row.error_code = "channel_delivery_failed"
                inbound_event_row.error_message = str(exc)
                inbound_event_row.processed_at = utc_now_iso()
            return ChannelInboundProcessingRead(
                processing_status="failed",
                member_id=member_id,
                conversation_session_id=conversation_session_id,
                assistant_message_id=assistant_message_id,
                reply_text=reply_text,
            )

    return ChannelInboundProcessingRead(
        processing_status=processing_status,
        member_id=member_id,
        conversation_session_id=conversation_session_id,
        assistant_message_id=assistant_message_id,
        reply_text=reply_text,
        delivery_id=delivery_id,
        delivery_status=delivery_status,
        provider_message_ref=provider_message_ref,
    )


def _extract_delivery_metadata(inbound_event) -> dict[str, Any]:
    try:
        normalized_payload = json.loads(inbound_event.normalized_payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    metadata = normalized_payload.get("metadata") if isinstance(normalized_payload, dict) else None
    return metadata if isinstance(metadata, dict) else {}


def _parse_channel_inbound_message(inbound_event) -> ChannelInboundMessage:
    try:
        normalized_payload = json.loads(inbound_event.normalized_payload_json or "{}")
    except json.JSONDecodeError as exc:
        raise ChannelGatewayServiceError("channel inbound normalized payload is invalid") from exc
    return ChannelInboundMessage.model_validate(normalized_payload)


def _parse_http_response(payload: Any) -> ChannelGatewayHttpResponse | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ChannelGatewayServiceError("channel plugin http_response must be an object")
    return ChannelGatewayHttpResponse.model_validate(payload)
