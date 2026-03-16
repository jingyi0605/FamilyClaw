from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.conversation.models import ConversationMessage, ConversationSession

from . import repository
from .account_service import (
    ChannelAccountServiceError,
    create_channel_account,
    delete_channel_account,
    get_channel_account_or_404,
    list_channel_accounts,
    update_channel_account,
)
from .binding_service import (
    MemberChannelBindingServiceError,
    create_member_binding,
    delete_channel_account_binding,
    list_member_bindings,
    update_member_binding,
)
from .models import ChannelDelivery, ChannelInboundEvent
from .schemas import (
    ChannelAccountCreate,
    ChannelAccountRead,
    ChannelAccountUpdate,
    ChannelDeliveryCreate,
    ChannelDeliveryRead,
    ChannelInboundEventCreate,
    ChannelInboundEventRead,
    MemberChannelBindingCreate,
    MemberChannelBindingRead,
    MemberChannelBindingUpdate,
)


class ChannelServiceError(ValueError):
    pass


def record_channel_inbound_event(
    db: Session,
    *,
    payload: ChannelInboundEventCreate,
) -> tuple[ChannelInboundEventRead, bool]:
    account = get_channel_account_or_404(
        db,
        household_id=payload.household_id,
        account_id=payload.channel_account_id,
    )
    if payload.conversation_session_id is not None:
        session = db.get(ConversationSession, payload.conversation_session_id)
        if session is None or session.household_id != payload.household_id:
            raise ChannelServiceError("conversation session does not belong to current household")

    existing = repository.get_channel_inbound_event_by_external_event(
        db,
        household_id=payload.household_id,
        channel_account_id=payload.channel_account_id,
        external_event_id=payload.external_event_id,
    )
    if existing is not None:
        return _to_channel_inbound_event_read(existing), False

    row = ChannelInboundEvent(
        id=new_uuid(),
        household_id=payload.household_id,
        channel_account_id=payload.channel_account_id,
        platform_code=account.platform_code,
        external_event_id=payload.external_event_id,
        event_type=payload.event_type,
        external_user_id=payload.external_user_id,
        external_conversation_key=payload.external_conversation_key,
        normalized_payload_json=dump_json(payload.normalized_payload) or "{}",
        status=payload.status,
        conversation_session_id=payload.conversation_session_id,
        error_code=payload.error_code,
        error_message=payload.error_message,
        received_at=payload.received_at or utc_now_iso(),
        processed_at=payload.processed_at,
    )
    repository.add_channel_inbound_event(db, row)
    db.flush()
    return _to_channel_inbound_event_read(row), True


def list_recorded_channel_inbound_events(db: Session, *, household_id: str) -> list[ChannelInboundEventRead]:
    return [_to_channel_inbound_event_read(item) for item in repository.list_channel_inbound_events(db, household_id=household_id)]


def create_channel_delivery(
    db: Session,
    *,
    payload: ChannelDeliveryCreate,
) -> ChannelDeliveryRead:
    account = get_channel_account_or_404(
        db,
        household_id=payload.household_id,
        account_id=payload.channel_account_id,
    )
    if payload.conversation_session_id is not None:
        session = db.get(ConversationSession, payload.conversation_session_id)
        if session is None or session.household_id != payload.household_id:
            raise ChannelServiceError("conversation session does not belong to current household")
    if payload.assistant_message_id is not None:
        message = db.get(ConversationMessage, payload.assistant_message_id)
        if message is None:
            raise ChannelServiceError("assistant message not found")
        if payload.conversation_session_id is not None and message.session_id != payload.conversation_session_id:
            raise ChannelServiceError("assistant message does not belong to target conversation session")

    now = utc_now_iso()
    row = ChannelDelivery(
        id=new_uuid(),
        household_id=payload.household_id,
        channel_account_id=payload.channel_account_id,
        platform_code=account.platform_code,
        conversation_session_id=payload.conversation_session_id,
        assistant_message_id=payload.assistant_message_id,
        external_conversation_key=payload.external_conversation_key,
        delivery_type=payload.delivery_type,
        request_payload_json=dump_json(payload.request_payload) or "{}",
        provider_message_ref=payload.provider_message_ref,
        status=payload.status,
        attempt_count=payload.attempt_count,
        last_error_code=payload.last_error_code,
        last_error_message=payload.last_error_message,
        created_at=now,
        updated_at=now,
    )
    repository.add_channel_delivery(db, row)
    db.flush()
    return _to_channel_delivery_read(row)


def list_channel_delivery_records(db: Session, *, household_id: str) -> list[ChannelDeliveryRead]:
    return [_to_channel_delivery_read(item) for item in repository.list_channel_deliveries(db, household_id=household_id)]


def _to_channel_inbound_event_read(row: ChannelInboundEvent) -> ChannelInboundEventRead:
    payload = load_json(row.normalized_payload_json)
    return ChannelInboundEventRead(
        id=row.id,
        household_id=row.household_id,
        channel_account_id=row.channel_account_id,
        platform_code=row.platform_code,
        external_event_id=row.external_event_id,
        event_type=row.event_type,
        external_user_id=row.external_user_id,
        external_conversation_key=row.external_conversation_key,
        normalized_payload=payload if isinstance(payload, dict) else {},
        status=row.status,
        conversation_session_id=row.conversation_session_id,
        error_code=row.error_code,
        error_message=row.error_message,
        received_at=row.received_at,
        processed_at=row.processed_at,
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


__all__ = [
    "ChannelAccountCreate",
    "ChannelAccountRead",
    "ChannelAccountServiceError",
    "ChannelAccountUpdate",
    "ChannelDeliveryCreate",
    "ChannelDeliveryRead",
    "ChannelInboundEventCreate",
    "ChannelInboundEventRead",
    "ChannelServiceError",
    "MemberChannelBindingCreate",
    "MemberChannelBindingRead",
    "MemberChannelBindingServiceError",
    "MemberChannelBindingUpdate",
    "create_channel_account",
    "create_channel_delivery",
    "create_member_binding",
    "delete_channel_account",
    "delete_channel_account_binding",
    "get_channel_account_or_404",
    "list_channel_accounts",
    "list_channel_delivery_records",
    "list_member_bindings",
    "list_recorded_channel_inbound_events",
    "record_channel_inbound_event",
    "update_channel_account",
    "update_member_binding",
]
