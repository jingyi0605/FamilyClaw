from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, pagination_params, require_bound_member_actor
from app.db.session import get_db
from app.modules.audit.query_service import list_audit_logs
from app.modules.audit.schemas import AuditLogListResponse, AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    action: str | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> AuditLogListResponse:
    ensure_actor_can_access_household(actor, household_id)
    page, page_size = pagination
    items, total = list_audit_logs(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        action=action,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )

