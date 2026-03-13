from __future__ import annotations


def sync(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    room_id = normalized_payload.get("room_id", "living-room")
    sensor_id = normalized_payload.get("sensor_id", f"{room_id}-sensor")
    light_id = normalized_payload.get("light_id", f"{room_id}-main-light")
    return {
        "source": "homeassistant-device-sync",
        "mode": "connector",
        "received_payload": normalized_payload,
        "records": [
            {
                "record_type": "device_power_state",
                "external_device_id": light_id,
                "device": light_id,
                "room_id": room_id,
                "value": "on",
                "unit": "state",
                "captured_at": "2026-03-12T08:30:00Z",
            },
            {
                "record_type": "temperature",
                "external_device_id": sensor_id,
                "device": sensor_id,
                "room_id": room_id,
                "value": 23.5,
                "unit": "celsius",
                "captured_at": "2026-03-12T08:30:00Z",
            },
            {
                "record_type": "humidity",
                "external_device_id": sensor_id,
                "device": sensor_id,
                "room_id": room_id,
                "value": 48.0,
                "unit": "percent",
                "captured_at": "2026-03-12T08:30:00Z",
            }
        ],
    }
