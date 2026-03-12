from __future__ import annotations


def transform(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    return {
        "source": "health-basic-reader",
        "mode": "memory-ingestor",
        "observation_count": len(normalized_payload.get("records", [])),
    }
