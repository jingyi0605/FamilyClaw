from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConversationRoute:
    base_conversation_key: str
    binding_conversation_key: str
    delivery_conversation_key: str
    thread_key: str | None


def resolve_channel_conversation_route(
    external_conversation_key: str | None,
    *,
    external_user_id: str | None,
    chat_type: str,
    thread_key: str | None,
) -> ChannelConversationRoute:
    base_conversation_key = _resolve_base_conversation_key(
        external_conversation_key,
        external_user_id=external_user_id,
        chat_type=chat_type,
    )
    normalized_thread_key = _normalize_optional_text(thread_key)
    if normalized_thread_key is None:
        return ChannelConversationRoute(
            base_conversation_key=base_conversation_key,
            binding_conversation_key=base_conversation_key,
            delivery_conversation_key=base_conversation_key,
            thread_key=None,
        )

    thread_conversation_key = _build_thread_conversation_key(
        base_conversation_key=base_conversation_key,
        thread_key=normalized_thread_key,
    )
    return ChannelConversationRoute(
        base_conversation_key=base_conversation_key,
        binding_conversation_key=thread_conversation_key,
        delivery_conversation_key=thread_conversation_key,
        thread_key=normalized_thread_key,
    )


def _resolve_base_conversation_key(
    external_conversation_key: str | None,
    *,
    external_user_id: str | None,
    chat_type: str,
) -> str:
    normalized_external_conversation_key = _normalize_optional_text(external_conversation_key)
    if normalized_external_conversation_key is not None:
        return normalized_external_conversation_key
    normalized_external_user_id = _normalize_optional_text(external_user_id)
    if chat_type == "direct" and normalized_external_user_id is not None:
        return f"direct:{normalized_external_user_id}"
    raise ValueError("external conversation key is required")


def _build_thread_conversation_key(*, base_conversation_key: str, thread_key: str) -> str:
    if base_conversation_key.startswith("chat:"):
        return f"{base_conversation_key}#thread:{thread_key}"
    return f"{base_conversation_key}#thread:{thread_key}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
