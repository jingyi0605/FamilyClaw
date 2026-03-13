from __future__ import annotations


def run(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    target_ref = normalized_payload.get("target_ref", "demo-light")
    action_name = normalized_payload.get("action_name", "turn_on")
    return {
        "source": "homeassistant-device-action",
        "mode": "action",
        "target_ref": target_ref,
        "action_name": action_name,
        "executed": True,
        "received_payload": normalized_payload,
    }
