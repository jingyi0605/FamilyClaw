from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.device_integration.service import DeviceIntegrationServiceError
from app.modules.integration import (
    IntegrationActionResultRead,
    IntegrationCatalogListRead,
    IntegrationInstanceActionRequest,
    IntegrationInstanceCreateRequest,
    IntegrationInstanceListRead,
    IntegrationInstanceRead,
    IntegrationPageViewRead,
    IntegrationResourceListRead,
)
from app.modules.integration.service import (
    build_integration_page_view,
    create_integration_instance,
    execute_integration_instance_action,
    list_integration_catalog,
    list_integration_instances,
    list_integration_resources,
)
from app.modules.plugin.service import PluginServiceError
from app.plugins.builtin.homeassistant_device_action.runtime import mark_home_assistant_instance_sync_failed


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/catalog", response_model=IntegrationCatalogListRead)
def list_integration_catalog_endpoint(
    household_id: str,
    q: str | None = Query(default=None),
    resource_type: Literal["device", "entity", "helper"] | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> IntegrationCatalogListRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return list_integration_catalog(
            db,
            household_id=household_id,
            search=q,
            resource_type=resource_type,  # type: ignore[arg-type]
        )
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.get("/instances", response_model=IntegrationInstanceListRead)
def list_integration_instances_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> IntegrationInstanceListRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return list_integration_instances(db, household_id=household_id)
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.get("/resources", response_model=IntegrationResourceListRead)
def list_integration_resources_endpoint(
    household_id: str,
    resource_type: Literal["device", "entity", "helper"] = Query(...),
    integration_instance_id: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> IntegrationResourceListRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return list_integration_resources(
            db,
            household_id=household_id,
            resource_type=resource_type,  # type: ignore[arg-type]
            integration_instance_id=integration_instance_id,
            room_id=room_id,
            status=status_value,
        )
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.get("/page-view", response_model=IntegrationPageViewRead)
def get_integration_page_view_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> IntegrationPageViewRead:
    ensure_actor_can_access_household(actor, household_id)
    try:
        return build_integration_page_view(db, household_id=household_id)
    except PluginServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.post("/instances", response_model=IntegrationInstanceRead, status_code=status.HTTP_201_CREATED)
def create_integration_instance_endpoint(
    payload: IntegrationInstanceCreateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> IntegrationInstanceRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = create_integration_instance(db, payload=payload, updated_by=actor.actor_id)
        db.commit()
        return result
    except PluginServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/instances/{instance_id}/actions", response_model=IntegrationActionResultRead)
async def execute_integration_instance_action_endpoint(
    instance_id: str,
    payload: IntegrationInstanceActionRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> IntegrationActionResultRead:
    try:
        result = await execute_integration_instance_action(
            db,
            instance_id=instance_id,
            payload=payload,
            updated_by=actor.actor_id,
        )
        db.commit()
        return result
    except DeviceIntegrationServiceError as exc:
        db.rollback()
        mark_home_assistant_instance_sync_failed(
            db,
            integration_instance_id=instance_id,
            error_code=exc.error_code,
            error_message=exc.message,
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except PluginServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
