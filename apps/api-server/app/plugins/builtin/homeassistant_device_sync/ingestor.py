from __future__ import annotations


def transform(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    return {
        "source": "homeassistant-device-sync",
        "mode": "memory-ingestor",
        "observation_count": len(normalized_payload.get("records", [])),
    }
