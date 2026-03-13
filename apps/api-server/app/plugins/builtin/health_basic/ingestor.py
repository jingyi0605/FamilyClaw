from __future__ import annotations


def transform(payload: dict | None = None) -> list[dict]:
    normalized_payload = payload or {}
    records = normalized_payload.get("records", [])
    observations: list[dict] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        record_type = record.get("record_type")
        source_ref = record.get("source_ref")
        raw_id = record.get("id")
        payload_data = record.get("payload", {})
        if not isinstance(payload_data, dict):
            payload_data = {}

        if record_type == "steps":
            observations.append(
                {
                    "type": "Observation",
                    "subject_type": "Person",
                    "subject_id": source_ref or payload_data.get("member_id"),
                    "category": "daily_steps",
                    "value": payload_data.get("value"),
                    "unit": payload_data.get("unit", "count"),
                    "observed_at": record.get("captured_at"),
                    "source_plugin_id": "health-basic-reader",
                    "source_record_ref": raw_id,
                }
            )
        elif record_type == "sleep":
            observations.append(
                {
                    "type": "Observation",
                    "subject_type": "Person",
                    "subject_id": source_ref or payload_data.get("member_id"),
                    "category": "sleep_duration",
                    "value": payload_data.get("value"),
                    "unit": payload_data.get("unit", "hour"),
                    "observed_at": record.get("captured_at"),
                    "source_plugin_id": "health-basic-reader",
                    "source_record_ref": raw_id,
                }
            )
    return observations
