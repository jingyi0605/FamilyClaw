from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.ai_gateway.schemas import (
    AiCapability,
    AiCapabilityRouteRead,
    AiCapabilityRouteUpsert,
    AiGatewayInvokeRequest,
    AiGatewayInvokeResponse,
    AiModelCallLogRead,
    AiProviderProfileCreate,
    AiProviderProfileRead,
    AiProviderProfileUpdate,
)
from app.modules.ai_gateway.gateway_service import invoke_capability
from app.modules.ai_gateway.service import (
    AiGatewayConfigurationError,
    AiGatewayNotFoundError,
    create_provider_profile,
    get_runtime_defaults,
    list_capability_routes,
    list_model_call_logs,
    list_provider_profiles,
    update_provider_profile,
    upsert_capability_route,
)
from app.modules.audit.service import write_audit_log

router = APIRouter(prefix="/ai", tags=["ai-admin"])


def _write_household_scoped_audit(
    db: Session,
    *,
    household_id: str | None,
    actor: ActorContext,
    action: str,
    target_type: str,
    target_id: str | None,
    result: str,
    details: dict[str, object],
) -> None:
    if household_id is None:
        return
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        details=details,
    )


@router.get("/runtime-defaults")
def get_ai_runtime_defaults_endpoint(
    _actor: ActorContext = Depends(require_admin_actor),
) -> dict[str, object]:
    return get_runtime_defaults()


@router.get("/providers", response_model=list[AiProviderProfileRead])
def list_ai_providers_endpoint(
    enabled: bool | None = Query(default=None),
    capability: AiCapability | None = Query(default=None),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiProviderProfileRead]:
    return list_provider_profiles(db, enabled=enabled, capability=capability)


@router.post("/providers", response_model=AiProviderProfileRead, status_code=status.HTTP_201_CREATED)
def create_ai_provider_endpoint(
    payload: AiProviderProfileCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiProviderProfileRead:
    try:
        result = create_provider_profile(db, payload)
        db.commit()
        return result
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.patch("/providers/{provider_profile_id}", response_model=AiProviderProfileRead)
def update_ai_provider_endpoint(
    provider_profile_id: str,
    payload: AiProviderProfileUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiProviderProfileRead:
    try:
        result = update_provider_profile(db, provider_profile_id, payload)
        db.commit()
        return result
    except AiGatewayNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/routes", response_model=list[AiCapabilityRouteRead])
def list_ai_routes_endpoint(
    household_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiCapabilityRouteRead]:
    return list_capability_routes(db, household_id=household_id)


@router.put("/routes/{capability}", response_model=AiCapabilityRouteRead)
def upsert_ai_route_endpoint(
    capability: AiCapability,
    payload: AiCapabilityRouteUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiCapabilityRouteRead:
    if payload.capability != capability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path capability 与 payload capability 不一致",
        )
    try:
        result = upsert_capability_route(db, payload)
        _write_household_scoped_audit(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="ai_route.upsert",
            target_type="ai_capability_route",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except AiGatewayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/call-logs", response_model=list[AiModelCallLogRead])
def list_ai_call_logs_endpoint(
    household_id: str | None = Query(default=None),
    capability: AiCapability | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[AiModelCallLogRead]:
    return list_model_call_logs(db, household_id=household_id, capability=capability, limit=limit)


@router.post("/invoke-preview", response_model=AiGatewayInvokeResponse)
def invoke_ai_preview_endpoint(
    payload: AiGatewayInvokeRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> AiGatewayInvokeResponse:
    try:
        result = invoke_capability(db, payload)
        _write_household_scoped_audit(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="ai_gateway.invoke_preview",
            target_type="ai_capability",
            target_id=payload.capability,
            result="success",
            details={
                "capability": payload.capability,
                "trace_id": result.trace_id,
                "provider_code": result.provider_code,
                "degraded": result.degraded,
            },
        )
        db.commit()
        return result
    except HTTPException:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
