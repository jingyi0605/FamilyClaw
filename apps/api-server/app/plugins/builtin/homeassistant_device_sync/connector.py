from __future__ import annotations


def sync(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    return {
        "source": "homeassistant-device-sync",
        "mode": "connector",
        "received_payload": normalized_payload,
        "records": [
            {
                "record_type": "temperature",
                "device": "living-room-sensor",
                "value": 23.5,
                "unit": "celsius",
            }
        ],
    }
