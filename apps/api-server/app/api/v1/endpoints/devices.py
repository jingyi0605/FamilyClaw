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
from app.modules.household.service import get_household_or_404
from app.modules.voice.discovery_registry import (
    VoiceTerminalBindingSnapshot,
    VoiceTerminalDiscoveryRecord,
    build_minimal_discovery,
    claim_voice_terminal_discovery,
    get_voice_terminal_binding,
    voice_terminal_discovery_registry,
)
from app.modules.voice.protocol import sanitize_terminal_capabilities
from app.modules.voiceprint.schemas import PendingVoiceprintEnrollmentRead

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
    voice_auto_takeover_enabled: bool
    voice_takeover_prefixes: list[str]
    pending_voiceprint_enrollment: PendingVoiceprintEnrollmentRead | None = None


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
    model: str | None = Field(default=None, min_length=1)
    sn: str | None = Field(default=None, min_length=1)
    connection_status: Literal["online", "offline", "unknown"] | None = None


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
    "/voice-terminals/discoveries/{fingerprint:path}/claim",
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
    if discovery is None and payload.model and payload.sn:
        discovery = build_minimal_discovery(
            fingerprint=fingerprint,
            model=payload.model,
            sn=payload.sn,
            connection_status=payload.connection_status or "unknown",
        )
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


@router.get("/voice-terminals/discoveries/{fingerprint:path}/binding", response_model=VoiceDiscoveryReportResponse)
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

