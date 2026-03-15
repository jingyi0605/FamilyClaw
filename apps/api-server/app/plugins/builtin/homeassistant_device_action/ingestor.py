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
        subject_id = source_ref or payload_data.get("device") or payload_data.get("external_device_id")
        observed_at = record.get("captured_at")

        if record_type == "device_power_state":
            observations.append({"type": "Observation", "subject_type": "Device", "subject_id": subject_id, "category": "device_power_state", "value": payload_data.get("value"), "unit": payload_data.get("unit", "state"), "observed_at": observed_at, "source_plugin_id": "homeassistant", "source_record_ref": raw_id})
        elif record_type == "temperature":
            observations.append({"type": "Observation", "subject_type": "Device", "subject_id": subject_id, "category": "room_temperature", "value": payload_data.get("value"), "unit": payload_data.get("unit", "celsius"), "observed_at": observed_at, "source_plugin_id": "homeassistant", "source_record_ref": raw_id})
        elif record_type == "humidity":
            observations.append({"type": "Observation", "subject_type": "Device", "subject_id": subject_id, "category": "room_humidity", "value": payload_data.get("value"), "unit": payload_data.get("unit", "percent"), "observed_at": observed_at, "source_plugin_id": "homeassistant", "source_record_ref": raw_id})
    return observations
