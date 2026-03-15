from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import acreate_conversation_turn, create_conversation_session
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceConversationBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_session_id: str
    response_text: str
    degraded: bool = False
    error_code: str | None = None


class VoiceConversationBridge:
    """慢路径直接复用现有 conversation 会话和 turn，不再只是挂一个空会话。"""

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

        try:
            turn = await acreate_conversation_turn(
                db,
                session_id=conversation_session_id,
                payload=ConversationTurnCreate(
                    message=transcript_text,
                    channel="voice_terminal",
                ),
                actor=actor,
            )
        except Exception:
            return VoiceConversationBridgeResult(
                conversation_session_id=conversation_session_id,
                response_text="我先收到你的问题了，但这次慢路径处理没跑通，请稍后再试。",
                degraded=True,
                error_code="conversation_bridge_unavailable",
            )

        assistant_message = next(
            (
                item
                for item in reversed(turn.session.messages)
                if item.role == "assistant" and item.content.strip()
            ),
            None,
        )
        response_text = assistant_message.content if assistant_message is not None else turn.error_message
        if not response_text:
            response_text = "我已经收到你的请求，但这轮还没有产出可播报的回复。"

        return VoiceConversationBridgeResult(
            conversation_session_id=conversation_session_id,
            response_text=response_text,
            degraded=turn.outcome != "completed",
            error_code=None if turn.outcome == "completed" else "conversation_bridge_unavailable",
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


voice_conversation_bridge = VoiceConversationBridge()
