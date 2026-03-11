from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.account.models import Account, AccountMemberBinding, AccountSession
from app.modules.account.schemas import BootstrapAccountCompleteRequest, HouseholdAccountCreateRequest
from app.modules.household.models import Household
from app.modules.member.models import Member

_PASSWORD_ITERATIONS = 120_000
_PASSWORD_SCHEME = "pbkdf2_sha256"


@dataclass(frozen=True)
class AuthenticatedActor:
    account_id: str
    username: str
    account_type: str
    account_status: str
    household_id: str | None
    member_id: str | None
    member_role: str | None
    must_change_password: bool

    @property
    def role(self) -> str:
        if self.account_type in {"system", "bootstrap"}:
            return "admin"
        return self.member_role or "guest"

    @property
    def actor_type(self) -> str:
        if self.account_type == "system":
            return "admin"
        if self.account_type == "bootstrap":
            return "bootstrap"
        if self.member_id is not None:
            return "member"
        return "account"

    @property
    def actor_id(self) -> str | None:
        if self.member_id is not None:
            return self.member_id
        if self.account_type in {"system", "bootstrap"}:
            return self.account_id
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PASSWORD_ITERATIONS,
    ).hex()
    return f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iteration_text, salt, expected_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != _PASSWORD_SCHEME:
        return False

    try:
        iterations = int(iteration_text)
    except ValueError:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def get_account_by_username(db: Session, username: str) -> Account | None:
    normalized_username = username.strip()
    if not normalized_username:
        return None
    return db.scalar(select(Account).where(Account.username == normalized_username))


def get_session_by_token(db: Session, token: str) -> AccountSession | None:
    if not token:
        return None
    token_hash = _hash_session_token(token)
    return db.scalar(select(AccountSession).where(AccountSession.session_token_hash == token_hash))


def build_authenticated_actor(db: Session, account: Account) -> AuthenticatedActor:
    binding = db.scalar(
        select(AccountMemberBinding).where(
            AccountMemberBinding.account_id == account.id,
            AccountMemberBinding.binding_status == "active",
        )
    )
    member_id: str | None = None
    member_role: str | None = None
    household_id = account.household_id

    if binding is not None:
        member = db.get(Member, binding.member_id)
        if member is not None:
            member_id = member.id
            member_role = member.role
            household_id = member.household_id

    return AuthenticatedActor(
        account_id=account.id,
        username=account.username,
        account_type=account.account_type,
        account_status=account.status,
        household_id=household_id,
        member_id=member_id,
        member_role=member_role,
        must_change_password=account.must_change_password,
    )


def authenticate_account(db: Session, username: str, password: str) -> AuthenticatedActor:
    account = get_account_by_username(db, username)
    if account is None or not verify_password(password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

    if account.status == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account disabled")
    if account.status == "locked":
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="account locked")

    return build_authenticated_actor(db, account)


def create_account_session(db: Session, account_id: str) -> tuple[AccountSession, str]:
    token = secrets.token_urlsafe(32)
    expires_at = (_utc_now() + timedelta(hours=settings.auth_session_ttl_hours)).replace(microsecond=0)
    session = AccountSession(
        id=new_uuid(),
        account_id=account_id,
        session_token_hash=_hash_session_token(token),
        status="active",
        expires_at=expires_at.isoformat().replace("+00:00", "Z"),
        last_seen_at=utc_now_iso(),
    )
    db.add(session)
    return session, token


