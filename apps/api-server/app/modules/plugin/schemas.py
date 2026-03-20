from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PluginType = Literal[
    "integration",
    "action",
    "agent-skill",
    "channel",
    "region-provider",
    "memory_engine",
    "memory_provider",
    "context_engine",
]
PluginManifestType = Literal[
    "integration",
    "action",
    "agent-skill",
    "channel",
    "locale-pack",
    "region-provider",
    "theme-pack",
    "ai-provider",
    "memory_engine",
    "memory_provider",
    "context_engine",
]
RiskLevel = Literal["low", "medium", "high"]
PluginSourceType = Literal["builtin", "third_party"]
PluginInstallMethod = Literal["local", "marketplace"]
PluginVersionGovernanceSourceType = Literal["builtin", "marketplace", "local"]
PluginVersionCompatibilityStatus = Literal["compatible", "host_too_old", "unknown"]
PluginVersionUpdateState = Literal[
    "up_to_date",
    "upgrade_available",
    "upgrade_blocked",
    "installed_newer_than_market",
    "not_market_managed",
    "unknown",
]
PluginExecutionBackend = Literal["in_process", "subprocess_runner"]
PluginJobStatus = Literal[
    "queued",
    "running",
    "retry_waiting",
    "waiting_response",
    "succeeded",
    "failed",
    "cancelled",
]
PluginJobAttemptStatus = Literal["running", "succeeded", "failed", "timed_out"]
PluginJobNotificationType = Literal["state_changed", "failed", "waiting_response", "recovered"]
PluginJobNotificationChannel = Literal["websocket", "in_app"]
PluginJobResponseAction = Literal["retry", "confirm", "cancel", "provide_input"]
PluginJobActorType = Literal["member", "admin", "system"]
PluginConfigScopeType = Literal["plugin", "integration_instance", "channel_account", "device"]
PluginConfigFieldType = Literal["string", "text", "integer", "number", "boolean", "enum", "multi_enum", "secret", "json"]
PluginConfigWidgetType = Literal["input", "password", "textarea", "switch", "select", "multi_select", "json_editor"]
PluginConfigVisibilityOperator = Literal["equals", "not_equals", "in", "truthy"]
PluginConfigDynamicOptionSourceType = Literal["region_provider_list", "region_catalog_children"]
RegionCatalogAdminLevel = Literal["province", "city", "district"]
PluginDashboardCardPlacement = Literal["home"]
PluginDashboardCardTemplateType = Literal["metric", "status_list", "timeline", "insight", "action_group"]
PluginDashboardCardSize = Literal["half", "full"]
PluginDashboardCardHeight = Literal["compact", "regular", "tall"]
PluginDashboardCardRefreshStrategy = Literal["manual", "scheduled", "event_driven"]
PluginDashboardCardActionType = Literal["navigate", "open_plugin_detail", "trigger_plugin_action"]
PluginDashboardCardSnapshotState = Literal["ready", "stale", "invalid", "error"]
HomeDashboardCardState = Literal["ready", "empty", "stale", "error"]
HomeDashboardCardTone = Literal["neutral", "info", "success", "warning", "danger"]
HomeDashboardCardTrendDirection = Literal["up", "down", "flat"]

DASHBOARD_CARD_LIST_TEMPLATE_TYPES = {"status_list", "timeline", "action_group"}
DASHBOARD_CARD_KEY_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")

ENTRYPOINT_KEY_BY_TYPE: dict[PluginType, str] = {
    "integration": "integration",
    "action": "action",
    "agent-skill": "agent_skill",
    "channel": "channel",
    "region-provider": "region_provider",
    "memory_engine": "memory_engine",
    "memory_provider": "memory_provider",
    "context_engine": "context_engine",
}
NON_EXECUTABLE_PLUGIN_TYPES = {"locale-pack", "theme-pack", "ai-provider"}


def _normalize_plugin_source_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized == "official":
        return "third_party"
    return normalized


