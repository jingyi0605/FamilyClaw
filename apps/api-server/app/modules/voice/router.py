from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.modules.context.service import get_context_overview
from app.modules.voice.fast_action_service import VoiceRouteDecision, voice_fast_action_service
from app.modules.voice.identity_service import VoiceIdentityResolution, voice_identity_service
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: VoiceRouteDecision
    identity: VoiceIdentityResolution


class VoiceRouter:
    """先把上下文、身份和快路径解析收进同一个保守路由口。"""

    async def route(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
    ) -> VoiceRoutingResult:
        context_overview = get_context_overview(db, session.household_id)
        identity = await voice_identity_service.resolve(
            db,
            household_id=session.household_id,
            session=session,
            terminal=terminal,
            transcript_text=transcript_text,
            context_overview=context_overview,
            audio_artifact_path=session.audio_file_path,
        )
        decision = await voice_fast_action_service.resolve(
            db,
            household_id=session.household_id,
            transcript_text=transcript_text,
            context_overview=context_overview,
            terminal=terminal,
            session=session,
            identity=identity,
        )
        return VoiceRoutingResult(decision=decision, identity=identity)


voice_router = VoiceRouter()
