from __future__ import annotations

import json
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "webhook":
        return _handle_webhook(data)
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    raise ValueError("discord channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("discord channel account payload is missing")
    config = _load_account_config(account.get("config"))
    request = payload.get("request")
    headers = _normalize_headers(request)
    body_text = _load_body_text(request)
    _verify_signature(config, headers, body_text)

    body = _load_body_json(body_text)
    interaction_type = body.get("type")
    if interaction_type == 1:
        return {
            "message": "discord ping acknowledged",
            "http_response": {
                "status_code": 200,
                "body_json": {"type": 1},
            },
        }
    if interaction_type != 2:
        return {
            "message": "discord interaction ignored",
            "http_response": {
                "status_code": 200,
                "body_json": {
                    "type": 4,
                    "data": {
                        "content": "当前只支持文本命令对话。",
                        "flags": 64,
                    },
                },
            },
        }

    text = _extract_command_text(body.get("data"))
    if not text:
        return {
            "message": "discord command text is missing",
            "http_response": {
                "status_code": 200,
                "body_json": {
                    "type": 4,
                    "data": {
                        "content": "请在命令里提供文本内容。",
                        "flags": 64,
                    },
                },
            },
        }

    member = body.get("member")
    user = member.get("user") if isinstance(member, dict) else body.get("user")
    if not isinstance(user, dict):
        raise ValueError("discord interaction user is missing")
    external_user_id = _stringify(user.get("id"))
    channel_id = _stringify(body.get("channel_id"))
    interaction_id = _stringify(body.get("id"))
    interaction_token = _first_text(body, "token")
    application_id = _stringify(body.get("application_id"))
    if external_user_id is None or channel_id is None or interaction_id is None:
        raise ValueError("discord interaction ids are incomplete")

    chat_type = "direct" if body.get("guild_id") is None else "group"
    sender_display_name = _first_text(user, "global_name", "username")

    return {
        "message": "discord interaction accepted",
        "http_response": {
            "status_code": 200,
            "body_json": {"type": 5},
            "defer_processing": True,
        },
        "event": {
            "external_event_id": interaction_id,
            "event_type": "message",
            "external_user_id": external_user_id,
            "external_conversation_key": f"channel:{channel_id}",
            "normalized_payload": {
                "text": text,
                "chat_type": chat_type,
                "sender_display_name": sender_display_name,
                "metadata": {
                    "channel_id": channel_id,
                    "application_id": application_id,
                    "interaction_token": interaction_token,
                },
            },
            "status": "received",
        },
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(account, dict) or not isinstance(delivery, dict):
        raise ValueError("discord delivery payload is missing")
    config = _load_account_config(account.get("config"))
    text = _first_text(delivery, "text")
    if not text:
        raise ValueError("discord delivery text is missing")
    metadata = delivery.get("metadata")
    provider_message_ref = _send_via_interaction_followup(text, metadata)
    if provider_message_ref is not None:
        return {"provider_message_ref": provider_message_ref}
    return {"provider_message_ref": _send_via_bot_channel(config, delivery, text)}


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("discord channel account payload is missing")
    config = _load_account_config(account.get("config"))
    public_key = _first_text(config, "application_public_key", "applicationPublicKey", "public_key", "publicKey")
    if not public_key:
        raise ValueError("discord application public key is missing")
    bot_token = _first_text(config, "bot_token", "botToken", "token")
    if not bot_token:
        return {
            "probe_status": "ok",
            "message": "discord interaction webhook configured",
        }
    response = httpx.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bot {bot_token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    username = _first_text(payload_json, "username")
    return {
        "probe_status": "ok",
        "message": f"discord bot online{f' @{username}' if username else ''}",
    }


def _send_via_interaction_followup(text: str, metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    application_id = _first_text(metadata, "application_id")
    interaction_token = _first_text(metadata, "interaction_token")
    if not application_id or not interaction_token:
        return None
    response = httpx.post(
        f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}",
        params={"wait": "true"},
        json={"content": text},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    return _stringify(payload.get("id")) if isinstance(payload, dict) else None


def _send_via_bot_channel(config: dict[str, Any], delivery: dict[str, Any], text: str) -> str | None:
    bot_token = _first_text(config, "bot_token", "botToken", "token")
    target = _first_text(delivery, "external_conversation_key")
    if not bot_token or not target or not target.startswith("channel:"):
        raise ValueError("discord bot token or channel target is missing")
    channel_id = target.removeprefix("channel:")
    response = httpx.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        },
        json={"content": text},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    return _stringify(payload.get("id")) if isinstance(payload, dict) else None


def _verify_signature(config: dict[str, Any], headers: dict[str, str], body_text: str) -> None:
    public_key_hex = _first_text(
        config,
        "application_public_key",
        "applicationPublicKey",
        "public_key",
        "publicKey",
    )
    if not public_key_hex:
        raise ValueError("discord application public key is missing")
    signature_hex = headers.get("x-signature-ed25519")
    timestamp = headers.get("x-signature-timestamp")
    if not signature_hex or not timestamp:
        raise ValueError("discord signature headers are missing")
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    signed_message = (timestamp + body_text).encode("utf-8")
    try:
        public_key.verify(bytes.fromhex(signature_hex), signed_message)
    except InvalidSignature as exc:
        raise ValueError("discord webhook signature is invalid") from exc


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("discord account config is not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_headers(raw_request: Any) -> dict[str, str]:
    if not isinstance(raw_request, dict):
        return {}
    headers = raw_request.get("headers")
    if not isinstance(headers, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key.lower()] = value
    return normalized


def _load_body_text(raw_request: Any) -> str:
    if not isinstance(raw_request, dict):
        raise ValueError("discord webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str):
        raise ValueError("discord webhook body is missing")
    return body_text


def _load_body_json(body_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(body_text or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("discord webhook body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("discord webhook body must be a JSON object")
    return payload


def _extract_command_text(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    options = data.get("options")
    if not isinstance(options, list):
        return None
    for option in options:
        text = _extract_option_value(option)
        if text:
            return text
    return None


def _extract_option_value(option: Any) -> str | None:
    if not isinstance(option, dict):
        return None
    value = option.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip()
    nested_options = option.get("options")
    if isinstance(nested_options, list):
        for nested in nested_options:
            text = _extract_option_value(nested)
            if text:
                return text
    return None


def _first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _stringify(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return None
