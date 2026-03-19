from __future__ import annotations

import logging
from typing import Any

from app.db.session import SessionLocal
from app.db.utils import utc_now_iso
from app.modules.channel import repository
from app.modules.channel.schemas import ChannelInboundEventCreate
from app.modules.channel.service import record_channel_inbound_event

from .api import send_text_message
from .common import first_text, load_account_config, resolve_open_base_url


logger = logging.getLogger(__name__)

UNBOUND_DIRECT_REPLY_TEXT = "当前平台账号还没有绑定家庭成员，请联系管理员先完成绑定。"


def route_inbound_event_for_core(
    account_payload: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """飞书插件自己的入站门禁。

    已绑定消息交给核心继续处理；
    未绑定消息在插件内直接落候选事件，并按私聊/群聊策略处理。
    """
    if str(event.get("event_type") or "").strip() != "message":
        return event

    household_id = first_text(account_payload, "household_id")
    account_id = first_text(account_payload, "id")
    if not household_id or not account_id:
        raise ValueError("feishu channel account identifiers are missing")

    normalized_payload = event.get("normalized_payload")
    payload_dict = normalized_payload if isinstance(normalized_payload, dict) else {}
    chat_type = first_text(payload_dict, "chat_type") or "direct"
    external_user_id = first_text(event, "external_user_id")
    external_event_id = _required_text(event, "external_event_id")
    logger.info(
        "feishu-debug binding_gate_enter account_id=%s household_id=%s external_event_id=%s external_user_id=%s chat_type=%s",
        account_id,
        household_id,
        external_event_id,
        external_user_id,
        chat_type,
    )

    binding = _get_active_member_binding(
        household_id=household_id,
        account_id=account_id,
        external_user_id=external_user_id,
    )
    if binding is not None:
        logger.info(
            "feishu-debug binding_gate_bound account_id=%s household_id=%s external_event_id=%s member_id=%s binding_id=%s",
            account_id,
            household_id,
            external_event_id,
            binding["member_id"],
            binding["binding_id"],
        )
        return _attach_plugin_binding_metadata(event, binding)

    is_direct = chat_type == "direct"
    error_message = (
        "direct member binding is missing"
        if is_direct
        else "group message ignored because member binding is missing"
    )
    now = utc_now_iso()

    with SessionLocal() as db:
        inbound_event, created = record_channel_inbound_event(
            db,
            payload=ChannelInboundEventCreate(
                household_id=household_id,
                channel_account_id=account_id,
                external_event_id=external_event_id,
                event_type="message",
                external_user_id=external_user_id,
                external_conversation_key=first_text(event, "external_conversation_key"),
                normalized_payload=payload_dict,
                status="ignored",
                error_code="channel_member_binding_not_found",
                error_message=error_message,
                received_at=first_text(event, "received_at"),
                processed_at=now,
            ),
        )

        account_row = repository.get_channel_plugin_account(db, account_id)
        if account_row is not None:
            account_row.last_inbound_at = inbound_event.received_at
            account_row.updated_at = now
        db.commit()
    logger.info(
        "feishu-debug binding_gate_unbound_recorded account_id=%s household_id=%s external_event_id=%s external_user_id=%s chat_type=%s created=%s",
        account_id,
        household_id,
        external_event_id,
        external_user_id,
        chat_type,
        created,
    )

    if not is_direct or not created:
        logger.info(
            "feishu-debug binding_gate_stop_in_plugin account_id=%s household_id=%s external_event_id=%s reason=%s",
            account_id,
            household_id,
            external_event_id,
            "group_unbound" if not is_direct else "duplicate_unbound_event",
        )
        return None

    try:
        _send_unbound_direct_reply(account_payload, payload_dict)
        logger.info(
            "feishu-debug binding_gate_direct_reply_sent account_id=%s household_id=%s external_event_id=%s external_user_id=%s",
            account_id,
            household_id,
            external_event_id,
            external_user_id,
        )
    except Exception:
        logger.exception(
            "feishu plugin direct-unbound auto-reply failed account_id=%s external_user_id=%s",
            account_id,
            external_user_id,
        )
    return None


def _get_active_member_binding(
    *,
    household_id: str,
    account_id: str,
    external_user_id: str | None,
) -> dict[str, str] | None:
    normalized_external_user_id = external_user_id.strip() if isinstance(external_user_id, str) and external_user_id.strip() else None
    if normalized_external_user_id is None:
        logger.info(
            "feishu-debug binding_lookup_skipped account_id=%s household_id=%s reason=missing_external_user_id",
            account_id,
            household_id,
        )
        return None

    with SessionLocal() as db:
        binding = repository.get_member_channel_binding_by_external_user(
            db,
            household_id=household_id,
            channel_account_id=account_id,
            external_user_id=normalized_external_user_id,
        )
        if binding is None or binding.binding_status != "active":
            logger.info(
                "feishu-debug binding_lookup_miss account_id=%s household_id=%s external_user_id=%s",
                account_id,
                household_id,
                normalized_external_user_id,
            )
            return None
        logger.info(
            "feishu-debug binding_lookup_hit account_id=%s household_id=%s external_user_id=%s member_id=%s binding_id=%s",
            account_id,
            household_id,
            normalized_external_user_id,
            binding.member_id,
            binding.id,
        )
        return {
            "member_id": binding.member_id,
            "binding_id": binding.id,
        }


def _attach_plugin_binding_metadata(
    event: dict[str, Any],
    binding: dict[str, str],
) -> dict[str, Any]:
    normalized_payload = event.get("normalized_payload")
    payload_dict = dict(normalized_payload) if isinstance(normalized_payload, dict) else {}
    metadata = payload_dict.get("metadata")
    metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
    metadata_dict["plugin_binding"] = {
        "managed_by_plugin": True,
        "matched": True,
        "strategy": "bound",
        "member_id": binding["member_id"],
        "binding_id": binding["binding_id"],
        "plugin": "channel-feishu",
    }
    payload_dict["metadata"] = metadata_dict

    forwarded_event = dict(event)
    forwarded_event["normalized_payload"] = payload_dict
    return forwarded_event


def _send_unbound_direct_reply(account_payload: dict[str, Any], normalized_payload: dict[str, Any]) -> None:
    config = load_account_config(account_payload.get("config"))
    app_id = first_text(config, "app_id", "appId")
    app_secret = first_text(config, "app_secret", "appSecret")
    if not app_id or not app_secret:
        raise ValueError("feishu app credentials are missing")

    metadata = normalized_payload.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    chat_id = first_text(metadata_dict, "chat_id")
    if not chat_id:
        raise ValueError("feishu direct chat_id is missing")

    logger.info(
        "feishu-debug direct_reply_start account_id=%s chat_id=%s",
        first_text(account_payload, "id"),
        chat_id,
    )
    send_text_message(
        base_url=resolve_open_base_url(config),
        app_id=app_id,
        app_secret=app_secret,
        chat_id=chat_id,
        text=UNBOUND_DIRECT_REPLY_TEXT,
    )
    logger.info(
        "feishu-debug direct_reply_success account_id=%s chat_id=%s",
        first_text(account_payload, "id"),
        chat_id,
    )

    account_id = first_text(account_payload, "id")
    if not account_id:
        return
    with SessionLocal() as db:
        account_row = repository.get_channel_plugin_account(db, account_id)
        if account_row is not None:
            now = utc_now_iso()
            account_row.last_outbound_at = now
            account_row.updated_at = now
            db.commit()


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = first_text(mapping, key)
    if value is None:
        raise ValueError(f"feishu inbound event {key} is missing")
    return value
