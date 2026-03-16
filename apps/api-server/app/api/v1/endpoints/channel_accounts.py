from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.channel.account_service import ChannelAccountServiceError
from app.modules.channel.schemas import (
    ChannelAccountCreate,
    ChannelAccountRead,
    ChannelAccountStatusRead,
    ChannelBindingCandidateRead,
    ChannelAccountUpdate,
    ChannelDeliveryRead,
    ChannelInboundEventRead,
    MemberChannelBindingCreate,
    MemberChannelBindingRead,
    MemberChannelBindingUpdate,
)
from app.modules.channel.binding_service import (
    MemberChannelBindingServiceError,
    create_channel_account_binding,
    delete_channel_account_binding,
    list_channel_account_binding_candidates,
    list_channel_account_bindings,
    update_channel_account_binding,
)
from app.modules.channel.service import create_channel_account, delete_channel_account, list_channel_accounts, update_channel_account
from app.modules.channel.status_service import (
    ChannelStatusServiceError,
    get_channel_account_status,
    list_channel_delivery_status_records,
    list_channel_inbound_event_status_records,
    probe_channel_account,
)


router = APIRouter(prefix="/ai-config", tags=["ai-config"])


@router.get("/{household_id}/channel-accounts", response_model=list[ChannelAccountRead])
def list_channel_accounts_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[ChannelAccountRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_channel_accounts(db, household_id=household_id)


@router.post("/{household_id}/channel-accounts", response_model=ChannelAccountRead, status_code=status.HTTP_201_CREATED)
def create_channel_account_endpoint(
    household_id: str,
    payload: ChannelAccountCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ChannelAccountRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = create_channel_account(db, household_id=household_id, payload=payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account.create",
            target_type="channel_plugin_account",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except ChannelAccountServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.put("/{household_id}/channel-accounts/{account_id}", response_model=ChannelAccountRead)
def update_channel_account_endpoint(
    household_id: str,
    account_id: str,
    payload: ChannelAccountUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ChannelAccountRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = update_channel_account(
            db,
            household_id=household_id,
            account_id=account_id,
            payload=payload,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account.update",
            target_type="channel_plugin_account",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json", exclude_unset=True),
        )
        db.commit()
        return result
    except ChannelAccountServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.delete("/{household_id}/channel-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel_account_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    ensure_actor_can_access_household(actor, household_id)
    try:
        deleted_account = delete_channel_account(
            db,
            household_id=household_id,
            account_id=account_id,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account.delete",
            target_type="channel_plugin_account",
            target_id=account_id,
            result="success",
            details={
                "platform_code": deleted_account.platform_code,
                "account_code": deleted_account.account_code,
                "display_name": deleted_account.display_name,
            },
        )
        db.commit()
        return None
    except ChannelAccountServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{household_id}/channel-accounts/{account_id}/probe", response_model=ChannelAccountStatusRead)
def probe_channel_account_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ChannelAccountStatusRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = probe_channel_account(db, household_id=household_id, account_id=account_id)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account.probe",
            target_type="channel_plugin_account",
            target_id=account_id,
            result="success" if result.account.last_probe_status != "failed" else "fail",
            details={"account_id": account_id, "last_probe_status": result.account.last_probe_status},
        )
        db.commit()
        return result
    except (ChannelAccountServiceError, ChannelStatusServiceError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{household_id}/channel-accounts/{account_id}/status", response_model=ChannelAccountStatusRead)
def get_channel_account_status_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ChannelAccountStatusRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return get_channel_account_status(db, household_id=household_id, account_id=account_id)
    except (ChannelAccountServiceError, ChannelStatusServiceError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{household_id}/channel-deliveries", response_model=list[ChannelDeliveryRead])
def list_channel_deliveries_endpoint(
    household_id: str,
    channel_account_id: str | None = Query(default=None),
    platform_code: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[ChannelDeliveryRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_channel_delivery_status_records(
        db,
        household_id=household_id,
        channel_account_id=channel_account_id,
        platform_code=platform_code,
        status=status_value,
    )


@router.get("/{household_id}/channel-inbound-events", response_model=list[ChannelInboundEventRead])
def list_channel_inbound_events_endpoint(
    household_id: str,
    channel_account_id: str | None = Query(default=None),
    platform_code: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[ChannelInboundEventRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_channel_inbound_event_status_records(
        db,
        household_id=household_id,
        channel_account_id=channel_account_id,
        platform_code=platform_code,
        status=status_value,
    )


# ====== 绑定管理接口（平台账号视角）======


@router.get(
    "/{household_id}/channel-accounts/{account_id}/bindings",
    response_model=list[MemberChannelBindingRead],
)
def list_channel_account_bindings_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[MemberChannelBindingRead]:
    """列出某个平台账号下的所有成员绑定"""
    ensure_actor_can_access_household(actor, household_id)
    try:
        return list_channel_account_bindings(db, household_id=household_id, account_id=account_id)
    except ChannelAccountServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{household_id}/channel-accounts/{account_id}/binding-candidates",
    response_model=list[ChannelBindingCandidateRead],
)
def list_channel_account_binding_candidates_endpoint(
    household_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> list[ChannelBindingCandidateRead]:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return list_channel_account_binding_candidates(db, household_id=household_id, account_id=account_id)
    except ChannelAccountServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{household_id}/channel-accounts/{account_id}/bindings",
    response_model=MemberChannelBindingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_channel_account_binding_endpoint(
    household_id: str,
    account_id: str,
    payload: MemberChannelBindingCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberChannelBindingRead:
    """在某个平台账号下创建成员绑定"""
    ensure_actor_can_access_household(actor, household_id)
    try:
        # 确保 payload 中的 channel_account_id 与路径一致
        if payload.channel_account_id != account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="channel_account_id in payload does not match path",
            )
        result = create_channel_account_binding(db, household_id=household_id, payload=payload)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account_binding.create",
            target_type="member_channel_binding",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except (ChannelAccountServiceError, MemberChannelBindingServiceError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.put(
    "/{household_id}/channel-accounts/{account_id}/bindings/{binding_id}",
    response_model=MemberChannelBindingRead,
)
def update_channel_account_binding_endpoint(
    household_id: str,
    account_id: str,
    binding_id: str,
    payload: MemberChannelBindingUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberChannelBindingRead:
    """更新某个平台账号下的成员绑定"""
    ensure_actor_can_access_household(actor, household_id)
    try:
        result = update_channel_account_binding(
            db,
            household_id=household_id,
            account_id=account_id,
            binding_id=binding_id,
            payload=payload,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account_binding.update",
            target_type="member_channel_binding",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json", exclude_unset=True),
        )
        db.commit()
        return result
    except (ChannelAccountServiceError, MemberChannelBindingServiceError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.delete(
    "/{household_id}/channel-accounts/{account_id}/bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_channel_account_binding_endpoint(
    household_id: str,
    account_id: str,
    binding_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    ensure_actor_can_access_household(actor, household_id)
    try:
        delete_channel_account_binding(
            db,
            household_id=household_id,
            account_id=account_id,
            binding_id=binding_id,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="channel_account_binding.delete",
            target_type="member_channel_binding",
            target_id=binding_id,
            result="success",
            details={"channel_account_id": account_id},
        )
        db.commit()
        return None
    except (ChannelAccountServiceError, MemberChannelBindingServiceError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
