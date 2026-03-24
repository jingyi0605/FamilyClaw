from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.modules.household.service import get_household_or_404


WEEKDAY_LABELS = (
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
)


def build_realtime_prompt_context(
    db: Session,
    *,
    household_id: str,
    generated_at: str | None = None,
    quiet_hours_enabled: bool | None = None,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
    now_utc: datetime | None = None,
) -> str:
    household = get_household_or_404(db, household_id)
    return render_realtime_prompt_context(
        timezone_name=household.timezone,
        city=household.city,
        generated_at=generated_at,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
        now_utc=now_utc,
    )


def render_realtime_prompt_context(
    *,
    timezone_name: str,
    city: str | None = None,
    generated_at: str | None = None,
    quiet_hours_enabled: bool | None = None,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
    now_utc: datetime | None = None,
) -> str:
    current_utc = _normalize_utc_datetime(now_utc)
    timezone_info, timezone_label = _resolve_timezone(timezone_name)
    local_now = current_utc.astimezone(timezone_info)
    tomorrow = local_now.date() + timedelta(days=1)

    lines = [
        f"- 今天日期：{local_now.strftime('%Y-%m-%d')}",
        f"- 当前本地时间：{local_now.strftime('%Y-%m-%d %H:%M')}",
        f"- 星期：{WEEKDAY_LABELS[local_now.weekday()]}",
        # 显式提供今天和明天的周期信息，避免模型自行猜测相对日期。
        f"- 今天类型：{_describe_day_type(local_now.date())}",
        f"- 明天日期：{tomorrow.strftime('%Y-%m-%d')}",
        f"- 明天星期：{WEEKDAY_LABELS[tomorrow.weekday()]}",
        f"- 明天类型：{_describe_day_type(tomorrow)}",
        f"- 当前时区：{timezone_label}",
        f"- 当前时段：{_describe_day_period(local_now)}",
    ]

    normalized_city = str(city or "").strip()
    if normalized_city:
        lines.append(f"- 家庭所在城市：{normalized_city}")

    quiet_hours_text = _build_quiet_hours_text(
        local_now=local_now,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
    )
    if quiet_hours_text:
        lines.append(f"- 静默时段：{quiet_hours_text}")

    generated_at_text = _format_generated_at(generated_at, timezone_info)
    if generated_at_text:
        lines.append(f"- 上下文快照时间：{generated_at_text}")

    return "当前实时信息：\n" + "\n".join(lines)


def _normalize_utc_datetime(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _resolve_timezone(timezone_name: str) -> tuple[ZoneInfo, str]:
    normalized_name = str(timezone_name or "").strip() or "UTC"
    try:
        return ZoneInfo(normalized_name), normalized_name
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC"), "UTC"


def _describe_day_period(local_now: datetime) -> str:
    hour = local_now.hour
    if hour < 6:
        return "凌晨"
    if hour < 9:
        return "早晨"
    if hour < 12:
        return "上午"
    if hour < 14:
        return "中午"
    if hour < 18:
        return "下午"
    if hour < 19:
        return "傍晚"
    return "晚上"


def _describe_day_type(target_date: date) -> str:
    return "工作日" if target_date.weekday() < 5 else "周末"


def _build_quiet_hours_text(
    *,
    local_now: datetime,
    quiet_hours_enabled: bool | None,
    quiet_hours_start: str | None,
    quiet_hours_end: str | None,
) -> str | None:
    if quiet_hours_enabled is False:
        return "未启用"

    start_time = _parse_clock_time(quiet_hours_start)
    end_time = _parse_clock_time(quiet_hours_end)
    if quiet_hours_enabled is not True or start_time is None or end_time is None:
        return None

    active = _is_quiet_hours_active(local_now.time(), start_time, end_time)
    state_text = "当前在静默时段内" if active else "当前不在静默时段内"
    return f"{state_text}（{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}）"


def _parse_clock_time(raw_value: str | None) -> time | None:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return None
    try:
        return time.fromisoformat(normalized)
    except ValueError:
        return None


def _is_quiet_hours_active(current_time: time, start_time: time, end_time: time) -> bool:
    if start_time == end_time:
        return False
    if start_time < end_time:
        return start_time <= current_time < end_time
    return current_time >= start_time or current_time < end_time


def _format_generated_at(generated_at: str | None, timezone_info: ZoneInfo) -> str | None:
    parsed = _parse_iso_datetime(generated_at)
    if parsed is None:
        return None
    return parsed.astimezone(timezone_info).strftime("%Y-%m-%d %H:%M")


def _parse_iso_datetime(raw_value: str | None) -> datetime | None:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
