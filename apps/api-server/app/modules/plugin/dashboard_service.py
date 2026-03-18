from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.context.service import get_context_overview
from app.modules.household.service import get_household_or_404
from app.modules.member.service import get_member_or_404
from app.modules.reminder.service import build_reminder_overview

from . import repository
from .models import MemberDashboardLayout, PluginDashboardCardSnapshot
from .schemas import (
    HomeDashboardCardActionRead,
    HomeDashboardCardRead,
    HomeDashboardRead,
    MemberDashboardLayoutItem,
    MemberDashboardLayoutPayload,
    MemberDashboardLayoutRead,
    MemberDashboardLayoutUpdateRequest,
    PluginDashboardCardSnapshotEnvelope,
    PluginDashboardCardSnapshotErrorUpsert,
    PluginDashboardCardSnapshotRead,
    PluginDashboardCardSnapshotUpsert,
    PluginManifestDashboardCardSpec,
)
from .service import (
    PluginServiceError,
    get_household_plugin,
    list_registered_plugins_for_household,
    require_available_household_plugin,
)

PLUGIN_DASHBOARD_CARD_NOT_DECLARED_ERROR_CODE = "plugin_dashboard_card_not_declared"
PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE = "plugin_dashboard_card_payload_invalid"
MEMBER_DASHBOARD_LAYOUT_INVALID_ERROR_CODE = "member_dashboard_layout_invalid"
MEMBER_DASHBOARD_CARD_NOT_VISIBLE_ERROR_CODE = "member_dashboard_card_not_visible"
PLUGIN_DASHBOARD_CARD_ACTION_LIMIT = 5
PLUGIN_DASHBOARD_CARD_PAYLOAD_MAX_BYTES = 12_000
PLUGIN_DASHBOARD_CARD_ACTION_PAYLOAD_MAX_BYTES = 2_000
DEFAULT_HOME_DASHBOARD_CARD_HEIGHT = "regular"
ALLOWED_HOME_DASHBOARD_CARD_SIZES = {"half", "full"}
ALLOWED_HOME_DASHBOARD_CARD_HEIGHTS = {"compact", "regular", "tall"}
DEFAULT_HOME_LAYOUT_CARD_REFS = (
    "builtin:weather",
    "builtin:stats",
    "builtin:rooms",
    "builtin:members",
    "builtin:events",
    "builtin:quick-actions",
)
OFFICIAL_WEATHER_PLUGIN_ID = "official-weather"
OFFICIAL_WEATHER_DEFAULT_CARD_KEY = "weather-default"
OFFICIAL_WEATHER_DEVICE_CARD_KEY_PREFIX = "weather-device-"
OFFICIAL_WEATHER_CARD_REF_PREFIX = f"plugin:{OFFICIAL_WEATHER_PLUGIN_ID}:home:weather-"
BUILTIN_DASHBOARD_TEXT_DEFAULTS: dict[str, str] = {
    "home.familyStatus": "家庭状态",
    "home.dashboardOverview": "首页总览",
    "home.keyMetrics": "关键指标",
    "home.builtinSummary": "内置聚合摘要",
    "home.roomStatus": "房间状态",
    "home.currentSpaceActivity": "当前空间活跃度",
    "home.memberStatus": "成员状态",
    "home.currentAtHomeAndActivity": "当前在家与活动",
    "home.recentEvents": "最近事件",
    "home.systemInsightsAndReminders": "系统洞察与提醒",
    "home.quickActions": "快捷操作",
    "home.systemControlledNavigation": "系统内受控跳转",
    "home.contextUnavailable": "家庭上下文暂不可用。",
    "home.privacySummary": "隐私：{value}",
    "home.automationSummary": "自动化：{value}",
    "home.quietHoursSummary": "安静时段：{start}-{end}",
    "home.quietHoursDisabled": "安静时段未开启",
    "home.pendingRemindersSummary": "待处理提醒：{count}",
    "home.roomOccupancySummary": "{room_type} · {occupant_count} 人",
    "home.roomDevicesOnlineSummary": "{online}/{total} 设备在线",
    "home.membersAtHome": "在家成员",
    "home.activeRooms": "活跃房间",
    "home.devicesOnline": "在线设备",
    "home.alerts": "待处理提醒",
    "home.eventStatus.done": "已完成",
    "home.eventStatus.pending": "待处理",
    "home.quickAction.assistant.label": "对话",
    "home.quickAction.assistant.description": "打开助手会话",
    "home.quickAction.memories.label": "记忆",
    "home.quickAction.memories.description": "查看家庭记忆",
    "home.quickAction.settings.label": "设置",
    "home.quickAction.settings.description": "进入设置页",
    "home.quickAction.family.label": "家庭",
    "home.quickAction.family.description": "查看家庭成员与房间",
    "home.homeMode.home": "居家模式",
    "home.homeMode.away": "离家模式",
    "home.homeMode.night": "夜间模式",
    "home.homeMode.sleep": "睡眠模式",
    "home.homeMode.custom": "自定义模式",
    "home.homeMode.default": "未设置",
    "home.assistantStatus.healthy": "连接健康",
    "home.assistantStatus.degraded": "部分降级",
    "home.assistantStatus.offline": "连接离线",
    "home.assistantStatus.default": "状态未知",
    "home.privacyMode.balanced": "平衡保护",
    "home.privacyMode.strict": "严格保护",
    "home.privacyMode.care": "关怀优先",
    "home.privacyMode.default": "未设置",
    "home.automationLevel.manual": "手动优先",
    "home.automationLevel.assisted": "辅助自动",
    "home.automationLevel.automatic": "自动优先",
    "home.automationLevel.default": "未设置",
    "home.memberPresence.home": "在家",
    "home.memberPresence.away": "外出",
    "home.memberPresence.unknown": "未知",
    "home.memberPresence.default": "未知",
}
BUILTIN_QUICK_ACTION_SPECS = (
    ("assistant", "/pages/assistant/index"),
    ("memories", "/pages/memories/index"),
    ("settings", "/pages/settings/index"),
    ("family", "/pages/family/index"),
)



def build_plugin_dashboard_card_ref(*, plugin_id: str, placement: str, card_key: str) -> str:
    return f"plugin:{plugin_id}:{placement}:{card_key}"


