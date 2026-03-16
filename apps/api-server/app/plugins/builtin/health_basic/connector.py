from __future__ import annotations

from datetime import datetime, timedelta, timezone


def sync(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    member_id = normalized_payload.get("member_id", "demo-member")
    captured_at = datetime.now(timezone.utc).replace(microsecond=0)
    captured_at_iso = captured_at.isoformat().replace("+00:00", "Z")
    expires_at_iso = (captured_at + timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    step_value = 8421
    return {
        "source": "health-basic-reader",
        "mode": "connector",
        "member_id": member_id,
        "records": [
            {
                "record_type": "steps",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": step_value,
                "unit": "count",
                "captured_at": captured_at_iso,
            },
            {
                "record_type": "sleep",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 6.8,
                "unit": "hour",
                "captured_at": captured_at_iso,
            },
            {
                "record_type": "heart_rate",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 72,
                "unit": "bpm",
                "captured_at": captured_at_iso,
            },
        ],
        "dashboard_snapshots": [
            {
                "card_key": "daily-steps-summary",
                "payload": {
                    "value": step_value,
                    "unit": "步",
                    "context": "今天已经记录到的步数",
                    "trend": {
                        "direction": "up",
                        "label": "继续保持今天的活动节奏",
                    },
                },
                "actions": [
                    {
                        "action_key": "open-detail",
                        "action_type": "open_plugin_detail",
                        "label": "查看插件",
                    }
                ],
                "expires_at": expires_at_iso,
            }
        ],
    }


def fail_sync(payload: dict | None = None) -> dict:
    raise RuntimeError("demo plugin failure")
