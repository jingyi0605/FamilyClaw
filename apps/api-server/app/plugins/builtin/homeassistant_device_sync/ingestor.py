from __future__ import annotations


def transform(payload: dict | None = None) -> list[dict]:
    normalized_payload = payload or {}
    records = normalized_payload.get("records", [])
    observations: list[dict] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        raw_id = record.get("id")
        source_ref = record.get("source_ref")
        payload_data = record.get("payload", {})
        if not isinstance(payload_data, dict):
            payload_data = {}
        record_type = record.get("record_type")

        if record_type == "temperature":
            observations.append(
                {
                    "type": "Observation",
                    "subject_type": "Device",
                    "subject_id": source_ref or payload_data.get("device"),
                    "category": "room_temperature",
                    "value": payload_data.get("value"),
                    "unit": payload_data.get("unit", "celsius"),
                    "observed_at": record.get("captured_at"),
                    "source_plugin_id": "homeassistant-device-sync",
                    "source_record_ref": raw_id,
                }
            )
    return observations
