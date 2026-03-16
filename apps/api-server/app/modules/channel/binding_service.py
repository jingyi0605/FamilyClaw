from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.utils import load_json, new_uuid, utc_now_iso
from app.modules.member.service import get_member_or_404

from . import repository
from .account_service import get_channel_account_or_404
from .models import ChannelInboundEvent, MemberChannelBinding
from .schemas import (
    ChannelBindingCandidateRead,
    ChannelBindingResolveRead,
    MemberChannelBindingCreate,
    MemberChannelBindingRead,
    MemberChannelBindingUpdate,
)


class MemberChannelBindingServiceError(ValueError):
    pass


UNBOUND_DIRECT_REPLY_TEXT = "当前平台账号还没有绑定家庭成员，请联系管理员先完成绑定。"
CANDIDATE_EVENT_SCAN_LIMIT = 100


def list_member_bindings(db: Session, *, member_id: str) -> list[MemberChannelBindingRead]:
    get_member_or_404(db, member_id)
    bindings = repository.list_member_channel_bindings(db, member_id=member_id)
    return [_to_member_channel_binding_read(item) for item in bindings]


def create_member_binding(
    db: Session,
    *,
    member_id: str,
    payload: MemberChannelBindingCreate,
) -> MemberChannelBindingRead:
    member = get_member_or_404(db, member_id)
    account = get_channel_account_or_404(db, household_id=member.household_id, account_id=payload.channel_account_id)
    _ensure_external_user_not_conflicted(
        db,
        household_id=member.household_id,
        channel_account_id=account.id,
        external_user_id=payload.external_user_id,
        binding_id=None,
    )

    now = utc_now_iso()
    row = MemberChannelBinding(
        id=new_uuid(),
        household_id=member.household_id,
        member_id=member.id,
        channel_account_id=account.id,
        platform_code=account.platform_code,
        external_user_id=payload.external_user_id.strip(),
        external_chat_id=_normalize_optional_text(payload.external_chat_id),
        display_hint=_normalize_optional_text(payload.display_hint),
        binding_status=payload.binding_status,
        created_at=now,
        updated_at=now,
    )
    repository.add_member_channel_binding(db, row)
    db.flush()
    return _to_member_channel_binding_read(row)


def update_member_binding(
    db: Session,
    *,
    member_id: str,
    binding_id: str,
    payload: MemberChannelBindingUpdate,
) -> MemberChannelBindingRead:
    member = get_member_or_404(db, member_id)
    row = repository.get_member_channel_binding(db, binding_id)
    if row is None or row.member_id != member.id:
        raise MemberChannelBindingServiceError("member channel binding not found")

    if payload.external_user_id is not None:
        _ensure_external_user_not_conflicted(
            db,
            household_id=row.household_id,
            channel_account_id=row.channel_account_id,
            external_user_id=payload.external_user_id,
            binding_id=row.id,
        )
        row.external_user_id = payload.external_user_id.strip()
    if payload.external_chat_id is not None:
        row.external_chat_id = _normalize_optional_text(payload.external_chat_id)
    if payload.display_hint is not None:
        row.display_hint = _normalize_optional_text(payload.display_hint)
    if payload.binding_status is not None:
        row.binding_status = payload.binding_status
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_member_channel_binding_read(row)


def resolve_member_binding_for_inbound(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_user_id: str | None,
    chat_type: str,
) -> ChannelBindingResolveRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=channel_account_id)
    normalized_external_user_id = _normalize_optional_text(external_user_id)
    if normalized_external_user_id is not None:
        existing = repository.get_member_channel_binding_by_external_user(
            db,
            household_id=household_id,
            channel_account_id=account.id,
            external_user_id=normalized_external_user_id,
        )
        if existing is not None and existing.binding_status == "active":
            return ChannelBindingResolveRead(
                matched=True,
                strategy="bound",
                member_id=existing.member_id,
                binding_id=existing.id,
                reply_text=None,
            )

    if chat_type == "direct":
        return ChannelBindingResolveRead(
            matched=False,
            strategy="direct_unbound_prompt",
            reply_text=UNBOUND_DIRECT_REPLY_TEXT,
        )
    return ChannelBindingResolveRead(
        matched=False,
        strategy="group_unbound_ignore",
        reply_text=None,
    )


def list_channel_account_bindings(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> list[MemberChannelBindingRead]:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    bindings = repository.list_channel_account_bindings(db, channel_account_id=account.id)
    return [_to_member_channel_binding_read(item) for item in bindings]


def create_channel_account_binding(
    db: Session,
    *,
    household_id: str,
    payload: MemberChannelBindingCreate,
) -> MemberChannelBindingRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=payload.channel_account_id)
    member = get_member_or_404(db, payload.member_id)
    if member.household_id != household_id:
        raise MemberChannelBindingServiceError("member does not belong to current household")

    _ensure_external_user_not_conflicted(
        db,
        household_id=household_id,
        channel_account_id=account.id,
        external_user_id=payload.external_user_id,
        binding_id=None,
    )

    now = utc_now_iso()
    row = MemberChannelBinding(
        id=new_uuid(),
        household_id=household_id,
        member_id=member.id,
        channel_account_id=account.id,
        platform_code=account.platform_code,
        external_user_id=payload.external_user_id.strip(),
        external_chat_id=_normalize_optional_text(payload.external_chat_id),
        display_hint=_normalize_optional_text(payload.display_hint),
        binding_status=payload.binding_status,
        created_at=now,
        updated_at=now,
    )
    repository.add_member_channel_binding(db, row)
    db.flush()
    return _to_member_channel_binding_read(row)


