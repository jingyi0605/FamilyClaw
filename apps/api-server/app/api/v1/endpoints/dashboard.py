from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.plugin import (
    HomeDashboardRead,
    MemberDashboardLayoutRead,
    MemberDashboardLayoutUpdateRequest,
    PluginServiceError,
    get_home_dashboard,
    get_member_dashboard_layout_read,
    save_member_dashboard_layout,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/home", response_model=HomeDashboardRead)
def get_home_dashboard_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> HomeDashboardRead:
    ensure_actor_can_access_household(actor, household_id)
    if actor.member_id is None:
        raise HTTPException(status_code=400, detail="当前账号未绑定成员，无法读取首页仪表盘")
    try:
        return get_home_dashboard(db, household_id=household_id, member_id=actor.member_id)
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.put("/home/layout", response_model=MemberDashboardLayoutRead)
def save_home_dashboard_layout_endpoint(
    household_id: str,
    payload: MemberDashboardLayoutUpdateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberDashboardLayoutRead:
    ensure_actor_can_access_household(actor, household_id)
    if actor.member_id is None:
        raise HTTPException(status_code=400, detail="当前账号未绑定成员，无法保存首页布局")
    try:
        result = save_member_dashboard_layout(
            db,
            household_id=household_id,
            member_id=actor.member_id,
            payload=payload,
        )
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="dashboard.home.layout.save",
            target_type="member_dashboard_layout",
            target_id=actor.member_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except PluginServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/home/layout", response_model=MemberDashboardLayoutRead)
def get_home_dashboard_layout_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberDashboardLayoutRead:
    ensure_actor_can_access_household(actor, household_id)
    if actor.member_id is None:
        raise HTTPException(status_code=400, detail="当前账号未绑定成员，无法读取首页布局")
    try:
        return get_member_dashboard_layout_read(db, member_id=actor.member_id)
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