def build_builtin_dashboard_card_ref(card_key: str) -> str:
    return f"builtin:{card_key}"


def upsert_plugin_dashboard_card_snapshot(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginDashboardCardSnapshotUpsert,
) -> PluginDashboardCardSnapshotRead:
    get_household_or_404(db, household_id)
    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
    )

    card_spec = _get_plugin_dashboard_card_spec(plugin, card_key=payload.card_key, placement=payload.placement)
    row = _get_or_create_snapshot_row(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        placement=payload.placement,
        card_key=payload.card_key,
    )
    generated_at = payload.generated_at or utc_now_iso()

    try:
        envelope = _validate_snapshot_envelope(card_spec, payload.payload, payload.actions)
    except PluginServiceError as exc:
        row.state = "invalid"
        row.payload_json = dump_json({"payload": {}, "actions": []}) or "{}"
        row.error_code = exc.error_code
        row.error_message = exc.detail
        row.generated_at = generated_at
        row.expires_at = payload.expires_at
        row.updated_at = utc_now_iso()
        db.add(row)
        db.flush()
        raise

    row.payload_json = dump_json(envelope.model_dump(mode="json")) or "{}"
    row.state = "ready"
    row.error_code = None
    row.error_message = None
    row.generated_at = generated_at
    row.expires_at = payload.expires_at
    row.updated_at = utc_now_iso()
    db.add(row)
    db.flush()
    return _to_snapshot_read(row)


def record_plugin_dashboard_card_snapshot_error(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    payload: PluginDashboardCardSnapshotErrorUpsert,
) -> PluginDashboardCardSnapshotRead:
    get_household_or_404(db, household_id)
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    _get_plugin_dashboard_card_spec(plugin, card_key=payload.card_key, placement=payload.placement)

    row = _get_or_create_snapshot_row(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        placement=payload.placement,
        card_key=payload.card_key,
    )
    row.payload_json = dump_json({"payload": {}, "actions": []}) or "{}"
    row.state = "error"
    row.error_code = payload.error_code
    row.error_message = payload.error_message
    row.generated_at = payload.generated_at or utc_now_iso()
    row.expires_at = payload.expires_at
    row.updated_at = utc_now_iso()
    db.add(row)
    db.flush()
    return _to_snapshot_read(row)


def list_plugin_dashboard_card_snapshot_reads(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    placement: str = "home",
) -> list[PluginDashboardCardSnapshotRead]:
    rows = repository.list_plugin_dashboard_card_snapshots(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        placement=placement,
    )
    return [_to_snapshot_read(row) for row in rows]