def _normalize_plugin_install_method(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized == "manual":
        return "local"
    return normalized


def _normalize_text_list(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = value.strip()
        if not item:
            raise ValueError(f"{field_name} 里不能有空字符串")
        if item in seen:
            raise ValueError(f"{field_name} 里不能有重复值: {item}")
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_i18n_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("i18n key 不能为空")
    return normalized


class PluginManifestEntrypoints(BaseModel):
    integration: str | None = None
    action: str | None = None
    agent_skill: str | None = None
    channel: str | None = None
    region_provider: str | None = None
    ai_provider: str | None = None
    memory_engine: str | None = None
    memory_provider: str | None = None
    context_engine: str | None = None

    @field_validator(
        "integration",
        "action",
        "agent_skill",
        "channel",
        "region_provider",
        "ai_provider",
        "memory_engine",
        "memory_provider",
        "context_engine",
    )
    @classmethod
    def validate_entrypoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("entrypoint 不能为空字符串")
        if "." not in normalized:
            raise ValueError("entrypoint 必须是模块路径加函数名")
        return normalized


class PluginManifestContextReads(BaseModel):
    household_region_context: bool = False


class PluginManifestRegionProviderSpec(BaseModel):
    provider_code: str | None = None
    country_codes: list[str] = Field(default_factory=list)
    entrypoint: str | None = None
    reserved: bool = True

    @field_validator("provider_code", "entrypoint")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空字符串")
        return normalized

    @field_validator("country_codes")
    @classmethod
    def validate_country_codes(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="country_codes")


class PluginManifestThemePackSpec(BaseModel):
    theme_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    tokens_resource: str | None = Field(default=None, max_length=255)
    # 兼容旧字段，内部统一为 tokens_resource。
    entry_resource: str | None = Field(default=None, max_length=255)
    resource_source: Literal["builtin_bundle", "managed_plugin_dir"]
    resource_version: str = Field(min_length=1, max_length=64)
    theme_schema_version: int = Field(ge=1, le=1000)
    platform_targets: list[Literal["h5", "rn"]] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
    fallback_theme_id: str | None = Field(default=None, max_length=64)

    @field_validator("theme_id", "display_name", "tokens_resource", "entry_resource", "resource_version", "fallback_theme_id")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空字符串")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("description 不能为空字符串")
        return normalized

    @field_validator("entry_resource", "tokens_resource")
    @classmethod
    def validate_tokens_resource(cls, value: str | None) -> str | None:
        if value is None:
            return None
        resource_path = Path(value)
        if resource_path.is_absolute():
            raise ValueError("主题资源路径必须是插件目录内的相对路径")
        if ".." in resource_path.parts:
            raise ValueError("主题资源路径不能跳出插件目录")
        return value.replace("\\", "/")

    @field_validator("platform_targets")
    @classmethod
    def validate_platform_targets(cls, value: list[Literal["h5", "rn"]]) -> list[Literal["h5", "rn"]]:
        if not value:
            raise ValueError("platform_targets 至少要声明一个目标端")
        deduped: list[Literal["h5", "rn"]] = []
        for item in value:
            if item not in deduped:
                deduped.append(item)
        return deduped

    @model_validator(mode="after")
    def normalize_resource_alias(self) -> "PluginManifestThemePackSpec":
        if self.tokens_resource is None and self.entry_resource is None:
            raise ValueError("theme-pack 插件必须声明 tokens_resource（兼容字段 entry_resource 也可）")
        if self.tokens_resource is None and self.entry_resource is not None:
            self.tokens_resource = self.entry_resource
        if self.entry_resource is None and self.tokens_resource is not None:
            self.entry_resource = self.tokens_resource
        return self

    @model_validator(mode="after")
    def validate_fallback_theme(self) -> "PluginManifestThemePackSpec":
        if self.fallback_theme_id is not None and self.fallback_theme_id == self.theme_id:
            raise ValueError("fallback_theme_id 不能等于 theme_id")
        return self


class PluginManifestAiProviderSpec(BaseModel):
    class BrandingSpec(BaseModel):
        logo_resource: str = Field(min_length=1, max_length=255)
        logo_resource_dark: str | None = Field(default=None, max_length=255)
        description_resource: str = Field(min_length=1, max_length=255)

        @field_validator("logo_resource", "logo_resource_dark", "description_resource")
        @classmethod
        def validate_resource_path(cls, value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            if not normalized:
                raise ValueError("资源路径不能为空")
            resource_path = Path(normalized)
            if resource_path.is_absolute():
                raise ValueError("资源路径必须是插件目录内的相对路径")
            if ".." in resource_path.parts:
                raise ValueError("资源路径不能跳出插件目录")
            return normalized.replace("\\", "/")

    class VisibilityRule(BaseModel):
        field: str = Field(min_length=1, max_length=64)
        operator: Literal["equals", "not_equals", "in", "truthy"] = "equals"
        value: Any | None = None

        @field_validator("field")
        @classmethod
        def validate_rule_field(cls, value: str) -> str:
            normalized = value.strip()
            if not normalized:
                raise ValueError("visible rule.field 不能为空")
            return normalized

    class ConfigFieldUiSpec(BaseModel):
        help_text: str | None = Field(default=None, max_length=255)
        hidden_when: list["PluginManifestAiProviderSpec.VisibilityRule"] = Field(default_factory=list)

        @field_validator("help_text")
        @classmethod
        def validate_help_text(cls, value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            if not normalized:
                raise ValueError("help_text 不能为空")
            return normalized

    class ConfigActionSpec(BaseModel):
        key: str = Field(min_length=1, max_length=64)
        label: str = Field(min_length=1, max_length=100)
        description: str | None = Field(default=None, max_length=255)
        kind: Literal["model_discovery"] = "model_discovery"
        placement: Literal["field"] = "field"
        field_key: str = Field(min_length=1, max_length=64)

        @field_validator("key", "label", "description", "field_key")
        @classmethod
        def validate_action_text(cls, value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            if not normalized:
                raise ValueError("action 字段不能为空")
            return normalized

    class ConfigSectionSpec(BaseModel):
        key: str = Field(min_length=1, max_length=64)
        title: str = Field(min_length=1, max_length=100)
        description: str | None = Field(default=None, max_length=255)
        fields: list[str] = Field(default_factory=list)

        @field_validator("key", "title", "description")
        @classmethod
        def validate_section_text(cls, value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            if not normalized:
                raise ValueError("section 字段不能为空")
            return normalized

        @field_validator("fields")
        @classmethod
        def validate_section_fields(cls, value: list[str]) -> list[str]:
            return _normalize_text_list(value, field_name="ai_provider.config_ui.sections.fields")

    class ConfigUiSpec(BaseModel):
        field_order: list[str] = Field(default_factory=list)
        hidden_fields: list[str] = Field(default_factory=list)
        sections: list["PluginManifestAiProviderSpec.ConfigSectionSpec"] = Field(default_factory=list)
        field_ui: dict[str, "PluginManifestAiProviderSpec.ConfigFieldUiSpec"] = Field(default_factory=dict)
        actions: list["PluginManifestAiProviderSpec.ConfigActionSpec"] = Field(default_factory=list)

        @field_validator("field_order", "hidden_fields")
        @classmethod
        def validate_field_lists(cls, value: list[str], info: Any) -> list[str]:
            return _normalize_text_list(value, field_name=str(info.field_name))

    class ModelDiscoverySpec(BaseModel):
        enabled: bool = False
        action_key: str | None = Field(default=None, max_length=64)
        depends_on_fields: list[str] = Field(default_factory=list)
        target_field: str | None = Field(default=None, max_length=64)
        debounce_ms: int = Field(default=500, ge=0, le=10000)
        empty_state_text: str | None = Field(default=None, max_length=255)
        discovery_hint_text: str | None = Field(default=None, max_length=255)
        discovering_text: str | None = Field(default=None, max_length=255)
        discovered_text_template: str | None = Field(default=None, max_length=255)

        @field_validator(
            "action_key",
            "target_field",
            "empty_state_text",
            "discovery_hint_text",
            "discovering_text",
            "discovered_text_template",
        )
        @classmethod
        def validate_optional_text(cls, value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            if not normalized:
                raise ValueError("model_discovery 字段不能为空")
            return normalized

        @field_validator("depends_on_fields")
        @classmethod
        def validate_depends_on_fields(cls, value: list[str]) -> list[str]:
            return _normalize_text_list(value, field_name="depends_on_fields")

    adapter_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    branding: BrandingSpec
    field_schema: list[dict[str, Any]] = Field(default_factory=list)
    config_ui: ConfigUiSpec
    model_discovery: ModelDiscoverySpec
    supported_model_types: list[str] = Field(default_factory=list)
    llm_workflow: str = Field(min_length=1, max_length=100)
    runtime_capability: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adapter_code", "display_name", "llm_workflow")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空字符串")
        return normalized

    @field_validator("supported_model_types")
    @classmethod
    def validate_supported_model_types(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="supported_model_types")

    @model_validator(mode="after")
    def validate_ui_contract(self) -> "PluginManifestAiProviderSpec":
        field_keys = {
            str(field.get("key") or "").strip()
            for field in self.field_schema
            if isinstance(field, dict) and str(field.get("key") or "").strip()
        }
        if not field_keys:
            return self

        for field_key in self.config_ui.field_order:
            if field_key not in field_keys:
                raise ValueError(f"config_ui.field_order 引用了不存在的字段 {field_key}")
        if not self.config_ui.field_order:
            raise ValueError("config_ui.field_order 不能为空")

        for field_key in self.config_ui.hidden_fields:
            if field_key not in field_keys:
                raise ValueError(f"config_ui.hidden_fields 引用了不存在的字段 {field_key}")

        if not self.config_ui.sections:
            raise ValueError("config_ui.sections 不能为空")

        for section in self.config_ui.sections:
            for field_key in section.fields:
                if field_key not in field_keys:
                    raise ValueError(f"config_ui.sections.fields 引用了不存在的字段 {field_key}")

        for field_key, field_ui in self.config_ui.field_ui.items():
            if field_key not in field_keys:
                raise ValueError(f"config_ui.field_ui 引用了不存在的字段 {field_key}")
            for rule in field_ui.hidden_when:
                if rule.field not in field_keys:
                    raise ValueError(f"config_ui.field_ui.hidden_when 引用了不存在的字段 {rule.field}")

        action_map: dict[str, PluginManifestAiProviderSpec.ConfigActionSpec] = {}
        for action in self.config_ui.actions:
            if action.field_key not in field_keys:
                raise ValueError(f"config_ui.actions.field_key 引用了不存在的字段 {action.field_key}")
            if action.key in action_map:
                raise ValueError(f"config_ui.actions.key 不能重复: {action.key}")
            action_map[action.key] = action

        if self.model_discovery.enabled:
            if self.model_discovery.action_key is None:
                raise ValueError("model_discovery.enabled=true 时必须声明 action_key")
            if self.model_discovery.target_field is None:
                raise ValueError("model_discovery.enabled=true 时必须声明 target_field")
            if self.model_discovery.target_field not in field_keys:
                raise ValueError(f"model_discovery.target_field 引用了不存在的字段 {self.model_discovery.target_field}")
            for field_key in self.model_discovery.depends_on_fields:
                if field_key not in field_keys:
                    raise ValueError(f"model_discovery.depends_on_fields 引用了不存在的字段 {field_key}")
            action = action_map.get(self.model_discovery.action_key)
            if action is None:
                raise ValueError(f"model_discovery.action_key 引用了不存在的动作 {self.model_discovery.action_key}")
            if action.kind != "model_discovery":
                raise ValueError("model_discovery.action_key 必须绑定 kind=model_discovery 的动作")
        return self


PluginManifestAiProviderSpec.model_rebuild()


class PluginManifestIntegrationSpec(BaseModel):
    domains: list[str] = Field(default_factory=list)
    instance_model: str = Field(min_length=1, max_length=64)
    refresh_mode: Literal["polling", "event_driven", "manual"] = "polling"
    supports_discovery: bool = False
    supports_actions: bool = False
    supports_cards: bool = False
    supports_live_state: bool = False
    auto_create_default_instance: bool = False
    default_instance_display_name: str | None = Field(default=None, max_length=100)
    default_instance_config: dict[str, Any] = Field(default_factory=dict)
    entity_types: list[str] = Field(default_factory=list)
    default_cache_ttl_seconds: int = Field(default=300, ge=0, le=86400)
    max_stale_seconds: int = Field(default=3600, ge=0, le=604800)

    @field_validator("domains", "entity_types")
    @classmethod
    def validate_text_lists(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="integration_list")

    @field_validator("instance_model")
    @classmethod
    def validate_instance_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("instance_model 不能为空")
        return normalized

    @field_validator("default_instance_display_name")
    @classmethod
    def validate_default_instance_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("default_instance_display_name 不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_stale_window(self) -> "PluginManifestIntegrationSpec":
        if self.max_stale_seconds < self.default_cache_ttl_seconds:
            raise ValueError("max_stale_seconds 不能小于 default_cache_ttl_seconds")
        return self


class PluginManifestSlotSpec(BaseModel):
    slot_name: Literal["memory_engine", "memory_provider", "context_engine"]
    exclusive: bool = True
    fallback_required: bool = True
    input_contract_version: int = Field(default=1, ge=1)
    output_contract_version: int = Field(default=1, ge=1)


class PluginManifestChannelConfigField(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    type: Literal["text", "password"] = "text"
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=255)

    @field_validator("key", "label", "placeholder", "help_text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class PluginManifestChannelBindingUiSpec(BaseModel):
    identity_label: str | None = Field(default=None, max_length=100)
    identity_placeholder: str | None = Field(default=None, max_length=255)
    identity_help_text: str | None = Field(default=None, max_length=255)
    chat_label: str | None = Field(default=None, max_length=100)
    chat_placeholder: str | None = Field(default=None, max_length=255)
    chat_help_text: str | None = Field(default=None, max_length=255)
    candidate_title: str | None = Field(default=None, max_length=100)
    candidate_help_text: str | None = Field(default=None, max_length=255)

    @field_validator(
        "identity_label",
        "identity_placeholder",
        "identity_help_text",
        "chat_label",
        "chat_placeholder",
        "chat_help_text",
        "candidate_title",
        "candidate_help_text",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class PluginManifestChannelUiSpec(BaseModel):
    binding: PluginManifestChannelBindingUiSpec = Field(default_factory=PluginManifestChannelBindingUiSpec)


class PluginManifestChannelSpec(BaseModel):
    platform_code: str | None = None
    inbound_modes: list[str] = Field(default_factory=list)
    delivery_modes: list[str] = Field(default_factory=list)
    supports_member_binding: bool = False
    supports_group_chat: bool = False
    supports_threading: bool = False
    ui: PluginManifestChannelUiSpec = Field(default_factory=PluginManifestChannelUiSpec)
    reserved: bool = True

    @field_validator("platform_code")
    @classmethod
    def validate_platform_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("platform_code 不能为空")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(char not in allowed for char in normalized):
            raise ValueError("platform_code 只能包含小写字母、数字和连字符")
        return normalized

    @field_validator("inbound_modes")
    @classmethod
    def validate_inbound_modes(cls, value: list[str]) -> list[str]:
        normalized = _normalize_text_list(value, field_name="inbound_modes")
        allowed_modes = {"webhook", "polling", "websocket"}
        invalid_modes = [item for item in normalized if item not in allowed_modes]
        if invalid_modes:
            raise ValueError(f"inbound_modes 包含不支持的模式: {', '.join(invalid_modes)}")
        return normalized

    @field_validator("delivery_modes")
    @classmethod
    def validate_delivery_modes(cls, value: list[str]) -> list[str]:
        normalized = _normalize_text_list(value, field_name="delivery_modes")
        allowed_modes = {"reply", "push"}
        invalid_modes = [item for item in normalized if item not in allowed_modes]
        if invalid_modes:
            raise ValueError(f"delivery_modes 包含不支持的模式: {', '.join(invalid_modes)}")
        return normalized


class PluginManifestCapabilities(BaseModel):
    context_reads: PluginManifestContextReads = Field(default_factory=PluginManifestContextReads)
    integration: PluginManifestIntegrationSpec | None = None
    channel: PluginManifestChannelSpec | None = None
    region_provider: PluginManifestRegionProviderSpec | None = None
    theme_pack: PluginManifestThemePackSpec | None = None
    ai_provider: PluginManifestAiProviderSpec | None = None
    memory_engine: PluginManifestSlotSpec | None = None
    memory_provider: PluginManifestSlotSpec | None = None
    context_engine: PluginManifestSlotSpec | None = None
    device_detail_tabs: list["PluginManifestDeviceDetailTabSpec"] = Field(default_factory=list)


class PluginManifestDeviceDetailTabSpec(BaseModel):
    tab_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    config_scope_type: Literal["device"] = "device"

    @field_validator("tab_key", "title", "description")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


PluginManifestCapabilities.model_rebuild()


class PluginManifestDashboardCardSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_key: str = Field(min_length=1, max_length=64)
    card_key_prefix: str | None = Field(default=None, max_length=64)
    placement: PluginDashboardCardPlacement
    template_type: PluginDashboardCardTemplateType
    size: PluginDashboardCardSize
    title_key: str = Field(min_length=1, max_length=255)
    subtitle_key: str | None = Field(default=None, max_length=255)
    empty_state_key: str | None = Field(default=None, max_length=255)
    refresh_strategy: PluginDashboardCardRefreshStrategy
    max_items: int | None = Field(default=None, ge=1, le=20)
    allowed_actions: list[PluginDashboardCardActionType] = Field(default_factory=list)

    @field_validator("card_key", "card_key_prefix")
    @classmethod
    def validate_card_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("card_key 不能为空")
        if any(char not in DASHBOARD_CARD_KEY_ALLOWED_CHARS for char in normalized):
            raise ValueError("card_key 只能包含小写字母、数字、连字符和下划线")
        return normalized

    @field_validator("title_key", "subtitle_key", "empty_state_key")
    @classmethod
    def validate_i18n_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)

    @field_validator("allowed_actions")
    @classmethod
    def validate_allowed_actions(cls, value: list[PluginDashboardCardActionType]) -> list[PluginDashboardCardActionType]:
        normalized = _normalize_text_list(value, field_name="allowed_actions")
        return [cast(PluginDashboardCardActionType, item) for item in normalized]

    @model_validator(mode="after")
    def validate_template_constraints(self) -> "PluginManifestDashboardCardSpec":
        if self.max_items is not None and self.template_type not in DASHBOARD_CARD_LIST_TEMPLATE_TYPES:
            raise ValueError("只有列表类卡片才能声明 max_items")
        return self


class PluginManifestConfigFieldOption(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    label_key: str | None = Field(default=None, max_length=255)
    value: str = Field(min_length=1, max_length=100)

    @field_validator("label", "value")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("label_key")
    @classmethod
    def validate_label_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)


class PluginManifestConfigFieldOptionSource(BaseModel):
    source: PluginConfigDynamicOptionSourceType
    country_code: str | None = Field(default=None, max_length=8)
    provider_code: str | None = Field(default=None, max_length=100)
    provider_field: str | None = Field(default=None, max_length=64)
    parent_field: str | None = Field(default=None, max_length=64)
    admin_level: RegionCatalogAdminLevel | None = None

    @field_validator("country_code", "provider_code", "provider_field", "parent_field")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_source_constraints(self) -> "PluginManifestConfigFieldOptionSource":
        if self.country_code is None:
            raise ValueError("option_source.country_code 不能为空")

        if self.source == "region_provider_list":
            if self.provider_code or self.provider_field or self.parent_field or self.admin_level:
                raise ValueError("region_provider_list 不接受 provider_code/provider_field/parent_field/admin_level")
            return self

        if (self.provider_code is None) == (self.provider_field is None):
            raise ValueError("region_catalog_children 必须且只能声明 provider_code 或 provider_field 其中一个")
        if self.admin_level is None:
            raise ValueError("region_catalog_children 必须声明 admin_level")
        if self.admin_level == "province":
            if self.parent_field is not None:
                raise ValueError("province 级联选项不需要 parent_field")
            return self
        if self.parent_field is None:
            raise ValueError("city / district 级联选项必须声明 parent_field")
        return self


class PluginManifestConfigField(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    label_key: str | None = Field(default=None, max_length=255)
    type: PluginConfigFieldType
    required: bool = False
    description: str | None = Field(default=None, max_length=255)
    description_key: str | None = Field(default=None, max_length=255)
    default: Any = None
    enum_options: list[PluginManifestConfigFieldOption] = Field(default_factory=list)
    option_source: PluginManifestConfigFieldOptionSource | None = None
    depends_on: list[str] = Field(default_factory=list)
    clear_on_dependency_change: bool = False
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = Field(default=None, max_length=255)
    nullable: bool = False

    @field_validator("key", "label", "description", "pattern")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("label_key", "description_key")
    @classmethod
    def validate_i18n_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)

    @field_validator("depends_on")
    @classmethod
    def validate_depends_on(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="depends_on")

    @model_validator(mode="after")
    def validate_field_constraints(self) -> "PluginManifestConfigField":
        string_like_types = {"string", "text", "secret"}
        numeric_types = {"integer", "number"}

        if self.min_length is not None and self.type not in string_like_types:
            raise ValueError("只有字符串类字段才能声明 min_length")
        if self.max_length is not None and self.type not in string_like_types:
            raise ValueError("只有字符串类字段才能声明 max_length")
        if self.minimum is not None and self.type not in numeric_types:
            raise ValueError("只有数值类字段才能声明 minimum")
        if self.maximum is not None and self.type not in numeric_types:
            raise ValueError("只有数值类字段才能声明 maximum")
        if self.pattern is not None and self.type not in string_like_types:
            raise ValueError("只有字符串类字段才能声明 pattern")
        if self.enum_options and self.type not in {"enum", "multi_enum"}:
            raise ValueError("只有 enum / multi_enum 字段才能声明 enum_options")
        if self.option_source is not None and self.type not in {"enum", "multi_enum"}:
            raise ValueError("只有 enum / multi_enum 字段才能声明 option_source")
        if self.enum_options and self.option_source is not None:
            raise ValueError("enum / multi_enum 字段不能同时声明 enum_options 和 option_source")
        if self.type in {"enum", "multi_enum"} and not self.enum_options and self.option_source is None:
            raise ValueError("enum / multi_enum 字段必须声明 enum_options 或 option_source")
        if self.clear_on_dependency_change and not self.depends_on:
            raise ValueError("clear_on_dependency_change = true 时必须声明 depends_on")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length 不能大于 max_length")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum 不能大于 maximum")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"pattern 不是合法正则: {exc}") from exc
        self._validate_default_value()
        return self

    def _validate_default_value(self) -> None:
        if self.default is None:
            return
        if self.default is None and not self.nullable:
            return
        self.validate_value(self.default)

    def validate_value(self, value: Any) -> None:
        if value is None:
            if self.nullable:
                return
            raise ValueError(f"{self.key} 不允许为 null")

        if self.type in {"string", "text", "secret"}:
            if not isinstance(value, str):
                raise ValueError(f"{self.key} 必须是字符串")
            if self.min_length is not None and len(value) < self.min_length:
                raise ValueError(f"{self.key} 长度不能小于 {self.min_length}")
            if self.max_length is not None and len(value) > self.max_length:
                raise ValueError(f"{self.key} 长度不能大于 {self.max_length}")
            if self.pattern is not None and re.fullmatch(self.pattern, value) is None:
                raise ValueError(f"{self.key} 格式不合法")
            return

        if self.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{self.key} 必须是整数")
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"{self.key} 不能小于 {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"{self.key} 不能大于 {self.maximum}")
            return

        if self.type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{self.key} 必须是数字")
            numeric_value = float(value)
            if self.minimum is not None and numeric_value < self.minimum:
                raise ValueError(f"{self.key} 不能小于 {self.minimum}")
            if self.maximum is not None and numeric_value > self.maximum:
                raise ValueError(f"{self.key} 不能大于 {self.maximum}")
            return

        if self.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{self.key} 必须是布尔值")
            return

        option_values = {option.value for option in self.enum_options}
        if self.type == "enum":
            if not isinstance(value, str):
                raise ValueError(f"{self.key} 必须是字符串枚举")
            if value not in option_values:
                raise ValueError(f"{self.key} 不是合法选项")
            return

        if self.type == "multi_enum":
            if not isinstance(value, list):
                raise ValueError(f"{self.key} 必须是数组")
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"{self.key} 的选项必须是字符串")
                if item not in option_values:
                    raise ValueError(f"{self.key} 包含非法选项: {item}")
            return

        if self.type == "json":
            if not isinstance(value, (dict, list)):
                raise ValueError(f"{self.key} 必须是 JSON 对象或数组")
            try:
                json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{self.key} 不是合法 JSON") from exc
            return

        raise ValueError(f"{self.key} 使用了不支持的字段类型: {self.type}")


class PluginManifestConfigSchema(BaseModel):
    fields: list[PluginManifestConfigField] = Field(default_factory=list)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[PluginManifestConfigField]) -> list[PluginManifestConfigField]:
        if not value:
            raise ValueError("config_schema.fields 不能为空")

        seen: set[str] = set()
        for item in value:
            if item.key in seen:
                raise ValueError(f"config_schema.fields 里不能有重复 key: {item.key}")
            seen.add(item.key)
        return value

    def field_keys(self) -> list[str]:
        return [field.key for field in self.fields]

    def field_map(self) -> dict[str, PluginManifestConfigField]:
        return {field.key: field for field in self.fields}


class PluginManifestVisibilityRule(BaseModel):
    field: str = Field(min_length=1, max_length=64)
    operator: PluginConfigVisibilityOperator
    value: Any = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field 不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_rule(self) -> "PluginManifestVisibilityRule":
        if self.operator == "truthy":
            return self
        if self.operator == "in":
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("visible_when.operator = in 时，value 必须是非空数组")
            return self
        if self.value is None:
            raise ValueError("visible_when 必须提供 value")
        return self


class PluginManifestFieldUiSchema(BaseModel):
    widget: PluginConfigWidgetType | None = None
    placeholder: str | None = Field(default=None, max_length=255)
    placeholder_key: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=255)
    help_text_key: str | None = Field(default=None, max_length=255)
    visible_when: list[PluginManifestVisibilityRule] = Field(default_factory=list)

    @field_validator("placeholder", "help_text")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("placeholder_key", "help_text_key")
    @classmethod
    def validate_i18n_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)


class PluginManifestUiSection(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    title_key: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    description_key: str | None = Field(default=None, max_length=255)
    fields: list[str] = Field(default_factory=list)

    @field_validator("id", "title", "description")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("title_key", "description_key")
    @classmethod
    def validate_i18n_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="section.fields")


class PluginManifestUiSchema(BaseModel):
    sections: list[PluginManifestUiSection] = Field(default_factory=list)
    field_order: list[str] = Field(default_factory=list)
    submit_text: str | None = Field(default=None, max_length=50)
    submit_text_key: str | None = Field(default=None, max_length=255)
    widgets: dict[str, PluginManifestFieldUiSchema] = Field(default_factory=dict)

    @field_validator("field_order")
    @classmethod
    def validate_field_order(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="field_order")

    @field_validator("submit_text")
    @classmethod
    def validate_submit_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("submit_text 不能为空")
        return normalized

    @field_validator("submit_text_key")
    @classmethod
    def validate_submit_text_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value: list[PluginManifestUiSection]) -> list[PluginManifestUiSection]:
        if not value:
            raise ValueError("ui_schema.sections 不能为空")

        seen: set[str] = set()
        for item in value:
            if item.id in seen:
                raise ValueError(f"ui_schema.sections 里不能有重复 id: {item.id}")
            seen.add(item.id)
        return value


class PluginManifestConfigSpec(BaseModel):
    scope_type: PluginConfigScopeType
    title: str = Field(min_length=1, max_length=100)
    title_key: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    description_key: str | None = Field(default=None, max_length=255)
    schema_version: int = Field(ge=1)
    config_schema: PluginManifestConfigSchema
    ui_schema: PluginManifestUiSchema

    @field_validator("title", "description")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("title_key", "description_key")
    @classmethod
    def validate_i18n_key(cls, value: str | None) -> str | None:
        return _normalize_i18n_key(value)

    @model_validator(mode="after")
    def validate_schema_references(self) -> "PluginManifestConfigSpec":
        field_map = self.config_schema.field_map()
        field_keys = set(field_map)
        seen_in_sections: set[str] = set()

        for section in self.ui_schema.sections:
            for field_key in section.fields:
                if field_key not in field_keys:
                    raise ValueError(f"ui_schema.sections 引用了不存在的字段: {field_key}")
                if field_key in seen_in_sections:
                    raise ValueError(f"ui_schema.sections 里字段不能重复出现: {field_key}")
                seen_in_sections.add(field_key)

        missing_fields = field_keys - seen_in_sections
        if missing_fields:
            missing_text = ", ".join(sorted(missing_fields))
            raise ValueError(f"ui_schema.sections 缺少字段: {missing_text}")

        for field_key in self.ui_schema.field_order:
            if field_key not in field_keys:
                raise ValueError(f"ui_schema.field_order 引用了不存在的字段: {field_key}")

        for field in self.config_schema.fields:
            for dependency_field in field.depends_on:
                if dependency_field not in field_keys:
                    raise ValueError(f"字段 {field.key} 的 depends_on 引用了不存在的字段: {dependency_field}")
                if dependency_field == field.key:
                    raise ValueError(f"字段 {field.key} 不能依赖自己")
            if field.option_source is None:
                continue
            if field.option_source.provider_field is not None:
                if field.option_source.provider_field not in field_keys:
                    raise ValueError(
                        f"字段 {field.key} 的 option_source.provider_field 引用了不存在的字段: {field.option_source.provider_field}"
                    )
                if field.option_source.provider_field == field.key:
                    raise ValueError(f"字段 {field.key} 不能把自己声明为 provider_field")
            if field.option_source.parent_field is not None:
                if field.option_source.parent_field not in field_keys:
                    raise ValueError(
                        f"字段 {field.key} 的 option_source.parent_field 引用了不存在的字段: {field.option_source.parent_field}"
                    )
                if field.option_source.parent_field == field.key:
                    raise ValueError(f"字段 {field.key} 不能把自己声明为 parent_field")

        for field_key, widget in self.ui_schema.widgets.items():
            if field_key not in field_keys:
                raise ValueError(f"ui_schema.widgets 引用了不存在的字段: {field_key}")
            self._validate_widget(field_map[field_key], widget)
            for rule in widget.visible_when:
                if rule.field not in field_keys:
                    raise ValueError(f"visible_when 引用了不存在的字段: {rule.field}")
        return self

    @staticmethod
    def _validate_widget(
        field: PluginManifestConfigField,
        widget: PluginManifestFieldUiSchema,
    ) -> None:
        if widget.widget is None:
            return

        allowed_widgets: dict[PluginConfigFieldType, set[PluginConfigWidgetType]] = {
            "string": {"input", "password", "textarea"},
            "text": {"input", "textarea"},
            "integer": {"input"},
            "number": {"input"},
            "boolean": {"switch"},
            "enum": {"select"},
            "multi_enum": {"multi_select"},
            "secret": {"password"},
            "json": {"json_editor", "textarea"},
        }
        if widget.widget not in allowed_widgets[field.type]:
            raise ValueError(f"字段 {field.key} 的 widget {widget.widget} 和类型 {field.type} 不匹配")


class PluginManifestLocaleSpec(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=100)
    native_label: str = Field(min_length=1, max_length=100)
    resource: str = Field(min_length=1, max_length=255)
    fallback: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("id", "label", "native_label", "fallback")
    @classmethod
    def validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("resource")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource 不能为空")

        resource_path = Path(normalized)
        if resource_path.is_absolute():
            raise ValueError("resource 必须是插件目录内的相对路径")
        if ".." in resource_path.parts:
            raise ValueError("resource 不能跳出插件目录")
        return normalized.replace("\\", "/")


class PluginManifestScheduleTemplate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    default_definition: dict[str, Any] = Field(default_factory=dict)
    enabled_by_default: bool = False

    @field_validator("code", "name", "description")
    @classmethod
    def validate_template_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class PluginManifest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=32)
    api_version: int = Field(default=1, ge=1)
    types: list[PluginManifestType] = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    triggers: list[str] = Field(default_factory=list)
    entrypoints: PluginManifestEntrypoints = Field(default_factory=PluginManifestEntrypoints)
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    dashboard_cards: list[PluginManifestDashboardCardSpec] = Field(default_factory=list)
    config_specs: list[PluginManifestConfigSpec] = Field(default_factory=list)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)
    schedule_templates: list[PluginManifestScheduleTemplate] = Field(default_factory=list)
    compatibility: dict[str, Any] | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("id 不能为空")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-.")
        if any(char not in allowed for char in normalized):
            raise ValueError("id 只能包含小写字母、数字、点号和连字符")
        return normalized

    @field_validator("name", "version")
    @classmethod
    def validate_text_field(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("types")
    @classmethod
    def validate_types(cls, value: list[PluginManifestType]) -> list[PluginManifestType]:
        seen: set[str] = set()

        for item in value:
            if item in seen:
                raise ValueError(f"types 里不能有重复值: {item}")
            seen.add(item)
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="permissions")

    @field_validator("triggers")
    @classmethod
    def validate_triggers(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, field_name="triggers")

    @field_validator("locales")
    @classmethod
    def validate_locales(cls, value: list[PluginManifestLocaleSpec]) -> list[PluginManifestLocaleSpec]:
        seen: set[str] = set()
        for item in value:
            if item.id in seen:
                raise ValueError(f"locales 里不能有重复 locale id: {item.id}")
            seen.add(item.id)
        return value

    @field_validator("config_specs")
    @classmethod
    def validate_config_specs(cls, value: list[PluginManifestConfigSpec]) -> list[PluginManifestConfigSpec]:
        seen: set[str] = set()
        for item in value:
            if item.scope_type in seen:
                raise ValueError(f"config_specs 里不能有重复 scope_type: {item.scope_type}")
            seen.add(item.scope_type)
        return value

    @field_validator("dashboard_cards")
    @classmethod
    def validate_dashboard_cards(cls, value: list[PluginManifestDashboardCardSpec]) -> list[PluginManifestDashboardCardSpec]:
        seen: set[str] = set()
        for item in value:
            if item.card_key in seen:
                raise ValueError(f"dashboard_cards 里不能有重复 card_key: {item.card_key}")
            seen.add(item.card_key)
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_entrypoint_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        entrypoints = data.get("entrypoints")
        if not isinstance(entrypoints, dict):
            return data

        normalized_entrypoints: dict[str, Any] = {}
        for key, value in entrypoints.items():
            normalized_key = str(key).strip().replace("-", "_")
            normalized_entrypoints[normalized_key] = value
        data = dict(data)
        data["entrypoints"] = normalized_entrypoints
        return data

    @model_validator(mode="after")
    def validate_required_entrypoints(self) -> "PluginManifest":
        missing_keys: list[str] = []
        for plugin_type in self.types:
            if plugin_type in NON_EXECUTABLE_PLUGIN_TYPES:
                continue
            entrypoint_key = ENTRYPOINT_KEY_BY_TYPE[plugin_type]
            if getattr(self.entrypoints, entrypoint_key) is None:
                missing_keys.append(entrypoint_key)
        if missing_keys:
            missing_text = ", ".join(missing_keys)
            raise ValueError(f"entrypoints 缺少类型对应入口: {missing_text}")
        if "locale-pack" in self.types and not self.locales:
            raise ValueError("locale-pack 插件至少要声明一个 locale")
        if self.schedule_templates and "schedule" not in self.triggers:
            raise ValueError("声明计划任务模板前，triggers 必须包含 schedule")
        self._validate_integration_capability()
        self._validate_channel_capability()
        self._validate_config_specs()
        self._validate_region_provider_capability()
        self._validate_theme_pack_capability()
        self._validate_ai_provider_capability()
        self._validate_slot_capabilities()
        self._validate_device_detail_tabs()
        return self

    def _validate_integration_capability(self) -> None:
        spec = self.capabilities.integration
        if spec is None:
            return

        if "integration" not in self.types:
            raise ValueError("声明 capabilities.integration 时，types 必须包含 integration")
        if self.entrypoints.integration is None:
            raise ValueError("integration 插件必须声明 entrypoints.integration")
        if not spec.domains:
            raise ValueError("integration 插件至少要声明一个 domain")

    def _validate_channel_capability(self) -> None:
        spec = self.capabilities.channel
        if spec is None:
            if "channel" in self.types:
                raise ValueError("channel 插件必须声明 capabilities.channel")
            return

        if spec.reserved:
            if "channel" in self.types:
                raise ValueError("channel 插件不能把 capabilities.channel 标成 reserved")
            return

        if "channel" not in self.types:
            raise ValueError("启用通讯通道运行时必须把 channel 写进 types")
        if spec.platform_code is None:
            raise ValueError("通讯通道运行时必须声明 platform_code")
        if not spec.inbound_modes:
            raise ValueError("通讯通道运行时至少要声明一个 inbound_mode")
        if not spec.delivery_modes:
            raise ValueError("通讯通道运行时至少要声明一个 delivery_mode")
        if self.entrypoints.channel is None:
            raise ValueError("通讯通道运行时必须声明 entrypoints.channel")

    def _validate_region_provider_capability(self) -> None:
        spec = self.capabilities.region_provider
        if spec is None:
            if "region-provider" in self.types:
                raise ValueError("region-provider 插件必须声明 capabilities.region_provider")
            return

        if spec.reserved:
            if "region-provider" in self.types:
                raise ValueError("region-provider 插件不能把 capabilities.region_provider 标成 reserved")
            return

        if "region-provider" not in self.types:
            raise ValueError("启用地区 provider 运行时必须把 region-provider 写进 types")
        if spec.provider_code is None:
            raise ValueError("地区 provider 运行时必须声明 provider_code")
        if spec.entrypoint is None:
            raise ValueError("地区 provider 运行时必须声明 entrypoint")
        if not spec.country_codes:
            raise ValueError("地区 provider 运行时至少要声明一个 country_code")
        if self.entrypoints.region_provider != spec.entrypoint:
            raise ValueError("entrypoints.region_provider 必须和 capabilities.region_provider.entrypoint 一致")

    def _validate_theme_pack_capability(self) -> None:
        spec = self.capabilities.theme_pack
        if spec is None:
            if "theme-pack" in self.types:
                raise ValueError("theme-pack 插件必须声明 capabilities.theme_pack")
            return

        if "theme-pack" not in self.types:
            raise ValueError("声明 capabilities.theme_pack 时，types 必须包含 theme-pack")

    def _validate_ai_provider_capability(self) -> None:
        spec = self.capabilities.ai_provider
        if spec is None:
            if "ai-provider" in self.types:
                raise ValueError("ai-provider 插件必须声明 capabilities.ai_provider")
            return

        if "ai-provider" not in self.types:
            raise ValueError("声明 capabilities.ai_provider 时，types 必须包含 ai-provider")
        if self.entrypoints.ai_provider is None:
            raise ValueError("ai-provider 插件必须声明 entrypoints.ai_provider")
        if not spec.field_schema:
            raise ValueError("ai-provider 插件至少要声明一个 field_schema 字段")
        if not spec.supported_model_types:
            raise ValueError("ai-provider 插件至少要声明一个 supported_model_type")

    def _validate_device_detail_tabs(self) -> None:
        tabs = self.capabilities.device_detail_tabs
        if not tabs:
            return

        seen: set[str] = set()
        declared_scope_types = {item.scope_type for item in self.config_specs}
        for tab in tabs:
            if tab.tab_key in seen:
                raise ValueError(f"device_detail_tabs 里不能有重复 tab_key: {tab.tab_key}")
            seen.add(tab.tab_key)
            if tab.config_scope_type not in declared_scope_types:
                raise ValueError(
                    f"device_detail_tabs.{tab.tab_key} 引用了未声明的 config scope_type: {tab.config_scope_type}"
                )

    def _validate_config_specs(self) -> None:
        if not self.config_specs:
            return

        allowed_scope_types = {"plugin", "integration_instance", "channel_account", "device"}
        for item in self.config_specs:
            if item.scope_type not in allowed_scope_types:
                raise ValueError(f"不支持的 config scope_type: {item.scope_type}")
            if item.scope_type == "channel_account" and "channel" not in self.types:
                raise ValueError("只有 channel 插件才能声明 channel_account 作用域配置")
            if item.scope_type == "integration_instance" and "integration" not in self.types:
                raise ValueError("只有 integration 插件才能声明 integration_instance 作用域配置")

    def _validate_slot_capabilities(self) -> None:
        for slot_name in ("memory_engine", "memory_provider", "context_engine"):
            spec = getattr(self.capabilities, slot_name)
            if spec is None:
                if slot_name in self.types:
                    raise ValueError(f"{slot_name} 插件必须声明 capabilities.{slot_name}")
                continue
            if slot_name not in self.types:
                raise ValueError(f"声明 capabilities.{slot_name} 时，types 必须包含 {slot_name}")
            if spec.slot_name != slot_name:
                raise ValueError(f"capabilities.{slot_name}.slot_name 必须等于 {slot_name}")


