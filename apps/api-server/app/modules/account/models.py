from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("idx_accounts_account_type", "account_type"),
        Index("idx_accounts_household_id", "household_id"),
        Index("idx_accounts_status", "status"),
        UniqueConstraint("username", name="uq_accounts_username"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    household_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class AccountMemberBinding(Base):
    __tablename__ = "account_member_bindings"
    __table_args__ = (
        Index("idx_account_member_bindings_household_id", "household_id"),
        Index("idx_account_member_bindings_status", "binding_status"),
        UniqueConstraint("member_id", name="uq_account_member_bindings_member_id"),
    )

    account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    binding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class AccountSession(Base):
    __tablename__ = "account_sessions"
    __table_args__ = (
        Index("idx_account_sessions_account_id", "account_id"),
        Index("idx_account_sessions_expires_at", "expires_at"),
        Index("idx_account_sessions_status", "status"),
        UniqueConstraint("session_token_hash", name="uq_account_sessions_session_token_hash"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