def get_member_dashboard_layout_read(
    db: Session,
    *,
    member_id: str,
    placement: str = "home",
) -> MemberDashboardLayoutRead:
    get_member_or_404(db, member_id)
    row = repository.get_member_dashboard_layout(db, member_id=member_id, placement=placement)
    if row is None:
        return MemberDashboardLayoutRead(
            member_id=member_id,
            placement="home",
            layout_version=0,
            items=[],
            created_at=None,
            updated_at=None,
        )
    payload = _load_member_dashboard_layout_payload(row.layout_json)
    return MemberDashboardLayoutRead(
        member_id=member_id,
        placement=row.placement,
        layout_version=payload.version,
        items=payload.items,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def save_member_dashboard_layout(
    db: Session,
    *,
    household_id: str,
    member_id: str,
    payload: MemberDashboardLayoutUpdateRequest,
) -> MemberDashboardLayoutRead:
    member = get_member_or_404(db, member_id)
    if member.household_id != household_id:
        raise PluginServiceError(
            "成员不属于当前家庭，不能保存首页布局。",
            error_code=MEMBER_DASHBOARD_CARD_NOT_VISIBLE_ERROR_CODE,
            field="member_id",
            status_code=400,
        )

    available_cards, _ = _build_visible_home_cards(db, household_id=household_id)
    normalized = _normalize_member_layout(
        available_cards=available_cards,
        requested_items=payload.items,
        existing_layout=None,
        strict=True,
    )
    existing_row = repository.get_member_dashboard_layout(db, member_id=member_id, placement="home")
    current_version = _load_member_dashboard_layout_payload(existing_row.layout_json).version if existing_row is not None else 0
    next_version = current_version + 1
    persisted_payload = MemberDashboardLayoutPayload(version=next_version, items=normalized)
    now = utc_now_iso()

    if existing_row is None:
        existing_row = MemberDashboardLayout(
            id=new_uuid(),
            member_id=member_id,
            placement="home",
            layout_json=dump_json(persisted_payload.model_dump(mode="json")) or '{"items":[]}',
            created_at=now,
            updated_at=now,
        )
        repository.add_member_dashboard_layout(db, existing_row)
    else:
        existing_row.layout_json = dump_json(persisted_payload.model_dump(mode="json")) or '{"items":[]}'
        existing_row.updated_at = now
        db.add(existing_row)

    db.flush()
    return MemberDashboardLayoutRead(
        member_id=member_id,
        placement="home",
        layout_version=next_version,
        items=normalized,
        created_at=existing_row.created_at,
        updated_at=existing_row.updated_at,
    )


def get_home_dashboard(
    db: Session,
    *,
    household_id: str,
    member_id: str,
) -> HomeDashboardRead:
    member = get_member_or_404(db, member_id)
    if member.household_id != household_id:
        raise PluginServiceError(
            "成员不属于当前家庭，不能读取首页聚合结果。",
            error_code=MEMBER_DASHBOARD_CARD_NOT_VISIBLE_ERROR_CODE,
            field="member_id",
            status_code=400,
        )

    available_cards, warnings = _build_visible_home_cards(db, household_id=household_id)
    layout_row = repository.get_member_dashboard_layout(db, member_id=member_id, placement="home")
    layout_payload = (
        _load_member_dashboard_layout_payload(layout_row.layout_json)
        if layout_row is not None
        else MemberDashboardLayoutPayload(version=0, items=[])
    )
    normalized_layout = _normalize_member_layout(
        available_cards=available_cards,
        requested_items=layout_payload.items,
        existing_layout=layout_payload.items,
        strict=False,
    )

    ordered_cards: list[HomeDashboardCardRead] = []
    for item in normalized_layout:
        if not item.visible:
            continue
        card = available_cards[item.card_ref]
        ordered_cards.append(card.model_copy(update={"size": item.size}))

    return HomeDashboardRead(
        household_id=household_id,
        member_id=member_id,
        member_name=member.name,
        member_nickname=member.nickname,
        layout_version=layout_payload.version,
        cards=ordered_cards,
        warnings=warnings,
    )


def _build_visible_home_cards(
    db: Session,
    *,
    household_id: str,
) -> tuple[dict[str, HomeDashboardCardRead], list[str]]:
    builtin_cards, builtin_warnings = _build_builtin_home_cards(db, household_id=household_id)
    plugin_cards, plugin_warnings = _build_plugin_home_cards(db, household_id=household_id)
    cards = {card.card_ref: card for card in [*builtin_cards, *plugin_cards]}
    return cards, [*builtin_warnings, *plugin_warnings]


def _build_builtin_home_cards(
    db: Session,
    *,
    household_id: str,
) -> tuple[list[HomeDashboardCardRead], list[str]]:
    warnings: list[str] = []
    household = get_household_or_404(db, household_id)
    locale_messages = _load_household_plugin_locale_messages(
        db,
        household_id=household_id,
        locale_id=household.locale,
    )
    context = None
    reminders = None

    try:
        context = get_context_overview(db, household_id)
    except Exception as exc:
        warnings.append(f"内置卡片 context 聚合失败：{exc}")

    try:
        reminders = build_reminder_overview(db, household_id=household_id)
    except Exception as exc:
        warnings.append(f"内置卡片 reminder 聚合失败：{exc}")

    weather_message = _resolve_builtin_dashboard_text(locale_messages, "home.contextUnavailable")
    weather_highlights: list[str] = []
    if context is not None:
        weather_message = (
            f"{_format_home_mode(locale_messages, context.home_mode)}，"
            f"{_format_home_assistant_status(locale_messages, context.home_assistant_status)}。"
        )
        weather_highlights = [
            _resolve_builtin_dashboard_text(
                locale_messages,
                "home.privacySummary",
                value=_format_privacy_mode(locale_messages, context.privacy_mode),
            ),
            _resolve_builtin_dashboard_text(
                locale_messages,
                "home.automationSummary",
                value=_format_automation_level(locale_messages, context.automation_level),
            ),
            (
                _resolve_builtin_dashboard_text(
                    locale_messages,
                    "home.quietHoursSummary",
                    start=context.quiet_hours_start,
                    end=context.quiet_hours_end,
                )
                if context.quiet_hours_enabled
                else _resolve_builtin_dashboard_text(locale_messages, "home.quietHoursDisabled")
            ),
        ]
    if reminders is not None:
        weather_highlights.append(
            _resolve_builtin_dashboard_text(
                locale_messages,
                "home.pendingRemindersSummary",
                count=reminders.pending_runs,
            )
        )

    quick_action_items = [
        {
            "label": _resolve_builtin_dashboard_text(locale_messages, f"home.quickAction.{action_key}.label"),
            "description": _resolve_builtin_dashboard_text(locale_messages, f"home.quickAction.{action_key}.description"),
            "action_key": action_key,
        }
        for action_key, _ in BUILTIN_QUICK_ACTION_SPECS
    ]
    quick_actions = [
        HomeDashboardCardActionRead(
            action_key=action_key,
            action_type="navigate",
            label=_resolve_builtin_dashboard_text(locale_messages, f"home.quickAction.{action_key}.label"),
            target=target,
        )
        for action_key, target in BUILTIN_QUICK_ACTION_SPECS
    ]

    cards = [
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("weather"),
            source_type="builtin",
            template_type="insight",
            size="half",
            state="ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.familyStatus"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.dashboardOverview"),
            payload={
                "message": weather_message,
                "tone": "info" if context is not None and not context.degraded else "warning",
                "highlights": weather_highlights[:3],
            },
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("stats"),
            source_type="builtin",
            template_type="status_list",
            size="full",
            state="ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.keyMetrics"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.builtinSummary"),
            payload={"items": _build_builtin_stats_items(locale_messages, context, reminders)},
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("rooms"),
            source_type="builtin",
            template_type="status_list",
            size="half",
            state="empty" if context is None or not context.room_occupancy else "ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.roomStatus"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.currentSpaceActivity"),
            payload={
                "items": [
                    {
                        "title": room.name,
                        "subtitle": _resolve_builtin_dashboard_text(
                            locale_messages,
                            "home.roomOccupancySummary",
                            room_type=room.room_type,
                            occupant_count=room.occupant_count,
                        ),
                        "value": _resolve_builtin_dashboard_text(
                            locale_messages,
                            "home.roomDevicesOnlineSummary",
                            online=room.online_device_count,
                            total=room.device_count,
                        ),
                        "tone": "success" if room.occupant_count > 0 or room.online_device_count > 0 else "neutral",
                    }
                    for room in (context.room_occupancy[:4] if context is not None else [])
                ],
            },
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("members"),
            source_type="builtin",
            template_type="status_list",
            size="half",
            state="empty" if context is None or not context.member_states else "ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.memberStatus"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.currentAtHomeAndActivity"),
            payload={
                "items": [
                    {
                        "title": member_state.name,
                        "subtitle": member_state.role,
                        "value": _format_member_presence(locale_messages, member_state.presence),
                        "tone": "success" if member_state.presence == "home" else "neutral",
                    }
                    for member_state in (context.member_states[:4] if context is not None else [])
                ],
            },
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("events"),
            source_type="builtin",
            template_type="timeline",
            size="half",
            state="empty" if _is_builtin_events_empty(context, reminders) else "ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.recentEvents"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.systemInsightsAndReminders"),
            payload={"items": _build_builtin_event_items(locale_messages, context, reminders)},
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("quick-actions"),
            source_type="builtin",
            template_type="action_group",
            size="half",
            state="ready",
            title=_resolve_builtin_dashboard_text(locale_messages, "home.quickActions"),
            subtitle=_resolve_builtin_dashboard_text(locale_messages, "home.systemControlledNavigation"),
            payload={"items": quick_action_items},
            actions=quick_actions,
        ),
    ]
    return cards, warnings