class PluginRegistryStateEntry(BaseModel):
    enabled: bool = True
    updated_at: str | None = None


class PluginStateOverrideRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    enabled: bool
    source_type: PluginSourceType
    updated_by: str | None = None
    created_at: str
    updated_at: str

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)


class PluginStateUpdateRequest(BaseModel):
    enabled: bool


PluginConfigState = Literal["unconfigured", "configured", "invalid"]


class PluginConfigScopeInstanceRead(BaseModel):
    scope_key: str
    label: str
    description: str | None = None
    configured: bool = False


class PluginConfigScopeRead(BaseModel):
    scope_type: PluginConfigScopeType
    title: str
    description: str | None = None
    instances: list[PluginConfigScopeInstanceRead] = Field(default_factory=list)


class PluginConfigScopeListRead(BaseModel):
    plugin_id: str
    items: list[PluginConfigScopeRead] = Field(default_factory=list)


class PluginConfigSecretFieldRead(BaseModel):
    has_value: bool = False
    masked: str | None = None


class PluginConfigView(BaseModel):
    scope_type: PluginConfigScopeType
    scope_key: str
    schema_version: int = Field(ge=1)
    state: PluginConfigState
    values: dict[str, Any] = Field(default_factory=dict)
    secret_fields: dict[str, PluginConfigSecretFieldRead] = Field(default_factory=dict)
    field_errors: dict[str, str] = Field(default_factory=dict)


