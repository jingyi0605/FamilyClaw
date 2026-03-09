from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status


@dataclass(frozen=True)
class ActorContext:
    role: str
    actor_type: str
    actor_id: str | None


def get_actor_context(
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> ActorContext:
    role = (x_actor_role or "guest").lower()
    actor_type = "admin" if role == "admin" else "member"
    return ActorContext(role=role, actor_type=actor_type, actor_id=x_actor_id)


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