def _build_plugin_home_cards(
    db: Session,
    *,
    household_id: str,
) -> tuple[list[HomeDashboardCardRead], list[str]]:
    warnings: list[str] = []
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    snapshot_rows = {
        (row.plugin_id, row.placement, row.card_key): row
        for row in repository.list_plugin_dashboard_card_snapshots(db, household_id=household_id, placement="home")
    }
    household = get_household_or_404(db, household_id)
    locale_messages = _load_household_plugin_locale_messages(db, household_id=household_id, locale_id=household.locale)
    cards: list[HomeDashboardCardRead] = []

    for plugin in snapshot.items:
        if not plugin.enabled:
            continue
        for card_spec in plugin.dashboard_cards:
            if card_spec.placement != "home":
                continue
            card_ref = build_plugin_dashboard_card_ref(
                plugin_id=plugin.id,
                placement=card_spec.placement,
                card_key=card_spec.card_key,
            )
            title = _resolve_plugin_dashboard_text(locale_messages, card_spec.title_key, plugin_name=plugin.name)
            subtitle = _resolve_plugin_dashboard_text(locale_messages, card_spec.subtitle_key, plugin_name=plugin.name)
            row = snapshot_rows.get((plugin.id, card_spec.placement, card_spec.card_key))
            if row is None:
                warnings.append(f"插件卡片缺少快照：{plugin.id}/{card_spec.card_key}")
                cards.append(
                    HomeDashboardCardRead(
                        card_ref=card_ref,
                        source_type="plugin",
                        template_type=card_spec.template_type,
                        size=card_spec.size,
                        state="error",
                        title=title or plugin.name,
                        subtitle=subtitle,
                        payload={},
                        actions=[],
                    )
                )
                continue

            snapshot_read = _to_snapshot_read(row)
            try:
                envelope = PluginDashboardCardSnapshotEnvelope.model_validate(load_json(row.payload_json) or {})
            except Exception as exc:
                warnings.append(f"插件卡片快照损坏：{plugin.id}/{card_spec.card_key}：{exc}")
                cards.append(
                    HomeDashboardCardRead(
                        card_ref=card_ref,
                        source_type="plugin",
                        template_type=card_spec.template_type,
                        size=card_spec.size,
                        state="error",
                        title=title or plugin.name,
                        subtitle=subtitle,
                        payload={},
                        actions=[],
                    )
                )
                continue

            current_state = _resolve_snapshot_state(snapshot_read)
            if current_state == "invalid":
                warnings.append(f"插件卡片快照结构非法：{plugin.id}/{card_spec.card_key}")
            elif current_state == "error":
                warnings.append(f"插件卡片快照生成失败：{plugin.id}/{card_spec.card_key}")

            home_state = (
                "error"
                if current_state in {"invalid", "error"}
                else _resolve_home_card_state(card_spec.template_type, current_state, envelope.payload)
            )
            cards.append(
                HomeDashboardCardRead(
                    card_ref=card_ref,
                    source_type="plugin",
                    template_type=card_spec.template_type,
                    size=card_spec.size,
                    state=home_state,
                    title=title or plugin.name,
                    subtitle=subtitle,
                    payload={} if home_state == "error" else envelope.payload,
                    actions=[] if home_state == "error" else envelope.actions,
                )
            )

    weather_cards, weather_warnings = _build_official_weather_home_cards(
        db,
        household_id=household_id,
        enabled_plugin_ids={plugin.id for plugin in snapshot.items if plugin.enabled},
    )
    cards.extend(weather_cards)
    warnings.extend(weather_warnings)
    cards.sort(key=lambda item: item.card_ref)
    return cards, warnings


def _build_official_weather_home_cards(
    db: Session,
    *,
    household_id: str,
    enabled_plugin_ids: set[str],
) -> tuple[list[HomeDashboardCardRead], list[str]]:
    if OFFICIAL_WEATHER_PLUGIN_ID not in enabled_plugin_ids:
        return [], []

    from app.modules.weather.service import (
        WEATHER_DEFAULT_BINDING_TYPE,
        list_weather_card_snapshots,
        list_weather_device_binding_reads,
    )

    warnings: list[str] = []
    try:
        bindings = list_weather_device_binding_reads(db, household_id=household_id)
        snapshots = {
            item.device_id: item
            for item in list_weather_card_snapshots(db, household_id=household_id)
        }
    except Exception as exc:
        return [], [f"官方天气卡片聚合失败：{exc}"]

    cards: list[HomeDashboardCardRead] = []
    for binding in bindings:
        snapshot = snapshots.get(binding.device_id)
        if snapshot is None:
            warnings.append(f"官方天气卡片缺少快照：{binding.device_id}")
            cards.append(
                HomeDashboardCardRead(
                    card_ref=_build_official_weather_card_ref(
                        device_id=binding.device_id,
                        binding_type=binding.binding_type,
                    ),
                    source_type="plugin",
                    template_type="insight",
                    size="half",
                    state="error",
                    title=binding.display_name,
                    subtitle=_build_official_weather_card_subtitle(binding.binding_type),
                    payload={
                        "card_kind": "weather",
                        "location": binding.display_name,
                        "message": "天气卡片暂不可用",
                    },
                    actions=[],
                )
            )
            continue

        payload = dict(snapshot.payload)
        payload["card_kind"] = "weather"
        payload["device_id"] = binding.device_id
        payload["binding_type"] = binding.binding_type
        cards.append(
            HomeDashboardCardRead(
                card_ref=_build_official_weather_card_ref(
                    device_id=binding.device_id,
                    binding_type=binding.binding_type,
                ),
                source_type="plugin",
                template_type="insight",
                size="half",
                state=_resolve_official_weather_home_card_state(snapshot.state),
                title=binding.display_name,
                subtitle=_build_official_weather_card_subtitle(binding.binding_type),
                payload=payload,
                actions=[],
            )
        )

    cards.sort(
        key=lambda item: (
            0 if item.card_ref.endswith(OFFICIAL_WEATHER_DEFAULT_CARD_KEY) else 1,
            item.title,
            item.card_ref,
        )
    )
    return cards, warnings


def _build_official_weather_card_ref(*, device_id: str, binding_type: str) -> str:
    if binding_type == "default_household":
        card_key = OFFICIAL_WEATHER_DEFAULT_CARD_KEY
    else:
        card_key = f"{OFFICIAL_WEATHER_DEVICE_CARD_KEY_PREFIX}{device_id}"
    return build_plugin_dashboard_card_ref(
        plugin_id=OFFICIAL_WEATHER_PLUGIN_ID,
        placement="home",
        card_key=card_key,
    )


