import json

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import new_uuid
from app.modules.audit.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext | None,
    action: str,
    target_type: str,
    target_id: str | None,
    result: str,
    details: dict | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        id=new_uuid(),
        household_id=household_id,
        actor_type=actor.actor_type if actor else "system",
        actor_id=actor.actor_id if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )
    db.add(audit_log)
    return audit_log

