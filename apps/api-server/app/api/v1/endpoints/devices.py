from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    ActorContext,
    ensure_actor_can_access_household,
    pagination_params,
    require_admin_actor,
    require_bound_member_actor,
)
from app.api.errors import translate_integrity_error
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import utc_now_iso
from app.modules.audit.service import write_audit_log
from app.modules.device.schemas import DeviceListResponse, DeviceRead, DeviceStatus, DeviceType, DeviceUpdate
from app.modules.device.service import get_device_or_404, list_devices, update_device
from app.modules.ha_integration.client import HomeAssistantClientError
from app.modules.ha_integration.schemas import (
    HomeAssistantConfigRead,
    HomeAssistantConfigUpsert,
    HomeAssistantDeviceCandidate,
    HomeAssistantDeviceCandidatesResponse,
    HomeAssistantRoomCandidate,
    HomeAssistantRoomCandidatesResponse,
    HomeAssistantRoomSyncRequest,
    HomeAssistantRoomSyncResponse,
    HomeAssistantSyncFailure,
    HomeAssistantSyncRequest,
    HomeAssistantSyncResponse,
)
from app.modules.ha_integration.service import (
    async_list_home_assistant_device_candidates,
    async_list_home_assistant_room_candidates,
    async_sync_home_assistant_devices,
    async_sync_home_assistant_rooms,
    get_home_assistant_config_view,
    list_home_assistant_device_candidates,
    list_home_assistant_room_candidates,
    sync_home_assistant_devices,
    sync_home_assistant_rooms,
    upsert_household_ha_config,
)
from app.modules.household.service import get_household_or_404
from app.modules.voice.discovery_registry import (
    VoiceTerminalBindingSnapshot,
    VoiceTerminalDiscoveryRecord,
    claim_voice_terminal_discovery,
    get_voice_terminal_binding,
    voice_terminal_discovery_registry,
)
from app.modules.voice.protocol import sanitize_terminal_capabilities

router = APIRouter(prefix="/devices", tags=["devices"])


class VoiceDiscoveryReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_type: Literal["open_xiaoai"] = "open_xiaoai"
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


class VoiceDiscoveryReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    claimed: bool
    binding: VoiceDiscoveryBindingRead | None = None
    reported_at: str


class VoiceDiscoveryListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    model: str
    sn: str
    runtime_version: str
    capabilities: list[str]
    discovered_at: str
    last_seen_at: str
    connection_status: str
    remote_addr: str | None = None


class VoiceDiscoveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    items: list[VoiceDiscoveryListItem]


class VoiceDiscoveryClaimPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    room_id: str = Field(min_length=1)
    terminal_name: str = Field(min_length=1, max_length=100)


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


def _discovery_to_list_item(record: VoiceTerminalDiscoveryRecord) -> VoiceDiscoveryListItem:
    return VoiceDiscoveryListItem(
        fingerprint=record.fingerprint,
        model=record.model,
        sn=record.sn,
        runtime_version=record.runtime_version,
        capabilities=record.capabilities,
        discovered_at=record.discovered_at,
        last_seen_at=record.last_seen_at,
        connection_status=record.connection_status,
        remote_addr=record.remote_addr,
    )


@router.post("/voice-terminals/discoveries/report", response_model=VoiceDiscoveryReportResponse)
def report_voice_terminal_discovery(
    payload: VoiceDiscoveryReportPayload,
    _gateway_auth: None = Depends(require_voice_gateway_token),
    db: Session = Depends(get_db),
) -> VoiceDiscoveryReportResponse:
    binding = get_voice_terminal_binding(db, fingerprint=payload.fingerprint)
    record = voice_terminal_discovery_registry.upsert(
        adapter_type=payload.adapter_type,
        fingerprint=payload.fingerprint,
        model=payload.model,
        sn=payload.sn,
        runtime_version=payload.runtime_version,
        capabilities=sanitize_terminal_capabilities(payload.capabilities),
        remote_addr=payload.remote_addr,
        discovered_at=payload.discovered_at,
        last_seen_at=payload.last_seen_at or utc_now_iso(),
        connection_status=payload.connection_status,
        claimed_binding=binding,
    )
    return VoiceDiscoveryReportResponse(
        fingerprint=record.fingerprint,
        claimed=binding is not None,
        binding=_binding_to_read(binding),
        reported_at=record.last_seen_at,
    )