class PluginConfigFormRead(BaseModel):
    plugin_id: str
    config_spec: PluginManifestConfigSpec
    view: PluginConfigView


class PluginConfigUpdateRequest(BaseModel):
    scope_type: PluginConfigScopeType
    scope_key: str = Field(min_length=1, max_length=100)
    values: dict[str, Any] = Field(default_factory=dict)
    clear_fields: list[str] = Field(default_factory=list)
    clear_secret_fields: list[str] = Field(default_factory=list)

    @field_validator("scope_key")
    @classmethod
    def validate_scope_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scope_key 不能为空")
        return normalized

    @field_validator("clear_fields", "clear_secret_fields")
    @classmethod
    def validate_clear_field_lists(cls, value: list[str], info: Any) -> list[str]:
        return _normalize_text_list(value, field_name=str(info.field_name))


class PluginConfigResolveRequest(BaseModel):
    scope_type: PluginConfigScopeType
    scope_key: str | None = Field(default=None, max_length=100)
    values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scope_key")
    @classmethod
    def validate_optional_scope_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("scope_key 不能为空")
        return normalized


class PluginRunnerConfig(BaseModel):
    plugin_root: str | None = None
    python_path: str | None = None
    working_dir: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    stdout_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    stderr_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)


class PluginVersionGovernanceRead(BaseModel):
    source_type: PluginVersionGovernanceSourceType
    installed_version: str | None = None
    declared_version: str | None = None
    latest_version: str | None = None
    latest_compatible_version: str | None = None
    compatibility_status: PluginVersionCompatibilityStatus
    update_state: PluginVersionUpdateState
    blocked_reason: str | None = None


