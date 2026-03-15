from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.modules.context.schemas import ContextOverviewMemberState, ContextOverviewRead
from app.modules.context.service import get_context_overview
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState
from app.modules.voiceprint.service import VoiceprintIdentificationRead, identify_household_member_by_voiceprint

VoiceIdentityStatus = Literal["resolved", "anonymous", "conflict", "degraded"]


class VoiceIdentityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
    name: str
    role: str
    confidence: float = Field(ge=0, le=1)
    current_room_id: str | None = None
    current_room_name: str | None = None
    reasons: list[str] = Field(default_factory=list)


class VoiceIdentityVoiceprintCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
    profile_id: str
    score: float = Field(ge=0, le=1)


class VoiceIdentityVoiceprintHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    status: str = "not_attempted"
    member_id: str | None = None
    profile_id: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    threshold: float | None = Field(default=None, ge=0, le=1)
    reason: str = "当前还没尝试声纹识别。"
    candidate_count: int = Field(default=0, ge=0)
    candidates: list[VoiceIdentityVoiceprintCandidate] = Field(default_factory=list)


class VoiceIdentityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VoiceIdentityStatus
    primary_member_id: str | None = None
    primary_member_name: str | None = None
    primary_member_role: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    inferred_room_id: str | None = None
    inferred_room_name: str | None = None
    context_conflict: bool = False
    reason: str
    candidates: list[VoiceIdentityCandidate] = Field(default_factory=list)
    voiceprint_hint: VoiceIdentityVoiceprintHint = Field(default_factory=VoiceIdentityVoiceprintHint)


