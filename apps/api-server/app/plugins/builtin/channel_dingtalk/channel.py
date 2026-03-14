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
    raise ValueError("dingtalk channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("request")
    body = _load_request_json(request)
    event = _extract_event(body)
    if event is None:
        return {"message": "dingtalk event ignored"}

    text = _extract_text(event)
    if not text:
        return {"message": "dingtalk text message is missing"}

    external_user_id = _first_text(
        event,
        "senderStaffId",
        "staffId",
        "sender_staff_id",
        "userid",
        "senderId",
    )
    conversation_id = _first_text(
        event,
        "conversationId",
        "conversation_id",
        "openConversationId",
    )
    message_id = _first_text(event, "msgId", "messageId")
    if not external_user_id or not conversation_id or not message_id:
        return {"message": "dingtalk event ids are incomplete"}

    chat_type = "direct" if _is_direct_chat(event) else "group"
    sender_display_name = _first_text(event, "senderNick", "nickName", "sender_name")
    session_webhook = _first_text(event, "sessionWebhook", "session_webhook")

    return {
        "message": "dingtalk webhook accepted",
        "event": {
            "external_event_id": message_id,
            "event_type": "message",
            "external_user_id": external_user_id,
            "external_conversation_key": f"conversation:{conversation_id}",
            "normalized_payload": {
                "text": text,
                "chat_type": chat_type,
                "sender_display_name": sender_display_name,
                "metadata": {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "session_webhook": session_webhook,
                },
            },
            "status": "received",
        },
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        raise ValueError("dingtalk delivery payload is missing")
    metadata = delivery.get("metadata")
    webhook_url = _resolve_session_webhook(metadata)
    if not webhook_url:
        raise ValueError("dingtalk session webhook is missing")
    text = _first_text(delivery, "text")
    if not text:
        raise ValueError("dingtalk delivery text is missing")

    response = httpx.post(
        webhook_url,
        json={
            "msgtype": "text",
            "text": {"content": text},
        },
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    if isinstance(payload_json, dict):
        provider_message_ref = _first_text(payload_json, "processQueryKey", "messageId")
    else:
        provider_message_ref = None
    return {
        "provider_message_ref": provider_message_ref,
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("dingtalk channel account payload is missing")
    config = _load_account_config(account.get("config"))
    app_key = _first_text(config, "app_key", "appKey", "client_id", "clientId")
    app_secret = _first_text(config, "app_secret", "appSecret", "client_secret", "clientSecret")
    if app_key and app_secret:
        return {
            "probe_status": "ok",
            "message": "dingtalk app credentials configured",
        }
    return {
        "probe_status": "ok",
        "message": "dingtalk sessionWebhook mode does not require active probe",
    }


def _extract_event(body: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(body.get("data"), str) and body["data"].strip():
        try:
            decoded = json.loads(body["data"])
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            return decoded
    if isinstance(body.get("data"), dict):
        return body["data"]
    if isinstance(body.get("event"), dict):
        return body["event"]
    if any(key in body for key in ("conversationId", "msgId", "text")):
        return body
    return None


def _extract_text(event: dict[str, Any]) -> str | None:
    text_payload = event.get("text")
    if isinstance(text_payload, dict):
        text = _first_text(text_payload, "content")
        if text:
            return text
    content = event.get("content")
    if isinstance(content, dict):
        text = _first_text(content, "text", "content")
        if text:
            return text
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            text = _first_text(parsed, "text", "content")
            if text:
                return text
    return _first_text(event, "text", "message")


def _is_direct_chat(event: dict[str, Any]) -> bool:
    conversation_type = _first_text(event, "conversationType", "conversation_type")
    if conversation_type in {"1", "single", "private"}:
        return True
    if conversation_type in {"2", "group"}:
        return False
    return _first_text(event, "chatbotCorpId") is None


def _resolve_session_webhook(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    return _first_text(metadata, "session_webhook", "sessionWebhook")


def _load_request_json(raw_request: Any) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("dingtalk webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("dingtalk webhook body is missing")
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise ValueError("dingtalk webhook body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("dingtalk webhook body must be a JSON object")
    return payload


def _first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