class PluginRegistryItem(BaseModel):
    id: str
    name: str
    version: str
    installed_version: str | None = None
    compatibility: dict[str, Any] | None = None
    update_state: str | None = None
    types: list[PluginManifestType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    base_enabled: bool = True
    household_enabled: bool | None = None
    enabled: bool
    disabled_reason: str | None = None
    manifest_path: str
    entrypoints: PluginManifestEntrypoints
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    dashboard_cards: list[PluginManifestDashboardCardSpec] = Field(default_factory=list)
    config_specs: list[PluginManifestConfigSpec] = Field(default_factory=list)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)
    schedule_templates: list[PluginManifestScheduleTemplate] = Field(default_factory=list)
    source_type: PluginSourceType = "builtin"
    install_method: PluginInstallMethod | None = None
    execution_backend: PluginExecutionBackend | None = None
    runner_config: PluginRunnerConfig | None = None
    install_status: str | None = None
    config_status: PluginConfigState | None = None
    marketplace_instance_id: str | None = None
    version_governance: PluginVersionGovernanceRead | None = None

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)

    @field_validator("install_method", mode="before")
    @classmethod
    def normalize_install_method(cls, value: str | None) -> str | None:
        return _normalize_plugin_install_method(value)

    @model_validator(mode="after")
    def validate_install_method(self) -> "PluginRegistryItem":
        if self.source_type == "builtin":
            self.install_method = None
            return self
        if self.install_method is None:
            raise ValueError("third_party 插件必须声明 install_method")
        return self


