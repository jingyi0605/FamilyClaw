from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.channel.models import (
    ChannelConversationBinding,
    ChannelDelivery,
    ChannelInboundEvent,
    ChannelPluginAccount,
    MemberChannelBinding,
)


def add_channel_plugin_account(db: Session, row: ChannelPluginAccount) -> ChannelPluginAccount:
    db.add(row)
    return row


def get_channel_plugin_account(db: Session, account_id: str) -> ChannelPluginAccount | None:
    return db.get(ChannelPluginAccount, account_id)


def list_channel_plugin_accounts(db: Session, *, household_id: str) -> list[ChannelPluginAccount]:
    stmt: Select[tuple[ChannelPluginAccount]] = (
        select(ChannelPluginAccount)
        .where(ChannelPluginAccount.household_id == household_id)
        .order_by(ChannelPluginAccount.created_at.desc(), ChannelPluginAccount.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_member_channel_binding(db: Session, binding_id: str) -> MemberChannelBinding | None:
    return db.get(MemberChannelBinding, binding_id)


def add_member_channel_binding(db: Session, row: MemberChannelBinding) -> MemberChannelBinding:
    db.add(row)
    return row


def list_member_channel_bindings(db: Session, *, member_id: str) -> list[MemberChannelBinding]:
    stmt: Select[tuple[MemberChannelBinding]] = (
        select(MemberChannelBinding)
        .where(MemberChannelBinding.member_id == member_id)
        .order_by(MemberChannelBinding.created_at.desc(), MemberChannelBinding.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_member_channel_binding_by_external_user(
    db: Session,
    *,
    household_id: str,
    platform_code: str,
    external_user_id: str,
) -> MemberChannelBinding | None:
    stmt: Select[tuple[MemberChannelBinding]] = select(MemberChannelBinding).where(
        MemberChannelBinding.household_id == household_id,
        MemberChannelBinding.platform_code == platform_code,
        MemberChannelBinding.external_user_id == external_user_id,
    )
    return db.scalar(stmt)


def add_channel_conversation_binding(
    db: Session,
    row: ChannelConversationBinding,
) -> ChannelConversationBinding:
    db.add(row)
    return row


def get_channel_conversation_binding_by_external_key(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_conversation_key: str,
) -> ChannelConversationBinding | None:
    stmt: Select[tuple[ChannelConversationBinding]] = select(ChannelConversationBinding).where(
        ChannelConversationBinding.household_id == household_id,
        ChannelConversationBinding.channel_account_id == channel_account_id,
        ChannelConversationBinding.external_conversation_key == external_conversation_key,
    )
    return db.scalar(stmt)


def add_channel_inbound_event(db: Session, row: ChannelInboundEvent) -> ChannelInboundEvent:
    db.add(row)
    return row


def get_channel_inbound_event(db: Session, inbound_event_id: str) -> ChannelInboundEvent | None:
    return db.get(ChannelInboundEvent, inbound_event_id)


def get_channel_inbound_event_by_external_event(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
    external_event_id: str,
) -> ChannelInboundEvent | None:
    stmt: Select[tuple[ChannelInboundEvent]] = select(ChannelInboundEvent).where(
        ChannelInboundEvent.household_id == household_id,
        ChannelInboundEvent.channel_account_id == channel_account_id,
        ChannelInboundEvent.external_event_id == external_event_id,
    )
    return db.scalar(stmt)


def list_channel_inbound_events(
    db: Session,
    *,
    household_id: str,
) -> list[ChannelInboundEvent]:
    stmt: Select[tuple[ChannelInboundEvent]] = (
        select(ChannelInboundEvent)
        .where(ChannelInboundEvent.household_id == household_id)
        .order_by(ChannelInboundEvent.received_at.desc(), ChannelInboundEvent.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_channel_delivery(db: Session, row: ChannelDelivery) -> ChannelDelivery:
    db.add(row)
    return row


def get_channel_delivery(db: Session, delivery_id: str) -> ChannelDelivery | None:
    return db.get(ChannelDelivery, delivery_id)


def list_channel_deliveries(db: Session, *, household_id: str) -> list[ChannelDelivery]:
    stmt: Select[tuple[ChannelDelivery]] = (
        select(ChannelDelivery)
        .where(ChannelDelivery.household_id == household_id)
        .order_by(ChannelDelivery.created_at.desc(), ChannelDelivery.id.desc())
    )
    return list(db.scalars(stmt).all())


def list_channel_deliveries_by_account(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
) -> list[ChannelDelivery]:
    stmt: Select[tuple[ChannelDelivery]] = (
        select(ChannelDelivery)
        .where(
            ChannelDelivery.household_id == household_id,
            ChannelDelivery.channel_account_id == channel_account_id,
        )
        .order_by(ChannelDelivery.created_at.desc(), ChannelDelivery.id.desc())
    )
    return list(db.scalars(stmt).all())
