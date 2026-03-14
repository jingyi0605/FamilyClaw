from __future__ import annotations

import json

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.channel import repository
from app.modules.channel.account_service import get_channel_account_or_404
from app.modules.channel.binding_service import resolve_member_binding_for_inbound
from app.modules.channel.models import ChannelConversationBinding
from app.modules.channel.schemas import (
    ChannelConversationBridgeRead,
    ChannelInboundMessage,
)
from app.modules.channel.service import ChannelServiceError
from app.modules.conversation.models import ConversationSession
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn


class ChannelConversationBridgeError(ValueError):
    pass


def handle_inbound_message(
    db,
    *,
    household_id: str,
    channel_account_id: str,
    inbound_event_id: str,
) -> ChannelConversationBridgeRead:
    inbound_event = repository.get_channel_inbound_event(db, inbound_event_id)
    if inbound_event is None or inbound_event.household_id != household_id:
        raise ChannelConversationBridgeError("channel inbound event not found")
    account = get_channel_account_or_404(db, household_id=household_id, account_id=channel_account_id)
    if account.status == "disabled":
        raise ChannelConversationBridgeError("channel account is disabled")
    if inbound_event.event_type != "message":
        raise ChannelConversationBridgeError("only message inbound events can enter conversation bridge")

    normalized_payload = json.loads(inbound_event.normalized_payload_json or "{}")
    normalized_message = ChannelInboundMessage.model_validate(normalized_payload)
    binding = resolve_member_binding_for_inbound(
        db,
        household_id=household_id,
        channel_account_id=channel_account_id,
        external_user_id=inbound_event.external_user_id,
        chat_type=normalized_message.chat_type,
    )

    now = utc_now_iso()
    account.last_inbound_at = now
    account.updated_at = now

    if not binding.matched or binding.member_id is None:
        inbound_event.status = "ignored"
        inbound_event.error_code = "channel_member_binding_not_found"
        inbound_event.error_message = (
            "direct member binding is missing" if binding.strategy == "direct_unbound_prompt" else "group message ignored because member binding is missing"
        )
        inbound_event.processed_at = now
        return ChannelConversationBridgeRead(
            inbound_event_id=inbound_event.id,
            disposition="ignored",
            member_id=None,
            binding_strategy=binding.strategy,
            conversation_session_id=None,
            assistant_message_id=None,
            request_id=None,
            reply_text=binding.reply_text,
            created_session=False,
            created_conversation_binding=False,
        )

    external_conversation_key = _resolve_external_conversation_key(
        inbound_event.external_conversation_key,
        external_user_id=inbound_event.external_user_id,
        chat_type=normalized_message.chat_type,
        thread_key=normalized_message.thread_key,
    )
    conversation_binding, created_conversation_binding, created_session = _get_or_create_conversation_binding(
        db,
        household_id=household_id,
        account=account,
        external_conversation_key=external_conversation_key,
        external_user_id=inbound_event.external_user_id,
        member_id=binding.member_id,
        now=now,
    )

    system_actor = _build_system_actor(household_id=household_id, member_id=binding.member_id)
    turn = create_conversation_turn(
        db,
        session_id=conversation_binding.conversation_session_id,
        payload=ConversationTurnCreate(
            message=normalized_message.text,
            channel=f"channel_{account.platform_code}",
        ),
        actor=system_actor,
    )

    conversation_binding.last_message_at = now
    conversation_binding.updated_at = now
    inbound_event.status = "dispatched"
    inbound_event.conversation_session_id = conversation_binding.conversation_session_id
    inbound_event.processed_at = now

    return ChannelConversationBridgeRead(
        inbound_event_id=inbound_event.id,
        disposition="dispatched",
        member_id=binding.member_id,
        binding_strategy=binding.strategy,
        conversation_session_id=conversation_binding.conversation_session_id,
        assistant_message_id=turn.assistant_message_id,
        request_id=turn.request_id,
        reply_text=_resolve_assistant_message_text(turn),
        created_session=created_session,
        created_conversation_binding=created_conversation_binding,
    )


def _resolve_external_conversation_key(
    external_conversation_key: str | None,
    *,
    external_user_id: str | None,
    chat_type: str,
    thread_key: str | None,
) -> str:
    if isinstance(external_conversation_key, str) and external_conversation_key.strip():
        key = external_conversation_key.strip()
    elif chat_type == "direct" and isinstance(external_user_id, str) and external_user_id.strip():
        key = f"direct:{external_user_id.strip()}"
    else:
        raise ChannelConversationBridgeError("external conversation key is required")
    if isinstance(thread_key, str) and thread_key.strip():
        return f"{key}#thread:{thread_key.strip()}"
    return key


def _get_or_create_conversation_binding(
    db,
    *,
    household_id: str,
    account,
    external_conversation_key: str,
    external_user_id: str | None,
    member_id: str,
    now: str,
) -> tuple[ChannelConversationBinding, bool, bool]:
    existing = repository.get_channel_conversation_binding_by_external_key(
        db,
        household_id=household_id,
        channel_account_id=account.id,
        external_conversation_key=external_conversation_key,
    )
    if existing is not None:
        if existing.status == "disabled":
            raise ChannelConversationBridgeError("channel conversation binding is disabled")
        if existing.member_id is None:
            existing.member_id = member_id
        existing.external_user_id = existing.external_user_id or external_user_id
        existing.last_message_at = now
        existing.updated_at = now
        return existing, False, False

    session = _create_conversation_session_for_channel(
        db,
        household_id=household_id,
        member_id=member_id,
    )
    binding = ChannelConversationBinding(
        id=new_uuid(),
        household_id=household_id,
        channel_account_id=account.id,
        platform_code=account.platform_code,
        external_conversation_key=external_conversation_key,
        external_user_id=external_user_id,
        member_id=member_id,
        conversation_session_id=session.id,
        active_agent_id=session.active_agent_id,
        last_message_at=now,
        status="active",
        created_at=now,
        updated_at=now,
    )
    repository.add_channel_conversation_binding(db, binding)
    db.flush()
    return binding, True, True


def _create_conversation_session_for_channel(
    db,
    *,
    household_id: str,
    member_id: str,
) -> ConversationSession:
    detail = create_conversation_session(
        db,
        payload=ConversationSessionCreate(
            household_id=household_id,
            requester_member_id=member_id,
        ),
        actor=_build_system_actor(household_id=household_id, member_id=member_id),
    )
    session = db.get(ConversationSession, detail.id)
    if session is None:
        raise ChannelServiceError("conversation session not found after creation")
    return session


def _resolve_assistant_message_text(turn) -> str | None:
    for message in turn.session.messages:
        if message.id == turn.assistant_message_id:
            return message.content
    return None


def _build_system_actor(*, household_id: str, member_id: str | None) -> ActorContext:
    return ActorContext(
        role="system",
        actor_type="system",
        actor_id="channel-conversation-bridge",
        account_id="system",
        account_type="system",
        account_status="active",
        username="system",
        household_id=household_id,
        member_id=member_id,
        member_role=None,
        is_authenticated=True,
    )
