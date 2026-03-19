from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.conversation.inbound_command_service import (
    execute_voice_terminal_inbound_command,
    parse_inbound_conversation_command,
)
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationMessageRead
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voice.service import (
    bind_voice_terminal_conversation,
    get_active_voice_terminal_conversation_binding,
    resolve_voice_terminal_binding_key,
)

_STREAM_SENTENCE_ENDINGS = frozenset({"。", "！", "？", "!", "?", "；", ";"})


class VoiceConversationBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_session_id: str
    response_text: str
    degraded: bool = False
    error_code: str | None = None
    streaming_playback: bool = False


class _VoiceConversationStreamForwarder:
    def __init__(self, *, voice_session_id: str, terminal_id: str) -> None:
        self._voice_session_id = voice_session_id
        self._terminal_id = terminal_id
        self._buffer = ""
        self._streaming_playback = False

    @property
    def streaming_playback(self) -> bool:
        return self._streaming_playback

    async def broadcast(self, *, household_id: str, session_id: str, event) -> None:
        _ = household_id
        _ = session_id
        if event.type == "agent.chunk":
            self._buffer += str(event.payload.text)
            await self._flush_ready_segments()
            return
        if event.type in {"agent.done", "agent.error"}:
            await self._flush_ready_segments(flush_tail=True)

    async def _flush_ready_segments(self, *, flush_tail: bool = False) -> None:
        from app.modules.voice.playback_service import voice_playback_service

        segments, self._buffer = _split_tts_segments(self._buffer, flush_tail=flush_tail)
        for segment in segments:
            await voice_playback_service.start_text_playback(
                session_id=self._voice_session_id,
                terminal_id=self._terminal_id,
                text=segment,
            )
            self._streaming_playback = True


class VoiceConversationBridge:
    """语音慢路径复用会话系统，并在有句子落地时尽快开始播报。"""

    async def bridge(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
        identity: VoiceIdentityResolution | None = None,
    ) -> VoiceConversationBridgeResult:
        from app.modules.conversation.service import (
            append_conversation_debug_log,
            conversation_turn_exists,
            create_conversation_session,
            get_conversation_session_detail,
            record_conversation_turn_source,
            run_conversation_realtime_turn,
        )

        actor = self._build_actor(session=session, identity=identity)
        terminal_type, terminal_code = resolve_voice_terminal_binding_key(terminal=terminal)
        inbound_command = parse_inbound_conversation_command(transcript_text)
        if inbound_command is not None:
            command_result = execute_voice_terminal_inbound_command(
                db,
                household_id=session.household_id,
                terminal_type=terminal_type,
                terminal_code=terminal_code,
                member_id=identity.primary_member_id if identity is not None else None,
                command=inbound_command,
                title=f"语音会话 {terminal.name or session.terminal_id}",
            )
            return VoiceConversationBridgeResult(
                conversation_session_id=command_result.conversation_session_id,
                response_text=command_result.reply_text,
                degraded=False,
                error_code=None,
                streaming_playback=False,
            )
        conversation_session_id = session.conversation_session_id
        if not conversation_session_id:
            existing_binding = get_active_voice_terminal_conversation_binding(
                db,
                household_id=session.household_id,
                terminal_type=terminal_type,
                terminal_code=terminal_code,
            )
            if existing_binding is not None:
                conversation_session_id = existing_binding.conversation_session_id
        if not conversation_session_id:
            conversation_session = create_conversation_session(
                db,
                payload=ConversationSessionCreate(
                    household_id=session.household_id,
                    requester_member_id=identity.primary_member_id if identity is not None else None,
                    session_mode="family_chat",
                    title=f"语音会话 {terminal.name or session.terminal_id}",
                ),
                actor=actor,
            )
            conversation_session_id = conversation_session.id
        bind_voice_terminal_conversation(
            db,
            household_id=session.household_id,
            terminal_type=terminal_type,
            terminal_code=terminal_code,
            conversation_session_id=conversation_session_id,
            member_id=identity.primary_member_id if identity is not None else None,
            last_message_at=utc_now_iso(),
        )

        streamer = _VoiceConversationStreamForwarder(
            voice_session_id=session.session_id,
            terminal_id=session.terminal_id,
        )
        request_id = new_uuid()
        append_conversation_debug_log(
            db,
            session_id=conversation_session_id,
            request_id=request_id,
            stage="voice.identity.resolved",
            source="voice",
            message="已完成声纹识别与身份决策。",
            payload=_build_voice_identity_debug_payload(
                session=session,
                terminal=terminal,
                terminal_code=terminal_code,
                transcript_text=transcript_text,
                identity=identity,
            ),
        )

        def _record_voice_turn_source() -> None:
            record_conversation_turn_source(
                db,
                conversation_session_id=conversation_session_id,
                conversation_turn_id=request_id,
                source_kind="voice_terminal",
                platform_code=terminal.adapter_type or "voice_terminal",
                voice_terminal_code=terminal_code,
            )

        try:
            await run_conversation_realtime_turn(
                db,
                session_id=conversation_session_id,
                request_id=request_id,
                user_message=transcript_text,
                actor=actor,
                connection_manager=streamer,
            )
        except Exception:
            if conversation_turn_exists(
                db,
                conversation_session_id=conversation_session_id,
                conversation_turn_id=request_id,
            ):
                _record_voice_turn_source()
            return VoiceConversationBridgeResult(
                conversation_session_id=conversation_session_id,
                response_text="我先收到你的问题了，但这次慢路径处理没跑通，请稍后再试。",
                degraded=True,
                error_code="conversation_bridge_unavailable",
                streaming_playback=False,
            )
        _record_voice_turn_source()

        session_detail = get_conversation_session_detail(
            db,
            session_id=conversation_session_id,
            actor=actor,
        )
        assistant_message = _find_latest_assistant_message(session_detail.messages)
        if assistant_message is None:
            return VoiceConversationBridgeResult(
                conversation_session_id=conversation_session_id,
                response_text="我已经收到你的请求，但这轮还没有产出可播报的回复。",
                degraded=True,
                error_code="conversation_bridge_unavailable",
                streaming_playback=streamer.streaming_playback,
            )

        response_text = assistant_message.content.strip()
        if not response_text:
            response_text = "我已经收到你的请求，但这轮还没有产出可播报的回复。"

        error_code = assistant_message.error_code
        degraded = assistant_message.status != "completed" or assistant_message.degraded
        if degraded and error_code is None:
            error_code = "conversation_bridge_unavailable"

        return VoiceConversationBridgeResult(
            conversation_session_id=conversation_session_id,
            response_text=response_text,
            degraded=degraded,
            error_code=error_code,
            streaming_playback=streamer.streaming_playback,
        )

    def _build_actor(
        self,
        *,
        session: VoiceSessionState,
        identity: VoiceIdentityResolution | None,
    ) -> ActorContext:
        member_id = identity.primary_member_id if identity is not None else None
        member_role = identity.primary_member_role if identity is not None else None
        return ActorContext(
            role="admin",
            actor_type="system",
            actor_id="voice_pipeline",
            account_type="system",
            account_status="active",
            household_id=session.household_id,
            member_id=member_id,
            member_role=member_role,
            is_authenticated=True,
        )


