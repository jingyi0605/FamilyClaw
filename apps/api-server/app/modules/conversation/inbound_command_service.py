from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.channel import repository as channel_repository
from app.modules.channel.models import ChannelConversationBinding
from app.modules.channel.service import ChannelServiceError
from app.modules.conversation.models import ConversationSession
from app.modules.conversation.schemas import ConversationSessionCreate
_INBOUND_COMMAND_PATTERN = re.compile(r"^/(?P<name>new|reset)(?:@[A-Za-z0-9_]{3,})?$", re.IGNORECASE)

InboundConversationCommandName = Literal["new", "reset"]


@dataclass(frozen=True)
class InboundConversationCommand:
    name: InboundConversationCommandName
    raw_text: str


@dataclass(frozen=True)
class InboundConversationCommandExecutionResult:
    command_name: InboundConversationCommandName
    conversation_session_id: str
    reply_text: str
    created_binding: bool


def parse_inbound_conversation_command(text: str | None) -> InboundConversationCommand | None:
    if text is None:
        return None
    normalized = text.strip()
    if not normalized:
        return None
    matched = _INBOUND_COMMAND_PATTERN.fullmatch(normalized)
    if matched is None:
        return None
    return InboundConversationCommand(
        name=matched.group("name").lower(),  # type: ignore[arg-type]
        raw_text=normalized,
    )


def execute_channel_inbound_command(
    db: Session,
    *,
    household_id: str,
    member_id: str,
    channel_account,
    external_conversation_key: str,
    external_user_id: str | None,
    command: InboundConversationCommand,
) -> InboundConversationCommandExecutionResult:
    now = utc_now_iso()
    session = _create_conversation_session(
        db,
        household_id=household_id,
        member_id=member_id,
        title="新对话",
        actor_id="channel-command-service",
    )
    binding = channel_repository.get_channel_conversation_binding_by_external_key(
        db,
        household_id=household_id,
        channel_account_id=channel_account.id,
        external_conversation_key=external_conversation_key,
    )
    created_binding = False
    if binding is None:
        binding = ChannelConversationBinding(
            id=new_uuid(),
            household_id=household_id,
            channel_account_id=channel_account.id,
            platform_code=channel_account.platform_code,
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
        channel_repository.add_channel_conversation_binding(db, binding)
        created_binding = True
    else:
        if binding.status == "disabled":
            raise ChannelServiceError("channel conversation binding is disabled")
        binding.external_user_id = binding.external_user_id or external_user_id
        binding.member_id = binding.member_id or member_id
        binding.conversation_session_id = session.id
        binding.active_agent_id = session.active_agent_id
        binding.last_message_at = now
        binding.updated_at = now
    db.flush()
    return InboundConversationCommandExecutionResult(
        command_name=command.name,
        conversation_session_id=session.id,
        reply_text=_build_command_reply_text(command),
        created_binding=created_binding,
    )


def execute_voice_terminal_inbound_command(
    db: Session,
    *,
    household_id: str,
    terminal_type: str,
    terminal_code: str,
    member_id: str | None,
    command: InboundConversationCommand,
    title: str,
) -> InboundConversationCommandExecutionResult:
    from app.modules.voice.service import bind_voice_terminal_conversation

    now = utc_now_iso()
    session = _create_conversation_session(
        db,
        household_id=household_id,
        member_id=member_id,
        title=title,
        actor_id="voice-command-service",
    )
    binding = bind_voice_terminal_conversation(
        db,
        household_id=household_id,
        terminal_type=terminal_type,
        terminal_code=terminal_code,
        conversation_session_id=session.id,
        member_id=member_id,
        last_command_at=now,
    )
    return InboundConversationCommandExecutionResult(
        command_name=command.name,
        conversation_session_id=binding.conversation_session_id,
        reply_text=_build_command_reply_text(command),
        created_binding=binding.created_at == binding.updated_at,
    )


def _create_conversation_session(
    db: Session,
    *,
    household_id: str,
    member_id: str | None,
    title: str,
    actor_id: str,
) -> ConversationSession:
    from app.modules.conversation.service import create_conversation_session

    detail = create_conversation_session(
        db,
        payload=ConversationSessionCreate(
            household_id=household_id,
            requester_member_id=member_id,
            title=title,
        ),
        actor=_build_system_actor(
            household_id=household_id,
            member_id=member_id,
            actor_id=actor_id,
        ),
    )
    session = db.get(ConversationSession, detail.id)
    if session is None:
        raise ChannelServiceError("conversation session not found after creation")
    return session


def _build_command_reply_text(command: InboundConversationCommand) -> str:
    if command.name == "reset":
        return "已重置当前上下文，并切换到新会话。"
    return "已开始新会话。"


def _build_system_actor(*, household_id: str, member_id: str | None, actor_id: str) -> ActorContext:
    return ActorContext(
        role="system",
        actor_type="system",
        actor_id=actor_id,
        account_id="system",
        account_type="system",
        account_status="active",
        username="system",
        household_id=household_id,
        member_id=member_id,
        member_role=None,
        is_authenticated=True,
    )
