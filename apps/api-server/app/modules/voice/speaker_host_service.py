from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid, utc_now_iso
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate, ConversationTurnRead
from app.modules.conversation.service import (
    create_conversation_session,
    create_conversation_turn,
    get_conversation_session_detail,
    record_conversation_turn_source,
)
from app.modules.device.models import Device, DeviceBinding
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.schemas import PluginRegistryItem
from app.modules.plugin.service import (
    PluginServiceError,
    get_household_plugin,
    require_available_household_plugin,
)
from app.modules.voice import repository as voice_repository
from app.modules.voice.models import SpeakerRuntimeState as SpeakerRuntimeStateModel
from app.modules.voice.speaker_schemas import (
    SpeakerAdapterCapability,
    SpeakerAudioSessionEnvelope,
    SpeakerAudioSessionResult,
    SpeakerRuntimeHeartbeat,
    SpeakerRuntimeHeartbeatAck,
    SpeakerRuntimeStateRead,
    SpeakerTextTurnRequest,
    SpeakerTextTurnResult,
)


SPEAKER_TURN_SOURCE_KIND = "speaker_adapter"
SPEAKER_BINDING_MISSING_ERROR_CODE = "speaker_binding_missing"
SPEAKER_TEXT_TURN_INVALID_ERROR_CODE = "speaker_text_turn_invalid"
SPEAKER_TURN_DUPLICATED_ERROR_CODE = "speaker_turn_duplicated"
SPEAKER_AUDIO_SESSION_UNSUPPORTED_ERROR_CODE = "speaker_audio_session_unsupported"
SPEAKER_RUNTIME_INVALID_ERROR_CODE = "speaker_runtime_invalid"