def update_channel_account_binding(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    binding_id: str,
    payload: MemberChannelBindingUpdate,
) -> MemberChannelBindingRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    row = repository.get_member_channel_binding(db, binding_id)
    if row is None or row.channel_account_id != account.id:
        raise MemberChannelBindingServiceError("member channel binding not found")

    if payload.external_user_id is not None:
        _ensure_external_user_not_conflicted(
            db,
            household_id=household_id,
            channel_account_id=account.id,
            external_user_id=payload.external_user_id,
            binding_id=row.id,
        )
        row.external_user_id = payload.external_user_id.strip()
    if payload.external_chat_id is not None:
        row.external_chat_id = _normalize_optional_text(payload.external_chat_id)
    if payload.display_hint is not None:
        row.display_hint = _normalize_optional_text(payload.display_hint)
    if payload.binding_status is not None:
        row.binding_status = payload.binding_status
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_member_channel_binding_read(row)


def delete_channel_account_binding(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    binding_id: str,
) -> None:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    row = repository.get_member_channel_binding(db, binding_id)
    if row is None or row.channel_account_id != account.id:
        raise MemberChannelBindingServiceError("member channel binding not found")

    repository.delete_member_channel_binding(db, row)
    db.flush()


def list_channel_account_binding_candidates(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> list[ChannelBindingCandidateRead]:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    bindings = repository.list_channel_account_bindings(db, channel_account_id=account.id)
    bound_external_user_ids = {item.external_user_id for item in bindings}
    inbound_events = repository.list_channel_account_unbound_inbound_events(
        db,
        channel_account_id=account.id,
        status="ignored",
        error_code="channel_member_binding_not_found",
        limit=CANDIDATE_EVENT_SCAN_LIMIT,
    )

    latest_events_by_user: dict[str, ChannelInboundEvent] = {}
    for inbound_event in inbound_events:
        external_user_id = _normalize_optional_text(inbound_event.external_user_id)
        if external_user_id is None:
            continue
        if external_user_id in bound_external_user_ids:
            continue
        current = latest_events_by_user.get(external_user_id)
        if current is None or _is_inbound_event_newer(inbound_event, current):
            latest_events_by_user[external_user_id] = inbound_event

    ordered_events = sorted(
        latest_events_by_user.values(),
        key=_build_inbound_event_sort_key,
        reverse=True,
    )
    return [_to_binding_candidate_read(item) for item in ordered_events]


def _ensure_external_user_not_conflicted(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_user_id: str,
    binding_id: str | None,
) -> None:
    existing = repository.get_member_channel_binding_by_external_user(
        db,
        household_id=household_id,
        channel_account_id=channel_account_id,
        external_user_id=external_user_id.strip(),
    )
    if existing is None:
        return
    if binding_id is not None and existing.id == binding_id:
        return
    raise MemberChannelBindingServiceError("external user is already bound in current channel account")


def _to_member_channel_binding_read(row: MemberChannelBinding) -> MemberChannelBindingRead:
    return MemberChannelBindingRead(
        id=row.id,
        household_id=row.household_id,
        member_id=row.member_id,
        channel_account_id=row.channel_account_id,
        platform_code=row.platform_code,
        external_user_id=row.external_user_id,
        external_chat_id=row.external_chat_id,
        display_hint=row.display_hint,
        binding_status=row.binding_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_binding_candidate_read(inbound_event: ChannelInboundEvent) -> ChannelBindingCandidateRead:
    normalized_payload = load_json(inbound_event.normalized_payload_json)
    payload = normalized_payload if isinstance(normalized_payload, dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    raw_chat_type = payload.get("chat_type")
    chat_type = raw_chat_type if raw_chat_type in {"direct", "group"} else "direct"

    return ChannelBindingCandidateRead(
        external_user_id=inbound_event.external_user_id or "",
        external_chat_id=_first_non_empty_text(
            metadata.get("chat_id"),
            _parse_chat_id_from_conversation_key(inbound_event.external_conversation_key),
        ),
        sender_display_name=_first_non_empty_text(payload.get("sender_display_name")),
        username=_first_non_empty_text(metadata.get("username")),
        chat_type=chat_type,
        last_message_text=_first_non_empty_text(payload.get("text")),
        last_seen_at=inbound_event.received_at,
        inbound_event_id=inbound_event.id,
        platform_code=inbound_event.platform_code,
        channel_account_id=inbound_event.channel_account_id,
    )


def _parse_chat_id_from_conversation_key(external_conversation_key: str | None) -> str | None:
    normalized = _normalize_optional_text(external_conversation_key)
    if normalized is None or not normalized.startswith("chat:"):
        return None
    base_key = normalized.split("#thread:", 1)[0]
    chat_id = base_key.removeprefix("chat:").strip()
    return chat_id or None


def _normalize_optional_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _first_non_empty_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_inbound_event_newer(left: ChannelInboundEvent, right: ChannelInboundEvent) -> bool:
    return _build_inbound_event_sort_key(left) > _build_inbound_event_sort_key(right)


def _build_inbound_event_sort_key(inbound_event: ChannelInboundEvent) -> tuple[str, int, str]:
    return (
        inbound_event.received_at or "",
        _coerce_event_sequence(inbound_event.external_event_id),
        inbound_event.id,
    )


def _coerce_event_sequence(external_event_id: str | None) -> int:
    normalized = _normalize_optional_text(external_event_id)
    if normalized is None:
        return -1
    try:
        return int(normalized)
    except ValueError:
        return -1
