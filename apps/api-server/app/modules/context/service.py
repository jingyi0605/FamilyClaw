from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, cast

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import dump_json, load_json, utc_now_iso
from app.modules.context.models import ContextConfig
from app.modules.context.schemas import (
    ActivityStatus,
    ClimatePolicy,
    ContextConfigMemberState,
    ContextConfigRead,
    ContextConfigRoomSetting,
    ContextConfigUpsert,
    ContextOverviewActiveMember,
    ContextOverviewDeviceSummary,
    ContextOverviewInsight,
    ContextOverviewMemberState,
    ContextOverviewRead,
    ContextOverviewRoomOccupancy,
    ContextOverviewRoomOccupant,
    PresenceStatus,
    RoomScenePreset,
)
from app.modules.device.models import Device
from app.modules.household.service import get_household_or_404
from app.modules.member.models import Member
from app.modules.presence.models import MemberPresenceState
from app.modules.room.models import Room


def _list_household_members(db: Session, household_id: str) -> list[Member]:
    statement = (
        select(Member)
        .where(Member.household_id == household_id)
        .order_by(Member.created_at.asc(), Member.id.asc())
    )
    return list(db.scalars(statement).all())


def _list_household_rooms(db: Session, household_id: str) -> list[Room]:
    statement = (
        select(Room)
        .where(Room.household_id == household_id)
        .order_by(Room.created_at.asc(), Room.id.asc())
    )
    return list(db.scalars(statement).all())


def _list_household_devices(db: Session, household_id: str) -> list[Device]:
    statement = (
        select(Device)
        .where(Device.household_id == household_id)
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    return list(db.scalars(statement).all())


def _list_household_presence_states(db: Session, household_id: str) -> list[MemberPresenceState]:
    statement = select(MemberPresenceState).where(MemberPresenceState.household_id == household_id)
    return list(db.scalars(statement).all())


def _find_room_id_by_type(rooms: list[Room], room_types: list[str]) -> str | None:
    for room_type in room_types:
        room = next((item for item in rooms if item.room_type == room_type), None)
        if room is not None:
            return room.id
    return rooms[0].id if rooms else None


def _default_member_presence(member: Member) -> PresenceStatus:
    if member.status != "active":
        return "away"
    if member.role == "guest":
        return "away"
    return "home"


def _default_member_activity(member: Member) -> ActivityStatus:
    if member.role == "admin":
        return "focused"
    if member.role == "adult":
        return "active"
    if member.role == "child":
        return "resting"
    return "idle"


def _default_member_confidence(member: Member) -> int:
    return {
        "admin": 92,
        "adult": 88,
        "child": 84,
        "elder": 80,
        "guest": 65,
    }.get(member.role, 0)


def _default_last_seen_minutes(member: Member) -> int:
    return {
        "admin": 4,
        "adult": 8,
        "child": 6,
        "elder": 12,
        "guest": 45,
    }.get(member.role, 0)


def _default_member_highlight(member: Member) -> str:
    return {
        "admin": "偏好与权限配置最完整，适合作为默认服务对象。",
        "adult": "优先联动公共空间设备与家庭提醒。",
        "child": "需结合儿童保护与作息规则处理内容和设备控制。",
        "elder": "优先关注健康提醒、低打扰播报与安全确认。",
        "guest": "默认只暴露公共信息与有限控制范围。",
    }.get(member.role, "当前成员尚未配置额外上下文提示。")


def _default_member_room_id(member: Member, rooms: list[Room]) -> str | None:
    return {
        "admin": _find_room_id_by_type(rooms, ["study", "living_room", "bedroom"]),
        "adult": _find_room_id_by_type(rooms, ["living_room", "study", "bedroom"]),
        "child": _find_room_id_by_type(rooms, ["bedroom", "living_room"]),
        "elder": _find_room_id_by_type(rooms, ["living_room", "bedroom"]),
        "guest": _find_room_id_by_type(rooms, ["entrance", "living_room"]),
    }.get(member.role, rooms[0].id if rooms else None)


def _build_default_member_state(member: Member, rooms: list[Room]) -> ContextConfigMemberState:
    presence = _default_member_presence(member)
    activity: ActivityStatus = "idle" if presence == "away" else _default_member_activity(member)
    return ContextConfigMemberState(
        member_id=member.id,
        presence=presence,
        activity=activity,
        current_room_id=None if presence == "away" else _default_member_room_id(member, rooms),
        confidence=_default_member_confidence(member),
        last_seen_minutes=_default_last_seen_minutes(member),
        highlight=_default_member_highlight(member),
    )


def _default_room_scene_preset(room: Room) -> RoomScenePreset:
    if room.room_type == "living_room":
        return "welcome"
    if room.room_type in {"bedroom", "bathroom"}:
        return "rest"
    if room.room_type in {"study", "gym"}:
        return "focus"
    return "auto"


def _default_climate_policy(room: Room) -> ClimatePolicy:
    if room.room_type in {"bedroom", "study", "gym"}:
        return "follow_member"
    if room.room_type in {"entrance", "bathroom", "garage"}:
        return "manual"
    return "follow_room"


def _build_default_room_setting(room: Room) -> ContextConfigRoomSetting:
    return ContextConfigRoomSetting(
        room_id=room.id,
        scene_preset=_default_room_scene_preset(room),
        climate_policy=_default_climate_policy(room),
        privacy_guard_enabled=room.privacy_level != "public",
        announcement_enabled=room.privacy_level == "public",
    )


def _build_default_context_config(members: list[Member], rooms: list[Room]) -> ContextConfigUpsert:
    member_states = [_build_default_member_state(member, rooms) for member in members]
    first_home_member = next((item for item in member_states if item.presence == "home"), None)
    return ContextConfigUpsert(
        home_mode="home",
        privacy_mode="balanced",
        automation_level="assisted",
        home_assistant_status="healthy",
        active_member_id=first_home_member.member_id if first_home_member else None,
        voice_fast_path_enabled=True,
        guest_mode_enabled=False,
        child_protection_enabled=True,
        elder_care_watch_enabled=True,
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        member_states=member_states,
        room_settings=[_build_default_room_setting(room) for room in rooms],
    )


def _ensure_unique_ids(
    items: list[Any],
    *,
    get_id: Callable[[Any], str],
    label: str,
) -> None:
    seen_ids: set[str] = set()
    for item in items:
        item_id = get_id(item)
        if item_id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"duplicate {label} id in context config",
            )
        seen_ids.add(item_id)