class PluginRegistrySnapshot(BaseModel):
    items: list[PluginRegistryItem] = Field(default_factory=list)


class PluginLocaleRead(BaseModel):
    plugin_id: str
    locale_id: str
    label: str
    native_label: str
    fallback: str | None = None
    source_type: PluginSourceType
    messages: dict[str, str] = Field(default_factory=dict)
    overridden_plugin_ids: list[str] = Field(default_factory=list)

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)


class PluginLocaleListRead(BaseModel):
    household_id: str
    items: list[PluginLocaleRead] = Field(default_factory=list)


class PluginThemeRegistryItemRead(BaseModel):
    plugin_id: str
    plugin_name: str
    source_type: PluginSourceType
    enabled: bool
    disabled_reason: str | None = None
    state: Literal["ready", "disabled", "invalid", "stale"] = "ready"
    theme_id: str
    display_name: str
    description: str | None = None
    resource_source: Literal["builtin_bundle", "managed_plugin_dir"]
    tokens_resource: str
    resource_version: str
    theme_schema_version: int
    platform_targets: list[Literal["h5", "rn"]] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
    fallback_theme_id: str | None = None

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)


class PluginThemeRegistrySnapshotRead(BaseModel):
    household_id: str
    items: list[PluginThemeRegistryItemRead] = Field(default_factory=list)