def resolve_authenticated_actor_by_session_token(db: Session, token: str | None) -> AuthenticatedActor | None:
    if not token:
        return None

    session = get_session_by_token(db, token)
    if session is None or session.status != "active":
        return None

    try:
        expires_at = datetime.fromisoformat(session.expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None

    if expires_at <= _utc_now():
        session.status = "expired"
        db.add(session)
        db.commit()
        return None

    account = db.get(Account, session.account_id)
    if account is None or account.status != "active":
        return None

    session.last_seen_at = utc_now_iso()
    db.add(session)
    db.commit()
    db.refresh(session)
    return build_authenticated_actor(db, account)


def revoke_session_by_token(db: Session, token: str | None) -> bool:
    if not token:
        return False
    session = get_session_by_token(db, token)
    if session is None:
        return False
    if session.status != "revoked":
        session.status = "revoked"
        db.add(session)
        db.commit()
    return True


def ensure_bootstrap_admin_account(db: Session) -> None:
    username = settings.bootstrap_admin_username
    password = settings.bootstrap_admin_password
    if not username or not password:
        return

    account = get_account_by_username(db, username)
    if account is not None:
        return

    db.add(
        Account(
            id=new_uuid(),
            username=username,
            password_hash=hash_password(password),
            account_type="system",
            status="active",
            household_id=None,
            must_change_password=False,
        )
    )
    db.commit()


def ensure_household_bootstrap_account(db: Session, household_id: str) -> Account | None:
    username = settings.bootstrap_household_username.strip()
    password = settings.bootstrap_household_password
    if not username or not password:
        return None

    existing_for_household = db.scalar(
        select(Account).where(
            Account.household_id == household_id,
            Account.account_type == "bootstrap",
        )
    )
    if existing_for_household is not None:
        if existing_for_household.status != "active":
            existing_for_household.status = "active"
            existing_for_household.must_change_password = True
            existing_for_household.password_hash = hash_password(password)
            db.add(existing_for_household)
        return existing_for_household

    username_owner = get_account_by_username(db, username)
    if username_owner is not None:
        return None

    account = Account(
        id=new_uuid(),
        username=username,
        password_hash=hash_password(password),
        account_type="bootstrap",
        status="active",
        household_id=household_id,
        must_change_password=True,
    )
    db.add(account)
    return account


def ensure_pending_household_bootstrap_accounts(db: Session) -> None:
    pending_households = list(
        db.scalars(
            select(Household).where(Household.setup_status.in_(["pending", "in_progress"]))
        ).all()
    )
    changed = False
    for household in pending_households:
        account = ensure_household_bootstrap_account(db, household.id)
        if account is not None:
            changed = True
    if changed:
        db.commit()


def create_household_account_with_binding(
    db: Session,
    payload: HouseholdAccountCreateRequest,
) -> tuple[Account, AccountMemberBinding]:
    household = db.get(Household, payload.household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")

    member = db.get(Member, payload.member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

    if member.household_id != payload.household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member must belong to the target household",
        )

    if member.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member must be active before binding account",
        )

    existing_account = get_account_by_username(db, payload.username)
    if existing_account is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

    existing_binding = db.scalar(
        select(AccountMemberBinding).where(
            AccountMemberBinding.member_id == payload.member_id,
            AccountMemberBinding.binding_status == "active",
        )
    )
    if existing_binding is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="member already bound to account")

    account = Account(
        id=new_uuid(),
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        account_type="household",
        status="active",
        household_id=payload.household_id,
        must_change_password=payload.must_change_password,
    )
    binding = AccountMemberBinding(
        account_id=account.id,
        member_id=member.id,
        household_id=payload.household_id,
        binding_status="active",
    )
    db.add(account)
    db.add(binding)
    return account, binding


def _get_active_binding_for_account(db: Session, account_id: str) -> AccountMemberBinding | None:
    return db.scalar(
        select(AccountMemberBinding).where(
            AccountMemberBinding.account_id == account_id,
            AccountMemberBinding.binding_status == "active",
        )
    )


def revoke_sessions_for_account(db: Session, account_id: str) -> None:
    sessions = list(
        db.scalars(select(AccountSession).where(AccountSession.account_id == account_id)).all()
    )
    for session in sessions:
        if session.status == "active":
            session.status = "revoked"
            db.add(session)


def complete_bootstrap_account(
    db: Session,
    *,
    actor: AuthenticatedActor,
    payload: BootstrapAccountCompleteRequest,
) -> Account:
    household = db.get(Household, payload.household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")

    member = db.get(Member, payload.member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    if member.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="member must belong to the target household")

    if actor.account_type == "bootstrap":
        if actor.household_id != payload.household_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bootstrap account cannot finish another household")
        bootstrap_account = db.get(Account, actor.account_id)
    else:
        bootstrap_account = db.scalar(
            select(Account).where(
                Account.household_id == payload.household_id,
                Account.account_type == "bootstrap",
                Account.status == "active",
            )
        )

    normalized_username = payload.username.strip()
    if not normalized_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username cannot be empty")

    username_owner = get_account_by_username(db, normalized_username)
    if username_owner is not None and username_owner.id not in {actor.account_id, bootstrap_account.id if bootstrap_account else None}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

    active_binding = db.scalar(
        select(AccountMemberBinding).where(
            AccountMemberBinding.member_id == payload.member_id,
            AccountMemberBinding.binding_status == "active",
        )
    )
    if active_binding is not None and active_binding.account_id not in {bootstrap_account.id if bootstrap_account else None}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="member already bound to account")

    if bootstrap_account is not None:
        bootstrap_account.username = normalized_username
        bootstrap_account.password_hash = hash_password(payload.password)
        bootstrap_account.account_type = "household"
        bootstrap_account.status = "active"
        bootstrap_account.must_change_password = False
        bootstrap_account.household_id = payload.household_id
        db.add(bootstrap_account)

        binding = active_binding or _get_active_binding_for_account(db, bootstrap_account.id)
        if binding is None:
            binding = AccountMemberBinding(
                account_id=bootstrap_account.id,
                member_id=payload.member_id,
                household_id=payload.household_id,
                binding_status="active",
            )
        else:
            binding.member_id = payload.member_id
            binding.household_id = payload.household_id
            binding.binding_status = "active"
        db.add(binding)
        return bootstrap_account

    account, _binding = create_household_account_with_binding(
        db,
        HouseholdAccountCreateRequest(
            household_id=payload.household_id,
            member_id=payload.member_id,
            username=normalized_username,
            password=payload.password,
            must_change_password=False,
        ),
    )
    return account
