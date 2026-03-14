from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
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
    raise ValueError("feishu channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("feishu channel account payload is missing")
    config = _load_account_config(account.get("config"))
    body = _load_request_json(
        payload.get("request"),
        encrypt_key=_first_text(config, "encrypt_key", "encryptKey"),
    )

    verification_token = _first_text(config, "verification_token", "verificationToken")
    if verification_token:
        incoming_token = _first_text(body, "token")
        if incoming_token != verification_token:
            raise ValueError("feishu verification token is invalid")

    if _first_text(body, "challenge"):
        return {
            "message": "feishu challenge accepted",
            "http_response": {
                "status_code": 200,
                "body_json": {"challenge": _first_text(body, "challenge")},
            },
        }

    event = body.get("event")
    if not isinstance(event, dict):
        return {"message": "feishu event ignored"}

    message = event.get("message")
    sender = event.get("sender")
    if not isinstance(message, dict) or not isinstance(sender, dict):
        return {"message": "feishu event ignored"}
    if str(message.get("message_type")) != "text":
        return {"message": "feishu non-text event ignored"}

    content = _parse_feishu_content(message.get("content"))
    text = _first_text(content, "text")
    if not text:
        return {"message": "feishu text content is missing"}

    sender_id = sender.get("sender_id")
    if not isinstance(sender_id, dict):
        return {"message": "feishu sender id is missing"}
    external_user_id = _first_text(sender_id, "open_id", "user_id", "union_id")
    chat_id = _first_text(message, "chat_id")
    message_id = _first_text(message, "message_id")
    if not external_user_id or not chat_id or not message_id:
        return {"message": "feishu event ids are incomplete"}

    chat_type = "direct" if _first_text(message, "chat_type") == "p2p" else "group"
    thread_key = _first_text(message, "thread_id", "root_id")

    return {
        "message": "feishu webhook accepted",
        "event": {
            "external_event_id": _first_text(body, "event_id") or message_id,
            "event_type": "message",
            "external_user_id": external_user_id,
            "external_conversation_key": f"chat:{chat_id}",
            "normalized_payload": {
                "text": text,
                "chat_type": chat_type,
                "thread_key": thread_key,
                "sender_display_name": _first_text(sender, "tenant_key"),
                "metadata": {
                    "chat_id": chat_id,
                    "message_id": message_id,
                },
            },
            "status": "received",
        },
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
    chat_id = target.removeprefix("chat:")
    base_url = _resolve_base_url(config)
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
    return {
        "provider_message_ref": _first_text(data, "message_id"),
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("feishu channel account payload is missing")
    config = _load_account_config(account.get("config"))
    app_id = _first_text(config, "app_id", "appId")
    app_secret = _first_text(config, "app_secret", "appSecret")
    if not app_id or not app_secret:
        raise ValueError("feishu app credentials are missing")
    base_url = _resolve_base_url(config)
    _fetch_tenant_access_token(base_url, app_id, app_secret)
    return {
        "probe_status": "ok",
        "message": "feishu app credentials verified",
    }


def _fetch_tenant_access_token(base_url: str, app_id: str, app_secret: str) -> str:
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
    token = _first_text(payload, "tenant_access_token")
    if not token:
        raise ValueError("feishu tenant access token is missing")
    return token


def _resolve_base_url(config: dict[str, Any]) -> str:
    domain = _first_text(config, "domain")
    if not domain or domain == "feishu":
        return "https://open.feishu.cn"
    if domain == "lark":
        return "https://open.larksuite.com"
    if domain.startswith("https://"):
        return domain.rstrip("/")
    raise ValueError("feishu domain is invalid")


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("feishu account config is not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def _load_request_json(raw_request: Any, *, encrypt_key: str | None) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("feishu webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("feishu webhook body is missing")
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise ValueError("feishu webhook body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("feishu webhook body must be a JSON object")
    encrypted = _first_text(payload, "encrypt")
    if encrypted is not None:
        if not encrypt_key:
            raise ValueError("feishu encrypt callback requires encrypt_key")
        return _decrypt_encrypted_payload(encrypted, encrypt_key)
    return payload


def _parse_feishu_content(raw_content: Any) -> dict[str, Any]:
    if isinstance(raw_content, dict):
        return raw_content
    if isinstance(raw_content, str) and raw_content.strip():
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValueError("feishu message content is not valid JSON") from exc
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


def _decrypt_encrypted_payload(encrypted_text: str, encrypt_key: str) -> dict[str, Any]:
    encrypted_bytes = _decode_base64(encrypted_text)
    candidate_keys = _build_candidate_keys(encrypt_key)
    for key_bytes in candidate_keys:
        try:
            plaintext = _decrypt_with_key(encrypted_bytes, key_bytes)
            payload = _parse_decrypted_payload(plaintext)
        except ValueError:
            continue
        if payload is not None:
            return payload
    raise ValueError("feishu encrypt payload cannot be decrypted with current encrypt_key")


def _build_candidate_keys(encrypt_key: str) -> list[bytes]:
    normalized = encrypt_key.strip()
    candidates: list[bytes] = []
    raw_bytes = normalized.encode("utf-8")
    if len(raw_bytes) in {16, 24, 32}:
        candidates.append(raw_bytes)
    sha_key = hashlib.sha256(raw_bytes).digest()
    candidates.append(sha_key)
    try:
        decoded = _decode_base64(normalized)
    except ValueError:
        decoded = None
    if decoded is not None and len(decoded) in {16, 24, 32}:
        candidates.append(decoded)

    unique_candidates: list[bytes] = []
    seen: set[bytes] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique_candidates.append(item)
    return unique_candidates


def _decrypt_with_key(ciphertext: bytes, key_bytes: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(key_bytes[:16]))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise ValueError("feishu decrypt padding is invalid") from exc


def _parse_decrypted_payload(plaintext: bytes) -> dict[str, Any] | None:
    try:
        decoded = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        decoded = plaintext.decode("utf-8", errors="ignore")
    candidates = [decoded]
    start = decoded.find("{")
    end = decoded.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidates.append(decoded[start : end + 1])

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _decode_base64(value: str) -> bytes:
    normalized = value.strip()
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        return base64.b64decode(padded)
    except Exception as exc:
        raise ValueError("feishu encrypted payload is not valid base64") from exc
