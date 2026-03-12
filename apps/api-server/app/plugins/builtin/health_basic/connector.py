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
                "value": 8421,
                "unit": "count",
            },
            {
                "record_type": "sleep",
                "value": 6.8,
                "unit": "hour",
            },
        ],
    }


def fail_sync(payload: dict | None = None) -> dict:
    raise RuntimeError("demo plugin failure")
