from __future__ import annotations

import asyncio

from app.modules.voice.protocol import build_voice_command_event
from app.modules.voice.realtime_service import voice_realtime_service
from app.plugins.builtin.open_xiaoai_speaker.runtime import error_result, parse_action_payload, success_result

_SUPPORTED_ACTIONS = frozenset({"play_pause", "turn_off", "turn_on", "set_volume"})


def run(payload: dict | None = None) -> dict:
    raw_payload = payload or {}
    plugin_id = str(raw_payload.get("plugin_id") or "open-xiaoai-speaker")
    action = str(raw_payload.get("action") or "play_pause")

    try:
        request = parse_action_payload(raw_payload)
        plugin_id = request.plugin_id
        action = request.action
    except Exception as exc:
        return error_result(
            plugin_id=plugin_id,
            action=action,
            error_code="plugin_internal_error",
            error_message=f"控制 payload 不合法: {exc}",
        )

    terminal_id = request.device_snapshot.id
    if not terminal_id.strip():
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="plugin_payload_invalid",
            error_message="缺少终端标识",
        )

    if request.action not in _SUPPORTED_ACTIONS:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="action_not_supported",
            error_message=f"open-xiaoai-speaker 暂不支持动作: {request.action}",
        )

    try:
        event_type, command_payload = _build_command_payload(action=request.action, params=request.params)
        asyncio.run(
            _send_command(
                terminal_id=terminal_id,
                event_type=event_type,
                payload=command_payload,
            )
        )
    except LookupError:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="platform_unreachable",
            error_message="speaker is offline",
        )
    except Exception as exc:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="plugin_internal_error",
            error_message=str(exc),
        )

    return success_result(
        plugin_id=request.plugin_id,
        action=request.action,
        external_request={
            "terminal_id": terminal_id,
            "command": event_type,
            "payload": command_payload,
        },
        external_response={"accepted": True},
        normalized_state_patch=None,
    )


def _build_command_payload(*, action: str, params: dict) -> tuple[str, dict]:
    if action in {"play_pause", "turn_off"}:
        return "play.stop", {"playback_id": None, "reason": "device_control"}
    if action == "turn_on":
        return "speaker.turn_on", {"reason": "device_control"}
    if action == "set_volume":
        return "speaker.set_volume", {"volume_pct": int(params.get("volume_pct", 0)), "reason": "device_control"}
    raise ValueError(f"unsupported action: {action}")


async def _send_command(*, terminal_id: str, event_type: str, payload: dict) -> None:
    command = build_voice_command_event(
        event_type=event_type,
        terminal_id=terminal_id,
        seq=0,
        payload=payload,
        session_id=f"device-control-{terminal_id}",
    )
    await voice_realtime_service.send_command(command)