class PluginThemeResourceRead(BaseModel):
    household_id: str
    plugin_id: str
    theme_id: str
    display_name: str
    description: str | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    source_type: PluginSourceType
    resource_source: Literal["builtin_bundle", "managed_plugin_dir"]
    resource_version: str
    theme_schema_version: int
    platform_targets: list[Literal["h5", "rn"]] = Field(default_factory=list)
    tokens: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)


class HomeDashboardCardActionRead(BaseModel):
    action_key: str | None = Field(default=None, min_length=1, max_length=64)
    action_type: PluginDashboardCardActionType
    label: str = Field(min_length=1, max_length=80)
    target: str | None = Field(default=None, max_length=255)
    payload: dict[str, Any] | None = None

    @field_validator("action_key", "label", "target")
    @classmethod
    def validate_optional_action_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("动作字段不能为空")
        return normalized


class PluginDashboardCardSnapshotEnvelope(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    subtitle: str | None = Field(default=None, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    actions: list[HomeDashboardCardActionRead] = Field(default_factory=list)

    @field_validator("title", "subtitle")
    @classmethod
    def validate_snapshot_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("快照标题字段不能为空")
        return normalized

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: list[HomeDashboardCardActionRead]) -> list[HomeDashboardCardActionRead]:
        seen_action_keys: set[str] = set()
        for item in value:
            if item.action_key is None:
                continue
            if item.action_key in seen_action_keys:
                raise ValueError(f"actions 里不能有重复 action_key: {item.action_key}")
            seen_action_keys.add(item.action_key)
        return value


class PluginDashboardCardSnapshotUpsert(BaseModel):
    card_key: str = Field(min_length=1, max_length=64)
    placement: PluginDashboardCardPlacement = "home"
    title: str | None = Field(default=None, max_length=100)
    subtitle: str | None = Field(default=None, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    actions: list[HomeDashboardCardActionRead] = Field(default_factory=list)
    generated_at: str | None = None
    expires_at: str | None = None

    @field_validator("card_key")
    @classmethod
    def validate_snapshot_card_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("card_key 不能为空")
        return normalized


class PluginDashboardCardSnapshotErrorUpsert(BaseModel):
    card_key: str = Field(min_length=1, max_length=64)
    placement: PluginDashboardCardPlacement = "home"
    error_code: str = Field(min_length=1, max_length=100)
    error_message: str | None = Field(default=None, max_length=500)
    generated_at: str | None = None
    expires_at: str | None = None

    @field_validator("card_key", "error_code", "error_message")
    @classmethod
    def validate_snapshot_error_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("错误字段不能为空")
        return normalized


class PluginDashboardCardSnapshotRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    card_key: str
    placement: PluginDashboardCardPlacement
    state: PluginDashboardCardSnapshotState
    title: str | None = None
    subtitle: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    actions: list[HomeDashboardCardActionRead] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    generated_at: str | None = None
    expires_at: str | None = None
    created_at: str
    updated_at: str


class MemberDashboardLayoutItem(BaseModel):
    card_ref: str = Field(min_length=1, max_length=255)
    visible: bool = True
    order: int = Field(default=0, ge=0, le=100000)
    size: PluginDashboardCardSize
    height: PluginDashboardCardHeight = "regular"

    @field_validator("card_ref")
    @classmethod
    def validate_card_ref(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("card_ref 不能为空")
        return normalized


class MemberDashboardLayoutPayload(BaseModel):
    version: int = Field(default=0, ge=0)
    items: list[MemberDashboardLayoutItem] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def validate_layout_items(cls, value: list[MemberDashboardLayoutItem]) -> list[MemberDashboardLayoutItem]:
        seen_card_refs: set[str] = set()
        for item in value:
            if item.card_ref in seen_card_refs:
                raise ValueError(f"layout.items 里不能有重复 card_ref: {item.card_ref}")
            seen_card_refs.add(item.card_ref)
        return value


class MemberDashboardLayoutUpdateRequest(BaseModel):
    items: list[MemberDashboardLayoutItem] = Field(default_factory=list)


class MemberDashboardLayoutRead(BaseModel):
    member_id: str
    placement: PluginDashboardCardPlacement
    layout_version: int = Field(default=0, ge=0)
    items: list[MemberDashboardLayoutItem] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class HomeDashboardCardRead(BaseModel):
    card_ref: str
    source_type: Literal["builtin", "plugin"]
    template_type: PluginDashboardCardTemplateType
    size: PluginDashboardCardSize
    state: HomeDashboardCardState
    title: str
    subtitle: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    actions: list[HomeDashboardCardActionRead] = Field(default_factory=list)


class HomeDashboardRead(BaseModel):
    household_id: str
    member_id: str
    member_name: str
    member_nickname: str | None = None
    layout_version: int = Field(default=0, ge=0)
    cards: list[HomeDashboardCardRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PluginMountBase(BaseModel):
    source_type: Literal["third_party"] = "third_party"
    install_method: PluginInstallMethod = "local"
    execution_backend: Literal["subprocess_runner"] = "subprocess_runner"
    plugin_root: str = Field(min_length=1)
    manifest_path: str | None = None
    python_path: str = Field(min_length=1)
    working_dir: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    stdout_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    stderr_limit_bytes: int = Field(default=65536, ge=1024, le=1048576)
    enabled: bool = True

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        normalized = _normalize_plugin_source_type(value)
        return "third_party" if normalized is None else normalized

    @field_validator("install_method", mode="before")
    @classmethod
    def normalize_install_method(cls, value: str | None) -> str | None:
        normalized = _normalize_plugin_install_method(value)
        return "local" if normalized is None else normalized


class PluginMountCreate(PluginMountBase):
    pass


class PluginMountUpdate(BaseModel):
    source_type: Literal["third_party"] | None = None
    install_method: PluginInstallMethod | None = None
    python_path: str | None = None
    working_dir: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    stdout_limit_bytes: int | None = Field(default=None, ge=1024, le=1048576)
    stderr_limit_bytes: int | None = Field(default=None, ge=1024, le=1048576)
    enabled: bool | None = None

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        return _normalize_plugin_source_type(value)

    @field_validator("install_method", mode="before")
    @classmethod
    def normalize_install_method(cls, value: str | None) -> str | None:
        return _normalize_plugin_install_method(value)


class PluginMountRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    name: str
    version: str
    types: list[PluginManifestType]
    permissions: list[str]
    risk_level: RiskLevel
    triggers: list[str]
    entrypoints: PluginManifestEntrypoints
    capabilities: PluginManifestCapabilities = Field(default_factory=PluginManifestCapabilities)
    dashboard_cards: list[PluginManifestDashboardCardSpec] = Field(default_factory=list)
    config_specs: list[PluginManifestConfigSpec] = Field(default_factory=list)
    locales: list[PluginManifestLocaleSpec] = Field(default_factory=list)
    source_type: Literal["third_party"]
    install_method: PluginInstallMethod
    execution_backend: Literal["subprocess_runner"] = "subprocess_runner"
    manifest_path: str
    plugin_root: str
    python_path: str
    working_dir: str | None = None
    timeout_seconds: int
    stdout_limit_bytes: int
    stderr_limit_bytes: int
    enabled: bool
    created_at: str
    updated_at: str

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        normalized = _normalize_plugin_source_type(value)
        return "third_party" if normalized is None else normalized

    @field_validator("install_method", mode="before")
    @classmethod
    def normalize_install_method(cls, value: str | None) -> str | None:
        normalized = _normalize_plugin_install_method(value)
        return "local" if normalized is None else normalized


PluginPackageInstallAction = Literal["installed", "upgraded", "reinstalled"]


class PluginPackageInstallRead(BaseModel):
    household_id: str
    plugin_id: str
    plugin_name: str
    version: str
    previous_version: str | None = None
    install_action: PluginPackageInstallAction
    overwritten: bool = False
    enabled: bool
    source_type: Literal["third_party"] = "third_party"
    install_method: Literal["local"] = "local"
    execution_backend: Literal["subprocess_runner"] = "subprocess_runner"
    plugin_root: str
    manifest_path: str
    message: str


class PluginJobCreate(BaseModel):
    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1, max_length=64)
    plugin_type: PluginType
    trigger: str = Field(min_length=1, max_length=50)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    payload_summary: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    source_task_definition_id: str | None = Field(default=None, min_length=1)
    source_task_run_id: str | None = Field(default=None, min_length=1)
    initial_status: Literal["queued", "waiting_response"] = "queued"
    max_attempts: int = Field(default=1, ge=1, le=20)
    retry_after_at: str | None = None
    response_deadline_at: str | None = None


class PluginJobAttemptRead(BaseModel):
    id: str
    job_id: str
    attempt_no: int
    status: PluginJobAttemptStatus
    worker_id: str | None = None
    started_at: str
    finished_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    output_summary: Any | None = None


class PluginJobNotificationRead(BaseModel):
    id: str
    job_id: str
    notification_type: PluginJobNotificationType
    channel: PluginJobNotificationChannel
    payload: Any
    delivered_at: str | None = None
    created_at: str


class PluginJobResponseCreate(BaseModel):
    action: PluginJobResponseAction
    actor_type: PluginJobActorType
    actor_id: str | None = None
    payload: dict[str, Any] | None = None


class PluginJobResponseRead(BaseModel):
    id: str
    job_id: str
    action: PluginJobResponseAction
    actor_type: PluginJobActorType
    actor_id: str | None = None
    payload: Any | None = None
    created_at: str


class PluginJobRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    plugin_type: PluginType
    trigger: str
    status: PluginJobStatus
    request_payload: Any
    payload_summary: Any | None = None
    idempotency_key: str | None = None
    source_task_definition_id: str | None = None
    source_task_run_id: str | None = None
    current_attempt: int
    max_attempts: int
    last_error_code: str | None = None
    last_error_message: str | None = None
    retry_after_at: str | None = None
    response_deadline_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str
    created_at: str


class PluginJobNotificationSummaryRead(BaseModel):
    id: str
    notification_type: PluginJobNotificationType
    channel: PluginJobNotificationChannel
    delivered_at: str | None = None
    created_at: str
    payload: Any


class PluginJobDetailRead(BaseModel):
    job: PluginJobRead
    latest_attempt: PluginJobAttemptRead | None = None
    allowed_actions: list[PluginJobResponseAction] = Field(default_factory=list)
    recent_notifications: list[PluginJobNotificationSummaryRead] = Field(default_factory=list)


class PluginJobListItemRead(BaseModel):
    job: PluginJobRead
    allowed_actions: list[PluginJobResponseAction] = Field(default_factory=list)


class PluginJobListRead(BaseModel):
    items: list[PluginJobListItemRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class PluginJobEnqueueRequest(BaseModel):
    plugin_id: str = Field(min_length=1, max_length=64)
    plugin_type: PluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="manual", min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    payload_summary: dict[str, Any] | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=20)


class PluginExecutionRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    plugin_type: PluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="manual", min_length=1, max_length=50)
    execution_backend: PluginExecutionBackend | None = None


class PluginExecutionResult(BaseModel):
    run_id: str
    plugin_id: str
    plugin_type: PluginType
    execution_backend: PluginExecutionBackend | None = None
    success: bool
    trigger: str
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None


class PluginRawRecordCreate(BaseModel):
    household_id: str = Field(min_length=1)
    plugin_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    trigger: str = Field(min_length=1, max_length=50)
    record_type: str = Field(min_length=1, max_length=50)
    source_ref: str | None = Field(default=None, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    captured_at: str | None = None


class PluginRawRecordRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    run_id: str
    trigger: str
    record_type: str
    source_ref: str | None = None
    payload: Any | None = None
    captured_at: str
    created_at: str


PluginRunStatus = Literal["running", "success", "failed"]


class PluginRunRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    plugin_type: PluginType
    trigger: str
    status: PluginRunStatus
    raw_record_count: int
    memory_card_count: int
    error_code: str | None = None
    error_message: str | None = None
    started_at: str
    finished_at: str | None = None
    created_at: str


class PluginSyncPipelineResult(BaseModel):
    run: PluginRunRead
    execution: PluginExecutionResult
    raw_records: list[PluginRawRecordRead] = Field(default_factory=list)
    written_memory_cards: list[dict[str, Any]] = Field(default_factory=list)


AgentCallablePluginType = Literal["integration", "agent-skill"]


class AgentPluginInvokeRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    plugin_type: AgentCallablePluginType
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="agent", min_length=1, max_length=50)


class AgentPluginInvokeResult(BaseModel):
    agent_id: str
    agent_name: str
    plugin_id: str
    plugin_type: AgentCallablePluginType
    run_id: str
    success: bool
    trigger: str
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    queued: bool = False
    job_id: str | None = None
    job_status: PluginJobStatus | None = None


class AgentActionPluginInvokeRequest(BaseModel):
    plugin_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    trigger: str = Field(default="agent-action", min_length=1, max_length=50)


class AgentActionPluginInvokeResult(BaseModel):
    agent_id: str
    agent_name: str
    plugin_id: str
    plugin_type: Literal["action"] = "action"
    run_id: str
    success: bool
    trigger: str
    risk_level: RiskLevel
    authorization_status: Literal["allowed", "denied", "confirmation_required"]
    confirmation_request_id: str | None = None
    started_at: str
    finished_at: str
    output: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    queued: bool = False
    job_id: str | None = None
    job_status: PluginJobStatus | None = None


class AgentActionConfirmationRead(BaseModel):
    confirmation_request_id: str
    household_id: str
    plugin_id: str
    risk_level: RiskLevel
    status: Literal["pending", "confirmed", "consumed"]
    trigger: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
