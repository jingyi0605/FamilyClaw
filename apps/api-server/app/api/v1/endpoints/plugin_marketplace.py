from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.plugin import PluginServiceError, set_household_plugin_enabled
from app.modules.plugin.schemas import PluginStateUpdateRequest, PluginVersionGovernanceRead
from app.modules.plugin_marketplace import (
    MarketplaceCatalogListRead,
    MarketplaceEntryDetailRead,
    MarketplaceInstallTaskCreateRequest,
    MarketplaceInstallTaskRead,
    MarketplaceInstanceRead,
    MarketplaceSourceCreateRequest,
    MarketplaceSourceRead,
    MarketplaceSourceSyncResultRead,
    PluginVersionOperationRequest,
    PluginVersionOperationResultRead,
    PluginMarketplaceServiceError,
    add_marketplace_source,
    create_marketplace_install_task,
    get_marketplace_entry_detail,
    get_marketplace_instance,
    get_marketplace_version_governance,
    list_marketplace_catalog,
    list_marketplace_sources,
    operate_marketplace_instance_version,
    sync_marketplace_source,
)


router = APIRouter(prefix="/plugin-marketplace", tags=["plugin-marketplace"])


@router.get("/sources", response_model=list[MarketplaceSourceRead])
def list_marketplace_sources_endpoint(
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[MarketplaceSourceRead]:
    return list_marketplace_sources(db)


@router.post("/sources", response_model=MarketplaceSourceRead)
def add_marketplace_source_endpoint(
    payload: MarketplaceSourceCreateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceSourceRead:
    try:
        result = add_marketplace_source(db, payload=payload)
        write_audit_log(
            db,
            household_id=actor.household_id,
            actor=actor,
            action="marketplace.source.create",
            target_type="marketplace_source",
            target_id=result.source_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except PluginMarketplaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/sources/{source_id}/sync", response_model=MarketplaceSourceSyncResultRead)
def sync_marketplace_source_endpoint(
    source_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceSourceSyncResultRead:
    try:
        result = sync_marketplace_source(db, source_id=source_id)
        write_audit_log(
            db,
            household_id=actor.household_id,
            actor=actor,
            action="marketplace.source.sync",
            target_type="marketplace_source",
            target_id=source_id,
            result="success",
            details={"source_id": source_id},
        )
        db.commit()
        return result
    except PluginMarketplaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.get("/catalog", response_model=MarketplaceCatalogListRead)
def list_marketplace_catalog_endpoint(
    household_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceCatalogListRead:
    if household_id is not None:
        ensure_actor_can_access_household(actor, household_id)
    return list_marketplace_catalog(db, household_id=household_id)


@router.get("/catalog/{source_id}/{plugin_id}", response_model=MarketplaceEntryDetailRead)
def get_marketplace_entry_detail_endpoint(
    source_id: str,
    plugin_id: str,
    household_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceEntryDetailRead:
    if household_id is not None:
        ensure_actor_can_access_household(actor, household_id)
    try:
        return get_marketplace_entry_detail(
            db,
            source_id=source_id,
            plugin_id=plugin_id,
            household_id=household_id,
        )
    except PluginMarketplaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.get("/catalog/{source_id}/{plugin_id}/version-governance", response_model=PluginVersionGovernanceRead)
def get_marketplace_version_governance_endpoint(
    source_id: str,
    plugin_id: str,
    household_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
):
    if household_id is not None:
        ensure_actor_can_access_household(actor, household_id)
    try:
        return get_marketplace_version_governance(
            db,
            source_id=source_id,
            plugin_id=plugin_id,
            household_id=household_id,
        )
    except PluginMarketplaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.post("/install-tasks", response_model=MarketplaceInstallTaskRead)
def create_marketplace_install_task_endpoint(
    payload: MarketplaceInstallTaskCreateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceInstallTaskRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = create_marketplace_install_task(db, payload=payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="marketplace.install.create",
            target_type="marketplace_install_task",
            target_id=result.task_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except PluginMarketplaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/instances/{instance_id}", response_model=MarketplaceInstanceRead)
def get_marketplace_instance_endpoint(
    instance_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceInstanceRead:
    try:
        result = get_marketplace_instance(db, instance_id=instance_id)
        ensure_actor_can_access_household(actor, result.household_id)
        return result
    except PluginMarketplaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.post("/instances/{instance_id}/enable", response_model=MarketplaceInstanceRead)
def enable_marketplace_instance_endpoint(
    instance_id: str,
    payload: PluginStateUpdateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MarketplaceInstanceRead:
    try:
        instance = get_marketplace_instance(db, instance_id=instance_id)
        ensure_actor_can_access_household(actor, instance.household_id)
        set_household_plugin_enabled(
            db,
            household_id=instance.household_id,
            plugin_id=instance.plugin_id,
            payload=payload,
            updated_by=actor.actor_id,
        )
        result = get_marketplace_instance(db, instance_id=instance_id)
        write_audit_log(
            db,
            household_id=instance.household_id,
            actor=actor,
            action="marketplace.instance.enable",
            target_type="marketplace_instance",
            target_id=instance_id,
            result="success",
            details={"plugin_id": instance.plugin_id, **payload.model_dump(mode="json")},
        )
        db.commit()
        return result
    except PluginServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except PluginMarketplaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


@router.post("/instances/{instance_id}/version-operations", response_model=PluginVersionOperationResultRead)
def operate_marketplace_instance_version_endpoint(
    instance_id: str,
    payload: PluginVersionOperationRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> PluginVersionOperationResultRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = operate_marketplace_instance_version(db, instance_id=instance_id, payload=payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action=f"marketplace.instance.version_{payload.operation}",
            target_type="marketplace_instance",
            target_id=instance_id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except PluginMarketplaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