def _find_latest_assistant_message(messages: list[ConversationMessageRead]) -> ConversationMessageRead | None:
    for item in reversed(messages):
        if item.role != "assistant":
            continue
        if item.status == "pending":
            continue
        return item
    return None


def _build_voice_identity_debug_payload(
    *,
    session: VoiceSessionState,
    terminal: VoiceTerminalState,
    terminal_code: str | None,
    transcript_text: str,
    identity: VoiceIdentityResolution | None,
) -> dict[str, object]:
    if identity is None:
        return {
            "voice_session_id": session.session_id,
            "terminal_id": session.terminal_id,
            "terminal_code": terminal_code,
            "terminal_name": terminal.name,
            "transcript_text": transcript_text,
            "identity_status": None,
            "requester_member_id": None,
            "requester_member_name": None,
            "requester_member_role": None,
            "speaker_confidence": None,
            "identity_reason": None,
            "context_conflict": None,
            "voiceprint_hint": None,
            "candidates": [],
        }

    return {
        "voice_session_id": session.session_id,
        "terminal_id": session.terminal_id,
        "terminal_code": terminal_code,
        "terminal_name": terminal.name,
        "transcript_text": transcript_text,
        "identity_status": identity.status,
        "requester_member_id": identity.primary_member_id,
        "requester_member_name": identity.primary_member_name,
        "requester_member_role": identity.primary_member_role,
        "speaker_confidence": identity.confidence,
        "identity_reason": identity.reason,
        "context_conflict": identity.context_conflict,
        "voiceprint_hint": identity.voiceprint_hint.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in identity.candidates],
    }


def _split_tts_segments(text: str, *, flush_tail: bool) -> tuple[list[str], str]:
    normalized = text.strip()
    if not normalized:
        return [], ""

    segments: list[str] = []
    last_index = 0
    for index, char in enumerate(normalized):
        if char not in _STREAM_SENTENCE_ENDINGS:
            continue
        segment = normalized[last_index : index + 1].strip()
        if segment:
            segments.append(segment)
        last_index = index + 1

    remainder = normalized[last_index:].strip()
    if flush_tail and remainder:
        segments.append(remainder)
        remainder = ""
    return segments, remainder


voice_conversation_bridge = VoiceConversationBridge()