class SpeakerHostServiceError(ValueError):
    def __init__(
        self,
        detail: str,
        *,
        error_code: str,
        status_code: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.field = field

    def to_detail(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "detail": self.detail,
            "error_code": self.error_code,
            "timestamp": utc_now_iso(),
        }
        if self.field is not None:
            payload["field"] = self.field
        return payload


@dataclass(slots=True)
class _ResolvedSpeakerRequestContext:
    plugin: PluginRegistryItem
    capability: SpeakerAdapterCapability
    instance: IntegrationInstance
    binding: DeviceBinding
    device: Device


def resolve_speaker_adapter_capability(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> SpeakerAdapterCapability:
    plugin = _require_speaker_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
    )
    return _build_speaker_adapter_capability(
        plugin,
        error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
    )


def ensure_speaker_runtime_execution_allowed(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
) -> SpeakerAdapterCapability:
    resolved = _resolve_speaker_runtime_context(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        integration_instance_id=integration_instance_id,
    )
    if not resolved.capability.requires_runtime_worker:
        raise SpeakerHostServiceError(
            "当前 speaker 插件没有声明 runtime worker，不能继续上报或执行轮询。",
            error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
            status_code=409,
            field="plugin_id",
        )
    return resolved.capability


def submit_speaker_text_turn(
    db: Session,
    *,
    payload: SpeakerTextTurnRequest,
) -> SpeakerTextTurnResult:
    try:
        return _submit_speaker_text_turn_or_raise(db, payload=payload)
    except SpeakerHostServiceError as exc:
        return SpeakerTextTurnResult(
            accepted=False,
            duplicated=False,
            result_type="error",
            error_code=exc.error_code,
            error_message=exc.detail,
            conversation_state={
                "household_id": payload.household_id,
                "plugin_id": payload.plugin_id,
                "integration_instance_id": payload.integration_instance_id,
                "binding_id": payload.binding_id,
                "external_device_id": payload.external_device_id,
                "conversation_id": payload.conversation_id,
            },
        )


async def asubmit_speaker_text_turn(
    db: Session,
    *,
    payload: SpeakerTextTurnRequest,
) -> SpeakerTextTurnResult:
    return submit_speaker_text_turn(db, payload=payload)


def report_speaker_runtime_heartbeat(
    db: Session,
    *,
    payload: SpeakerRuntimeHeartbeat,
) -> SpeakerRuntimeHeartbeatAck:
    resolved = _resolve_speaker_runtime_context(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        integration_instance_id=payload.integration_instance_id,
    )
    if not resolved.capability.requires_runtime_worker:
        raise SpeakerHostServiceError(
            "当前 speaker 插件没有声明 runtime worker，heartbeat 不应该继续上报。",
            error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
            status_code=409,
            field="plugin_id",
        )

    _apply_runtime_heartbeat_to_instance(instance=resolved.instance, payload=payload)
    _upsert_speaker_runtime_state(
        db,
        resolved=resolved,
        payload=payload,
    )
    db.add(resolved.instance)
    db.flush()
    return SpeakerRuntimeHeartbeatAck(
        accepted=True,
        integration_instance_id=payload.integration_instance_id,
        runtime_state=payload.state,
        last_heartbeat_at=payload.reported_at,
    )


def open_speaker_audio_session(
    db: Session,
    *,
    payload: SpeakerAudioSessionEnvelope,
) -> SpeakerAudioSessionResult:
    resolved = _resolve_speaker_request_context(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        integration_instance_id=payload.integration_instance_id,
        binding_id=payload.binding_id,
        external_device_id=payload.external_device_id,
        device_id=payload.device_id,
        required_mode="audio_session",
    )
    actor = _build_system_actor(household_id=payload.household_id)
    external_conversation_key = _build_external_conversation_key(
        plugin_id=payload.plugin_id,
        integration_instance_id=payload.integration_instance_id,
        external_device_id=payload.external_device_id,
        conversation_id=payload.conversation_id,
    )
    conversation_session_id = _resolve_or_create_conversation_session(
        db,
        actor=actor,
        resolved=resolved,
        external_conversation_key=external_conversation_key,
    )
    return SpeakerAudioSessionResult(
        accepted=True,
        session_id=payload.session_id,
        stage=payload.stage,
        conversation_session_id=conversation_session_id,
        conversation_state={
            "binding_id": resolved.binding.id,
            "integration_instance_id": resolved.instance.id,
            "external_conversation_key": external_conversation_key,
        },
    )


def get_speaker_runtime_state(
    db: Session,
    *,
    integration_instance_id: str,
) -> SpeakerRuntimeStateRead | None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None:
        return None

    runtime_state_row = voice_repository.get_speaker_runtime_state_by_integration_instance(
        db,
        integration_instance_id=integration_instance_id,
    )
    if runtime_state_row is not None:
        return SpeakerRuntimeStateRead(
            id=runtime_state_row.id,
            household_id=runtime_state_row.household_id,
            plugin_id=runtime_state_row.plugin_id,
            integration_instance_id=runtime_state_row.integration_instance_id,
            adapter_code=runtime_state_row.adapter_code,
            runtime_state=runtime_state_row.runtime_state,
            consecutive_failures=runtime_state_row.consecutive_failures,
            last_succeeded_at=runtime_state_row.last_succeeded_at,
            last_failed_at=runtime_state_row.last_failed_at,
            last_error_summary=runtime_state_row.last_error_summary,
            last_heartbeat_at=runtime_state_row.last_heartbeat_at,
            created_at=runtime_state_row.created_at,
            updated_at=runtime_state_row.updated_at,
        )

    try:
        plugin = get_household_plugin(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
        )
        capability = _build_speaker_adapter_capability(
            plugin,
            error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
        )
    except (PluginServiceError, SpeakerHostServiceError):
        return None

    runtime_state = _map_instance_status_to_runtime_state(instance)
    return SpeakerRuntimeStateRead(
        id=f"speaker-runtime:{instance.id}",
        household_id=instance.household_id,
        plugin_id=instance.plugin_id,
        integration_instance_id=instance.id,
        adapter_code=capability.adapter_code,
        runtime_state=runtime_state,
        consecutive_failures=0 if runtime_state in {"idle", "running"} else 1,
        last_succeeded_at=instance.last_synced_at if runtime_state in {"idle", "running"} else None,
        last_failed_at=instance.updated_at if runtime_state in {"degraded", "error", "stopped"} else None,
        last_error_summary=instance.last_error_message,
        last_heartbeat_at=instance.last_synced_at or instance.updated_at,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def _submit_speaker_text_turn_or_raise(
    db: Session,
    *,
    payload: SpeakerTextTurnRequest,
) -> SpeakerTextTurnResult:
    resolved = _resolve_speaker_request_context(
        db,
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        integration_instance_id=payload.integration_instance_id,
        binding_id=payload.binding_id,
        external_device_id=payload.external_device_id,
        device_id=payload.device_id,
        required_mode="text_turn",
    )
    actor = _build_system_actor(household_id=payload.household_id)
    turn_key = _build_turn_request_id(payload)
    external_conversation_key = _build_external_conversation_key(
        plugin_id=payload.plugin_id,
        integration_instance_id=payload.integration_instance_id,
        external_device_id=payload.external_device_id,
        conversation_id=payload.conversation_id,
    )

    existing_source = conversation_repository.get_turn_source_by_turn_id(
        db,
        conversation_turn_id=turn_key,
    )
    if existing_source is not None:
        session = conversation_repository.get_session(db, existing_source.conversation_session_id)
        if session is not None and session.household_id == payload.household_id:
            return _build_text_turn_result_from_session(
                db,
                actor=actor,
                session_id=existing_source.conversation_session_id,
                request_id=existing_source.thread_key or turn_key,
                duplicated=True,
                conversation_state=_build_conversation_state(
                    resolved=resolved,
                    external_conversation_key=external_conversation_key,
                ),
            )

    conversation_session_id = _resolve_or_create_conversation_session(
        db,
        actor=actor,
        resolved=resolved,
        external_conversation_key=external_conversation_key,
    )
    try:
        turn = create_conversation_turn(
            db,
            session_id=conversation_session_id,
            payload=ConversationTurnCreate(
                message=payload.input_text,
                channel=SPEAKER_TURN_SOURCE_KIND,
            ),
            actor=actor,
        )
    except HTTPException as exc:
        raise SpeakerHostServiceError(
            _render_http_exception_detail(exc),
            error_code=SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
            status_code=exc.status_code,
        ) from exc

    record_conversation_turn_source(
        db,
        conversation_session_id=conversation_session_id,
        conversation_turn_id=turn_key,
        source_kind=SPEAKER_TURN_SOURCE_KIND,
        platform_code=payload.plugin_id,
        voice_terminal_code=payload.external_device_id,
        external_conversation_key=external_conversation_key,
        thread_key=turn.request_id,
    )
    return _build_text_turn_result_from_turn(
        turn,
        duplicated=False,
        conversation_state=_build_conversation_state(
            resolved=resolved,
            external_conversation_key=external_conversation_key,
        ),
    )


def _resolve_speaker_runtime_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
) -> _ResolvedSpeakerRequestContext:
    plugin = _require_speaker_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
    )
    capability = _build_speaker_adapter_capability(
        plugin,
        error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
    )
    instance = _require_integration_instance(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        integration_instance_id=integration_instance_id,
        error_code=SPEAKER_RUNTIME_INVALID_ERROR_CODE,
    )
    device = Device(
        id=f"speaker-runtime:{instance.id}",
        household_id=household_id,
        room_id=None,
        name=plugin.name,
        device_type="speaker",
        vendor="speaker",
        status="active",
        controllable=0,
        voice_auto_takeover_enabled=0,
        voiceprint_identity_enabled=0,
    )
    binding = DeviceBinding(
        id=f"speaker-runtime:{instance.id}",
        device_id=device.id,
        integration_instance_id=instance.id,
        platform=capability.adapter_code,
        external_entity_id=f"speaker-runtime:{instance.id}",
        external_device_id=f"speaker-runtime:{instance.id}",
        plugin_id=plugin_id,
        binding_version=1,
    )
    return _ResolvedSpeakerRequestContext(
        plugin=plugin,
        capability=capability,
        instance=instance,
        binding=binding,
        device=device,
    )