class VoiceIdentityService:
    """先把终端、房间、活跃成员和在家状态收成一个最小身份结果。"""

    async def resolve(
        self,
        db: Session,
        *,
        household_id: str,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
        context_overview: ContextOverviewRead | None = None,
        audio_artifact_path: str | None = None,
    ) -> VoiceIdentityResolution:
        overview = context_overview or get_context_overview(db, household_id)
        normalized_text = transcript_text.strip()
        active_member_id = overview.active_member.member_id if overview.active_member is not None else None
        terminal_room_id = session.room_id or terminal.room_id
        voiceprint_hint = self._build_voiceprint_hint(
            identify_household_member_by_voiceprint(
                db,
                household_id=household_id,
                artifact_path=audio_artifact_path,
            )
            if audio_artifact_path
            else None
        )

        if voiceprint_hint.status == "matched" and voiceprint_hint.member_id:
            voiceprint_member = self._find_member_state(overview, voiceprint_hint.member_id)
            inferred_room_id = terminal_room_id
            inferred_room_name = self._find_room_name(overview, terminal_room_id)
            if voiceprint_member is not None and inferred_room_id is None:
                inferred_room_id = voiceprint_member.current_room_id
                inferred_room_name = voiceprint_member.current_room_name

            return VoiceIdentityResolution(
                status="resolved",
                primary_member_id=voiceprint_hint.member_id,
                primary_member_name=voiceprint_member.name if voiceprint_member is not None else None,
                primary_member_role=voiceprint_member.role if voiceprint_member is not None else None,
                confidence=voiceprint_hint.score or 0,
                inferred_room_id=inferred_room_id,
                inferred_room_name=inferred_room_name,
                context_conflict=False,
                reason="声纹识别已命中家庭成员，当前优先使用声纹结果。",
                candidates=(
                    [
                        VoiceIdentityCandidate(
                            member_id=voiceprint_member.member_id,
                            name=voiceprint_member.name,
                            role=voiceprint_member.role,
                            confidence=voiceprint_hint.score or 0,
                            current_room_id=voiceprint_member.current_room_id,
                            current_room_name=voiceprint_member.current_room_name,
                            reasons=["声纹识别命中", voiceprint_hint.reason],
                        )
                    ]
                    if voiceprint_member is not None
                    else []
                ),
                voiceprint_hint=voiceprint_hint,
            )

        candidates = [
            self._build_candidate(
                member=member,
                transcript_text=normalized_text,
                terminal_room_id=terminal_room_id,
                active_member_id=active_member_id,
            )
            for member in overview.member_states
        ]
        candidates = [candidate for candidate in candidates if candidate.confidence > 0]
        candidates.sort(key=lambda item: (item.confidence, item.name), reverse=True)

        inferred_room_id = terminal_room_id
        inferred_room_name = self._find_room_name(overview, terminal_room_id)
        if inferred_room_id is None and overview.active_member is not None:
            inferred_room_id = overview.active_member.current_room_id
            inferred_room_name = overview.active_member.current_room_name

        if not candidates:
            return VoiceIdentityResolution(
                status="anonymous",
                inferred_room_id=inferred_room_id,
                inferred_room_name=inferred_room_name,
                reason="上下文里没有可用的在家成员候选，先按匿名请求处理。",
                voiceprint_hint=voiceprint_hint,
            )

        primary = candidates[0]
        secondary = candidates[1] if len(candidates) > 1 else None
        confidence_gap = primary.confidence - (secondary.confidence if secondary is not None else 0.0)
        explicit_member_mentioned = self._contains_member_name(normalized_text, primary.name)
        context_conflict = bool(
            terminal_room_id
            and primary.current_room_id
            and terminal_room_id != primary.current_room_id
            and not explicit_member_mentioned
        )

        status: VoiceIdentityStatus
        reason: str
        if primary.confidence < 0.45:
            status = "anonymous"
            reason = "有身份候选，但置信度太低，不拿它当正式身份。"
        elif secondary is not None and secondary.confidence >= 0.45 and confidence_gap < 0.15:
            status = "conflict"
            reason = "多个成员都像当前说话人，先保守处理。"
        elif context_conflict:
            status = "degraded"
            reason = "终端所在房间和成员所在房间冲突，身份只做弱参考。"
        else:
            status = "resolved"
            reason = "终端房间、活跃成员和在家状态能收敛到单一身份候选。"

        if inferred_room_id is None:
            inferred_room_id = primary.current_room_id
            inferred_room_name = primary.current_room_name

        return VoiceIdentityResolution(
            status=status,
            primary_member_id=primary.member_id if status != "anonymous" else None,
            primary_member_name=primary.name if status != "anonymous" else None,
            primary_member_role=primary.role if status != "anonymous" else None,
            confidence=primary.confidence if status != "anonymous" else 0,
            inferred_room_id=inferred_room_id,
            inferred_room_name=inferred_room_name,
            context_conflict=context_conflict,
            reason=reason,
            candidates=candidates[:4],
            voiceprint_hint=voiceprint_hint,
        )

    def _build_candidate(
        self,
        *,
        member: ContextOverviewMemberState,
        transcript_text: str,
        terminal_room_id: str | None,
        active_member_id: str | None,
    ) -> VoiceIdentityCandidate:
        score = 0.0
        reasons: list[str] = []

        if member.presence == "home":
            score += 0.35
            reasons.append("成员当前在家")
        elif member.presence == "unknown":
            score += 0.12
            reasons.append("成员状态未知，只给低权重")
        else:
            score += 0.02

        if member.member_id == active_member_id:
            score += 0.22
            reasons.append("命中当前活跃成员")

        if terminal_room_id and member.current_room_id == terminal_room_id:
            score += 0.28
            reasons.append("成员和语音终端位于同一房间")

        if member.source == "snapshot":
            score += 0.08
            reasons.append("成员位置来自实时快照")

        if self._contains_member_name(transcript_text, member.name):
            score += 0.36
            reasons.append("转写文本直接提到了成员名字")

        if member.role == "admin":
            score += 0.04
        elif member.role == "adult":
            score += 0.02

        return VoiceIdentityCandidate(
            member_id=member.member_id,
            name=member.name,
            role=member.role,
            confidence=max(0.0, min(1.0, round(score, 3))),
            current_room_id=member.current_room_id,
            current_room_name=member.current_room_name,
            reasons=reasons,
        )

    def _contains_member_name(self, transcript_text: str, member_name: str | None) -> bool:
        if not transcript_text or not member_name:
            return False
        return member_name.strip() in transcript_text

    def _find_room_name(self, overview: ContextOverviewRead, room_id: str | None) -> str | None:
        if room_id is None:
            return None
        for room in overview.room_occupancy:
            if room.room_id == room_id:
                return room.name
        return None

    def _find_member_state(self, overview: ContextOverviewRead, member_id: str) -> ContextOverviewMemberState | None:
        for member in overview.member_states:
            if member.member_id == member_id:
                return member
        return None

    def _build_voiceprint_hint(
        self,
        result: VoiceprintIdentificationRead | None,
    ) -> VoiceIdentityVoiceprintHint:
        if result is None:
            return VoiceIdentityVoiceprintHint()
        return VoiceIdentityVoiceprintHint(
            provider=result.provider,
            status=result.status,
            member_id=result.member_id,
            profile_id=result.profile_id,
            score=result.score,
            threshold=result.threshold,
            reason=result.reason,
            candidate_count=result.candidate_count,
            candidates=[
                VoiceIdentityVoiceprintCandidate(
                    member_id=item.member_id,
                    profile_id=item.profile_id,
                    score=item.score,
                )
                for item in result.candidates
            ],
        )


voice_identity_service = VoiceIdentityService()
