from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .api import fetch_tenant_access_token
from .common import first_text, load_account_config, load_callback_body, resolve_open_base_url
from .event_parser import extract_challenge, normalize_feishu_message_event, validate_verification_token
from .plugin_binding import route_inbound_event_for_core
from .ws_runtime import manager as ws_runtime_manager


logger = logging.getLogger(__name__)


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "webhook":
        return _handle_webhook(data)
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    if action == "poll":
        return _handle_poll(data)
    raise ValueError("feishu channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("feishu channel account payload is missing")
    account_id = _first_text(account, "id")
    household_id = _first_text(account, "household_id")
    config = _load_account_config(account.get("config"))
    body = load_callback_body(
        payload.get("request"),
        encrypt_key=_first_text(config, "encrypt_key", "encryptKey"),
    )
    logger.info(
        "feishu-debug webhook_received account_id=%s household_id=%s body_keys=%s",
        account_id,
        household_id,
        sorted(body.keys()),
    )

    validate_verification_token(body, _first_text(config, "verification_token", "verificationToken"))

    challenge = extract_challenge(body)
    if challenge:
        logger.info(
            "feishu-debug webhook_challenge account_id=%s household_id=%s",
            account_id,
            household_id,
        )
        return {
            "message": "feishu challenge accepted",
            "http_response": {
                "status_code": 200,
                "body_json": {"challenge": challenge},
            },
        }

    event = normalize_feishu_message_event(body)
    if event is None:
        logger.info(
            "feishu-debug webhook_ignored account_id=%s household_id=%s reason=normalize_returned_none",
            account_id,
            household_id,
        )
        return {"message": "feishu event ignored"}

    logger.info(
        "feishu-debug webhook_normalized account_id=%s household_id=%s external_event_id=%s external_user_id=%s conversation_key=%s chat_type=%s",
        account_id,
        household_id,
        _first_text(event, "external_event_id"),
        _first_text(event, "external_user_id"),
        _first_text(event, "external_conversation_key"),
        _first_text(event.get("normalized_payload"), "chat_type"),
    )

    forwarded_event = route_inbound_event_for_core(account, event)
    if forwarded_event is None:
        logger.info(
            "feishu-debug webhook_handled_in_plugin account_id=%s household_id=%s external_event_id=%s",
            account_id,
            household_id,
            _first_text(event, "external_event_id"),
        )
        return {"message": "feishu inbound event handled in plugin"}

    logger.info(
        "feishu-debug webhook_forward_to_core account_id=%s household_id=%s external_event_id=%s",
        account_id,
        household_id,
        _first_text(forwarded_event, "external_event_id"),
    )

    return {
        "message": "feishu webhook accepted",
        "event": forwarded_event,
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(account, dict) or not isinstance(delivery, dict):
        raise ValueError("feishu delivery payload is missing")
    config = _load_account_config(account.get("config"))
    app_id = _first_text(config, "app_id", "appId")
    app_secret = _first_text(config, "app_secret", "appSecret")
    if not app_id or not app_secret:
        raise ValueError("feishu app credentials are missing")
    text = _first_text(delivery, "text")
    target = _first_text(delivery, "external_conversation_key")
    if not text or not target or not target.startswith("chat:"):
        raise ValueError("feishu delivery target or text is missing")

    account_id = _first_text(account, "id")
    chat_id = target.removeprefix("chat:")
    base_url = _resolve_base_url(config)
    logger.info(
        "feishu-debug outbound_send_start account_id=%s conversation_key=%s chat_id=%s text_length=%s",
        account_id,
        target,
        chat_id,
        len(text),
    )
    access_token = _fetch_tenant_access_token(base_url, app_id, app_secret)
    response = httpx.post(
        f"{base_url}/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    data = payload_json.get("data") if isinstance(payload_json, dict) else None
    provider_message_ref = _first_text(data, "message_id")
    logger.info(
        "feishu-debug outbound_send_success account_id=%s conversation_key=%s chat_id=%s provider_message_ref=%s",
        account_id,
        target,
        chat_id,
        provider_message_ref,
    )
    return {
        "provider_message_ref": provider_message_ref,
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("feishu channel account payload is missing")
    account_id = _first_text(account, "id")
    config = _load_account_config(account.get("config"))
    app_id = _first_text(config, "app_id", "appId")
    app_secret = _first_text(config, "app_secret", "appSecret")
    if not app_id or not app_secret:
        raise ValueError("feishu app credentials are missing")

    base_url = _resolve_base_url(config)
    logger.info(
        "feishu-debug probe_start account_id=%s connection_mode=%s base_url=%s",
        account_id,
        _first_text(account, "connection_mode"),
        base_url,
    )
    _fetch_tenant_access_token(base_url, app_id, app_secret)
    if str(account.get("connection_mode") or "").strip() == "polling":
        ws_runtime_manager.probe_long_connection(account)
    logger.info(
        "feishu-debug probe_success account_id=%s connection_mode=%s",
        account_id,
        _first_text(account, "connection_mode"),
    )
    return {
        "probe_status": "ok",
        "message": "feishu app credentials verified",
    }


def _handle_poll(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("feishu channel account payload is missing")
    account_id = _first_text(account, "id")
    batch = ws_runtime_manager.poll(account)
    raw_events = batch.get("events")
    if not isinstance(raw_events, list):
        return batch
    logger.info(
        "feishu-debug poll_batch_received account_id=%s event_count=%s next_cursor=%s message=%s",
        account_id,
        len(raw_events),
        batch.get("next_cursor"),
        batch.get("message"),
    )

    forwarded_events: list[dict[str, Any]] = []
    plugin_handled_count = 0
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        forwarded = route_inbound_event_for_core(account, item)
        if forwarded is None:
            plugin_handled_count += 1
            continue
        forwarded_events.append(forwarded)

    batch["events"] = forwarded_events
    if plugin_handled_count > 0:
        original_message = batch.get("message")
        suffix = f"plugin_handled_unbound={plugin_handled_count}"
        if isinstance(original_message, str) and original_message.strip():
            batch["message"] = f"{original_message}; {suffix}"
        else:
            batch["message"] = suffix
    logger.info(
        "feishu-debug poll_batch_processed account_id=%s forwarded_count=%s plugin_handled_count=%s next_cursor=%s",
        account_id,
        len(forwarded_events),
        plugin_handled_count,
        batch.get("next_cursor"),
    )
    return batch


def _fetch_tenant_access_token(base_url: str, app_id: str, app_secret: str) -> str:
    return fetch_tenant_access_token(base_url, app_id, app_secret)


def _resolve_base_url(config: dict[str, Any]) -> str:
    return resolve_open_base_url(config)


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    return load_account_config(raw_config)


def _first_text(mapping: Any, *keys: str) -> str | None:
    return first_text(mapping, *keys)
