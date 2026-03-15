from __future__ import annotations

from app.plugins.builtin.homeassistant_device_action.adapter import run_legacy_homeassistant_action

def run(payload: dict | None = None) -> dict:
    return run_legacy_homeassistant_action(payload)