def _normalize_context_config(
    payload: ContextConfigUpsert,
    *,
    members: list[Member],
    rooms: list[Room],
) -> ContextConfigUpsert:
    default_config = _build_default_context_config(members, rooms)
    member_ids = {member.id for member in members}
    room_ids = {room.id for room in rooms}

    _ensure_unique_ids(payload.member_states, get_id=lambda item: item.member_id, label="member")
    _ensure_unique_ids(payload.room_settings, get_id=lambda item: item.room_id, label="room")

    for member_state in payload.member_states:
        if member_state.member_id not in member_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context config contains member outside household",
            )
        if member_state.current_room_id and member_state.current_room_id not in room_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context config contains room outside household",
            )

    for room_setting in payload.room_settings:
        if room_setting.room_id not in room_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context config contains room outside household",
            )

    member_state_map = {item.member_id: item for item in payload.member_states}
    room_setting_map = {item.room_id: item for item in payload.room_settings}

    normalized_member_states: list[ContextConfigMemberState] = []
    for default_member_state in default_config.member_states:
        source = member_state_map.get(default_member_state.member_id)
        if source is None:
            normalized_member_states.append(default_member_state)
            continue

        presence = source.presence
        current_room_id = source.current_room_id if presence == "home" else None
        normalized_member_states.append(
            ContextConfigMemberState(
                member_id=default_member_state.member_id,
                presence=presence,
                activity=source.activity,
                current_room_id=current_room_id,
                confidence=source.confidence,
                last_seen_minutes=source.last_seen_minutes,
                highlight=source.highlight or default_member_state.highlight,
            )
        )

    normalized_room_settings: list[ContextConfigRoomSetting] = []
    for default_room_setting in default_config.room_settings:
        source = room_setting_map.get(default_room_setting.room_id)
        if source is None:
            normalized_room_settings.append(default_room_setting)
            continue

        normalized_room_settings.append(
            ContextConfigRoomSetting(
                room_id=default_room_setting.room_id,
                scene_preset=source.scene_preset,
                climate_policy=source.climate_policy,
                privacy_guard_enabled=source.privacy_guard_enabled,
                announcement_enabled=source.announcement_enabled,
            )
        )

    if payload.active_member_id and payload.active_member_id not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="active_member_id must belong to the same household",
        )

    home_member_ids = {item.member_id for item in normalized_member_states if item.presence == "home"}
    active_member_id = payload.active_member_id if payload.active_member_id in home_member_ids else None
    if active_member_id is None:
        first_home_member = next((item for item in normalized_member_states if item.presence == "home"), None)
        active_member_id = first_home_member.member_id if first_home_member else None

    return ContextConfigUpsert(
        home_mode=payload.home_mode,
        privacy_mode=payload.privacy_mode,
        automation_level=payload.automation_level,
        home_assistant_status=payload.home_assistant_status,
        active_member_id=active_member_id,
        voice_fast_path_enabled=payload.voice_fast_path_enabled,
        guest_mode_enabled=payload.guest_mode_enabled,
        child_protection_enabled=payload.child_protection_enabled,
        elder_care_watch_enabled=payload.elder_care_watch_enabled,
        quiet_hours_enabled=payload.quiet_hours_enabled,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
        member_states=normalized_member_states,
        room_settings=normalized_room_settings,
    )


