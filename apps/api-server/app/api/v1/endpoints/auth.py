from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_authenticated_actor
from app.db.session import get_db
from app.modules.account.schemas import (
    AuthActorSummary,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthLogoutResponse,
    BootstrapAccountCompleteRequest,
)
from app.modules.account.service import (
    AuthenticatedActor,
    authenticate_account,
    build_authenticated_actor,
    complete_bootstrap_account,
    create_account_session,
    revoke_session_by_token,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_authenticated_actor(actor: ActorContext) -> AuthenticatedActor:
    return AuthenticatedActor(
        account_id=actor.account_id or "",
        username=actor.username or "",
        account_type=actor.account_type,
        account_status=actor.account_status,
        household_id=actor.household_id,
        member_id=actor.member_id,
        member_role=actor.member_role,
        must_change_password=actor.must_change_password,
    )


def _build_actor_summary(actor: ActorContext) -> AuthActorSummary:
    return AuthActorSummary(
        account_id=actor.account_id or "",
        username=actor.username or actor.actor_type,
        account_type=actor.account_type,
        account_status=actor.account_status,
        household_id=actor.household_id,
        member_id=actor.member_id,
        member_role=actor.member_role,
        role=actor.role,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        must_change_password=actor.must_change_password,
        authenticated=actor.is_authenticated,
    )


@router.post("/login", response_model=AuthLoginResponse)
def login_endpoint(
    payload: AuthLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthLoginResponse:
    actor = authenticate_account(db, payload.username, payload.password)
    _, session_token = create_account_session(db, actor.account_id)
    db.commit()

    expires = datetime.now(timezone.utc) + timedelta(hours=settings.auth_session_ttl_hours)
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        expires=expires,
    )
    return AuthLoginResponse(actor=_build_actor_summary(ActorContext.from_authenticated_actor(actor)))


@router.get("/me", response_model=AuthLoginResponse)
def me_endpoint(actor: ActorContext = Depends(require_authenticated_actor)) -> AuthLoginResponse:
    return AuthLoginResponse(actor=_build_actor_summary(actor))


@router.post("/logout", response_model=AuthLogoutResponse)
def logout_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_authenticated_actor),
) -> AuthLogoutResponse:
    session_token = request.cookies.get(settings.auth_session_cookie_name)
    revoke_session_by_token(db, session_token)
    response.delete_cookie(settings.auth_session_cookie_name)
    return AuthLogoutResponse()


@router.post("/bootstrap/complete", response_model=AuthLoginResponse)
def complete_bootstrap_endpoint(
    payload: BootstrapAccountCompleteRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_authenticated_actor),
) -> AuthLoginResponse:
    account = complete_bootstrap_account(
        db,
        actor=_to_authenticated_actor(actor),
        payload=payload,
    )
    previous_session_token = request.cookies.get(settings.auth_session_cookie_name)
    revoke_session_by_token(db, previous_session_token)
    _, session_token = create_account_session(db, account.id)
    db.commit()
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return AuthLoginResponse(actor=_build_actor_summary(ActorContext.from_authenticated_actor(build_authenticated_actor(db, account))))
