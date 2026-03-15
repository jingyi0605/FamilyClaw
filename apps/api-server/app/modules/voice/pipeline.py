from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.voice.conversation_bridge import voice_conversation_bridge
from app.modules.voice.fast_action_service import VoiceFastActionExecutionError, VoiceRouteDecision, voice_fast_action_service
from app.modules.voice.protocol import (
    AgentErrorPayload,
    AudioAppendPayload,
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
from app.modules.voice.router import VoiceRoutingResult, voice_router
from app.modules.voice.runtime_client import voice_runtime_client


class VoicePipelineService:
    """把 commit 之后的身份、上下文、快慢路由和播报收成一条保守主链。"""

    async def handle_inbound_event(self, db: Session, event: VoiceGatewayEvent) -> list[VoiceCommandEvent]:
        voice_gateway_connection_registry.touch(terminal_id=event.terminal_id)

        if event.type == "terminal.online":
            payload = event.payload
            assert isinstance(payload, TerminalOnlinePayload)
            connection = voice_gateway_connection_registry.get(event.terminal_id)
            voice_terminal_registry.upsert_online(
                terminal_id=event.terminal_id,
                household_id=payload.household_id,
                fingerprint=connection.fingerprint if connection else None,
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
                        detail="终端还没注册，不能开始语音会话。",
                    )
                ]

            voice_session_registry.start_session(
                session_id=event.session_id or "",
                terminal_id=event.terminal_id,
                household_id=payload.household_id,
                room_id=payload.room_id or terminal.room_id,
                inbound_seq=event.seq,
            )
            session = voice_session_registry.get(event.session_id or "")
            if session is not None:
                runtime_start = await voice_runtime_client.start_session(
                    session=session,
                    terminal=terminal,
                    sample_rate=payload.sample_rate,
                    codec=payload.codec,
                    channels=payload.channels,
                )
                voice_session_registry.update_runtime_state(
                    session_id=session.session_id,
                    runtime_status=runtime_start.runtime_status,
                    runtime_session_id=runtime_start.runtime_session_id,
                    runtime_error_detail=runtime_start.detail,
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
            payload = event.payload
            assert isinstance(payload, AudioAppendPayload)
            session = voice_session_registry.append_audio(
                session_id=event.session_id or "",
                chunk_bytes=payload.chunk_bytes,
                inbound_seq=event.seq,
            )
            if session is None:
                return [
                    self._build_error(
                        terminal_id=event.terminal_id,
                        session_id=event.session_id,
                        error_code="session_not_found",
                        detail="语音会话不存在，不能继续追加音频。",
                    )
                ]
            terminal = voice_terminal_registry.get(event.terminal_id)
            if terminal is not None:
                runtime_append = await voice_runtime_client.append_audio(
                    session=session,
                    terminal=terminal,
                    chunk_base64=payload.chunk_base64,
                    chunk_bytes=payload.chunk_bytes,
                    codec=payload.codec,
                    sample_rate=payload.sample_rate,
                )
                voice_session_registry.update_runtime_state(
                    session_id=session.session_id,
                    runtime_status=runtime_append.runtime_status,
                    runtime_session_id=runtime_append.runtime_session_id,
                    runtime_error_detail=runtime_append.detail,
                )
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
                        detail="语音会话不存在，无法提交音频。",
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
                        detail="终端状态丢了，后续链路没法继续。",
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
                detail=f"不支持的语音事件: {event.type}",
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
                    detail=transcript_result.detail or "语音运行时当前不可用。",
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
            runtime_session_id=transcript_result.runtime_session_id,
            runtime_error_detail=transcript_result.detail,
        )

        routing_result = await voice_router.route(
            db,
            session=session,
            terminal=terminal,
            transcript_text=transcript_text,
        )
        self._record_identity(session_id=session.session_id, routing_result=routing_result)
        session = voice_session_registry.get(session.session_id) or session
        return await self._execute_route(
            db,
            session=session,
            terminal=terminal,
            transcript_text=transcript_text,
            routing_result=routing_result,
        )

    async def _execute_route(
        self,
        db: Session,
        *,
        session: VoiceSessionState,
        terminal: VoiceTerminalState,
        transcript_text: str,
        routing_result: VoiceRoutingResult,
    ) -> list[VoiceCommandEvent]:
        decision = routing_result.decision
        if decision.route_type in {"device_action", "scene"}:
            try:
                executed = await voice_fast_action_service.execute(
                    db,
                    household_id=session.household_id,
                    decision=decision,
                )
                db.commit()
            except VoiceFastActionExecutionError as exc:
                db.rollback()
                voice_session_registry.update_route(
                    session_id=session.session_id,
                    lane="fast_action",
                    route_type=decision.route_type,
                    route_target=decision.route_target,
                    route_error_code=exc.error_code,
                )
                return self._build_route_feedback(
                    session=session,
                    text=exc.response_text or "这次设备动作没有执行成功。",
                )
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
                route_error_code=executed.error_code,
            )
            if executed.response_text:
                voice_session_registry.record_response_text(session_id=session.session_id, response_text=executed.response_text)
                return self._build_route_feedback(session=session, text=executed.response_text)
            return []

        if decision.response_text and not decision.handoff_to_conversation:
            voice_session_registry.update_route(
                session_id=session.session_id,
                lane="conversation",
                route_type="conversation",
                route_target=None,
                route_error_code=decision.error_code,
            )
            voice_session_registry.record_response_text(session_id=session.session_id, response_text=decision.response_text)
            return self._build_route_feedback(session=session, text=decision.response_text)

        try:
            bridge_result = await voice_conversation_bridge.bridge(
                db,
                session=session,
                terminal=terminal,
                transcript_text=transcript_text,
                identity=routing_result.identity,
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
            route_error_code=bridge_result.error_code or decision.error_code,
        )
        voice_session_registry.attach_conversation(
            session_id=session.session_id,
            conversation_session_id=bridge_result.conversation_session_id,
        )
        voice_session_registry.record_response_text(
            session_id=session.session_id,
            response_text=bridge_result.response_text,
        )
        if bridge_result.streaming_playback:
            return []
        return self._build_route_feedback(session=session, text=bridge_result.response_text)

    def _record_identity(self, *, session_id: str, routing_result: VoiceRoutingResult) -> None:
        identity = routing_result.identity
        voice_session_registry.update_identity(
            session_id=session_id,
            requester_member_id=identity.primary_member_id,
            requester_member_role=identity.primary_member_role,
            speaker_confidence=identity.confidence if identity.primary_member_id else None,
            identity_status=identity.status,
            identity_summary=identity.model_dump(mode="json"),
        )

    def _build_route_feedback(self, *, session: VoiceSessionState, text: str) -> list[VoiceCommandEvent]:
        if not text.strip():
            return []
        return [self._build_play_start(session=session, text=text)]

    def _build_play_start(self, *, session: VoiceSessionState, text: str) -> VoiceCommandEvent:
        seq = voice_session_registry.claim_next_seq(session_id=session.session_id)
        playback_id = f"{session.session_id}-playback-{seq}"
        voice_session_registry.set_active_playback(session_id=session.session_id, playback_id=playback_id)
        return build_voice_command_event(
            event_type="play.start",
            terminal_id=session.terminal_id,
            session_id=session.session_id,
            seq=seq,
            payload={
                "playback_id": playback_id,
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
