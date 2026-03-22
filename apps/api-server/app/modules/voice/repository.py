from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.voice.models import SpeakerRuntimeState, VoiceTerminalConversationBinding


def add_voice_terminal_conversation_binding(
    db: Session,
    row: VoiceTerminalConversationBinding,
) -> VoiceTerminalConversationBinding:
    db.add(row)
    return row


def get_voice_terminal_conversation_binding(
    db: Session,
    *,
    household_id: str,
    terminal_type: str,
    terminal_code: str,
) -> VoiceTerminalConversationBinding | None:
    stmt: Select[tuple[VoiceTerminalConversationBinding]] = select(VoiceTerminalConversationBinding).where(
        VoiceTerminalConversationBinding.household_id == household_id,
        VoiceTerminalConversationBinding.terminal_type == terminal_type,
        VoiceTerminalConversationBinding.terminal_code == terminal_code,
    )
    return db.scalar(stmt)


def list_voice_terminal_conversation_bindings(
    db: Session,
    *,
    household_id: str,
) -> list[VoiceTerminalConversationBinding]:
    stmt: Select[tuple[VoiceTerminalConversationBinding]] = (
        select(VoiceTerminalConversationBinding)
        .where(VoiceTerminalConversationBinding.household_id == household_id)
        .order_by(VoiceTerminalConversationBinding.created_at.asc(), VoiceTerminalConversationBinding.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_speaker_runtime_state(
    db: Session,
    row: SpeakerRuntimeState,
) -> SpeakerRuntimeState:
    db.add(row)
    return row


def get_speaker_runtime_state_by_integration_instance(
    db: Session,
    *,
    integration_instance_id: str,
) -> SpeakerRuntimeState | None:
    stmt: Select[tuple[SpeakerRuntimeState]] = select(SpeakerRuntimeState).where(
        SpeakerRuntimeState.integration_instance_id == integration_instance_id,
    )
    return db.scalar(stmt)
