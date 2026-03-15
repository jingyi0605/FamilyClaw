from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationMessageRead
from app.modules.conversation.service import (
    create_conversation_session,
    get_conversation_session_detail,
    run_conversation_realtime_turn,
)
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState

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
        actor = self._build_actor(session=session, identity=identity)
        conversation_session_id = session.conversation_session_id
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

        streamer = _VoiceConversationStreamForwarder(
            voice_session_id=session.session_id,
            terminal_id=session.terminal_id,
        )
        try:
            await run_conversation_realtime_turn(
                db,
                session_id=conversation_session_id,
                request_id=new_uuid(),
                user_message=transcript_text,
                actor=actor,
                connection_manager=streamer,
            )
        except Exception:
            return VoiceConversationBridgeResult(
                conversation_session_id=conversation_session_id,
                response_text="我先收到你的问题了，但这次慢路径处理没跑通，请稍后再试。",
                degraded=True,
                error_code="conversation_bridge_unavailable",
                streaming_playback=False,
            )

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
