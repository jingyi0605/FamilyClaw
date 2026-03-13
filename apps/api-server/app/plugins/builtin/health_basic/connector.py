from __future__ import annotations


def sync(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    member_id = normalized_payload.get("member_id", "demo-member")
    return {
        "source": "health-basic-reader",
        "mode": "connector",
        "member_id": member_id,
        "records": [
            {
                "record_type": "steps",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 8421,
                "unit": "count",
                "captured_at": "2026-03-12T07:00:00Z",
            },
            {
                "record_type": "sleep",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 6.8,
                "unit": "hour",
                "captured_at": "2026-03-12T07:00:00Z",
            },
            {
                "record_type": "heart_rate",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 72,
                "unit": "bpm",
                "captured_at": "2026-03-12T07:00:00Z",
            },
        ],
    }


def fail_sync(payload: dict | None = None) -> dict:
    raise RuntimeError("demo plugin failure")