def _build_official_weather_card_subtitle(binding_type: str) -> str:
    if binding_type == "default_household":
        return "家庭默认天气"
    return "附加地区天气"


def _resolve_official_weather_home_card_state(snapshot_state: str) -> str:
    if snapshot_state == "ready":
        return "ready"
    if snapshot_state == "stale":
        return "stale"
    if snapshot_state == "pending_coordinate":
        return "empty"
    return "error"


def _normalize_member_layout(
    *,
    available_cards: dict[str, HomeDashboardCardRead],
    requested_items: list[MemberDashboardLayoutItem],
    existing_layout: list[MemberDashboardLayoutItem] | None,
    strict: bool,
) -> list[MemberDashboardLayoutItem]:
    normalized: list[MemberDashboardLayoutItem] = []
    seen_card_refs: set[str] = set()
    default_order = _build_default_home_order(available_cards)

    for item in requested_items:
        card = available_cards.get(item.card_ref)
        if card is None:
            if strict:
                raise PluginServiceError(
                    f"卡片 {item.card_ref} 当前不可见，不能保存到首页布局。",
                    error_code=MEMBER_DASHBOARD_CARD_NOT_VISIBLE_ERROR_CODE,
                    field="items.card_ref",
                    status_code=400,
                )
            continue
        if item.card_ref in seen_card_refs:
            if strict:
                raise PluginServiceError(
                    f"布局里存在重复卡片：{item.card_ref}",
                    error_code=MEMBER_DASHBOARD_LAYOUT_INVALID_ERROR_CODE,
                    field="items.card_ref",
                    status_code=400,
                )
            continue
        if item.size not in ALLOWED_HOME_DASHBOARD_CARD_SIZES:
            if strict:
                raise PluginServiceError(
                    f"卡片 {item.card_ref} 不支持尺寸 {item.size}。",
                    error_code=MEMBER_DASHBOARD_LAYOUT_INVALID_ERROR_CODE,
                    field="items.size",
                    status_code=400,
                )
            size = card.size
        else:
            size = item.size
        if item.height not in ALLOWED_HOME_DASHBOARD_CARD_HEIGHTS:
            if strict:
                raise PluginServiceError(
                    f"卡片 {item.card_ref} 不支持高度 {item.height}。",
                    error_code=MEMBER_DASHBOARD_LAYOUT_INVALID_ERROR_CODE,
                    field="items.height",
                    status_code=400,
                )
            height = DEFAULT_HOME_DASHBOARD_CARD_HEIGHT
        else:
            height = item.height
        normalized.append(
            MemberDashboardLayoutItem(
                card_ref=item.card_ref,
                visible=item.visible,
                order=item.order,
                size=size,
                height=height,
            )
        )
        seen_card_refs.add(item.card_ref)

    existing_visibility = {item.card_ref: item.visible for item in (existing_layout or [])}
    existing_height = {item.card_ref: item.height for item in (existing_layout or [])}
    max_order = max((item.order for item in normalized), default=0)
    next_order = max_order + 10
    for card_ref, order in _build_default_home_order(available_cards).items():
        if card_ref in seen_card_refs:
            continue
        normalized.append(
            MemberDashboardLayoutItem(
                card_ref=card_ref,
                visible=existing_visibility.get(card_ref, True),
                order=max(order, next_order),
                size=available_cards[card_ref].size,
                height=existing_height.get(card_ref, DEFAULT_HOME_DASHBOARD_CARD_HEIGHT),
            )
        )
        next_order = max(next_order, order) + 10

    normalized.sort(key=lambda item: (item.order, item.card_ref))
    return normalized


def _build_default_home_order(available_cards: dict[str, HomeDashboardCardRead]) -> dict[str, int]:
    order_map: dict[str, int] = {}
    for index, card_ref in enumerate(DEFAULT_HOME_LAYOUT_CARD_REFS, start=1):
        if card_ref in available_cards:
            order_map[card_ref] = index * 10

    next_order = (len(order_map) + 1) * 10
    for card_ref in sorted(available_cards):
        if card_ref in order_map or not card_ref.startswith(OFFICIAL_WEATHER_CARD_REF_PREFIX):
            continue
        order_map[card_ref] = next_order
        next_order += 10

    for card_ref in sorted(available_cards):
        if card_ref in order_map:
            continue
        order_map[card_ref] = next_order
        next_order += 10
    return order_map


