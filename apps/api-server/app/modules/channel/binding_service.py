from sqlalchemy.orm import Session

from app.db.utils import new_uuid, utc_now_iso
from app.modules.member.service import get_member_or_404

from . import repository
from .account_service import get_channel_account_or_404
from .models import MemberChannelBinding
from .schemas import (
    ChannelBindingResolveRead,
    MemberChannelBindingCreate,
    MemberChannelBindingRead,
    MemberChannelBindingUpdate,
)


class MemberChannelBindingServiceError(ValueError):
    pass


UNBOUND_DIRECT_REPLY_TEXT = "当前平台账号还没有绑定家庭成员，请联系管理员先完成绑定。"


def list_member_bindings(db: Session, *, member_id: str) -> list[MemberChannelBindingRead]:
    get_member_or_404(db, member_id)
    return [_to_member_channel_binding_read(item) for item in repository.list_member_channel_bindings(db, member_id=member_id)]


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
        platform_code=account.platform_code,
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
        external_chat_id=payload.external_chat_id.strip() if isinstance(payload.external_chat_id, str) and payload.external_chat_id.strip() else None,
        display_hint=payload.display_hint.strip() if isinstance(payload.display_hint, str) and payload.display_hint.strip() else None,
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
            platform_code=row.platform_code,
            external_user_id=payload.external_user_id,
            binding_id=row.id,
        )
        row.external_user_id = payload.external_user_id.strip()
    if payload.external_chat_id is not None:
        row.external_chat_id = payload.external_chat_id.strip() if payload.external_chat_id.strip() else None
    if payload.display_hint is not None:
        row.display_hint = payload.display_hint.strip() if payload.display_hint.strip() else None
    if payload.binding_status is not None:
        row.binding_status = payload.binding_status
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_member_channel_binding_read(row)


def _ensure_external_user_not_conflicted(
    db: Session,
    *,
    household_id: str,
    platform_code: str,
    external_user_id: str,
    binding_id: str | None,
) -> None:
    existing = repository.get_member_channel_binding_by_external_user(
        db,
        household_id=household_id,
        platform_code=platform_code,
        external_user_id=external_user_id.strip(),
    )
    if existing is None:
        return
    if binding_id is not None and existing.id == binding_id:
        return
    raise MemberChannelBindingServiceError("external user is already bound in current household")


def resolve_member_binding_for_inbound(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_user_id: str | None,
    chat_type: str,
) -> ChannelBindingResolveRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=channel_account_id)
    if external_user_id is not None:
        existing = repository.get_member_channel_binding_by_external_user(
            db,
            household_id=household_id,
            platform_code=account.platform_code,
            external_user_id=external_user_id.strip(),
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
