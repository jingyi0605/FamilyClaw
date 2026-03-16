from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.utils import new_uuid, utc_now_iso
from app.modules.voice import repository
from app.modules.voice.models import VoiceTerminalConversationBinding
from app.modules.voice.registry import VoiceTerminalState


def resolve_voice_terminal_binding_key(*, terminal: VoiceTerminalState) -> tuple[str, str]:
    terminal_type = (terminal.adapter_type or "voice_terminal").strip() or "voice_terminal"
    terminal_code = (terminal.terminal_code or terminal.terminal_id).strip()
    return terminal_type, terminal_code


def get_active_voice_terminal_conversation_binding(
    db: Session,
    *,
    household_id: str,
    terminal_type: str,
    terminal_code: str,
) -> VoiceTerminalConversationBinding | None:
    binding = repository.get_voice_terminal_conversation_binding(
        db,
        household_id=household_id,
        terminal_type=terminal_type,
        terminal_code=terminal_code,
    )
    if binding is None or binding.binding_status == "disabled":
        return None
    return binding


def bind_voice_terminal_conversation(
    db: Session,
    *,
    household_id: str,
    terminal_type: str,
    terminal_code: str,
    conversation_session_id: str,
    member_id: str | None,
    last_message_at: str | None = None,
    last_command_at: str | None = None,
) -> VoiceTerminalConversationBinding:
    now = utc_now_iso()
    binding = repository.get_voice_terminal_conversation_binding(
        db,
        household_id=household_id,
        terminal_type=terminal_type,
        terminal_code=terminal_code,
    )
    if binding is None:
        binding = VoiceTerminalConversationBinding(
            id=new_uuid(),
            household_id=household_id,
            terminal_type=terminal_type,
            terminal_code=terminal_code,
            member_id=member_id,
            conversation_session_id=conversation_session_id,
            binding_status="active",
            last_command_at=last_command_at,
            last_message_at=last_message_at,
            created_at=now,
            updated_at=now,
        )
        repository.add_voice_terminal_conversation_binding(db, binding)
        db.flush()
        return binding

    if member_id is not None:
        binding.member_id = member_id
    binding.conversation_session_id = conversation_session_id
    binding.binding_status = "active"
    if last_command_at is not None:
        binding.last_command_at = last_command_at
    if last_message_at is not None:
        binding.last_message_at = last_message_at
    binding.updated_at = now
    db.flush()
    return binding