def _load_persisted_context_config(row: ContextConfig | None) -> ContextConfigUpsert | None:
    if row is None:
        return None

    raw_value = load_json(row.config_json)
    if not isinstance(raw_value, dict):
        return None

    try:
        return ContextConfigUpsert.model_validate(raw_value)
    except ValidationError:
        return None


def _to_context_config_read(
    *,
    household_id: str,
    config: ContextConfigUpsert,
    row: ContextConfig | None,
    default_updated_at: str,
) -> ContextConfigRead:
    return ContextConfigRead(
        household_id=household_id,
        version=row.version if row is not None else 0,
        updated_by=row.updated_by if row is not None else None,
        updated_at=row.updated_at if row is not None else default_updated_at,
        **config.model_dump(mode="json"),
    )


def get_context_config(db: Session, household_id: str) -> ContextConfigRead:
    household = get_household_or_404(db, household_id)
    members = _list_household_members(db, household_id)
    rooms = _list_household_rooms(db, household_id)
    row = db.get(ContextConfig, household_id)

    payload = _load_persisted_context_config(row) or _build_default_context_config(members, rooms)
    normalized = _normalize_context_config(payload, members=members, rooms=rooms)
    return _to_context_config_read(
        household_id=household_id,
        config=normalized,
        row=row,
        default_updated_at=household.updated_at,
    )


