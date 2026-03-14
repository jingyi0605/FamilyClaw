from __future__ import annotations

import base64
import hashlib
import json
from typing import Any
from xml.etree import ElementTree

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
    raise ValueError("wecom app channel action is not supported")


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    request = payload.get("request")
    if not isinstance(account, dict):
        raise ValueError("wecom app account payload is missing")
    config = _load_account_config(account.get("config"))
    query_params = _normalize_query_params(request)
    method = _extract_method(request)
    token = _first_text(config, "callback_token", "callbackToken", "token")
    aes_key = _first_text(config, "encoding_aes_key", "encodingAESKey", "aes_key")
    if not token or not aes_key:
        raise ValueError("wecom app callback token or encoding_aes_key is missing")

    if method == "GET":
        echo_str = query_params.get("echostr")
        timestamp = query_params.get("timestamp")
        nonce = query_params.get("nonce")
        signature = query_params.get("msg_signature")
        if not echo_str or not timestamp or not nonce or not signature:
            raise ValueError("wecom app handshake query is incomplete")
        _verify_signature(token, timestamp, nonce, echo_str, signature)
        plaintext = _decrypt_aes_payload(echo_str, aes_key, _first_text(config, "corp_id", "corpId"))
        return {
            "message": "wecom app handshake accepted",
            "http_response": {
                "status_code": 200,
                "body_text": plaintext,
                "media_type": "text/plain",
            },
        }

    body_xml = _load_xml_body(request)
    encrypted = _extract_xml_text(body_xml, "Encrypt")
    timestamp = query_params.get("timestamp") or _extract_xml_text(body_xml, "TimeStamp")
    nonce = query_params.get("nonce") or _extract_xml_text(body_xml, "Nonce")
    signature = query_params.get("msg_signature")
    if not encrypted or not timestamp or not nonce or not signature:
        raise ValueError("wecom app callback payload is incomplete")
    _verify_signature(token, timestamp, nonce, encrypted, signature)
    plaintext = _decrypt_aes_payload(encrypted, aes_key, _first_text(config, "corp_id", "corpId"))
    message_xml = ElementTree.fromstring(plaintext.encode("utf-8"))

    msg_type = _extract_xml_text(message_xml, "MsgType")
    if msg_type != "text":
        return {
            "message": "wecom app non-text event ignored",
            "http_response": {
                "status_code": 200,
                "body_text": "success",
                "media_type": "text/plain",
            },
        }

    from_user = _extract_xml_text(message_xml, "FromUserName")
    to_user = _extract_xml_text(message_xml, "ToUserName")
    content = _extract_xml_text(message_xml, "Content")
    msg_id = _extract_xml_text(message_xml, "MsgId") or _extract_xml_text(message_xml, "MsgId64")
    agent_id = _extract_xml_text(message_xml, "AgentID")
    if not from_user or not to_user or not content or not msg_id:
        raise ValueError("wecom app text message fields are incomplete")

    return {
        "message": "wecom app callback accepted",
        "http_response": {
            "status_code": 200,
            "body_text": "success",
            "media_type": "text/plain",
        },
        "event": {
            "external_event_id": msg_id,
            "event_type": "message",
            "external_user_id": from_user,
            "external_conversation_key": f"direct:{from_user}",
            "normalized_payload": {
                "text": content,
                "chat_type": "direct",
                "sender_display_name": from_user,
                "metadata": {
                    "touser": from_user,
                    "agent_id": agent_id,
                    "app_to_user": to_user,
                },
            },
            "status": "received",
        },
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(account, dict) or not isinstance(delivery, dict):
        raise ValueError("wecom app delivery payload is missing")
    config = _load_account_config(account.get("config"))
    corp_id = _first_text(config, "corp_id", "corpId")
    corp_secret = _first_text(config, "corp_secret", "corpSecret")
    agent_id = _first_text(config, "agent_id", "agentId")
    if not corp_id or not corp_secret or not agent_id:
        raise ValueError("wecom app credentials are missing")
    text = _first_text(delivery, "text")
    if not text:
        raise ValueError("wecom app delivery text is missing")
    metadata = delivery.get("metadata")
    touser = _resolve_touser(metadata, _first_text(delivery, "external_conversation_key"))
    if not touser:
        raise ValueError("wecom app target user is missing")

    access_token = _fetch_access_token(corp_id, corp_secret)
    response = httpx.post(
        f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}",
        json={
            "touser": touser,
            "msgtype": "text",
            "agentid": int(agent_id),
            "text": {"content": text},
            "safe": 0,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    payload_json = response.json()
    return {
        "provider_message_ref": _first_text(payload_json, "msgid", "invaliduser"),
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("wecom app account payload is missing")
    config = _load_account_config(account.get("config"))
    corp_id = _first_text(config, "corp_id", "corpId")
    corp_secret = _first_text(config, "corp_secret", "corpSecret")
    callback_token = _first_text(config, "callback_token", "callbackToken", "token")
    aes_key = _first_text(config, "encoding_aes_key", "encodingAESKey", "aes_key")
    agent_id = _first_text(config, "agent_id", "agentId")
    if not corp_id or not corp_secret or not callback_token or not aes_key or not agent_id:
        raise ValueError("wecom app config is incomplete")
    _fetch_access_token(corp_id, corp_secret)
    return {
        "probe_status": "ok",
        "message": "wecom app credentials verified",
    }


def _fetch_access_token(corp_id: str, corp_secret: str) -> str:
    response = httpx.get(
        "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
        params={"corpid": corp_id, "corpsecret": corp_secret},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    token = _first_text(payload, "access_token")
    if not token:
        raise ValueError("wecom app access token is missing")
    return token


def _resolve_touser(metadata: Any, external_conversation_key: str | None) -> str | None:
    if isinstance(metadata, dict):
        touser = _first_text(metadata, "touser")
        if touser:
            return touser
    if external_conversation_key and external_conversation_key.startswith("direct:"):
        return external_conversation_key.removeprefix("direct:")
    return None


def _verify_signature(token: str, timestamp: str, nonce: str, encrypted: str, signature: str) -> None:
    candidate = "".join(sorted([token, timestamp, nonce, encrypted]))
    digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()
    if digest != signature:
        raise ValueError("wecom app callback signature is invalid")


def _decrypt_aes_payload(encrypted_text: str, aes_key: str, receive_id: str | None) -> str:
    key = base64.b64decode(aes_key + "=")
    cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
    decryptor = cipher.decryptor()
    encrypted = base64.b64decode(encrypted_text)
    padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    msg_len = int.from_bytes(plaintext[16:20], byteorder="big")
    xml_bytes = plaintext[20 : 20 + msg_len]
    receive_id_bytes = plaintext[20 + msg_len :]
    if receive_id and receive_id_bytes and receive_id_bytes.decode("utf-8", errors="ignore") != receive_id:
        raise ValueError("wecom app callback receive id does not match config")
    return xml_bytes.decode("utf-8")


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("wecom app config is not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_query_params(raw_request: Any) -> dict[str, str]:
    if not isinstance(raw_request, dict):
        return {}
    query_params = raw_request.get("query_params")
    if not isinstance(query_params, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in query_params.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key] = value
    return normalized


def _extract_method(raw_request: Any) -> str:
    if not isinstance(raw_request, dict):
        return "POST"
    method = raw_request.get("method")
    return method.upper() if isinstance(method, str) and method.strip() else "POST"


def _load_xml_body(raw_request: Any) -> ElementTree.Element:
    if not isinstance(raw_request, dict):
        raise ValueError("wecom app webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("wecom app webhook body is missing")
    try:
        return ElementTree.fromstring(body_text.encode("utf-8"))
    except ElementTree.ParseError as exc:
        raise ValueError("wecom app webhook body is not valid XML") from exc


def _extract_xml_text(root: ElementTree.Element, tag: str) -> str | None:
    node = root.find(tag)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
