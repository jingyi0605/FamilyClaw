from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.channel import repository
from app.modules.channel.account_service import get_channel_account_or_404
from app.modules.channel.models import ChannelDelivery
from app.modules.channel.schemas import (
    ChannelDeliveryCreate,
    ChannelDeliveryDispatchRead,
    ChannelDeliveryFailureSummaryRead,
    ChannelDeliveryRead,
)
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginExecutionError,
    execute_plugin,
    resolve_plugin_execution_context,
)


class ChannelDeliveryServiceError(ValueError):
    pass


def send_reply(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_conversation_key: str,
    text: str,
    delivery_type: str = "reply",
    conversation_session_id: str | None = None,
    assistant_message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChannelDeliveryDispatchRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=channel_account_id)
    now = utc_now_iso()

    delivery = ChannelDelivery(
        id=new_uuid(),
        household_id=household_id,
        channel_account_id=account.id,
        platform_code=account.platform_code,
        conversation_session_id=conversation_session_id,
        assistant_message_id=assistant_message_id,
        external_conversation_key=external_conversation_key,
        delivery_type=delivery_type,
        request_payload_json=dump_json(
            {
                "text": text,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )
        or "{}",
        provider_message_ref=None,
        status="pending",
        attempt_count=0,
        last_error_code=None,
        last_error_message=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_channel_delivery(db, delivery)
    db.flush()
    return _dispatch_delivery(db, delivery=delivery, text=text)


def retry_delivery(
    db: Session,
    *,
    household_id: str,
    delivery_id: str,
) -> ChannelDeliveryDispatchRead:
    delivery = repository.get_channel_delivery(db, delivery_id)
    if delivery is None or delivery.household_id != household_id:
        raise ChannelDeliveryServiceError("channel delivery not found")
    payload = load_json(delivery.request_payload_json)
    text = payload.get("text") if isinstance(payload, dict) else None
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise ChannelDeliveryServiceError("channel delivery payload does not contain text")
    return _dispatch_delivery(
        db,
        delivery=delivery,
        text=text,
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _dispatch_delivery(
    db: Session,
    *,
    delivery: ChannelDelivery,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> ChannelDeliveryDispatchRead:
    account = get_channel_account_or_404(db, household_id=delivery.household_id, account_id=delivery.channel_account_id)
    delivery.attempt_count += 1
    delivery.updated_at = utc_now_iso()

    if account.status == "disabled":
        delivery.status = "skipped"
        delivery.last_error_code = "channel_account_disabled"
        delivery.last_error_message = "channel account is disabled"
        db.flush()
        return ChannelDeliveryDispatchRead(
            delivery=_to_channel_delivery_read(delivery),
            sent=False,
            provider_message_ref=None,
        )

    execution_context = resolve_plugin_execution_context(
        db,
        household_id=account.household_id,
        plugin_id=account.plugin_id,
    )
    execution = execute_plugin(
        PluginExecutionRequest(
            plugin_id=account.plugin_id,
            plugin_type="channel",
            payload={
                "action": "send",
                "account": {
                    "id": account.id,
                    "household_id": account.household_id,
                    "plugin_id": account.plugin_id,
                    "platform_code": account.platform_code,
                    "account_code": account.account_code,
                    "connection_mode": account.connection_mode,
                    "config": account.config_json,
                },
                "delivery": {
                    "delivery_id": delivery.id,
                    "delivery_type": delivery.delivery_type,
                    "external_conversation_key": delivery.external_conversation_key,
                    "conversation_session_id": delivery.conversation_session_id,
                    "assistant_message_id": delivery.assistant_message_id,
                    "text": text,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                },
            },
            trigger="channel-delivery",
        ),
        root_dir=execution_context.root_dir,
        source_type=execution_context.source_type,
        execution_backend=execution_context.execution_backend,
        runner_config=execution_context.runner_config,
    )

    if not execution.success:
        delivery.status = "failed"
        delivery.last_error_code = execution.error_code or "channel_delivery_failed"
        delivery.last_error_message = execution.error_message or "channel delivery failed"
        delivery.updated_at = utc_now_iso()
        db.flush()
        return ChannelDeliveryDispatchRead(
            delivery=_to_channel_delivery_read(delivery),
            sent=False,
            provider_message_ref=None,
        )

    output = execution.output if isinstance(execution.output, dict) else {}
    provider_message_ref = output.get("provider_message_ref")
    delivery.status = "sent"
    delivery.provider_message_ref = provider_message_ref if isinstance(provider_message_ref, str) and provider_message_ref.strip() else None
    delivery.last_error_code = None
    delivery.last_error_message = None
    delivery.updated_at = utc_now_iso()
    account.last_outbound_at = delivery.updated_at
    account.updated_at = delivery.updated_at
    db.flush()
    return ChannelDeliveryDispatchRead(
        delivery=_to_channel_delivery_read(delivery),
        sent=True,
        provider_message_ref=delivery.provider_message_ref,
    )


def _to_channel_delivery_read(row: ChannelDelivery) -> ChannelDeliveryRead:
    payload = load_json(row.request_payload_json)
    return ChannelDeliveryRead(
        id=row.id,
        household_id=row.household_id,
        channel_account_id=row.channel_account_id,
        platform_code=row.platform_code,
        conversation_session_id=row.conversation_session_id,
        assistant_message_id=row.assistant_message_id,
        external_conversation_key=row.external_conversation_key,
        delivery_type=row.delivery_type,
        request_payload=payload if isinstance(payload, dict) else {},
        provider_message_ref=row.provider_message_ref,
        status=row.status,
        attempt_count=row.attempt_count,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
