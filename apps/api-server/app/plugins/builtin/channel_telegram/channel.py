from __future__ import annotations

import json
import time
from typing import Any

import httpx

_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
_TELEGRAM_RETRYABLE_ATTEMPTS = 2
_TELEGRAM_RETRYABLE_DELAY_SECONDS = 0.2


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "poll":
        return _handle_poll(data)
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    raise ValueError("telegram channel action is not supported")


def _handle_poll(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("telegram channel account payload is missing")
    config = _load_account_config(account.get("config"))
    token = _first_text(config, "bot_token", "botToken", "token")
    if not token:
        raise ValueError("telegram bot token is missing")

    poll_state = payload.get("poll_state")
    request_body: dict[str, Any] = {
        "timeout": 0,
        "limit": 20,
        "allowed_updates": ["message", "edited_message"],
    }
    cursor = _extract_poll_cursor(poll_state)
    if cursor is not None:
        request_body["offset"] = cursor

    updates = _fetch_updates(token, request_body)
    events: list[dict[str, Any]] = []
    max_update_id: int | None = None
    for update in updates:
        update_id = _coerce_int(update.get("update_id"))
        if update_id is not None:
            max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
        event = _build_event_from_update(update)
        if event is not None:
            events.append(event)

    next_cursor = None if max_update_id is None else str(max_update_id + 1)
    return {
        "message": "telegram polling completed",
        "events": events,
        "next_cursor": next_cursor,
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

    response = _telegram_post(
        token,
        "sendMessage",
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
    response = _telegram_get(token, "getMe", timeout=10.0)
    response.raise_for_status()
    payload_json = response.json()
    result = payload_json.get("result") if isinstance(payload_json, dict) else None
    username = _first_text(result, "username")
    return {
        "probe_status": "ok",
        "message": f"telegram bot online{f' @{username}' if username else ''}",
    }


def _fetch_updates(token: str, request_body: dict[str, Any]) -> list[dict[str, Any]]:
    response = _telegram_post(
        token,
        "getUpdates",
        json=request_body,
        timeout=15.0,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 409:
            raise
        _delete_webhook(token)
        response = _telegram_post(
            token,
            "getUpdates",
            json=request_body,
            timeout=15.0,
        )
        response.raise_for_status()

    payload_json = response.json()
    result = payload_json.get("result") if isinstance(payload_json, dict) else None
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _delete_webhook(token: str) -> None:
    response = _telegram_post(
        token,
        "deleteWebhook",
        json={"drop_pending_updates": False},
        timeout=10.0,
    )
    response.raise_for_status()


def _telegram_get(token: str, method: str, *, timeout: float) -> httpx.Response:
    return _request_telegram_api(
        "GET",
        token,
        method,
        timeout=timeout,
    )


def _telegram_post(
    token: str,
    method: str,
    *,
    json: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    return _request_telegram_api(
        "POST",
        token,
        method,
        json=json,
        timeout=timeout,
    )


def _request_telegram_api(
    http_method: str,
    token: str,
    method: str,
    *,
    json: dict[str, Any] | None = None,
    timeout: float,
) -> httpx.Response:
    url = f"{_TELEGRAM_API_BASE_URL}/bot{token}/{method}"
    last_error: httpx.TransportError | None = None
    for attempt in range(_TELEGRAM_RETRYABLE_ATTEMPTS):
        try:
            if http_method == "GET":
                return httpx.get(url, timeout=timeout)
            return httpx.post(url, json=json, timeout=timeout)
        except httpx.TransportError as exc:
            last_error = exc
            if attempt + 1 >= _TELEGRAM_RETRYABLE_ATTEMPTS:
                raise
            time.sleep(_TELEGRAM_RETRYABLE_DELAY_SECONDS)
    if last_error is not None:
        raise last_error
    raise RuntimeError("telegram request did not execute")


def _build_event_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    message = _extract_message(update)
    if message is None:
        return None

    text = _first_text(message, "text", "caption")
    if not text:
        return None

    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return None

    external_user_id = _stringify(sender.get("id"))
    chat_id = _stringify(chat.get("id"))
    if external_user_id is None or chat_id is None:
        return None

    username = _first_text(sender, "username")
    sender_display_name = _build_sender_display_name(sender, username=username)
    thread_key = _stringify(message.get("message_thread_id"))
    update_id = _stringify(update.get("update_id"))
    message_id = _stringify(message.get("message_id"))
    event_id = update_id or message_id or f"telegram:{chat_id}:{external_user_id}"
    chat_type = "direct" if str(chat.get("type")) == "private" else "group"

    return {
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
                "message_id": message_id,
                "username": username,
            },
        },
        "status": "received",
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


def _extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    return None


def _build_sender_display_name(sender: dict[str, Any], *, username: str | None) -> str | None:
    first_name = _first_text(sender, "first_name")
    last_name = _first_text(sender, "last_name")
    if first_name and last_name:
        return f"{first_name} {last_name}"
    if first_name:
        return first_name
    if last_name:
        return last_name
    return username


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


def _extract_poll_cursor(poll_state: Any) -> int | None:
    if not isinstance(poll_state, dict):
        return None
    return _coerce_int(poll_state.get("cursor"))


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


def _coerce_int(value: Any) -> int | None:
    try:
        normalized = _stringify(value)
        if normalized is None:
            return None
        return int(normalized)
    except (TypeError, ValueError):
        return None