def _resolve_speaker_request_context(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
    binding_id: str,
    external_device_id: str,
    device_id: str | None,
    required_mode: str,
) -> _ResolvedSpeakerRequestContext:
    plugin = _require_speaker_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        error_code=SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
    )
    capability = _build_speaker_adapter_capability(
        plugin,
        error_code=SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
    )
    if required_mode not in capability.supported_modes:
        raise SpeakerHostServiceError(
            f"当前 speaker 插件没有声明 {required_mode} 能力。",
            error_code=(
                SPEAKER_AUDIO_SESSION_UNSUPPORTED_ERROR_CODE
                if required_mode == "audio_session"
                else SPEAKER_TEXT_TURN_INVALID_ERROR_CODE
            ),
            status_code=409,
            field="plugin_id",
        )
    instance = _require_integration_instance(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        integration_instance_id=integration_instance_id,
        error_code=(
            SPEAKER_RUNTIME_INVALID_ERROR_CODE
            if required_mode == "audio_session"
            else SPEAKER_TEXT_TURN_INVALID_ERROR_CODE
        ),
    )
    binding = db.get(DeviceBinding, binding_id)
    if binding is None:
        raise SpeakerHostServiceError(
            "speaker binding 不存在。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=404,
            field="binding_id",
        )
    if binding.integration_instance_id != instance.id:
        raise SpeakerHostServiceError(
            "speaker binding 不属于当前 integration_instance。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=409,
            field="binding_id",
        )
    if (binding.plugin_id or "").strip() != plugin_id:
        raise SpeakerHostServiceError(
            "speaker binding 不属于当前插件。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=409,
            field="binding_id",
        )
    if (binding.external_device_id or "").strip() != external_device_id:
        raise SpeakerHostServiceError(
            "speaker binding 的 external_device_id 不匹配。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=409,
            field="external_device_id",
        )
    if device_id is not None and binding.device_id != device_id:
        raise SpeakerHostServiceError(
            "speaker binding 的 device_id 不匹配。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=409,
            field="device_id",
        )
    device = db.get(Device, binding.device_id)
    if device is None or device.household_id != household_id:
        raise SpeakerHostServiceError(
            "speaker binding 指向的设备不存在，或不属于当前家庭。",
            error_code=SPEAKER_BINDING_MISSING_ERROR_CODE,
            status_code=404,
            field="binding_id",
        )
    if device.device_type != "speaker":
        raise SpeakerHostServiceError(
            "speaker host 只能接收 device_type=speaker 的绑定。",
            error_code=SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
            status_code=409,
            field="binding_id",
        )
    return _ResolvedSpeakerRequestContext(
        plugin=plugin,
        capability=capability,
        instance=instance,
        binding=binding,
        device=device,
    )


