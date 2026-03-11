from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Query, status

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.account.service import AuthenticatedActor, resolve_authenticated_actor_by_session_token


@dataclass(frozen=True)
class ActorContext:
    role: str
    actor_type: str
    actor_id: str | None
    account_id: str | None = None
    account_type: str = "anonymous"
    account_status: str = "anonymous"
    username: str | None = None
    household_id: str | None = None
    member_id: str | None = None
    member_role: str | None = None
    is_authenticated: bool = False
    must_change_password: bool = False

    @classmethod
    def from_authenticated_actor(cls, actor: AuthenticatedActor) -> "ActorContext":
        return cls(
            role=actor.role,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            account_id=actor.account_id,
            account_type=actor.account_type,
            account_status=actor.account_status,
            username=actor.username,
            household_id=actor.household_id,
            member_id=actor.member_id,
            member_role=actor.member_role,
            is_authenticated=True,
            must_change_password=actor.must_change_password,
        )


def get_actor_context(
    db: Annotated[Session, Depends(get_db)],
    session_token: Annotated[str | None, Cookie(alias=settings.auth_session_cookie_name)] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> ActorContext:
    authenticated_actor = resolve_authenticated_actor_by_session_token(db, session_token)
    if authenticated_actor is not None:
        return ActorContext.from_authenticated_actor(authenticated_actor)

    if settings.auth_legacy_header_enabled:
        role = (x_actor_role or "guest").lower()
        actor_type = "admin" if role == "admin" else "member"
        return ActorContext(role=role, actor_type=actor_type, actor_id=x_actor_id)

    role = (x_actor_role or "guest").lower()
    return ActorContext(role=role, actor_type="anonymous", actor_id=None)


def require_authenticated_actor(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> ActorContext:
    if not actor.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return actor


def require_bound_member_actor(
    actor: Annotated[ActorContext, Depends(require_authenticated_actor)],
) -> ActorContext:
    if actor.account_type != "system" and actor.member_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member binding required",
        )
    return actor


def ensure_actor_can_access_household(actor: ActorContext, household_id: str) -> None:
    if actor.account_type == "system":
        return
    if not actor.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    if actor.household_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="household access denied",
        )
    if actor.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot access another household",
        )


def require_admin_actor(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> ActorContext:
    if actor.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return actor


def pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> tuple[int, int]:
    return page, page_size

