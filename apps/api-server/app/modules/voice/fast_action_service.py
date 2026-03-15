from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.modules.context.schemas import ContextOverviewRead
from app.modules.device.models import Device
from app.modules.device.service import list_devices
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_action.service import HIGH_RISK_ACTIONS, aexecute_device_action
from app.modules.scene.schemas import SceneTriggerRequest
from app.modules.scene.service import atrigger_template, list_templates
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState

VoiceRouteType = Literal["device_action", "scene", "conversation"]

_ROOM_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "living_room": ("客厅", "起居室"),
    "bedroom": ("卧室", "主卧", "次卧"),
    "study": ("书房", "办公室"),
    "kids_room": ("儿童房", "孩子房", "宝宝房"),
    "balcony": ("阳台",),
    "kitchen": ("厨房",),
    "bathroom": ("卫生间", "洗手间"),
    "dining_room": ("餐厅",),
    "entrance": ("门口", "玄关"),
}
_DEVICE_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "light": ("灯", "灯光", "照明"),
    "ac": ("空调", "冷气"),
    "curtain": ("窗帘", "帘子"),
    "speaker": ("音箱", "音响", "喇叭"),
    "lock": ("门锁", "锁"),
}
_ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("turn_on", ("打开", "开启", "开一下", "开灯", "开空调", "开音箱")),
    ("turn_off", ("关闭", "关掉", "关上", "关一下", "关灯", "关空调", "关音箱")),
    ("stop", ("停止", "停下", "暂停")),
    ("open", ("拉开", "打开窗帘", "开窗帘")),
    ("close", ("拉上", "合上", "关窗帘")),
    ("increase", ("调高", "调大", "开大", "亮一点")),
    ("decrease", ("调低", "调小", "关小", "暗一点")),
    ("lock", ("反锁", "上锁", "锁上")),
    ("unlock", ("解锁", "开锁")),
)
_DISTURBING_DEVICE_TYPES = {"speaker"}
_HIGH_RISK_DEVICE_TYPES = {"lock"}
_DEFAULT_SCENE_ALIASES: dict[str, tuple[str, ...]] = {
    "smart_homecoming": ("回家模式", "回家场景", "回家"),
    "child_bedtime": ("睡前模式", "儿童睡前", "睡觉模式"),
    "elder_care": ("老人关怀", "长辈关怀"),
}


class VoiceRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_type: VoiceRouteType
    route_target: str | None = None
    route_params: dict[str, object] = Field(default_factory=dict)
    reason: str
    response_text: str | None = None
    error_code: str | None = None
    confirm_high_risk: bool = False
    handoff_to_conversation: bool = False


class VoiceFastActionExecutionError(RuntimeError):
    def __init__(self, *, error_code: str, detail: str, response_text: str | None = None) -> None:
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.response_text = response_text


@dataclass(slots=True)
class _ResolvedScope:
    explicit_room: bool
    room_ids: list[str]
    room_names: list[str]
    error_code: str | None = None
    response_text: str | None = None


