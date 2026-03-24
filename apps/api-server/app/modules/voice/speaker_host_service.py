from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.conversation.models import ConversationSession
from app.modules.conversation.schemas import ConversationMessageRead, ConversationSessionCreate
from app.modules.conversation.service import (
    conversation_turn_exists,
    create_conversation_session,
    get_conversation_session_detail,
    record_conversation_turn_source,
    run_conversation_realtime_turn,
)
from app.modules.device.models import Device, DeviceBinding
from app.modules.integration import repository as integration_repository
from app.modules.plugin.service import (
    PluginServiceError,
    get_household_plugin,
    require_available_household_plugin,
)

from .speaker_schemas import (
    SpeakerRuntimeHeartbeat,
    SpeakerRuntimeHeartbeatResult,
    SpeakerTextTurnRequest,
    SpeakerTextTurnResult,
)


class _SpeakerRealtimeForwarder:
    async def broadcast(self, *, household_id: str, session_id: str, event) -> None:
        _ = household_id
        _ = session_id
        _ = event


@dataclass(slots=True)
class _SpeakerBindingResolution:
    device_id: str | None
    binding: DeviceBinding | None


@dataclass(slots=True)
class _SpeakerAudioReply:
    audio_url: str
    content_type: str | None = None
    fallback_text: str | None = None


