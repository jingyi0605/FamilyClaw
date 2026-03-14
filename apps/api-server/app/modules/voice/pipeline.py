from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.voice.conversation_bridge import voice_conversation_bridge
from app.modules.voice.fast_action_service import VoiceRouteDecision, voice_fast_action_service
from app.modules.voice.protocol import (
    AgentErrorPayload,
    AudioCommitPayload,
    SessionStartPayload,
    TerminalHeartbeatPayload,
    TerminalOfflinePayload,
    TerminalOnlinePayload,
    VoiceCommandEvent,
    VoiceGatewayEvent,
    build_voice_command_event,
)
from app.modules.voice.registry import (
    VoiceSessionState,
    VoiceTerminalState,
    voice_gateway_connection_registry,
    voice_session_registry,
    voice_terminal_registry,
)
from app.modules.voice.router import voice_router
from app.modules.voice.runtime_client import voice_runtime_client


class VoicePipelineService:
    """语音主链最小编排器，先打通 commit 后的 runtime / route / playback 接缝。"""

    async def handle_inbound_event(self, db: Session, event: VoiceGatewayEvent) -> list[VoiceCommandEvent]:
        voice_gateway_connection_registry.touch(terminal_id=event.terminal_id)

        if event.type == "terminal.online":
            payload = event.payload
            assert isinstance(payload, TerminalOnlinePayload)
            connection = voice_gateway_connection_registry.get(event.terminal_id)
            voice_terminal_registry.upsert_online(
                terminal_id=event.terminal_id,
                household_id=payload.household_id,
                room_id=payload.room_id,
                terminal_code=payload.terminal_code,
                name=payload.name,
                adapter_type=payload.adapter_type,
                transport_type=payload.transport_type,
                capabilities=payload.capabilities,
                adapter_meta=payload.adapter_meta,
                connection_id=connection.connection_id if connection else None,
                remote_addr=connection.remote_addr if connection else None,
            )
            return []

        if event.type == "terminal.offline":
            payload = event.payload
            assert isinstance(payload, TerminalOfflinePayload)
            _ = payload
            voice_terminal_registry.mark_offline(terminal_id=event.terminal_id)
            return []

        if event.type == "terminal.heartbeat":
            payload = event.payload
            assert isinstance(payload, TerminalHeartbeatPayload)
            voice_terminal_registry.touch(
                terminal_id=event.terminal_id,
                household_id=payload.household_id,
                adapter_meta=payload.adapter_meta,
            )
            return []

        if event.type == "session.start":
            payload = event.payload
            assert isinstance(payload, SessionStartPayload)
            terminal = voice_terminal_registry.get(event.terminal_id)
            if terminal is None:
                return [
                    self._build_error(
                        terminal_id=event.terminal_id,
                        session_id=event.session_id,
                        error_code="terminal_not_found",
                        detail="终端未注册，无法开始语音会话",
                    )
                ]

            voice_session_registry.start_session(
                session_id=event.session_id or "",
                terminal_id=event.terminal_id,
                household_id=payload.household_id,
                room_id=payload.room_id or terminal.room_id,
                inbound_seq=event.seq,
            )
            seq = voice_session_registry.claim_next_seq(session_id=event.session_id or "")
            voice_session_registry.mark_ready(session_id=event.session_id or "")
            return [
                build_voice_command_event(
                    event_type="session.ready",
                    terminal_id=event.terminal_id,
                    session_id=event.session_id,
                    seq=seq,
                    payload={"accepted": True, "lane": "voice_pipeline"},
                )
            ]

        if event.type == "audio.append":
            session = voice_session_registry.append_audio(
                session_id=event.session_id or "",
                chunk_bytes=event.payload.chunk_bytes,
                inbound_seq=event.seq,
            )
            if session is None:
                return [
                    self._build_error(
                        terminal_id=event.terminal_id,
                        session_id=event.session_id,
                        error_code="session_not_found",
                        detail="语音会话不存在，无法追加音频",
                    )
                ]
            return []

        if event.type == "audio.commit":
            payload = event.payload
            assert isinstance(payload, AudioCommitPayload)
            session = voice_session_registry.commit_audio(session_id=event.session_id or "", inbound_seq=event.seq)
            if session is None:
                return [
                    self._build_error(
                        terminal_id=event.terminal_id,
                        session_id=event.session_id,
                        error_code="session_not_found",
                        detail="语音会话不存在，无法提交音频",
                    )
                ]
            terminal = voice_terminal_registry.get(event.terminal_id)
            if terminal is None:
                voice_session_registry.mark_failed(session_id=session.session_id, error_code="terminal_not_found")
                return [
                    self._build_error(
                        terminal_id=event.terminal_id,
                        session_id=event.session_id,
                        error_code="terminal_not_found",
                        detail="终端不存在，无法继续处理转写。",
                    )
                ]
            return await self._handle_committed_audio(
                db,
                session=session,
                terminal=terminal,
                debug_transcript=payload.debug_transcript,
            )

        if event.type == "session.cancel":
            voice_session_registry.cancel(session_id=event.session_id or "", inbound_seq=event.seq)
            return []

        if event.type == "playback.interrupted":
            voice_session_registry.attach_playback_receipt(
                session_id=event.session_id or "",
                playback_id=event.payload.playback_id,
                terminal_id=event.terminal_id,
                status="interrupted",
                detail=event.payload.reason,
                error_code=None,
                inbound_seq=event.seq,
            )
            return []

        if event.type == "playback.receipt":
            voice_session_registry.attach_playback_receipt(
                session_id=event.session_id or "",
                playback_id=event.payload.playback_id,
                terminal_id=event.terminal_id,
                status=event.payload.status,
                detail=event.payload.detail,
                error_code=event.payload.error_code,
                inbound_seq=event.seq,
            )
            return []

        return [
            self._build_error(
                terminal_id=event.terminal_id,
                session_id=event.session_id,
                error_code="invalid_event_payload",
                detail=f"未支持的语音事件: {event.type}",
            )
        ]

    def handle_terminal_disconnect(self, *, terminal_id: str) -> None:
        voice_terminal_registry.mark_offline(terminal_id=terminal_id)

    async def _handle_committed_audio(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        debug_transcript: str | None,
    ) -> list[VoiceCommandEvent]:
        transcript_result = await voice_runtime_client.finalize_session(
            session=session,
            terminal=terminal,
            debug_transcript=debug_transcript,
        )
        if not transcript_result.ok:
            voice_session_registry.mark_failed(
                session_id=session.session_id,
                error_code=transcript_result.error_code or "voice_runtime_unavailable",
            )
            return [
                self._build_error(
                    terminal_id=session.terminal_id,
                    session_id=session.session_id,
                    error_code=transcript_result.error_code or "voice_runtime_unavailable",
                    detail=transcript_result.detail or "语音运行时不可用。",
                )
            ]

        transcript_text = (transcript_result.transcript_text or "").strip()
        if not transcript_text:
            voice_session_registry.mark_failed(session_id=session.session_id, error_code="voice_transcript_empty")
            return [
                self._build_error(
                    terminal_id=session.terminal_id,
                    session_id=session.session_id,
                    error_code="voice_transcript_empty",
                    detail="没有拿到有效转写文本。",
                )
            ]

        voice_session_registry.update_transcript(
            session_id=session.session_id,
            transcript_text=transcript_text,
            runtime_status=transcript_result.runtime_status,
        )

        route_decision = await voice_router.route(
            db,
            household_id=session.household_id,
            transcript_text=transcript_text,
        )
        return await self._execute_route(
            db,
            session=session,
            terminal=terminal,
            transcript_text=transcript_text,
            route_decision=route_decision,
        )

    async def _execute_route(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
        route_decision: VoiceRouteDecision,
    ) -> list[VoiceCommandEvent]:
        if route_decision.error_code == "fast_action_ambiguous":
            voice_session_registry.update_route(
                session_id=session.session_id,
                lane="conversation",
                route_type="conversation",
                route_target=None,
            )
            bridge_result = await voice_conversation_bridge.bridge(
                db,
                session=session,
                terminal=terminal,
                transcript_text=transcript_text,
            )
            voice_session_registry.attach_conversation(
                session_id=session.session_id,
                conversation_session_id=bridge_result.conversation_session_id,
            )
            voice_session_registry.record_response_text(
                session_id=session.session_id,
                response_text=bridge_result.response_text,
            )
            return [self._build_play_start(session=session, text=bridge_result.response_text)]

        if route_decision.route_type in {"device_action", "scene"}:
            try:
                executed = await voice_fast_action_service.execute(
                    db,
                    household_id=session.household_id,
                    decision=route_decision,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                voice_session_registry.mark_failed(session_id=session.session_id, error_code="fast_action_blocked")
                return [
                    self._build_error(
                        terminal_id=session.terminal_id,
                        session_id=session.session_id,
                        error_code="fast_action_blocked",
                        detail=str(exc),
                    )
                ]

            voice_session_registry.update_route(
                session_id=session.session_id,
                lane="fast_action",
                route_type=executed.route_type,
                route_target=executed.route_target,
            )
            if executed.response_text:
                voice_session_registry.record_response_text(
                    session_id=session.session_id,
                    response_text=executed.response_text,
                )
                return [self._build_play_start(session=session, text=executed.response_text)]
            return []

        try:
            bridge_result = await voice_conversation_bridge.bridge(
                db,
                session=session,
                terminal=terminal,
                transcript_text=transcript_text,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            voice_session_registry.mark_failed(session_id=session.session_id, error_code="conversation_bridge_unavailable")
            return [
                self._build_error(
                    terminal_id=session.terminal_id,
                    session_id=session.session_id,
                    error_code="conversation_bridge_unavailable",
                    detail=str(exc),
                )
            ]

        voice_session_registry.update_route(
            session_id=session.session_id,
            lane="conversation",
            route_type="conversation",
            route_target=None,
        )
        voice_session_registry.attach_conversation(
            session_id=session.session_id,
            conversation_session_id=bridge_result.conversation_session_id,
        )
        voice_session_registry.record_response_text(
            session_id=session.session_id,
            response_text=bridge_result.response_text,
        )
        return [self._build_play_start(session=session, text=bridge_result.response_text)]

    def _build_play_start(self, *, session: VoiceSessionState, text: str) -> VoiceCommandEvent:
        seq = voice_session_registry.claim_next_seq(session_id=session.session_id)
        return build_voice_command_event(
            event_type="play.start",
            terminal_id=session.terminal_id,
            session_id=session.session_id,
            seq=seq,
            payload={
                "playback_id": f"{session.session_id}-playback-{seq}",
                "mode": "tts_text",
                "text": text,
            },
        )

    def _build_error(
        self,
        *,
        terminal_id: str,
        session_id: str | None,
        error_code: str,
        detail: str,
    ) -> VoiceCommandEvent:
        seq = 0
        if session_id and voice_session_registry.get(session_id) is not None:
            seq = voice_session_registry.claim_next_seq(session_id=session_id)
        payload = AgentErrorPayload(detail=detail, error_code=error_code, retryable=False)
        return build_voice_command_event(
            event_type="agent.error",
            terminal_id=terminal_id,
            session_id=session_id,
            seq=seq,
            payload=payload,
        )


voice_pipeline_service = VoicePipelineService()