class VoiceFastActionService:
    async def resolve(
        self,
        db: Session,
        *,
        household_id: str,
        transcript_text: str,
        context_overview: ContextOverviewRead,
        terminal: VoiceTerminalState | None = None,
        session: VoiceSessionState | None = None,
        identity: VoiceIdentityResolution | None = None,
    ) -> VoiceRouteDecision:
        text = transcript_text.strip()
        if not text:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="转写文本为空，直接回退慢路径。",
                handoff_to_conversation=True,
            )

        if not context_overview.voice_fast_path_enabled:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="家庭上下文关闭了语音快路径。",
                handoff_to_conversation=True,
            )

        scope = self._resolve_room_scope(
            transcript_text=text,
            context_overview=context_overview,
            terminal=terminal,
            session=session,
            identity=identity,
        )
        if scope.error_code is not None:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="房间范围无法收敛。",
                error_code=scope.error_code,
                response_text=scope.response_text,
                handoff_to_conversation=False,
            )

        scene_decision = self._match_scene(
            db,
            household_id=household_id,
            transcript_text=text,
            context_overview=context_overview,
        )
        if scene_decision is not None:
            return scene_decision

        return self._match_device(
            db,
            household_id=household_id,
            transcript_text=text,
            context_overview=context_overview,
            scope=scope,
            identity=identity,
        )

    async def execute(self, db: Session, *, household_id: str, decision: VoiceRouteDecision) -> VoiceRouteDecision:
        if decision.route_type == "scene":
            try:
                result = await atrigger_template(
                    db,
                    household_id=household_id,
                    template_code=decision.route_target or "",
                    payload=SceneTriggerRequest(
                        household_id=household_id,
                        trigger_source="voice_fast_path",
                        trigger_payload=decision.route_params,
                        confirm_high_risk=decision.confirm_high_risk,
                        updated_by="voice_pipeline",
                    ),
                )
            except HTTPException as exc:
                raise VoiceFastActionExecutionError(
                    error_code=decision.error_code or "fast_action_blocked",
                    detail=str(exc.detail),
                    response_text=decision.response_text,
                ) from exc

            return decision.model_copy(
                update={
                    "response_text": decision.response_text
                    or f"好的，已执行场景：{result.execution.summary.get('template_code') or decision.route_target}。",
                }
            )

        if decision.route_type == "device_action":
            device_id, action = self._split_device_route_target(decision.route_target)
            try:
                response, _audit_context = await aexecute_device_action(
                    db,
                    payload=DeviceActionExecuteRequest(
                        household_id=household_id,
                        device_id=device_id,
                        action=action,
                        params=decision.route_params,
                        reason="voice_fast_path",
                        confirm_high_risk=decision.confirm_high_risk,
                    ),
                )
            except HTTPException as exc:
                raise VoiceFastActionExecutionError(
                    error_code=decision.error_code or "fast_action_blocked",
                    detail=str(exc.detail),
                    response_text=decision.response_text,
                ) from exc

            return decision.model_copy(
                update={
                    "response_text": decision.response_text
                    or f"好的，已处理设备：{response.device.name}。",
                }
            )

        return decision

    def _match_scene(
        self,
        db: Session,
        *,
        household_id: str,
        transcript_text: str,
        context_overview: ContextOverviewRead,
    ) -> VoiceRouteDecision | None:
        templates = list_templates(db, household_id=household_id, enabled=True)
        matched_templates = []
        for template in templates:
            aliases = self._build_scene_aliases(template.template_code, template.name)
            if any(alias and alias in transcript_text for alias in aliases):
                matched_templates.append(template)

        if not matched_templates:
            return None

        if len(matched_templates) > 1:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="命中了多个场景模板，不能瞎猜。",
                error_code="fast_action_ambiguous",
                response_text="我听到了多个场景，你得说清楚要执行哪一个。",
                handoff_to_conversation=False,
            )

        template = matched_templates[0]
        scene_guard = self._guard_scene(template=template, context_overview=context_overview)
        if scene_guard is not None:
            return scene_guard

        return VoiceRouteDecision(
            route_type="scene",
            route_target=template.template_code,
            route_params={"matched_alias": template.name},
            reason="命中了单一场景模板。",
            response_text=f"好的，正在执行场景：{template.name}。",
        )

    def _match_device(
        self,
        db: Session,
        *,
        household_id: str,
        transcript_text: str,
        context_overview: ContextOverviewRead,
        scope: _ResolvedScope,
        identity: VoiceIdentityResolution | None,
    ) -> VoiceRouteDecision:
        action_key = self._resolve_action_key(transcript_text)
        if action_key is None and "锁" in transcript_text:
            if any(keyword in transcript_text for keyword in ("解", "开")):
                action_key = "unlock"
            elif any(keyword in transcript_text for keyword in ("反", "上")):
                action_key = "lock"
        if action_key is None:
            if "锁" in transcript_text and any(keyword in transcript_text for keyword in ("解", "开")):
                return VoiceRouteDecision(
                    route_type="conversation",
                    reason="门锁类高风险动作先阻断，不赌动作解析。",
                    error_code="high_risk_action_blocked",
                    response_text="门锁解锁这类高风险动作，不能只靠一句语音直接执行。",
                    handoff_to_conversation=False,
                )
            return VoiceRouteDecision(
                route_type="conversation",
                reason="没有找到明确动作词，回退慢路径。",
                handoff_to_conversation=True,
            )
        if action_key == "ambiguous":
            return VoiceRouteDecision(
                route_type="conversation",
                reason="动作词不明确。",
                error_code="fast_action_action_ambiguous",
                response_text="我没听明白你要做什么动作，请明确说打开、关闭、拉开、拉上或停止。",
                handoff_to_conversation=False,
            )

        devices, _total = list_devices(db, household_id=household_id, page=1, page_size=500)
        scored_devices: list[tuple[int, Device, list[str]]] = []
        for device in devices:
            if not bool(device.controllable):
                continue
            if device.status != "active":
                continue
            score, reasons = self._score_device(device=device, transcript_text=transcript_text, scope=scope)
            if score > 0:
                scored_devices.append((score, device, reasons))

        if not scored_devices:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="没有找到可控设备。",
                handoff_to_conversation=True,
            )

        scored_devices.sort(key=lambda item: (item[0], item[1].name), reverse=True)
        best_score = scored_devices[0][0]
        top_matches = [item for item in scored_devices if item[0] == best_score]
        if len(top_matches) > 1:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="命中了多个同分设备。",
                error_code="fast_action_device_ambiguous",
                response_text=self._build_device_ambiguity_text(top_matches),
                handoff_to_conversation=False,
            )

        device = top_matches[0][1]
        if device.device_type == "lock" and "锁" in transcript_text and any(
            keyword in transcript_text for keyword in ("解", "开")
        ):
            return VoiceRouteDecision(
                route_type="conversation",
                reason="门锁解锁属于高风险动作，先阻断。",
                error_code="high_risk_action_blocked",
                response_text="门锁解锁这类高风险动作，不能只靠一句语音直接执行。",
                handoff_to_conversation=False,
            )
        mapped = self._map_action_for_device(device=device, action_key=action_key)
        if mapped is None:
            if device.device_type == "lock":
                return VoiceRouteDecision(
                    route_type="conversation",
                    reason="门锁相关语音命令宁可拦住，也不做猜测。",
                    error_code="high_risk_action_blocked",
                    response_text="门锁这类高风险设备不会因为模糊语音直接执行。",
                    handoff_to_conversation=False,
                )
            return VoiceRouteDecision(
                route_type="conversation",
                reason="动作词存在，但当前设备不支持这类动作。",
                error_code="fast_action_action_ambiguous",
                response_text=f"{device.name} 不能这样控制，你得换个更明确的说法。",
                handoff_to_conversation=False,
            )

        guard_decision = self._guard_device_action(
            device=device,
            action=mapped.action,
            params=mapped.params,
            context_overview=context_overview,
            identity=identity,
        )
        if guard_decision is not None:
            return guard_decision

        return VoiceRouteDecision(
            route_type="device_action",
            route_target=f"{device.id}:{mapped.action}",
            route_params=mapped.params,
            reason="房间、设备、动作都收敛到了单一目标。",
            response_text=f"好的，正在处理{device.name}。",
        )

    def _resolve_room_scope(
        self,
        *,
        transcript_text: str,
        context_overview: ContextOverviewRead,
        terminal: VoiceTerminalState | None,
        session: VoiceSessionState | None,
        identity: VoiceIdentityResolution | None,
    ) -> _ResolvedScope:
        room_alias_hits: dict[str, str] = {}
        room_name_by_id = {room.room_id: room.name for room in context_overview.room_occupancy}
        for room in context_overview.room_occupancy:
            aliases = {room.name, *_ROOM_TYPE_ALIASES.get(room.room_type, ())}
            for alias in aliases:
                normalized_alias = alias.strip()
                if normalized_alias and normalized_alias in transcript_text:
                    room_alias_hits[room.room_id] = room.name

        if len(room_alias_hits) > 1:
            return _ResolvedScope(
                explicit_room=True,
                room_ids=list(room_alias_hits.keys()),
                room_names=list(room_alias_hits.values()),
                error_code="fast_action_room_ambiguous",
                response_text="你一下子提到了多个房间，我不能替你瞎选。",
            )

        if len(room_alias_hits) == 1:
            room_id, room_name = next(iter(room_alias_hits.items()))
            return _ResolvedScope(explicit_room=True, room_ids=[room_id], room_names=[room_name])

        inferred_room_id = session.room_id if session and session.room_id else terminal.room_id if terminal else None
        if inferred_room_id is None and identity is not None and identity.inferred_room_id is not None:
            inferred_room_id = identity.inferred_room_id
        if inferred_room_id is None and context_overview.active_member is not None:
            inferred_room_id = context_overview.active_member.current_room_id
        if inferred_room_id is None:
            occupied_rooms = [room for room in context_overview.room_occupancy if room.occupant_count > 0]
            if len(occupied_rooms) == 1:
                inferred_room_id = occupied_rooms[0].room_id

        if inferred_room_id is None:
            return _ResolvedScope(explicit_room=False, room_ids=[], room_names=[])

        return _ResolvedScope(
            explicit_room=False,
            room_ids=[inferred_room_id],
            room_names=[room_name_by_id.get(inferred_room_id) or inferred_room_id],
        )

    def _score_device(self, *, device: Device, transcript_text: str, scope: _ResolvedScope) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        normalized_name = device.name.strip()
        if normalized_name and normalized_name in transcript_text:
            score += 120
            reasons.append("命中设备名")

        for alias in _DEVICE_TYPE_ALIASES.get(device.device_type, ()):
            if alias in transcript_text:
                score += 40
                reasons.append("命中设备类型词")
                break

        if scope.room_ids:
            if device.room_id in scope.room_ids:
                score += 30
                reasons.append("命中房间范围")
            else:
                return 0, []

        return score, reasons

    def _resolve_action_key(self, transcript_text: str) -> str | None:
        matched_keys: list[str] = []
        for action_key, aliases in _ACTION_PATTERNS:
            if any(alias in transcript_text for alias in aliases):
                matched_keys.append(action_key)

        matched_keys = list(dict.fromkeys(matched_keys))
        if not matched_keys:
            return None

        conflict_pairs = {frozenset({"turn_on", "turn_off"}), frozenset({"open", "close"}), frozenset({"lock", "unlock"})}
        if len(matched_keys) > 1:
            for pair in conflict_pairs:
                if pair.issubset(set(matched_keys)):
                    return "ambiguous"
            preferred_order = ["unlock", "lock", "open", "close", "stop", "turn_on", "turn_off", "increase", "decrease"]
            for item in preferred_order:
                if item in matched_keys:
                    return item

        return matched_keys[0]

    def _map_action_for_device(self, *, device: Device, action_key: str) -> _MappedAction | None:
        if device.device_type == "curtain":
            mapping = {
                "turn_on": _MappedAction(action="open"),
                "open": _MappedAction(action="open"),
                "turn_off": _MappedAction(action="close"),
                "close": _MappedAction(action="close"),
                "stop": _MappedAction(action="stop"),
            }
            return mapping.get(action_key)

        if device.device_type == "light":
            mapping = {
                "turn_on": _MappedAction(action="turn_on"),
                "turn_off": _MappedAction(action="turn_off"),
                "increase": _MappedAction(action="set_brightness", params={"brightness": 80}),
                "decrease": _MappedAction(action="set_brightness", params={"brightness": 30}),
            }
            return mapping.get(action_key)

        if device.device_type == "speaker":
            mapping = {
                "turn_on": _MappedAction(action="turn_on"),
                "turn_off": _MappedAction(action="turn_off"),
                "stop": _MappedAction(action="play_pause"),
                "increase": _MappedAction(action="set_volume", params={"volume": 0.7}),
                "decrease": _MappedAction(action="set_volume", params={"volume": 0.3}),
            }
            return mapping.get(action_key)

        if device.device_type == "ac":
            mapping = {
                "turn_on": _MappedAction(action="turn_on"),
                "turn_off": _MappedAction(action="turn_off"),
            }
            return mapping.get(action_key)

        if device.device_type == "lock":
            mapping = {
                "lock": _MappedAction(action="lock"),
                "unlock": _MappedAction(action="unlock"),
            }
            return mapping.get(action_key)

        return None

    def _guard_device_action(
        self,
        *,
        device: Device,
        action: str,
        params: dict[str, object],
        context_overview: ContextOverviewRead,
        identity: VoiceIdentityResolution | None,
    ) -> VoiceRouteDecision | None:
        if self._is_high_risk(device_type=device.device_type, action=action):
            return VoiceRouteDecision(
                route_type="conversation",
                reason="命中了高风险动作，语音快路径不能直接放行。",
                error_code="high_risk_action_blocked",
                response_text="门锁解锁这类高风险动作，不能只靠一句语音直接执行。",
                handoff_to_conversation=False,
            )

        if self._is_quiet_hours_active(context_overview) and device.device_type in _DISTURBING_DEVICE_TYPES:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="静默时段阻断了高打扰动作。",
                error_code="quiet_hours_blocked",
                response_text="现在处于静默时段，我不会直接操作音箱这类高打扰设备。",
                handoff_to_conversation=False,
            )

        if context_overview.child_protection_enabled and (
            device.device_type in _HIGH_RISK_DEVICE_TYPES or action in {"set_volume", "turn_on"} and device.device_type == "speaker"
        ):
            return VoiceRouteDecision(
                route_type="conversation",
                reason="儿童保护要求收紧当前动作。",
                error_code="child_protection_blocked",
                response_text="儿童保护已开启，这个动作我不会直接执行。",
                handoff_to_conversation=False,
            )

        if context_overview.guest_mode_enabled and device.device_type in _HIGH_RISK_DEVICE_TYPES:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="访客模式下不允许高敏感设备动作。",
                error_code="context_conflict",
                response_text="访客模式已开启，高敏感设备动作不会走语音快路径。",
                handoff_to_conversation=False,
            )

        if identity is not None and identity.status == "conflict" and device.device_type in _HIGH_RISK_DEVICE_TYPES:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="当前身份候选冲突，高风险动作必须阻断。",
                error_code="voice_identity_conflict",
                response_text="我没法确认是谁在说话，这个敏感动作不会继续执行。",
                handoff_to_conversation=False,
            )

        return None

    def _guard_scene(self, *, template: Any, context_overview: ContextOverviewRead) -> VoiceRouteDecision | None:
        actions = template.actions if isinstance(template.actions, list) else []
        contains_broadcast = any(str(action.get("type") or "") == "broadcast" for action in actions if isinstance(action, dict))
        contains_high_risk = any(
            str(action.get("type") or "") == "device_action"
            and str(action.get("action") or "") in HIGH_RISK_ACTIONS.get("lock", set())
            for action in actions
            if isinstance(action, dict)
        )

        if contains_high_risk:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="场景里包含高风险动作。",
                error_code="high_risk_action_blocked",
                response_text="这个场景里有高风险动作，语音快路径不会直接放行。",
                handoff_to_conversation=False,
            )

        if self._is_quiet_hours_active(context_overview) and contains_broadcast:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="静默时段阻断了广播型场景。",
                error_code="quiet_hours_blocked",
                response_text="现在处于静默时段，我不会直接执行带广播的场景。",
                handoff_to_conversation=False,
            )

        if context_overview.child_protection_enabled and any(
            str(action.get("type") or "") in {"broadcast", "device_action"} for action in actions if isinstance(action, dict)
        ):
            return VoiceRouteDecision(
                route_type="conversation",
                reason="儿童保护要求收紧当前场景。",
                error_code="child_protection_blocked",
                response_text="儿童保护已开启，这个场景我不会直接执行。",
                handoff_to_conversation=False,
            )

        if context_overview.guest_mode_enabled and contains_broadcast:
            return VoiceRouteDecision(
                route_type="conversation",
                reason="访客模式下不直接执行广播类场景。",
                error_code="context_conflict",
                response_text="访客模式已开启，这种场景需要你在更明确的链路里确认。",
                handoff_to_conversation=False,
            )

        return None

    def _build_device_ambiguity_text(self, matches: list[tuple[int, Device, list[str]]]) -> str:
        names = [item[1].name for item in matches[:3]]
        return f"我找到了多个设备：{'、'.join(names)}。你得把房间或设备名说清楚。"

    def _build_scene_aliases(self, template_code: str, template_name: str) -> set[str]:
        aliases = {
            template_code.strip().lower(),
            template_name.strip(),
            template_name.replace("模式", "").strip(),
            template_name.replace("场景", "").strip(),
        }
        aliases.update(_DEFAULT_SCENE_ALIASES.get(template_code, ()))
        return {alias for alias in aliases if alias}

    def _is_high_risk(self, *, device_type: str, action: str) -> bool:
        return action in HIGH_RISK_ACTIONS.get(device_type, set())

    def _is_quiet_hours_active(self, context_overview: ContextOverviewRead) -> bool:
        if not context_overview.quiet_hours_enabled:
            return False
        current_minutes = self._minutes_of_day(datetime.now().astimezone().strftime("%H:%M"))
        start_minutes = self._minutes_of_day(context_overview.quiet_hours_start)
        end_minutes = self._minutes_of_day(context_overview.quiet_hours_end)
        if start_minutes == end_minutes:
            return True
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _minutes_of_day(self, value: str) -> int:
        hours, minutes = value.split(":", 1)
        return int(hours) * 60 + int(minutes)

    def _split_device_route_target(self, route_target: str | None) -> tuple[str, str]:
        if not route_target or ":" not in route_target:
            raise ValueError("device_action route_target 非法")
        device_id, action = route_target.split(":", 1)
        return device_id, action


class _MappedAction(BaseModel):
    action: str
    params: dict[str, object] = Field(default_factory=dict)


voice_fast_action_service = VoiceFastActionService()