@router.get("/voice-terminals/discoveries", response_model=VoiceDiscoveryListResponse)
def list_voice_terminal_discoveries(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> VoiceDiscoveryListResponse:
    ensure_actor_can_access_household(actor, household_id)
    get_household_or_404(db, household_id)
    records = voice_terminal_discovery_registry.list_pending()
    return VoiceDiscoveryListResponse(
        household_id=household_id,
        items=[_discovery_to_list_item(item) for item in records],
    )


@router.post(
    "/voice-terminals/discoveries/{fingerprint}/claim",
    response_model=VoiceDiscoveryBindingRead,
    status_code=status.HTTP_200_OK,
)
def claim_voice_terminal_discovery_endpoint(
    fingerprint: str,
    payload: VoiceDiscoveryClaimPayload,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> VoiceDiscoveryBindingRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    discovery = voice_terminal_discovery_registry.get(fingerprint)
    if discovery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voice discovery not found")

    binding = claim_voice_terminal_discovery(
        db,
        discovery=discovery,
        household_id=payload.household_id,
        room_id=payload.room_id,
        terminal_name=payload.terminal_name.strip(),
    )
    voice_terminal_discovery_registry.attach_binding(fingerprint=fingerprint, binding=binding)
    write_audit_log(
        db,
        household_id=payload.household_id,
        actor=actor,
        action="voice.discovery.claim",
        target_type="voice_terminal",
        target_id=binding.terminal_id,
        result="success",
        details={
            "fingerprint": fingerprint,
            "terminal_name": binding.terminal_name,
            "room_id": binding.room_id,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return VoiceDiscoveryBindingRead.model_validate(binding.model_dump(mode="json"))


@router.get("/voice-terminals/discoveries/{fingerprint}/binding", response_model=VoiceDiscoveryReportResponse)
def get_voice_terminal_discovery_binding(
    fingerprint: str,
    _gateway_auth: None = Depends(require_voice_gateway_token),
    db: Session = Depends(get_db),
) -> VoiceDiscoveryReportResponse:
    record = voice_terminal_discovery_registry.get(fingerprint)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voice discovery not found")
    binding = get_voice_terminal_binding(db, fingerprint=fingerprint)
    voice_terminal_discovery_registry.attach_binding(fingerprint=fingerprint, binding=binding)
    return VoiceDiscoveryReportResponse(
        fingerprint=fingerprint,
        claimed=binding is not None,
        binding=_binding_to_read(binding),
        reported_at=(record.last_seen_at if binding is None else utc_now_iso()),
    )


@router.get("", response_model=DeviceListResponse)
def list_devices_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    room_id: str | None = None,
    device_type: Annotated[DeviceType | None, Query()] = None,
    status_value: Annotated[DeviceStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceListResponse:
    ensure_actor_can_access_household(actor, household_id)
    page, page_size = pagination
    devices, total = list_devices(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        room_id=room_id,
        device_type=device_type,
        status_value=status_value,
    )
    return DeviceListResponse(
        items=[DeviceRead.model_validate(device) for device in devices],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device_endpoint(
    device_id: str,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> DeviceRead:
    device = get_device_or_404(db, device_id)
    device, changed_fields = update_device(db, device, payload)
    if changed_fields:
        write_audit_log(
            db,
            household_id=device.household_id,
            actor=actor,
            action="device.update",
            target_type="device",
            target_id=device.id,
            result="success",
            details={"changed_fields": changed_fields},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(device)
    return DeviceRead.model_validate(device)


@router.post("/sync/ha", response_model=HomeAssistantSyncResponse, status_code=status.HTTP_200_OK)
async def sync_home_assistant_devices_endpoint(
    payload: HomeAssistantSyncRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantSyncResponse:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        summary = await async_sync_home_assistant_devices(
            db,
            household_id=payload.household_id,
            external_device_ids=payload.external_device_ids,
        )
        audit_result = "success" if summary.failed_entities == 0 else "fail"
        write_audit_log(
            db,
            household_id=summary.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=summary.household_id,
            result=audit_result,
            details={
                "created_devices": summary.created_devices,
                "updated_devices": summary.updated_devices,
                "created_bindings": summary.created_bindings,
                "created_rooms": summary.created_rooms,
                "assigned_rooms": summary.assigned_rooms,
                "skipped_entities": summary.skipped_entities,
                "failed_entities": summary.failed_entities,
                "requested_device_ids": payload.external_device_ids,
            },
        )
        db.commit()
    except HomeAssistantClientError as exc:
        db.rollback()
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=payload.household_id,
            result="fail",
            details={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=payload.household_id,
            result="fail",
            details={"error": "database integrity error"},
        )
        db.commit()
        raise translate_integrity_error(exc) from exc

    return HomeAssistantSyncResponse(
        household_id=summary.household_id,
        created_devices=summary.created_devices,
        updated_devices=summary.updated_devices,
        created_bindings=summary.created_bindings,
        created_rooms=summary.created_rooms,
        assigned_rooms=summary.assigned_rooms,
        skipped_entities=summary.skipped_entities,
        failed_entities=summary.failed_entities,
        devices=[DeviceRead.model_validate(device) for device in summary.devices],
        failures=[
            HomeAssistantSyncFailure(entity_id=failure.entity_id, reason=failure.reason)
            for failure in summary.failures
        ],
    )


@router.get("/ha-candidates/{household_id}", response_model=HomeAssistantDeviceCandidatesResponse)
async def list_home_assistant_device_candidates_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> HomeAssistantDeviceCandidatesResponse:
    ensure_actor_can_access_household(actor, household_id)
    try:
        items = await async_list_home_assistant_device_candidates(db, household_id=household_id)
    except HomeAssistantClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return HomeAssistantDeviceCandidatesResponse(
        household_id=household_id,
        items=[
            HomeAssistantDeviceCandidate(
                external_device_id=item.external_device_id,
                primary_entity_id=item.primary_entity_id,
                name=item.name,
                room_name=item.room_name,
                device_type=item.device_type,
                entity_count=item.entity_count,
                already_synced=item.already_synced,
            )
            for item in items
        ],
    )


@router.get("/ha-config/{household_id}", response_model=HomeAssistantConfigRead)
def get_home_assistant_config_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> HomeAssistantConfigRead:
    ensure_actor_can_access_household(actor, household_id)
    return HomeAssistantConfigRead.model_validate(get_home_assistant_config_view(db, household_id))


@router.put("/ha-config/{household_id}", response_model=HomeAssistantConfigRead)
def upsert_home_assistant_config_endpoint(
    household_id: str,
    payload: HomeAssistantConfigUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantConfigRead:
    ensure_actor_can_access_household(actor, household_id)
    config = upsert_household_ha_config(
        db,
        household_id=household_id,
        base_url=payload.base_url,
        access_token=payload.access_token,
        clear_access_token=payload.clear_access_token,
        sync_rooms_enabled=payload.sync_rooms_enabled,
    )
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="device.home_assistant_config.upsert",
        target_type="home_assistant_config",
        target_id=household_id,
        result="success",
        details={
            "base_url": config.base_url,
            "token_configured": bool(config.access_token),
            "sync_rooms_enabled": config.sync_rooms_enabled,
            "clear_access_token": payload.clear_access_token,
        },
    )
    db.commit()
    return HomeAssistantConfigRead.model_validate(get_home_assistant_config_view(db, household_id))


@router.post("/rooms/sync/ha", response_model=HomeAssistantRoomSyncResponse, status_code=status.HTTP_200_OK)
async def sync_home_assistant_rooms_endpoint(
    payload: HomeAssistantRoomSyncRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantRoomSyncResponse:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        summary = await async_sync_home_assistant_rooms(
            db,
            household_id=payload.household_id,
            room_names=payload.room_names,
        )
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="room.sync.home_assistant",
            target_type="room_sync",
            target_id=payload.household_id,
            result="success",
            details={
                "created_rooms": summary.created_rooms,
                "matched_entities": summary.matched_entities,
                "skipped_entities": summary.skipped_entities,
                "requested_rooms": payload.room_names,
            },
        )
        db.commit()
    except HomeAssistantClientError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return HomeAssistantRoomSyncResponse(
        household_id=summary.household_id,
        created_rooms=summary.created_rooms,
        matched_entities=summary.matched_entities,
        skipped_entities=summary.skipped_entities,
        rooms=[{"id": room.id, "name": room.name} for room in summary.rooms],
    )


@router.get("/rooms/ha-candidates/{household_id}", response_model=HomeAssistantRoomCandidatesResponse)
async def list_home_assistant_room_candidates_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> HomeAssistantRoomCandidatesResponse:
    ensure_actor_can_access_household(actor, household_id)
    try:
        items = await async_list_home_assistant_room_candidates(db, household_id=household_id)
    except HomeAssistantClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return HomeAssistantRoomCandidatesResponse(
        household_id=household_id,
        items=[
            HomeAssistantRoomCandidate(
                name=item.name,
                entity_count=item.entity_count,
                exists_locally=item.exists_locally,
                can_sync=item.can_sync,
            )
            for item in items
        ],
    )