class SpeakerHostService:
    """把第三方 speaker 文本轮询请求桥接进宿主实时对话主链。"""

    async def submit_text_turn(
        self,
        db: Session,
        *,
        request: SpeakerTextTurnRequest,
    ) -> SpeakerTextTurnResult:
        instance = integration_repository.get_integration_instance(db, request.integration_instance_id)
        if instance is None:
            raise PluginServiceError(
                f"集成实例不存在: {request.integration_instance_id}",
                error_code="integration_instance_not_found",
                field="integration_instance_id",
                status_code=404,
            )
        if instance.plugin_id != request.plugin_id:
            raise PluginServiceError(
                "speaker text turn 的 plugin_id 和 integration_instance_id 不匹配",
                error_code="speaker_text_turn_invalid",
                field="plugin_id",
                status_code=409,
            )

        plugin = require_available_household_plugin(
            db,
            household_id=instance.household_id,
            plugin_id=request.plugin_id,
            plugin_type="integration",
            trigger="speaker-text-turn",
        )
        capability = plugin.capabilities.speaker_adapter
        if capability is None:
            raise PluginServiceError(
                "当前插件没有声明 speaker_adapter 能力",
                error_code="speaker_text_turn_invalid",
                field="plugin_id",
                status_code=409,
            )
        if "text_turn" not in capability.supported_modes:
            raise PluginServiceError(
                "当前 speaker_adapter 不支持 text_turn 模式",
                error_code="speaker_text_turn_invalid",
                field="plugin_id",
                status_code=409,
            )

        binding_resolution = self._resolve_device_binding(
            db,
            household_id=instance.household_id,
            plugin_id=request.plugin_id,
            integration_instance_id=request.integration_instance_id,
            device_id=request.device_id,
            external_device_id=request.external_device_id,
        )
        external_conversation_key = self._build_external_conversation_key(
            request=request,
            resolved_device_id=binding_resolution.device_id,
        )
        actor = self._build_actor(
            household_id=instance.household_id,
            requester_member_id=request.requester_member_id,
        )
        session_id = self._resolve_or_create_session(
            db,
            household_id=instance.household_id,
            instance_display_name=instance.display_name,
            external_conversation_key=external_conversation_key,
            actor=actor,
            requester_member_id=request.requester_member_id,
        )

        if conversation_turn_exists(
            db,
            conversation_session_id=session_id,
            conversation_turn_id=request.turn_id,
        ):
            self._record_turn_source(
                db,
                session_id=session_id,
                request=request,
                external_conversation_key=external_conversation_key,
            )
            session_detail = get_conversation_session_detail(
                db,
                session_id=session_id,
                actor=actor,
            )
            return self._build_turn_result(
                session_id=session_id,
                turn_id=request.turn_id,
                messages=session_detail.messages,
            )

        try:
            await run_conversation_realtime_turn(
                db,
                session_id=session_id,
                request_id=request.turn_id,
                user_message=request.input_text,
                actor=actor,
                connection_manager=_SpeakerRealtimeForwarder(),
            )
        except Exception as exc:
            if conversation_turn_exists(
                db,
                conversation_session_id=session_id,
                conversation_turn_id=request.turn_id,
            ):
                self._record_turn_source(
                    db,
                    session_id=session_id,
                    request=request,
                    external_conversation_key=external_conversation_key,
                )
            return SpeakerTextTurnResult(
                accepted=False,
                conversation_session_id=session_id,
                turn_id=request.turn_id,
                result_type="error",
                error_code=self._resolve_error_code(exc),
                error_message=self._resolve_error_message(exc),
            )

        self._record_turn_source(
            db,
            session_id=session_id,
            request=request,
            external_conversation_key=external_conversation_key,
        )
        session_detail = get_conversation_session_detail(
            db,
            session_id=session_id,
            actor=actor,
        )
        return self._build_turn_result(
            session_id=session_id,
            turn_id=request.turn_id,
            messages=session_detail.messages,
        )

    def report_runtime_heartbeat(
        self,
        db: Session,
        *,
        heartbeat: SpeakerRuntimeHeartbeat,
    ) -> SpeakerRuntimeHeartbeatResult:
        instance = integration_repository.get_integration_instance(db, heartbeat.integration_instance_id)
        if instance is None:
            raise PluginServiceError(
                f"集成实例不存在: {heartbeat.integration_instance_id}",
                error_code="integration_instance_not_found",
                field="integration_instance_id",
                status_code=404,
            )
        if instance.plugin_id != heartbeat.plugin_id:
            raise PluginServiceError(
                "speaker heartbeat 的 plugin_id 和 integration_instance_id 不匹配",
                error_code="speaker_runtime_heartbeat_invalid",
                field="plugin_id",
                status_code=409,
            )

        plugin = get_household_plugin(
            db,
            household_id=instance.household_id,
            plugin_id=heartbeat.plugin_id,
        )

        now = utc_now_iso()
        state = heartbeat.state
        if heartbeat.last_succeeded_at:
            instance.last_synced_at = heartbeat.last_succeeded_at
        if not plugin.enabled:
            instance.status = "disabled"
            instance.last_error_code = "plugin_disabled"
            instance.last_error_message = plugin.disabled_reason or "插件已停用"
        elif state in {"running", "idle"}:
            instance.status = "active"
            instance.last_error_code = None
            instance.last_error_message = None
            instance.last_synced_at = heartbeat.last_succeeded_at or now
        elif state == "degraded":
            instance.status = "degraded"
            instance.last_error_code = "speaker_runtime_degraded"
            instance.last_error_message = heartbeat.last_error_summary or "speaker runtime 已降级"
        elif state == "error":
            instance.status = "degraded"
            instance.last_error_code = "speaker_runtime_error"
            instance.last_error_message = heartbeat.last_error_summary or "speaker runtime 执行失败"
        else:
            instance.status = "degraded"
            instance.last_error_code = "speaker_runtime_stopped"
            instance.last_error_message = heartbeat.last_error_summary or "speaker runtime 已停止"

        instance.updated_at = now
        db.add(instance)
        return SpeakerRuntimeHeartbeatResult(
            accepted=True,
            integration_instance_id=instance.id,
            plugin_id=heartbeat.plugin_id,
            state=heartbeat.state,
            instance_status=instance.status,
            error_code=instance.last_error_code,
            error_message=instance.last_error_message,
        )

    def _resolve_device_binding(
        self,
        db: Session,
        *,
        household_id: str,
        plugin_id: str,
        integration_instance_id: str,
        device_id: str | None,
        external_device_id: str,
    ) -> _SpeakerBindingResolution:
        normalized_device_id = (device_id or "").strip() or None
        if normalized_device_id is not None:
            stmt: Select[tuple[DeviceBinding]] = (
                select(DeviceBinding)
                .join(Device, Device.id == DeviceBinding.device_id)
                .where(
                    Device.id == normalized_device_id,
                    Device.household_id == household_id,
                    DeviceBinding.integration_instance_id == integration_instance_id,
                )
                .order_by(DeviceBinding.id.asc())
            )
            binding = db.scalar(stmt)
            if binding is None:
                raise PluginServiceError(
                    "speaker 设备没有正式绑定到当前集成实例",
                    error_code="speaker_binding_missing",
                    field="device_id",
                    status_code=404,
                )
            if binding.plugin_id and binding.plugin_id != plugin_id:
                raise PluginServiceError(
                    "speaker 设备绑定的 plugin_id 和当前请求不一致",
                    error_code="speaker_binding_missing",
                    field="device_id",
                    status_code=409,
                )
            if binding.external_device_id and binding.external_device_id != external_device_id:
                raise PluginServiceError(
                    "speaker 设备绑定的 external_device_id 和当前请求不一致",
                    error_code="speaker_binding_missing",
                    field="external_device_id",
                    status_code=409,
                )
            return _SpeakerBindingResolution(device_id=normalized_device_id, binding=binding)

        stmt = (
            select(DeviceBinding)
            .join(Device, Device.id == DeviceBinding.device_id)
            .where(
                Device.household_id == household_id,
                DeviceBinding.integration_instance_id == integration_instance_id,
                DeviceBinding.external_device_id == external_device_id,
            )
            .order_by(DeviceBinding.id.asc())
        )
        binding = db.scalar(stmt)
        if binding is None:
            return _SpeakerBindingResolution(device_id=None, binding=None)
        if binding.plugin_id and binding.plugin_id != plugin_id:
            raise PluginServiceError(
                "speaker 设备绑定的 plugin_id 和当前请求不一致",
                error_code="speaker_binding_missing",
                field="external_device_id",
                status_code=409,
            )
        return _SpeakerBindingResolution(device_id=binding.device_id, binding=binding)

    def _resolve_or_create_session(
        self,
        db: Session,
        *,
        household_id: str,
        instance_display_name: str,
        external_conversation_key: str,
        actor: ActorContext,
        requester_member_id: str | None,
    ) -> str:
        from app.modules.conversation import repository as conversation_repository

        latest_turn_source = conversation_repository.get_latest_turn_source_by_external_conversation_key(
            db,
            external_conversation_key=external_conversation_key,
            source_kind="speaker_adapter",
        )
        if latest_turn_source is not None:
            return latest_turn_source.conversation_session_id

        detail = create_conversation_session(
            db,
            payload=ConversationSessionCreate(
                household_id=household_id,
                requester_member_id=requester_member_id,
                title=f"音箱对话 {instance_display_name}",
            ),
            actor=actor,
        )
        session = db.get(ConversationSession, detail.id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation session not found",
            )
        return session.id

    def _record_turn_source(
        self,
        db: Session,
        *,
        session_id: str,
        request: SpeakerTextTurnRequest,
        external_conversation_key: str,
    ) -> None:
        record_conversation_turn_source(
            db,
            conversation_session_id=session_id,
            conversation_turn_id=request.turn_id,
            source_kind="speaker_adapter",
            platform_code=request.plugin_id,
            external_conversation_key=external_conversation_key,
        )

    def _build_external_conversation_key(
        self,
        *,
        request: SpeakerTextTurnRequest,
        resolved_device_id: str | None,
    ) -> str:
        key_parts = [
            "speaker",
            request.plugin_id,
            request.integration_instance_id,
            request.external_device_id,
            request.conversation_id,
        ]
        if resolved_device_id:
            key_parts.append(resolved_device_id)
        return ":".join(part.strip() for part in key_parts if part and part.strip())

    def _build_actor(
        self,
        *,
        household_id: str,
        requester_member_id: str | None,
    ) -> ActorContext:
        return ActorContext(
            role="admin",
            actor_type="system",
            actor_id="speaker_host_service",
            account_type="system",
            account_status="active",
            household_id=household_id,
            member_id=requester_member_id,
            is_authenticated=True,
        )

    def _build_turn_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        messages: list[ConversationMessageRead],
    ) -> SpeakerTextTurnResult:
        assistant_message = self._find_assistant_message(messages=messages, turn_id=turn_id)
        if assistant_message is None:
            return SpeakerTextTurnResult(
                accepted=True,
                conversation_session_id=session_id,
                turn_id=turn_id,
                result_type="none",
                error_code="speaker_text_turn_empty_reply",
                error_message="宿主本轮没有产出可播报回复",
            )

        if assistant_message.status == "pending":
            return SpeakerTextTurnResult(
                accepted=True,
                conversation_session_id=session_id,
                turn_id=turn_id,
                result_type="none",
                assistant_message_id=assistant_message.id,
                error_code="speaker_text_turn_pending_reply",
                error_message="宿主仍在处理当前轮次",
            )

        audio_reply = self._extract_audio_reply(assistant_message)
        reply_text = assistant_message.content.strip()
        degraded = assistant_message.status != "completed" or assistant_message.degraded
        if audio_reply is not None:
            resolved_reply_text = audio_reply.fallback_text or reply_text or None
            return SpeakerTextTurnResult(
                accepted=True,
                conversation_session_id=session_id,
                turn_id=turn_id,
                result_type="audio_url",
                reply_text=resolved_reply_text,
                audio_url=audio_reply.audio_url,
                audio_content_type=audio_reply.content_type,
                degraded=degraded,
                assistant_message_id=assistant_message.id,
                error_code=assistant_message.error_code if degraded else None,
                error_message=None,
            )
        if reply_text:
            return SpeakerTextTurnResult(
                accepted=True,
                conversation_session_id=session_id,
                turn_id=turn_id,
                result_type="text",
                reply_text=reply_text,
                degraded=degraded,
                assistant_message_id=assistant_message.id,
                error_code=assistant_message.error_code if degraded else None,
                error_message=None,
            )

        if assistant_message.status != "completed":
            return SpeakerTextTurnResult(
                accepted=True,
                conversation_session_id=session_id,
                turn_id=turn_id,
                result_type="error",
                degraded=True,
                assistant_message_id=assistant_message.id,
                error_code=assistant_message.error_code or "speaker_text_turn_failed",
                error_message="宿主本轮处理失败，而且没有可返回文本",
            )

        return SpeakerTextTurnResult(
            accepted=True,
            conversation_session_id=session_id,
            turn_id=turn_id,
            result_type="none",
            degraded=degraded,
            assistant_message_id=assistant_message.id,
            error_code=assistant_message.error_code,
            error_message="宿主本轮没有产出文本回复",
        )

    def _extract_audio_reply(self, message: ConversationMessageRead) -> _SpeakerAudioReply | None:
        for item in message.facts:
            if not isinstance(item, dict):
                continue
            reply = self._parse_audio_reply_fact(item)
            if reply is not None:
                return reply
        return None

    def _parse_audio_reply_fact(self, item: dict) -> _SpeakerAudioReply | None:
        raw_type = str(item.get("type") or item.get("kind") or "").strip().lower()
        if raw_type not in {"speaker_audio_reply", "audio_reply", "speaker_reply"}:
            return None
        audio_url = str(item.get("audio_url") or item.get("url") or "").strip()
        if not self._is_absolute_http_url(audio_url):
            return None
        content_type = str(item.get("content_type") or "").strip() or None
        fallback_text = str(item.get("fallback_text") or item.get("text") or "").strip() or None
        return _SpeakerAudioReply(
            audio_url=audio_url,
            content_type=content_type,
            fallback_text=fallback_text,
        )

    def _is_absolute_http_url(self, value: str) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _find_assistant_message(
        self,
        *,
        messages: list[ConversationMessageRead],
        turn_id: str,
    ) -> ConversationMessageRead | None:
        pending_candidate: ConversationMessageRead | None = None
        for item in reversed(messages):
            if item.request_id != turn_id:
                continue
            if item.role != "assistant":
                continue
            if item.status == "pending":
                pending_candidate = item
                continue
            return item
        return pending_candidate

    def _resolve_error_code(self, exc: Exception) -> str:
        if isinstance(exc, PluginServiceError):
            return exc.error_code
        if isinstance(exc, HTTPException):
            detail = exc.detail
            if isinstance(detail, dict):
                raw_error_code = detail.get("error_code")
                if isinstance(raw_error_code, str) and raw_error_code.strip():
                    return raw_error_code.strip()
            return "conversation_bridge_unavailable"
        return "conversation_bridge_unavailable"

    def _resolve_error_message(self, exc: Exception) -> str:
        if isinstance(exc, PluginServiceError):
            return exc.detail
        if isinstance(exc, HTTPException):
            if isinstance(exc.detail, dict):
                detail_text = exc.detail.get("detail")
                if isinstance(detail_text, str) and detail_text.strip():
                    return detail_text.strip()
            if isinstance(exc.detail, str) and exc.detail.strip():
                return exc.detail.strip()
        return str(exc) or "speaker text turn 处理失败"


speaker_host_service = SpeakerHostService()
