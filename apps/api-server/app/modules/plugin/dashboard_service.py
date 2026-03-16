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
from .service import PluginServiceError, get_household_plugin, list_registered_plugins_for_household

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
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=plugin_id)
    if not plugin.enabled:
        raise PluginServiceError(
            f"插件 {plugin_id} 当前不可用，不能写入首页卡片快照。",
            error_code="plugin_not_visible_in_household",
            field="plugin_id",
            status_code=409,
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

    weather_message = "家庭上下文暂不可用。"
    weather_highlights: list[str] = []
    if context is not None:
        weather_message = f"{_format_home_mode(context.home_mode)}，{_format_home_assistant_status(context.home_assistant_status)}。"
        weather_highlights = [
            f"隐私：{_format_privacy_mode(context.privacy_mode)}",
            f"自动化：{_format_automation_level(context.automation_level)}",
            (
                f"安静时段：{context.quiet_hours_start}-{context.quiet_hours_end}"
                if context.quiet_hours_enabled
                else "安静时段未开启"
            ),
        ]
    if reminders is not None:
        weather_highlights.append(f"待处理提醒：{reminders.pending_runs}")

    cards = [
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("weather"),
            source_type="builtin",
            template_type="insight",
            size="half",
            state="ready",
            title="家庭状态",
            subtitle="首页总览",
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
            title="关键指标",
            subtitle="内置聚合摘要",
            payload={"items": _build_builtin_stats_items(context, reminders)},
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("rooms"),
            source_type="builtin",
            template_type="status_list",
            size="half",
            state="empty" if context is None or not context.room_occupancy else "ready",
            title="房间状态",
            subtitle="当前空间活跃度",
            payload={
                "items": [
                    {
                        "title": room.name,
                        "subtitle": f"{room.room_type} · {room.occupant_count} 人",
                        "value": f"{room.online_device_count}/{room.device_count} 设备在线",
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
            title="成员状态",
            subtitle="当前在家与活动",
            payload={
                "items": [
                    {
                        "title": member_state.name,
                        "subtitle": member_state.role,
                        "value": _format_member_presence(member_state.presence),
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
            title="最近事件",
            subtitle="系统洞察与提醒",
            payload={"items": _build_builtin_event_items(context, reminders)},
            actions=[],
        ),
        HomeDashboardCardRead(
            card_ref=build_builtin_dashboard_card_ref("quick-actions"),
            source_type="builtin",
            template_type="action_group",
            size="half",
            state="ready",
            title="快捷操作",
            subtitle="系统内受控跳转",
            payload={
                "items": [
                    {"label": "对话", "description": "打开助手会话", "action_key": "assistant"},
                    {"label": "记忆", "description": "查看家庭记忆", "action_key": "memories"},
                    {"label": "设置", "description": "进入设置页", "action_key": "settings"},
                    {"label": "家庭", "description": "查看家庭成员与房间", "action_key": "family"},
                ],
            },
            actions=[
                HomeDashboardCardActionRead(action_key="assistant", action_type="navigate", label="对话", target="/pages/assistant/index"),
                HomeDashboardCardActionRead(action_key="memories", action_type="navigate", label="记忆", target="/pages/memories/index"),
                HomeDashboardCardActionRead(action_key="settings", action_type="navigate", label="设置", target="/pages/settings/index"),
                HomeDashboardCardActionRead(action_key="family", action_type="navigate", label="家庭", target="/pages/family/index"),
            ],
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

    cards.sort(key=lambda item: item.card_ref)
    return cards, warnings


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


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_builtin_stats_items(context: Any, reminders: Any) -> list[dict[str, Any]]:
    return [
        {"title": "在家成员", "value": len(context.member_states) if context is not None else 0, "tone": "info"},
        {
            "title": "活跃房间",
            "value": len([item for item in (context.room_occupancy if context is not None else []) if item.occupant_count > 0 or item.online_device_count > 0]),
            "tone": "success",
        },
        {"title": "在线设备", "value": context.device_summary.active if context is not None else 0, "tone": "info"},
        {"title": "待处理提醒", "value": reminders.pending_runs if reminders is not None else 0, "tone": "warning"},
    ]


def _build_builtin_event_items(context: Any, reminders: Any) -> list[dict[str, Any]]:
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
                "description": "已完成" if item.latest_ack_action == "done" else "待处理",
                "tone": "warning",
            }
            for item in reminders.items[:3]
        )
    return items[:5]


def _is_builtin_events_empty(context: Any, reminders: Any) -> bool:
    return ((context is None or not context.insights) and (reminders is None or not reminders.items))


def _format_home_mode(value: str) -> str:
    return {
        "home": "居家模式",
        "away": "离家模式",
        "night": "夜间模式",
        "sleep": "睡眠模式",
        "custom": "自定义模式",
    }.get(value, "未设置")


def _format_home_assistant_status(value: str) -> str:
    return {
        "healthy": "连接健康",
        "degraded": "部分降级",
        "offline": "连接离线",
    }.get(value, "状态未知")


def _format_privacy_mode(value: str) -> str:
    return {
        "balanced": "平衡保护",
        "strict": "严格保护",
        "care": "关怀优先",
    }.get(value, "未设置")


def _format_automation_level(value: str) -> str:
    return {
        "manual": "手动优先",
        "assisted": "辅助自动",
        "automatic": "自动优先",
    }.get(value, "未设置")


def _format_member_presence(value: str) -> str:
    return {
        "home": "在家",
        "away": "外出",
        "unknown": "未知",
    }.get(value, "未知")