def _resolve_or_create_conversation_session(
    db: Session,
    *,
    actor: ActorContext,
    resolved: _ResolvedSpeakerRequestContext,
    external_conversation_key: str,
) -> str:
    latest_source = conversation_repository.get_latest_turn_source_by_external_conversation_key(
        db,
        household_id=resolved.instance.household_id,
        source_kind=SPEAKER_TURN_SOURCE_KIND,
        platform_code=resolved.plugin.id,
        external_conversation_key=external_conversation_key,
    )
    if latest_source is not None:
        return latest_source.conversation_session_id

    session = create_conversation_session(
        db,
        payload=ConversationSessionCreate(
            household_id=resolved.instance.household_id,
            requester_member_id=None,
            session_mode="family_chat",
            title=f"{resolved.device.name} 对话",
        ),
        actor=actor,
    )
    db.flush()
    return session.id


def _build_text_turn_result_from_turn(
    turn: ConversationTurnRead,
    *,
    duplicated: bool,
    conversation_state: dict[str, Any],
) -> SpeakerTextTurnResult:
    user_message = _find_message_by_id(turn.session.messages, turn.user_message_id)
    assistant_message = _find_message_by_id(turn.session.messages, turn.assistant_message_id)
    if assistant_message is None:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="none",
            request_id=turn.request_id,
            conversation_session_id=turn.session_id,
            user_message_id=turn.user_message_id,
            assistant_message_id=turn.assistant_message_id,
            conversation_state=conversation_state,
        )

    if assistant_message.message_type == "error" or assistant_message.status == "failed" or assistant_message.error_code:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="error",
            request_id=turn.request_id,
            conversation_session_id=turn.session_id,
            user_message_id=user_message.id if user_message is not None else turn.user_message_id,
            assistant_message_id=assistant_message.id,
            error_code=assistant_message.error_code or SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
            error_message=assistant_message.content or turn.error_message or "speaker text turn 处理失败",
            conversation_state=conversation_state,
        )

    reply_text = assistant_message.content.strip()
    if not reply_text:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="none",
            request_id=turn.request_id,
            conversation_session_id=turn.session_id,
            user_message_id=user_message.id if user_message is not None else turn.user_message_id,
            assistant_message_id=assistant_message.id,
            conversation_state=conversation_state,
        )

    return SpeakerTextTurnResult(
        accepted=True,
        duplicated=duplicated,
        result_type="text",
        request_id=turn.request_id,
        conversation_session_id=turn.session_id,
        user_message_id=user_message.id if user_message is not None else turn.user_message_id,
        assistant_message_id=assistant_message.id,
        reply_text=reply_text,
        conversation_state=conversation_state,
    )


