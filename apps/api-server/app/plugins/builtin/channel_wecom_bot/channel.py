from __future__ import annotations

import json
from typing import Any

import httpx


UNSUPPORTED_WEBHOOK_MESSAGE = "企业微信群机器人模式当前只支持出站推送，不支持用户消息直接入站。"


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "webhook":
        return {
            "message": UNSUPPORTED_WEBHOOK_MESSAGE,
            "http_response": {
                "status_code": 200,
                "body_text": "success",
                "media_type": "text/plain",
            },
        }
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    raise ValueError("wecom bot channel action is not supported")


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(account, dict) or not isinstance(delivery, dict):
        raise ValueError("wecom bot delivery payload is missing")
    config = _load_account_config(account.get("config"))
    webhook_url = _resolve_webhook_url(config)
    text = _first_text(delivery, "text")
    if not webhook_url or not text:
        raise ValueError("wecom bot webhook url or text is missing")
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
    provider_message_ref = _first_text(payload_json, "errmsg")
    return {
        "provider_message_ref": provider_message_ref,
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("wecom bot account payload is missing")
    config = _load_account_config(account.get("config"))
    webhook_url = _resolve_webhook_url(config)
    if not webhook_url:
        raise ValueError("wecom bot webhook url or key is missing")
    return {
        "probe_status": "ok",
        "message": "wecom bot outbound webhook configured",
    }


def _resolve_webhook_url(config: dict[str, Any]) -> str | None:
    webhook_url = _first_text(config, "webhook_url", "webhookUrl")
    if webhook_url:
        return webhook_url
    key = _first_text(config, "key")
    if key:
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    return None


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("wecom bot config is not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def _first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
