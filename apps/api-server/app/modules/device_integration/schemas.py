from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IntegrationSyncScope = Literal["device_candidates", "device_sync", "room_candidates", "room_sync"]


class IntegrationSyncPluginPayload(BaseModel):
    schema_version: str = "integration-sync-request.v1"
    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    integration_instance_id: str = Field(min_length=1)
    sync_scope: IntegrationSyncScope
    selected_external_ids: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    system_context: dict[str, Any] | None = None


class DeviceCandidateItem(BaseModel):
    external_device_id: str = Field(min_length=1)
    primary_entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    room_name: str | None = None
    device_type: str = Field(min_length=1)
    entity_count: int = Field(ge=1)


class RoomCandidateItem(BaseModel):
    name: str = Field(min_length=1)
    entity_count: int = Field(ge=0)


class DeviceSyncItem(BaseModel):
    external_device_id: str = Field(min_length=1)
    primary_entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    room_name: str | None = None
    device_type: str = Field(min_length=1)
    entity_count: int = Field(ge=1)
    controllable: bool
    status: str = Field(min_length=1)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class RoomSyncItem(BaseModel):
    name: str = Field(min_length=1)
    entity_count: int = Field(ge=0)


class DeviceIntegrationFailureItem(BaseModel):
    external_ref: str | None = None
    reason: str = Field(min_length=1)


class IntegrationSyncPluginResult(BaseModel):
    schema_version: str = "integration-sync-result.v1"
    plugin_id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    device_candidates: list[DeviceCandidateItem] = Field(default_factory=list)
    room_candidates: list[RoomCandidateItem] = Field(default_factory=list)
    devices: list[DeviceSyncItem] = Field(default_factory=list)
    rooms: list[RoomSyncItem] = Field(default_factory=list)
    failures: list[DeviceIntegrationFailureItem] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)