def _build_text_turn_result_from_session(
    db: Session,
    *,
    actor: ActorContext,
    session_id: str,
    request_id: str,
    duplicated: bool,
    conversation_state: dict[str, Any],
) -> SpeakerTextTurnResult:
    detail = get_conversation_session_detail(db, session_id=session_id, actor=actor)
    user_message = _find_message_by_request_id(detail.messages, request_id=request_id, role="user")
    assistant_message = _find_message_by_request_id(detail.messages, request_id=request_id, role="assistant")
    if assistant_message is None:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="error",
            request_id=request_id,
            conversation_session_id=session_id,
            user_message_id=user_message.id if user_message is not None else None,
            error_code=SPEAKER_TURN_DUPLICATED_ERROR_CODE,
            error_message="同一条 turn 已经入链，但还没有可复用的结果。",
            conversation_state=conversation_state,
        )

    if assistant_message.message_type == "error" or assistant_message.status == "failed" or assistant_message.error_code:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="error",
            request_id=request_id,
            conversation_session_id=session_id,
            user_message_id=user_message.id if user_message is not None else None,
            assistant_message_id=assistant_message.id,
            error_code=assistant_message.error_code or SPEAKER_TEXT_TURN_INVALID_ERROR_CODE,
            error_message=assistant_message.content or "speaker text turn 处理失败",
            conversation_state=conversation_state,
        )

    reply_text = assistant_message.content.strip()
    if not reply_text:
        return SpeakerTextTurnResult(
            accepted=True,
            duplicated=duplicated,
            result_type="none",
            request_id=request_id,
            conversation_session_id=session_id,
            user_message_id=user_message.id if user_message is not None else None,
            assistant_message_id=assistant_message.id,
            conversation_state=conversation_state,
        )

    return SpeakerTextTurnResult(
        accepted=True,
        duplicated=duplicated,
        result_type="text",
        request_id=request_id,
        conversation_session_id=session_id,
        user_message_id=user_message.id if user_message is not None else None,
        assistant_message_id=assistant_message.id,
        reply_text=reply_text,
        conversation_state=conversation_state,
    )


def _apply_runtime_heartbeat_to_instance(
    *,
    instance: IntegrationInstance,
    payload: SpeakerRuntimeHeartbeat,
) -> None:
    instance.last_synced_at = payload.reported_at
    instance.updated_at = utc_now_iso()

    if payload.state in {"idle", "running"} and payload.consecutive_failures == 0:
        instance.status = "active"
        instance.last_error_code = None
        instance.last_error_message = None
        return

    instance.status = "degraded"
    instance.last_error_code = _map_runtime_error_code(payload.state)
    instance.last_error_message = payload.last_error_summary or _build_runtime_error_message(payload.state)


def _upsert_speaker_runtime_state(
    db: Session,
    *,
    resolved: _ResolvedSpeakerRequestContext,
    payload: SpeakerRuntimeHeartbeat,
) -> SpeakerRuntimeStateModel:
    runtime_state = voice_repository.get_speaker_runtime_state_by_integration_instance(
        db,
        integration_instance_id=resolved.instance.id,
    )
    now = utc_now_iso()
    if runtime_state is None:
        runtime_state = SpeakerRuntimeStateModel(
            id=new_uuid(),
            household_id=resolved.instance.household_id,
            plugin_id=resolved.plugin.id,
            integration_instance_id=resolved.instance.id,
            adapter_code=resolved.capability.adapter_code,
            created_at=now,
            updated_at=now,
        )
        voice_repository.add_speaker_runtime_state(db, runtime_state)

    runtime_state.plugin_id = resolved.plugin.id
    runtime_state.adapter_code = resolved.capability.adapter_code
    runtime_state.runtime_state = payload.state
    runtime_state.consecutive_failures = payload.consecutive_failures
    runtime_state.last_succeeded_at = payload.last_succeeded_at
    runtime_state.last_failed_at = payload.last_failed_at
    runtime_state.last_error_summary = payload.last_error_summary
    runtime_state.last_heartbeat_at = payload.reported_at
    runtime_state.updated_at = now
    return runtime_state


def _build_system_actor(*, household_id: str) -> ActorContext:
    return ActorContext(
        role="admin",
        actor_type="system",
        actor_id="speaker-host-service",
        account_id="speaker-host-service",
        account_type="system",
        account_status="active",
        household_id=household_id,
        is_authenticated=True,
    )


