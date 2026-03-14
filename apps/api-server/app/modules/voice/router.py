from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.voice.fast_action_service import VoiceRouteDecision, voice_fast_action_service


class VoiceRouter:
    """先做最小路由器，后续再把身份融合和更细规则接进来。"""

    async def route(self, db: Session, *, household_id: str, transcript_text: str) -> VoiceRouteDecision:
        return await voice_fast_action_service.resolve(
            db,
            household_id=household_id,
            transcript_text=transcript_text,
        )


voice_router = VoiceRouter()
