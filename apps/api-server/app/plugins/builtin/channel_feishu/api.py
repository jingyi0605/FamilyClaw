from __future__ import annotations

import json

import httpx


def fetch_tenant_access_token(base_url: str, app_id: str, app_secret: str) -> str:
    response = httpx.post(
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        json={
            "app_id": app_id,
            "app_secret": app_secret,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("tenant_access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise ValueError("feishu tenant access token is missing")
    return token.strip()


def send_text_message(
    *,
    base_url: str,
    app_id: str,
    app_secret: str,
    chat_id: str,
    text: str,
) -> str | None:
    access_token = fetch_tenant_access_token(base_url, app_id, app_secret)
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
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    message_id = data.get("message_id") if isinstance(data, dict) else None
    return message_id.strip() if isinstance(message_id, str) and message_id.strip() else None
