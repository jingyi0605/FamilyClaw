from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import utc_now_iso
from app.modules.device_integration.service import DeviceIntegrationServiceError, mark_integration_instance_sync_failed
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
from app.modules.integration.discovery_service import upsert_open_xiaoai_discovery
from app.modules.integration.service import (
    build_integration_page_view,
    create_integration_instance,
    execute_integration_instance_action,
    list_integration_catalog,
    list_integration_instances,
    list_integration_resources,
)
from app.modules.plugin.service import PluginServiceError
from app.modules.voice.binding_service import VoiceTerminalBindingSnapshot
from app.modules.voice.protocol import sanitize_terminal_capabilities


router = APIRouter(prefix="/integrations", tags=["integrations"])


class VoiceGatewayDiscoveryReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: Literal["open-xiaoai-speaker"] = "open-xiaoai-speaker"
    gateway_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(min_length=1)
    model: str = Field(min_length=1)
    sn: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    remote_addr: str | None = None
    discovered_at: str | None = None
    last_seen_at: str | None = None
    connection_status: Literal["online", "offline", "unknown"] = "unknown"


class VoiceDiscoveryBindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    terminal_id: str
    room_id: str | None = None
    terminal_name: str
    voice_auto_takeover_enabled: bool
    voice_takeover_prefixes: list[str]
    pending_voiceprint_enrollment: dict | None = None


class VoiceGatewayDiscoveryReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway_id: str
    fingerprint: str
    claimed: bool
    binding: VoiceDiscoveryBindingRead | None = None
    reported_at: str


def require_voice_gateway_token(
    x_voice_gateway_token: Annotated[str | None, Header(alias="x-voice-gateway-token")] = None,
) -> None:
    token = (x_voice_gateway_token or "").strip()
    if token != settings.voice_gateway_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="voice gateway token invalid")


def _binding_to_read(binding: VoiceTerminalBindingSnapshot | None) -> VoiceDiscoveryBindingRead | None:
    if binding is None:
        return None
    return VoiceDiscoveryBindingRead.model_validate(binding.model_dump(mode="json"))


@router.post("/discoveries/report", response_model=VoiceGatewayDiscoveryReportResponse)
def report_open_xiaoai_discovery(
    payload: VoiceGatewayDiscoveryReportPayload,
    _gateway_auth: None = Depends(require_voice_gateway_token),
    db: Session = Depends(get_db),
) -> VoiceGatewayDiscoveryReportResponse:
    _discovery, binding = upsert_open_xiaoai_discovery(
        db,
        gateway_id=payload.gateway_id,
        fingerprint=payload.fingerprint,
        model=payload.model,
        sn=payload.sn,
        runtime_version=payload.runtime_version,
        capabilities=sanitize_terminal_capabilities(payload.capabilities),
        remote_addr=payload.remote_addr,
        discovered_at=payload.discovered_at,
        last_seen_at=payload.last_seen_at,
        connection_status=payload.connection_status,
    )
    db.commit()
    return VoiceGatewayDiscoveryReportResponse(
        gateway_id=payload.gateway_id,
        fingerprint=payload.fingerprint,
        claimed=binding is not None,
        binding=_binding_to_read(binding),
        reported_at=payload.last_seen_at or utc_now_iso(),
    )


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
        mark_integration_instance_sync_failed(
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
