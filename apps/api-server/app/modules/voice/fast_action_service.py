from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.modules.context.service import get_context_overview
from app.modules.device.models import Device
from app.modules.device.schemas import DeviceRead
from app.modules.device.service import list_devices
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_action.service import aexecute_device_action
from app.modules.scene.schemas import SceneTriggerRequest
from app.modules.scene.service import atrigger_template, list_templates

VoiceRouteType = Literal["device_action", "scene", "conversation"]


class VoiceRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_type: VoiceRouteType
    route_target: str | None = None
    reason: str
    response_text: str | None = None
    error_code: str | None = None
    confirm_high_risk: bool = False


class VoiceFastActionService:
    async def resolve(self, db: Session, *, household_id: str, transcript_text: str) -> VoiceRouteDecision:
        text = transcript_text.strip()
        if not text:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="转写结果为空，直接回退慢路径。",
            )

        scene_decision = self._match_scene(db, household_id=household_id, transcript_text=text)
        if scene_decision is not None:
            return scene_decision

        device_decision = self._match_device(db, household_id=household_id, transcript_text=text)
        if device_decision is not None:
            return device_decision

        return VoiceRouteDecision(
            route_type="conversation",
            reason="没有命中快路径设备或场景，回退慢路径。",
        )

    async def execute(self, db: Session, *, household_id: str, decision: VoiceRouteDecision) -> VoiceRouteDecision:
        if decision.route_type == "scene":
            result = await atrigger_template(
                db,
                household_id=household_id,
                template_code=decision.route_target or "",
                payload=SceneTriggerRequest(
                    household_id=household_id,
                    trigger_source="voice_fast_path",
                    trigger_payload={"route_target": decision.route_target},
                    confirm_high_risk=decision.confirm_high_risk,
                    updated_by="voice_pipeline",
                ),
            )
            return decision.model_copy(
                update={
                    "response_text": decision.response_text or f"好的，已执行场景：{result.execution.summary.get('template_code') or decision.route_target}。",
                }
            )

        if decision.route_type == "device_action":
            device_id, action = self._split_device_route_target(decision.route_target)
            response, _audit_context = await aexecute_device_action(
                db,
                payload=DeviceActionExecuteRequest(
                    household_id=household_id,
                    device_id=device_id,
                    action=action,
                    params={},
                    reason="voice_fast_path",
                    confirm_high_risk=decision.confirm_high_risk,
                ),
            )
            device = DeviceRead.model_validate(response.device)
            return decision.model_copy(
                update={
                    "response_text": decision.response_text or f"好的，已处理设备：{device.name}。",
                }
            )

        return decision

    def _match_scene(self, db: Session, *, household_id: str, transcript_text: str) -> VoiceRouteDecision | None:
        templates = list_templates(db, household_id=household_id, enabled=True)
        lowered = transcript_text.lower()
        for template in templates:
            if template.name in transcript_text or template.template_code in lowered:
                return VoiceRouteDecision(
                    route_type="scene",
                    route_target=template.template_code,
                    reason="命中已存在场景模板。",
                    response_text=f"好的，正在执行场景：{template.name}。",
                )
        return None

    def _match_device(self, db: Session, *, household_id: str, transcript_text: str) -> VoiceRouteDecision | None:
        action = self._resolve_action(transcript_text)
        if action is None:
            return None

        devices, _total = list_devices(db, household_id=household_id, page=1, page_size=200)
        context_overview = get_context_overview(db, household_id)
        room_names = {room.room_id: room.name for room in context_overview.room_occupancy}

        matched_devices: list[Device] = []
        for device in devices:
            if not bool(device.controllable):
                continue
            if device.name in transcript_text:
                matched_devices.append(device)

        if not matched_devices:
            return None

        if len(matched_devices) > 1:
            room_filtered = [
                item
                for item in matched_devices
                if item.room_id and room_names.get(item.room_id) and str(room_names[item.room_id]) in transcript_text
            ]
            if len(room_filtered) == 1:
                matched_devices = room_filtered

        if len(matched_devices) != 1:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="快路径命中多个设备，先回退慢路径避免误控。",
                error_code="fast_action_ambiguous",
            )

        device = matched_devices[0]
        resolved_action = self._map_action_for_device(device, action)
        if resolved_action is None:
            return None
        return VoiceRouteDecision(
            route_type="device_action",
            route_target=f"{device.id}:{resolved_action}",
            reason="命中单一可控设备。",
            response_text=f"好的，正在处理 {device.name}。",
        )

    def _resolve_action(self, transcript_text: str) -> str | None:
        if any(keyword in transcript_text for keyword in ("打开", "开启")):
            return "turn_on"
        if any(keyword in transcript_text for keyword in ("关闭", "关掉")):
            return "turn_off"
        if "停止" in transcript_text:
            return "stop"
        return None

    def _map_action_for_device(self, device: Device, action: str) -> str | None:
        if device.device_type == "curtain":
            if action == "turn_on":
                return "open"
            if action == "turn_off":
                return "close"
            if action == "stop":
                return "stop"
            return None
        if device.device_type in {"light", "ac", "speaker"} and action in {"turn_on", "turn_off"}:
            return action
        if device.device_type == "speaker" and action == "stop":
            return "play_pause"
        return None

    def _split_device_route_target(self, route_target: str | None) -> tuple[str, str]:
        if not route_target or ":" not in route_target:
            raise ValueError("device_action route_target 非法")
        device_id, action = route_target.split(":", 1)
        return device_id, action


voice_fast_action_service = VoiceFastActionService()
