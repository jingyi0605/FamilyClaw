from __future__ import annotations

import json
from typing import Any

from .common import first_text


def validate_verification_token(payload: dict[str, Any], expected_token: str | None) -> None:
    if not expected_token:
        return
    header = payload.get("header")
    incoming_token = first_text(payload, "token") or first_text(header, "token")
    if incoming_token != expected_token:
        raise ValueError("feishu verification token is invalid")


def extract_challenge(payload: dict[str, Any]) -> str | None:
    return first_text(payload, "challenge")


def normalize_feishu_message_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """把飞书事件压成核心通道层能直接落库的结构。"""
    event = payload.get("event")
    if not isinstance(event, dict):
        return None

    message = event.get("message")
    sender = event.get("sender")
    if not isinstance(message, dict) or not isinstance(sender, dict):
        return None
    if str(message.get("message_type")) != "text":
        return None

    content = _parse_feishu_content(message.get("content"))
    text = first_text(content, "text")
    if not text:
        return None

    sender_id = sender.get("sender_id")
    if not isinstance(sender_id, dict):
        return None
    external_user_id = first_text(sender_id, "open_id", "user_id", "union_id")
    chat_id = first_text(message, "chat_id")
    message_id = first_text(message, "message_id")
    if not external_user_id or not chat_id or not message_id:
        return None

    header = payload.get("header")
    chat_type_raw = first_text(message, "chat_type")
    # 飞书私聊在不同事件里可能给出 p2p / private。
    # 这里只有真正的 group 才应该落成群聊，别把 private 误杀成 group。
    chat_type = "group" if chat_type_raw == "group" else "direct"
    thread_key = first_text(message, "thread_id", "root_id", "parent_id")
    event_type = first_text(header, "event_type") or first_text(payload, "type")

    metadata: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if chat_type_raw:
        metadata["chat_type"] = chat_type_raw
    if event_type:
        metadata["event_type"] = event_type

    return {
        "external_event_id": first_text(header, "event_id") or first_text(payload, "event_id") or message_id,
        "event_type": "message",
        "external_user_id": external_user_id,
        "external_conversation_key": f"chat:{chat_id}",
        "normalized_payload": {
            "text": text,
            "chat_type": chat_type,
            "thread_key": thread_key,
            "sender_display_name": _resolve_sender_display_name(sender),
            "metadata": metadata,
        },
        "status": "received",
    }


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


def _resolve_sender_display_name(sender: dict[str, Any]) -> str | None:
    return first_text(
        sender,
        "name",
        "sender_name",
        "display_name",
        "tenant_key",
    )