def _build_speaker_adapter_capability(
    plugin: PluginRegistryItem,
    *,
    error_code: str,
) -> SpeakerAdapterCapability:
    spec = plugin.capabilities.speaker_adapter
    if spec is None:
        raise SpeakerHostServiceError(
            "当前插件没有声明正式 speaker_adapter 能力。",
            error_code=error_code,
            status_code=409,
            field="plugin_id",
        )
    return SpeakerAdapterCapability.model_validate(
        {
            "plugin_id": plugin.id,
            "adapter_code": spec.adapter_code,
            "supported_modes": list(spec.supported_modes),
            "supported_domains": list(spec.supported_domains),
            "requires_runtime_worker": spec.requires_runtime_worker,
            "supports_discovery": spec.supports_discovery,
            "supports_commands": spec.supports_commands,
            "runtime_entrypoint": plugin.entrypoints.speaker_adapter,
        }
    )


def _require_speaker_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    error_code: str,
) -> PluginRegistryItem:
    try:
        return require_available_household_plugin(
            db,
            household_id=household_id,
            plugin_id=plugin_id,
            plugin_type="integration",
        )
    except PluginServiceError as exc:
        mapped_error_code = exc.error_code if exc.error_code == "plugin_disabled" else error_code
        raise SpeakerHostServiceError(
            exc.detail,
            error_code=mapped_error_code,
            status_code=exc.status_code,
            field=exc.field,
        ) from exc


def _require_integration_instance(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    integration_instance_id: str,
    error_code: str,
) -> IntegrationInstance:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None or instance.household_id != household_id:
        raise SpeakerHostServiceError(
            "integration_instance 不存在，或不属于当前家庭。",
            error_code=error_code,
            status_code=404,
            field="integration_instance_id",
        )
    if instance.plugin_id != plugin_id:
        raise SpeakerHostServiceError(
            "integration_instance 不属于当前 speaker 插件。",
            error_code=error_code,
            status_code=409,
            field="integration_instance_id",
        )
    if instance.status not in {"active", "degraded"}:
        raise SpeakerHostServiceError(
            "integration_instance 还不可用，不能继续接入 speaker runtime。",
            error_code=error_code,
            status_code=409,
            field="integration_instance_id",
        )
    return instance


def _build_turn_request_id(payload: SpeakerTextTurnRequest) -> str:
    return (
        f"speaker:{payload.plugin_id}:{payload.integration_instance_id}:"
        f"{payload.binding_id}:{payload.conversation_id}:{payload.turn_id}"
    )


def _build_external_conversation_key(
    *,
    plugin_id: str,
    integration_instance_id: str,
    external_device_id: str,
    conversation_id: str,
) -> str:
    return (
        f"speaker:{plugin_id}:{integration_instance_id}:"
        f"{external_device_id}:{conversation_id}"
    )


def _build_conversation_state(
    *,
    resolved: _ResolvedSpeakerRequestContext,
    external_conversation_key: str,
) -> dict[str, Any]:
    return {
        "binding_id": resolved.binding.id,
        "device_id": resolved.device.id,
        "integration_instance_id": resolved.instance.id,
        "external_conversation_key": external_conversation_key,
    }


def _find_message_by_id(messages: list[Any], message_id: str) -> Any | None:
    return next((item for item in messages if item.id == message_id), None)


def _find_message_by_request_id(
    messages: list[Any],
    *,
    request_id: str,
    role: str,
) -> Any | None:
    candidates = [item for item in messages if item.request_id == request_id and item.role == role]
    return candidates[-1] if candidates else None


def _render_http_exception_detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        payload_detail = detail.get("detail")
        if isinstance(payload_detail, str) and payload_detail.strip():
            return payload_detail
        error_code = detail.get("error_code")
        if isinstance(error_code, str) and error_code.strip():
            return error_code
    return "speaker text turn 执行失败"


def _map_runtime_error_code(state: str) -> str:
    if state == "degraded":
        return "speaker_runtime_degraded"
    if state == "error":
        return "speaker_runtime_error"
    if state == "stopped":
        return "speaker_runtime_stopped"
    return "speaker_runtime_unhealthy"


def _build_runtime_error_message(state: str) -> str:
    if state == "degraded":
        return "speaker runtime 已降级。"
    if state == "error":
        return "speaker runtime 进入错误状态。"
    if state == "stopped":
        return "speaker runtime 已停止。"
    return "speaker runtime 当前不健康。"


def _map_instance_status_to_runtime_state(instance: IntegrationInstance) -> str:
    if instance.status == "active":
        return "running"
    if instance.status == "degraded":
        if instance.last_error_code == "speaker_runtime_stopped":
            return "stopped"
        if instance.last_error_code == "speaker_runtime_error":
            return "error"
        return "degraded"
    return "idle"
