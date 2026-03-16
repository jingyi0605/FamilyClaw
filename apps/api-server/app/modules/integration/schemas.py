from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.plugin.schemas import PluginConfigScopeType, PluginConfigState, PluginManifestConfigSpec, PluginSourceType, RiskLevel

IntegrationResourceType = Literal["device", "entity", "helper"]
IntegrationInstanceStatus = Literal["draft", "active", "degraded", "disabled", "deleted"]
IntegrationResourceStatus = Literal["active", "offline", "inactive", "degraded", "disabled", "deleted", "pending"]
IntegrationActionType = Literal["configure", "sync", "repair", "enable", "disable", "delete", "claim"]
IntegrationDiscoveryStatus = Literal["pending", "claimed", "dismissed"]


class IntegrationResourceSupportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: bool = False
    entity: bool = False
    helper: bool = False


class IntegrationSyncStateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_synced_at: str | None = None
    last_job_id: str | None = None
    last_job_status: str | None = None
    pending_job_id: str | None = None


class IntegrationErrorSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: str | None = None
    occurred_at: str | None = None


class IntegrationActionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: IntegrationActionType
    label: str
    destructive: bool = False
    disabled: bool = False
    disabled_reason: str | None = None


class IntegrationResourceCountsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: int = Field(default=0, ge=0)
    entity: int = Field(default=0, ge=0)
    helper: int = Field(default=0, ge=0)


class IntegrationConfigBindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: PluginConfigScopeType
    scope_key: str
    state: PluginConfigState
    form_available: bool = True
    config_spec: PluginManifestConfigSpec | None = None


class IntegrationCatalogItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    name: str
    description: str | None = None
    icon_url: str | None = None
    source_type: PluginSourceType
    risk_level: RiskLevel
    resource_support: IntegrationResourceSupportRead = Field(default_factory=IntegrationResourceSupportRead)
    config_schema_available: bool = False
    already_added: bool = False
    supported_actions: list[IntegrationActionType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class IntegrationInstanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    household_id: str
    plugin_id: str
    display_name: str
    description: str | None = None
    icon_url: str | None = None
    source_type: PluginSourceType
    status: IntegrationInstanceStatus
    config_state: PluginConfigState
    resource_support: IntegrationResourceSupportRead = Field(default_factory=IntegrationResourceSupportRead)
    resource_counts: IntegrationResourceCountsRead = Field(default_factory=IntegrationResourceCountsRead)
    sync_state: IntegrationSyncStateRead = Field(default_factory=IntegrationSyncStateRead)
    config_bindings: list[IntegrationConfigBindingRead] = Field(default_factory=list)
    allowed_actions: list[IntegrationActionRead] = Field(default_factory=list)
    last_error: IntegrationErrorSummaryRead | None = None
    created_at: str
    updated_at: str


class IntegrationResourceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    household_id: str
    integration_instance_id: str
    plugin_id: str
    resource_type: IntegrationResourceType
    resource_key: str
    name: str
    description: str | None = None
    category: str | None = None
    status: IntegrationResourceStatus
    room_id: str | None = None
    room_name: str | None = None
    device_id: str | None = None
    parent_resource_id: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_error: IntegrationErrorSummaryRead | None = None
    updated_at: str


class IntegrationDiscoveryItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    household_id: str
    plugin_id: str
    integration_instance_id: str | None = None
    discovery_type: str
    status: IntegrationDiscoveryStatus = "pending"
    title: str
    subtitle: str | None = None
    resource_type: IntegrationResourceType = "device"
    suggested_room_id: str | None = None
    capability_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    discovered_at: str
    updated_at: str


class IntegrationCatalogListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    items: list[IntegrationCatalogItemRead] = Field(default_factory=list)


class IntegrationInstanceListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    items: list[IntegrationInstanceRead] = Field(default_factory=list)


class IntegrationResourceListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    resource_type: IntegrationResourceType
    items: list[IntegrationResourceRead] = Field(default_factory=list)


class IntegrationDiscoveryListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    items: list[IntegrationDiscoveryItemRead] = Field(default_factory=list)


class IntegrationPageViewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str
    catalog: list[IntegrationCatalogItemRead] = Field(default_factory=list)
    instances: list[IntegrationInstanceRead] = Field(default_factory=list)
    discoveries: list[IntegrationDiscoveryItemRead] = Field(default_factory=list)
    resources: dict[IntegrationResourceType, list[IntegrationResourceRead]] = Field(
        default_factory=lambda: {"device": [], "entity": [], "helper": []}
    )


class IntegrationInstanceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    scope_type: PluginConfigScopeType = "plugin"
    scope_key: str = Field(default="default", min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)
    clear_secret_fields: list[str] = Field(default_factory=list)


class IntegrationInstanceActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: IntegrationActionType
    payload: dict[str, Any] = Field(default_factory=dict)


class IntegrationResourceListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    resource_type: IntegrationResourceType
    integration_instance_id: str | None = None
    room_id: str | None = None
    status: IntegrationResourceStatus | None = None
