from __future__ import annotations

import json
from typing import Any

import httpx


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "webhook":
        return _handle_webhook(data)
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    raise ValueError("telegram channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("telegram channel account payload is missing")
    config = _load_account_config(account.get("config"))
    headers = _normalize_headers(payload.get("request"))
    secret = _first_text(config, "webhook_secret", "webhookSecret")
    if secret:
        incoming_secret = headers.get("x-telegram-bot-api-secret-token")
        if incoming_secret != secret:
            raise ValueError("telegram webhook secret token is invalid")

    body = _load_request_json(payload.get("request"))
    message = _extract_message(body)
    if message is None:
        return {"message": "telegram update ignored"}

    text = _first_text(message, "text", "caption")
    if not text:
        return {"message": "telegram text message is missing"}

    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return {"message": "telegram update ignored"}

    external_user_id = _stringify(sender.get("id"))
    chat_id = _stringify(chat.get("id"))
    if external_user_id is None or chat_id is None:
        return {"message": "telegram update ignored"}

    chat_type = "direct" if str(chat.get("type")) == "private" else "group"
    sender_display_name = _build_sender_name(sender)
    thread_key = _stringify(message.get("message_thread_id"))
    event_id = _stringify(body.get("update_id")) or _stringify(message.get("message_id")) or f"telegram:{chat_id}:{external_user_id}"

    return {
        "message": "telegram webhook accepted",
        "event": {
            "external_event_id": event_id,
            "event_type": "message",
            "external_user_id": external_user_id,
            "external_conversation_key": f"chat:{chat_id}",
            "normalized_payload": {
                "text": text,
                "chat_type": chat_type,
                "thread_key": thread_key,
                "sender_display_name": sender_display_name,
                "metadata": {
                    "chat_id": chat_id,
                    "message_id": _stringify(message.get("message_id")),
                },
            },
            "status": "received",
        },
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(account, dict) or not isinstance(delivery, dict):
        raise ValueError("telegram delivery payload is missing")
    config = _load_account_config(account.get("config"))
    token = _first_text(config, "bot_token", "botToken", "token")
    if not token:
        raise ValueError("telegram bot token is missing")
    target = _parse_target(_first_text(delivery, "external_conversation_key"))
    text = _first_text(delivery, "text")
    if target["chat_id"] is None or not text:
        raise ValueError("telegram delivery target or text is missing")

    request_body: dict[str, Any] = {
        "chat_id": target["chat_id"],
        "text": text,
    }
    if target["thread_id"] is not None:
        request_body["message_thread_id"] = int(target["thread_id"])

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=request_body,
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    result = payload_json.get("result") if isinstance(payload_json, dict) else None
    provider_message_ref = _stringify(result.get("message_id")) if isinstance(result, dict) else None
    return {
        "provider_message_ref": provider_message_ref,
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("telegram channel account payload is missing")
    config = _load_account_config(account.get("config"))
    token = _first_text(config, "bot_token", "botToken", "token")
    if not token:
        raise ValueError("telegram bot token is missing")
    response = httpx.get(
        f"https://api.telegram.org/bot{token}/getMe",
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    result = payload_json.get("result") if isinstance(payload_json, dict) else None
    username = _first_text(result, "username")
    return {
        "probe_status": "ok",
        "message": f"telegram bot online{f' @{username}' if username else ''}",
    }


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("telegram account config is not valid JSON") from exc
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


def _load_request_json(raw_request: Any) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("telegram webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("telegram webhook body is missing")
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise ValueError("telegram webhook body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("telegram webhook body must be a JSON object")
    return payload


def _extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    return None


def _build_sender_name(sender: dict[str, Any]) -> str | None:
    for key in ("username", "first_name", "last_name"):
        value = sender.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_target(external_conversation_key: str | None) -> dict[str, str | None]:
    if not external_conversation_key:
        return {"chat_id": None, "thread_id": None}
    base_key, _, thread_value = external_conversation_key.partition("#thread:")
    if not base_key.startswith("chat:"):
        return {"chat_id": None, "thread_id": None}
    return {
        "chat_id": base_key.removeprefix("chat:"),
        "thread_id": thread_value or None,
    }


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
    if isinstance(value, (int, float)):
        return str(int(value))
    return None