def _get_or_create_snapshot_row(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    placement: str,
    card_key: str,
) -> PluginDashboardCardSnapshot:
    row = repository.get_plugin_dashboard_card_snapshot(
        db,
        household_id=household_id,
        plugin_id=plugin_id,
        placement=placement,
        card_key=card_key,
    )
    if row is not None:
        return row
    now = utc_now_iso()
    row = PluginDashboardCardSnapshot(
        id=new_uuid(),
        household_id=household_id,
        plugin_id=plugin_id,
        card_key=card_key,
        placement=placement,
        payload_json='{"payload":{},"actions":[]}',
        state="error",
        error_code=None,
        error_message=None,
        generated_at=None,
        expires_at=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_plugin_dashboard_card_snapshot(db, row)
    db.flush()
    return row


def _get_plugin_dashboard_card_spec(plugin: Any, *, card_key: str, placement: str) -> PluginManifestDashboardCardSpec:
    for item in plugin.dashboard_cards:
        if item.card_key == card_key and item.placement == placement:
            return item
    raise PluginServiceError(
        f"插件 {plugin.id} 没有声明首页卡片 {placement}/{card_key}。",
        error_code=PLUGIN_DASHBOARD_CARD_NOT_DECLARED_ERROR_CODE,
        field="card_key",
        status_code=400,
    )


def _validate_snapshot_envelope(
    card_spec: PluginManifestDashboardCardSpec,
    payload: dict[str, Any],
    actions: list[HomeDashboardCardActionRead],
) -> PluginDashboardCardSnapshotEnvelope:
    _ensure_json_size(payload, limit=PLUGIN_DASHBOARD_CARD_PAYLOAD_MAX_BYTES, field="payload")
    if len(actions) > PLUGIN_DASHBOARD_CARD_ACTION_LIMIT:
        raise PluginServiceError(
            f"卡片动作数量不能超过 {PLUGIN_DASHBOARD_CARD_ACTION_LIMIT} 个。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field="actions",
            status_code=400,
        )

    validated_actions = _validate_dashboard_actions(card_spec, actions)
    validated_payload = _validate_dashboard_payload(card_spec, payload, validated_actions)
    return PluginDashboardCardSnapshotEnvelope(payload=validated_payload, actions=validated_actions)


def _validate_dashboard_actions(
    card_spec: PluginManifestDashboardCardSpec,
    actions: list[HomeDashboardCardActionRead],
) -> list[HomeDashboardCardActionRead]:
    validated: list[HomeDashboardCardActionRead] = []
    seen_action_keys: set[str] = set()
    for item in actions:
        if item.action_type not in card_spec.allowed_actions:
            raise PluginServiceError(
                f"卡片动作 {item.action_type} 不在 manifest 白名单里。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field="actions.action_type",
                status_code=400,
            )
        if item.action_key is not None:
            if item.action_key in seen_action_keys:
                raise PluginServiceError(
                    f"卡片动作 action_key 重复：{item.action_key}",
                    error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                    field="actions.action_key",
                    status_code=400,
                )
            seen_action_keys.add(item.action_key)
        if item.action_type == "navigate":
            if item.target is None or not item.target.startswith("/"):
                raise PluginServiceError(
                    "navigate 动作必须使用站内相对路径。",
                    error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                    field="actions.target",
                    status_code=400,
                )
        if item.action_type == "trigger_plugin_action" and item.target is None:
            raise PluginServiceError(
                "trigger_plugin_action 动作必须声明受控 action 标识。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field="actions.target",
                status_code=400,
            )
        if item.payload is not None:
            _ensure_json_size(item.payload, limit=PLUGIN_DASHBOARD_CARD_ACTION_PAYLOAD_MAX_BYTES, field="actions.payload")
        validated.append(item)
    return validated


def _validate_dashboard_payload(
    card_spec: PluginManifestDashboardCardSpec,
    payload: dict[str, Any],
    actions: list[HomeDashboardCardActionRead],
) -> dict[str, Any]:
    action_key_map = {item.action_key: item for item in actions if item.action_key is not None}
    if card_spec.template_type == "metric":
        return _validate_metric_payload(payload)
    if card_spec.template_type == "insight":
        return _validate_insight_payload(payload)
    if card_spec.template_type == "status_list":
        return _validate_status_list_payload(payload, max_items=card_spec.max_items or 20, action_key_map=action_key_map)
    if card_spec.template_type == "timeline":
        return _validate_timeline_payload(payload, max_items=card_spec.max_items or 20, action_key_map=action_key_map)
    if card_spec.template_type == "action_group":
        return _validate_action_group_payload(payload, max_items=card_spec.max_items or 20, action_key_map=action_key_map)
    raise PluginServiceError(
        f"不支持的卡片模板：{card_spec.template_type}",
        error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
        field="template_type",
        status_code=400,
    )


def _validate_metric_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _assert_allowed_fields(payload, {"value", "unit", "context", "trend"}, field="payload")
    value = payload.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PluginServiceError(
            "metric 卡片必须声明 value，且只能是数字或短文本。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field="payload.value",
            status_code=400,
        )
    if isinstance(value, str) and len(value.strip()) > 40:
        raise PluginServiceError(
            "metric.value 不能超过 40 个字符。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field="payload.value",
            status_code=400,
        )
    if "unit" in payload:
        _ensure_text(payload.get("unit"), max_length=20, field="payload.unit")
    if "context" in payload:
        _ensure_text(payload.get("context"), max_length=120, field="payload.context")
    trend = payload.get("trend")
    if trend is not None:
        if not isinstance(trend, dict):
            raise PluginServiceError(
                "metric.trend 必须是对象。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field="payload.trend",
                status_code=400,
            )
        _assert_allowed_fields(trend, {"direction", "label"}, field="payload.trend")
        if trend.get("direction") not in {"up", "down", "flat"}:
            raise PluginServiceError(
                "metric.trend.direction 只支持 up/down/flat。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field="payload.trend.direction",
                status_code=400,
            )
        if "label" in trend:
            _ensure_text(trend.get("label"), max_length=60, field="payload.trend.label")
    return payload


def _validate_insight_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _assert_allowed_fields(payload, {"message", "tone", "highlights"}, field="payload")
    _ensure_text(payload.get("message"), max_length=500, field="payload.message", required=True)
    tone = payload.get("tone")
    if tone is not None and tone not in {"neutral", "info", "success", "warning", "danger"}:
        raise PluginServiceError(
            "insight.tone 不在允许范围里。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field="payload.tone",
            status_code=400,
        )
    highlights = payload.get("highlights")
    if highlights is not None:
        if not isinstance(highlights, list) or len(highlights) > 3:
            raise PluginServiceError(
                "insight.highlights 最多允许 3 项。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field="payload.highlights",
                status_code=400,
            )
        for index, item in enumerate(highlights):
            _ensure_text(item, max_length=60, field=f"payload.highlights[{index}]", required=True)
    return payload


def _validate_status_list_payload(
    payload: dict[str, Any],
    *,
    max_items: int,
    action_key_map: dict[str, HomeDashboardCardActionRead],
) -> dict[str, Any]:
    _assert_allowed_fields(payload, {"items"}, field="payload")
    items = _ensure_items_list(payload.get("items"), max_items=max_items, field="payload.items")
    for index, item in enumerate(items):
        _assert_allowed_fields(item, {"title", "subtitle", "value", "tone", "action_key"}, field=f"payload.items[{index}]")
        _ensure_text(item.get("title"), max_length=80, field=f"payload.items[{index}].title", required=True)
        if "subtitle" in item:
            _ensure_text(item.get("subtitle"), max_length=120, field=f"payload.items[{index}].subtitle")
        if "value" in item:
            _ensure_text_or_number(item.get("value"), max_length=40, field=f"payload.items[{index}].value")
        if "tone" in item and item.get("tone") not in {"neutral", "info", "success", "warning", "danger"}:
            raise PluginServiceError(
                "status_list.item.tone 不在允许范围里。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field=f"payload.items[{index}].tone",
                status_code=400,
            )
        _validate_action_key_reference(item.get("action_key"), action_key_map, field=f"payload.items[{index}].action_key")
    return payload


def _validate_timeline_payload(
    payload: dict[str, Any],
    *,
    max_items: int,
    action_key_map: dict[str, HomeDashboardCardActionRead],
) -> dict[str, Any]:
    _assert_allowed_fields(payload, {"items"}, field="payload")
    items = _ensure_items_list(payload.get("items"), max_items=max_items, field="payload.items")
    for index, item in enumerate(items):
        _assert_allowed_fields(item, {"title", "timestamp", "description", "tone", "action_key"}, field=f"payload.items[{index}]")
        _ensure_text(item.get("title"), max_length=80, field=f"payload.items[{index}].title", required=True)
        _ensure_text(item.get("timestamp"), max_length=60, field=f"payload.items[{index}].timestamp", required=True)
        if "description" in item:
            _ensure_text(item.get("description"), max_length=160, field=f"payload.items[{index}].description")
        if "tone" in item and item.get("tone") not in {"neutral", "info", "success", "warning", "danger"}:
            raise PluginServiceError(
                "timeline.item.tone 不在允许范围里。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field=f"payload.items[{index}].tone",
                status_code=400,
            )
        _validate_action_key_reference(item.get("action_key"), action_key_map, field=f"payload.items[{index}].action_key")
    return payload


def _validate_action_group_payload(
    payload: dict[str, Any],
    *,
    max_items: int,
    action_key_map: dict[str, HomeDashboardCardActionRead],
) -> dict[str, Any]:
    _assert_allowed_fields(payload, {"items"}, field="payload")
    items = _ensure_items_list(payload.get("items"), max_items=max_items, field="payload.items")
    for index, item in enumerate(items):
        _assert_allowed_fields(item, {"label", "description", "action_key"}, field=f"payload.items[{index}]")
        _ensure_text(item.get("label"), max_length=40, field=f"payload.items[{index}].label", required=True)
        if "description" in item:
            _ensure_text(item.get("description"), max_length=100, field=f"payload.items[{index}].description")
        _validate_action_key_reference(item.get("action_key"), action_key_map, field=f"payload.items[{index}].action_key", required=True)
    return payload


def _ensure_items_list(value: Any, *, max_items: int, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PluginServiceError(
            f"{field} 必须是数组。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    if len(value) > max_items:
        raise PluginServiceError(
            f"{field} 不能超过 {max_items} 项。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PluginServiceError(
                f"{field}[{index}] 必须是对象。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field=f"{field}[{index}]",
                status_code=400,
            )
        normalized.append(item)
    return normalized


def _validate_action_key_reference(
    action_key: Any,
    action_key_map: dict[str, HomeDashboardCardActionRead],
    *,
    field: str,
    required: bool = False,
) -> None:
    if action_key is None:
        if required:
            raise PluginServiceError(
                f"{field} 不能为空。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field=field,
                status_code=400,
            )
        return
    if not isinstance(action_key, str) or not action_key.strip():
        raise PluginServiceError(
            f"{field} 必须是非空字符串。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    if action_key.strip() not in action_key_map:
        raise PluginServiceError(
            f"{field} 引用了不存在的 action_key：{action_key}",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )


def _assert_allowed_fields(payload: dict[str, Any], allowed_fields: set[str], *, field: str) -> None:
    unexpected = sorted(set(payload) - allowed_fields)
    if unexpected:
        raise PluginServiceError(
            f"{field} 包含不支持的字段：{', '.join(unexpected)}",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )


def _ensure_text(value: Any, *, max_length: int, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise PluginServiceError(
                f"{field} 不能为空。",
                error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
                field=field,
                status_code=400,
            )
        return None
    if not isinstance(value, str):
        raise PluginServiceError(
            f"{field} 必须是字符串。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    normalized = value.strip()
    if required and not normalized:
        raise PluginServiceError(
            f"{field} 不能为空。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    if len(normalized) > max_length:
        raise PluginServiceError(
            f"{field} 不能超过 {max_length} 个字符。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    return normalized


def _ensure_text_or_number(value: Any, *, max_length: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PluginServiceError(
            f"{field} 必须是数字或短文本。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )
    if isinstance(value, str):
        _ensure_text(value, max_length=max_length, field=field, required=True)


def _ensure_json_size(value: Any, *, limit: int, field: str) -> None:
    try:
        raw = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise PluginServiceError(
            f"{field} 不是合法 JSON。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        ) from exc
    if len(raw.encode("utf-8")) > limit:
        raise PluginServiceError(
            f"{field} 体积不能超过 {limit} 字节。",
            error_code=PLUGIN_DASHBOARD_CARD_PAYLOAD_INVALID_ERROR_CODE,
            field=field,
            status_code=400,
        )


def _load_member_dashboard_layout_payload(layout_json: str) -> MemberDashboardLayoutPayload:
    try:
        raw_payload = load_json(layout_json)
    except Exception:
        raw_payload = None
    if not isinstance(raw_payload, dict):
        return MemberDashboardLayoutPayload(version=0, items=[])
    try:
        return MemberDashboardLayoutPayload.model_validate(raw_payload)
    except Exception:
        items = raw_payload.get("items")
        if not isinstance(items, list):
            return MemberDashboardLayoutPayload(version=0, items=[])
        try:
            return MemberDashboardLayoutPayload(
                version=0,
                items=[MemberDashboardLayoutItem.model_validate(item) for item in items],
            )
        except Exception:
            return MemberDashboardLayoutPayload(version=0, items=[])


def _to_snapshot_read(row: PluginDashboardCardSnapshot) -> PluginDashboardCardSnapshotRead:
    try:
        envelope = PluginDashboardCardSnapshotEnvelope.model_validate(load_json(row.payload_json) or {})
    except Exception:
        envelope = PluginDashboardCardSnapshotEnvelope(payload={}, actions=[])
    return PluginDashboardCardSnapshotRead(
        id=row.id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        card_key=row.card_key,
        placement=row.placement,
        state=row.state,
        payload=envelope.payload,
        actions=envelope.actions,
        error_code=row.error_code,
        error_message=row.error_message,
        generated_at=row.generated_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _resolve_snapshot_state(snapshot: PluginDashboardCardSnapshotRead) -> str:
    if snapshot.state != "ready":
        return snapshot.state
    expires_at = _parse_iso_datetime(snapshot.expires_at)
    if expires_at is None:
        return "ready"
    if expires_at <= datetime.now(timezone.utc):
        return "stale"
    return "ready"


def _resolve_home_card_state(template_type: str, snapshot_state: str, payload: dict[str, Any]) -> str:
    if snapshot_state == "stale":
        return "stale"
    if snapshot_state != "ready":
        return "error"
    if template_type in {"status_list", "timeline", "action_group"}:
        items = payload.get("items")
        return "empty" if not isinstance(items, list) or len(items) == 0 else "ready"
    if template_type == "insight":
        message = payload.get("message")
        return "empty" if not isinstance(message, str) or not message.strip() else "ready"
    if template_type == "metric":
        value = payload.get("value")
        return "empty" if value is None or (isinstance(value, str) and not value.strip()) else "ready"
    return "ready"


def _load_household_plugin_locale_messages(
    db: Session,
    *,
    household_id: str,
    locale_id: str,
) -> dict[str, str]:
    messages: dict[str, str] = {}
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    for plugin in snapshot.items:
        if not plugin.enabled or "locale-pack" not in plugin.types:
            continue
        manifest_dir = Path(plugin.manifest_path).resolve().parent
        for locale_spec in plugin.locales:
            if locale_spec.id != locale_id:
                continue
            resource_path = manifest_dir / locale_spec.resource
            try:
                raw_payload = json.loads(resource_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw_payload, dict):
                continue
            for key, value in raw_payload.items():
                if isinstance(key, str) and isinstance(value, str):
                    messages[key] = value
    return messages


def _resolve_plugin_dashboard_text(
    locale_messages: dict[str, str],
    key: str | None,
    *,
    plugin_name: str,
) -> str | None:
    if key is None:
        return None
    message = locale_messages.get(key)
    if isinstance(message, str) and message.strip():
        return message.strip()

    normalized_key = key.strip()
    if not normalized_key:
        return None

    segments = [segment for segment in normalized_key.split(".") if segment]
    if not segments:
        return plugin_name
    suffix = segments[-1]
    base_segment = segments[-2] if suffix in {"title", "subtitle", "empty"} and len(segments) >= 2 else segments[-1]
    humanized = base_segment.replace("_", " ").replace("-", " ").strip().title()
    if suffix == "subtitle":
        return f"{plugin_name} · {humanized}" if humanized else plugin_name
    if suffix == "empty":
        return f"{humanized or plugin_name} 暂无数据"
    return humanized or plugin_name

def _resolve_builtin_dashboard_text(
    locale_messages: dict[str, str],
    key: str,
    **kwargs: Any,
) -> str:
    message = locale_messages.get(key)
    if not isinstance(message, str) or not message.strip():
        message = BUILTIN_DASHBOARD_TEXT_DEFAULTS.get(key, key)
    template = message.strip()
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except Exception:
        return template




def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_builtin_stats_items(
    locale_messages: dict[str, str],
    context: Any,
    reminders: Any,
) -> list[dict[str, Any]]:
    return [
        {
            "title": _resolve_builtin_dashboard_text(locale_messages, "home.membersAtHome"),
            "value": len(context.member_states) if context is not None else 0,
            "tone": "info",
        },
        {
            "title": _resolve_builtin_dashboard_text(locale_messages, "home.activeRooms"),
            "value": len([item for item in (context.room_occupancy if context is not None else []) if item.occupant_count > 0 or item.online_device_count > 0]),
            "tone": "success",
        },
        {
            "title": _resolve_builtin_dashboard_text(locale_messages, "home.devicesOnline"),
            "value": context.device_summary.active if context is not None else 0,
            "tone": "info",
        },
        {
            "title": _resolve_builtin_dashboard_text(locale_messages, "home.alerts"),
            "value": reminders.pending_runs if reminders is not None else 0,
            "tone": "warning",
        },
    ]


def _build_builtin_event_items(
    locale_messages: dict[str, str],
    context: Any,
    reminders: Any,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if context is not None:
        items.extend(
            {
                "title": item.title,
                "timestamp": context.generated_at,
                "description": item.message,
                "tone": item.tone,
            }
            for item in context.insights[:3]
        )
    if reminders is not None:
        items.extend(
            {
                "title": item.title,
                "timestamp": item.latest_run_planned_at or item.next_trigger_at or "",
                "description": _resolve_builtin_dashboard_text(
                    locale_messages,
                    "home.eventStatus.done" if item.latest_ack_action == "done" else "home.eventStatus.pending",
                ),
                "tone": "warning",
            }
            for item in reminders.items[:3]
        )
    return items[:5]


def _is_builtin_events_empty(context: Any, reminders: Any) -> bool:
    return ((context is None or not context.insights) and (reminders is None or not reminders.items))


def _format_home_mode(locale_messages: dict[str, str], value: str) -> str:
    key = f"home.homeMode.{value}" if value in {"home", "away", "night", "sleep", "custom"} else "home.homeMode.default"
    return _resolve_builtin_dashboard_text(locale_messages, key)


def _format_home_assistant_status(locale_messages: dict[str, str], value: str) -> str:
    key = (
        f"home.assistantStatus.{value}"
        if value in {"healthy", "degraded", "offline"}
        else "home.assistantStatus.default"
    )
    return _resolve_builtin_dashboard_text(locale_messages, key)


def _format_privacy_mode(locale_messages: dict[str, str], value: str) -> str:
    key = f"home.privacyMode.{value}" if value in {"balanced", "strict", "care"} else "home.privacyMode.default"
    return _resolve_builtin_dashboard_text(locale_messages, key)


def _format_automation_level(locale_messages: dict[str, str], value: str) -> str:
    key = (
        f"home.automationLevel.{value}"
        if value in {"manual", "assisted", "automatic"}
        else "home.automationLevel.default"
    )
    return _resolve_builtin_dashboard_text(locale_messages, key)


def _format_member_presence(locale_messages: dict[str, str], value: str) -> str:
    key = f"home.memberPresence.{value}" if value in {"home", "away", "unknown"} else "home.memberPresence.default"
    return _resolve_builtin_dashboard_text(locale_messages, key)
