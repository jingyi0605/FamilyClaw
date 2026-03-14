from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import create_conversation_session
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceConversationBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_session_id: str
    response_text: str
    degraded: bool = True


class VoiceConversationBridge:
    """慢路径最小接缝，先把语音会话正式挂到 conversation session。"""

    async def bridge(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
    ) -> VoiceConversationBridgeResult:
        actor = ActorContext(
            role="admin",
            actor_type="system",
            actor_id="voice_pipeline",
            account_type="system",
            account_status="active",
            household_id=session.household_id,
            member_id=None,
            is_authenticated=True,
        )
        conversation_session = create_conversation_session(
            db,
            payload=ConversationSessionCreate(
                household_id=session.household_id,
                requester_member_id=None,
                session_mode="family_chat",
                title=f"语音会话 {terminal.name or session.terminal_id}",
            ),
            actor=actor,
        )
        return VoiceConversationBridgeResult(
            conversation_session_id=conversation_session.id,
            response_text=f"已收到你的语音请求：{transcript_text}。慢路径桥接已建立，后续接入完整对话主链。",
            degraded=True,
        )


voice_conversation_bridge = VoiceConversationBridge()