def upsert_context_config(
    db: Session,
    *,
    household_id: str,
    payload: ContextConfigUpsert,
    actor: ActorContext,
) -> ContextConfigRead:
    household = get_household_or_404(db, household_id)
    members = _list_household_members(db, household_id)
    rooms = _list_household_rooms(db, household_id)
    normalized = _normalize_context_config(payload, members=members, rooms=rooms)

    row = db.get(ContextConfig, household_id)
    if row is None:
        row = ContextConfig(
            household_id=household_id,
            config_json=dump_json(normalized.model_dump(mode="json")) or "{}",
            version=1,
            updated_by=actor.actor_id or actor.actor_type,
            updated_at=utc_now_iso(),
        )
    else:
        row.config_json = dump_json(normalized.model_dump(mode="json")) or "{}"
        row.version += 1
        row.updated_by = actor.actor_id or actor.actor_type
        row.updated_at = utc_now_iso()

    db.add(row)

    return _to_context_config_read(
        household_id=household_id,
        config=normalized,
        row=row,
        default_updated_at=household.updated_at,
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_since(value: str | None, fallback: int) -> int:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return fallback
    now = datetime.now(timezone.utc)
    minutes = int(max(0, (now - parsed).total_seconds() // 60))
    return minutes


def _presence_confidence_to_percent(value: float) -> int:
    if value <= 1:
        return int(round(max(0, min(1, value)) * 100))
    return int(round(max(0, min(100, value))))


def get_context_overview(db: Session, household_id: str) -> ContextOverviewRead:
    household = get_household_or_404(db, household_id)
    members = _list_household_members(db, household_id)
    rooms = _list_household_rooms(db, household_id)
    devices = _list_household_devices(db, household_id)
    presence_states = _list_household_presence_states(db, household_id)
    config_read = get_context_config(db, household_id)

    room_by_id = {room.id: room for room in rooms}
    config_member_state_map = {item.member_id: item for item in config_read.member_states}
    config_room_setting_map = {item.room_id: item for item in config_read.room_settings}
    presence_state_map = {item.member_id: item for item in presence_states}

    overview_member_states: list[ContextOverviewMemberState] = []
    live_snapshot_count = 0

    for member in members:
        config_member_state = config_member_state_map.get(member.id) or _build_default_member_state(member, rooms)
        presence_state = presence_state_map.get(member.id)

        if presence_state is not None:
            live_snapshot_count += 1
            if presence_state.status in {"home", "away", "unknown"}:
                presence: PresenceStatus = cast(PresenceStatus, presence_state.status)
            else:
                presence = "unknown"
            current_room_id = presence_state.current_room_id if presence == "home" else None
            current_room = room_by_id.get(current_room_id) if current_room_id else None
            overview_member_states.append(
                ContextOverviewMemberState(
                    member_id=member.id,
                    name=member.name,
                    role=member.role,
                    presence=presence,
                    activity=config_member_state.activity,
                    current_room_id=current_room_id,
                    current_room_name=current_room.name if current_room else None,
                    confidence=_presence_confidence_to_percent(presence_state.confidence),
                    last_seen_minutes=_minutes_since(
                        presence_state.updated_at,
                        config_member_state.last_seen_minutes,
                    ),
                    highlight=config_member_state.highlight,
                    source="snapshot",
                    source_summary=load_json(presence_state.source_summary),
                    updated_at=presence_state.updated_at,
                )
            )
            continue

        current_room_id = (
            config_member_state.current_room_id if config_member_state.presence == "home" else None
        )
        current_room = room_by_id.get(current_room_id) if current_room_id else None
        source = "configured" if config_read.version > 0 else "default"
        overview_member_states.append(
            ContextOverviewMemberState(
                member_id=member.id,
                name=member.name,
                role=member.role,
                presence=config_member_state.presence,
                activity=config_member_state.activity,
                current_room_id=current_room_id,
                current_room_name=current_room.name if current_room else None,
                confidence=config_member_state.confidence,
                last_seen_minutes=config_member_state.last_seen_minutes,
                highlight=config_member_state.highlight,
                source=source,
                source_summary=None,
                updated_at=config_read.updated_at if config_read.version > 0 else None,
            )
        )

    active_member: ContextOverviewActiveMember | None = None
    if config_read.active_member_id:
        configured_active = next(
            (
                item
                for item in overview_member_states
                if item.member_id == config_read.active_member_id and item.presence == "home"
            ),
            None,
        )
        if configured_active is not None:
            active_member = ContextOverviewActiveMember(
                member_id=configured_active.member_id,
                name=configured_active.name,
                role=configured_active.role,
                presence=configured_active.presence,
                activity=configured_active.activity,
                current_room_id=configured_active.current_room_id,
                current_room_name=configured_active.current_room_name,
                confidence=configured_active.confidence,
                source=configured_active.source,
            )

    if active_member is None:
        home_candidates = [item for item in overview_member_states if item.presence == "home"]
        home_candidates.sort(
            key=lambda item: (
                1 if item.source == "snapshot" else 0,
                item.confidence,
                item.name,
            ),
            reverse=True,
        )
        if home_candidates:
            item = home_candidates[0]
            active_member = ContextOverviewActiveMember(
                member_id=item.member_id,
                name=item.name,
                role=item.role,
                presence=item.presence,
                activity=item.activity,
                current_room_id=item.current_room_id,
                current_room_name=item.current_room_name,
                confidence=item.confidence,
                source=item.source,
            )

    room_occupancy: list[ContextOverviewRoomOccupancy] = []
    devices_by_room: dict[str, list[Device]] = {}
    for device in devices:
        if device.room_id is None:
            continue
        devices_by_room.setdefault(device.room_id, []).append(device)

    for room in rooms:
        occupants = [
            item
            for item in overview_member_states
            if item.presence == "home" and item.current_room_id == room.id
        ]
        room_devices = devices_by_room.get(room.id, [])
        room_setting = config_room_setting_map.get(room.id) or _build_default_room_setting(room)
        room_occupancy.append(
            ContextOverviewRoomOccupancy(
                room_id=room.id,
                name=room.name,
                room_type=room.room_type,
                privacy_level=room.privacy_level,
                occupant_count=len(occupants),
                occupants=[
                    ContextOverviewRoomOccupant(
                        member_id=item.member_id,
                        name=item.name,
                        role=item.role,
                        presence=item.presence,
                        activity=item.activity,
                    )
                    for item in occupants
                ],
                device_count=len(room_devices),
                online_device_count=sum(1 for device in room_devices if device.status == "active"),
                scene_preset=room_setting.scene_preset,
                climate_policy=room_setting.climate_policy,
                privacy_guard_enabled=room_setting.privacy_guard_enabled,
                announcement_enabled=room_setting.announcement_enabled,
            )
        )

    device_summary = ContextOverviewDeviceSummary(
        total=len(devices),
        active=sum(1 for device in devices if device.status == "active"),
        offline=sum(1 for device in devices if device.status == "offline"),
        inactive=sum(1 for device in devices if device.status == "inactive"),
        controllable=sum(1 for device in devices if bool(device.controllable)),
    )

    children_home = [item for item in overview_member_states if item.role == "child" and item.presence == "home"]
    elders_home = [item for item in overview_member_states if item.role == "elder" and item.presence == "home"]
    insights: list[ContextOverviewInsight] = []

    if live_snapshot_count == 0:
        insights.append(
            ContextOverviewInsight(
                code="no_live_presence",
                title="缺少实时在家快照",
                message="当前还没有实时的 member_presence_state 数据，系统只能回退到配置或默认状态。",
                tone="warning",
            )
        )

    if device_summary.offline > 0:
        insights.append(
            ContextOverviewInsight(
                code="offline_devices",
                title="存在离线设备",
                message=f"当前有 {device_summary.offline} 台设备离线，相关房间联动和状态判断可能失真。",
                tone="warning",
            )
        )

    if config_read.home_assistant_status == "offline":
        insights.append(
            ContextOverviewInsight(
                code="ha_offline",
                title="Home Assistant 离线",
                message="设备控制与状态同步目前不可依赖，页面只适合做只读判断。",
                tone="danger",
            )
        )
    elif config_read.home_assistant_status == "degraded":
        insights.append(
            ContextOverviewInsight(
                code="ha_degraded",
                title="Home Assistant 部分降级",
                message="设备同步和动作执行处于降级状态，需要关注失败日志。",
                tone="warning",
            )
        )

    if children_home and not config_read.child_protection_enabled:
        insights.append(
            ContextOverviewInsight(
                code="child_protection_disabled",
                title="儿童保护未开启",
                message="当前有儿童在家，但儿童保护关闭。这会让内容、播报和控制链路变得不可靠。",
                tone="danger",
            )
        )

    if elders_home and not config_read.elder_care_watch_enabled:
        insights.append(
            ContextOverviewInsight(
                code="elder_care_disabled",
                title="老人关怀未开启",
                message="当前有长辈在家，但老人关怀关闭。提醒和低打扰策略会明显变差。",
                tone="warning",
            )
        )

    if config_read.guest_mode_enabled:
        insights.append(
            ContextOverviewInsight(
                code="guest_mode_enabled",
                title="访客模式已开启",
                message="系统当前应收紧敏感信息展示和高风险动作范围。",
                tone="info",
            )
        )

    degraded = live_snapshot_count == 0 or config_read.home_assistant_status != "healthy"

    return ContextOverviewRead(
        household_id=household.id,
        household_name=household.name,
        home_mode=config_read.home_mode,
        privacy_mode=config_read.privacy_mode,
        automation_level=config_read.automation_level,
        home_assistant_status=config_read.home_assistant_status,
        voice_fast_path_enabled=config_read.voice_fast_path_enabled,
        guest_mode_enabled=config_read.guest_mode_enabled,
        child_protection_enabled=config_read.child_protection_enabled,
        elder_care_watch_enabled=config_read.elder_care_watch_enabled,
        quiet_hours_enabled=config_read.quiet_hours_enabled,
        quiet_hours_start=config_read.quiet_hours_start,
        quiet_hours_end=config_read.quiet_hours_end,
        active_member=active_member,
        member_states=overview_member_states,
        room_occupancy=room_occupancy,
        device_summary=device_summary,
        insights=insights,
        degraded=degraded,
        generated_at=utc_now_iso(),
    )
