import type {
  AccountWithBinding,
  ContextConfigRead,
  ContextOverviewRead,
  Device as CoreDevice,
  Household,
  HouseholdSetupStatus,
  LoginResponse,
  Member,
  MemberPreference,
  MemberRelationship,
  PaginatedResponse,
  PluginLocale,
  PluginLocaleListResponse,
  RegionNode,
  RegionSelection,
  ReminderOverviewRead,
  Room,
} from '@familyclaw/user-core';

export type {
  AccountWithBinding,
  ContextConfigRead,
  ContextOverviewRead,
  Household,
  HouseholdSetupStatus,
  LoginResponse,
  Member,
  MemberPreference,
  MemberRelationship,
  PaginatedResponse,
  PluginLocale,
  PluginLocaleListResponse,
  RegionNode,
  RegionSelection,
  ReminderOverviewRead,
  Room,
};

export type Device = Omit<CoreDevice, 'status'> & {
  status: CoreDevice['status'] | 'disabled';
};

export type AiProviderFieldOption = {
  label: string;
  value: string;
};

export type SystemVersionRead = {
  current_version: string;
  build_channel: 'stable' | 'preview' | 'development';
  build_time: string | null;
  release_notes_url: string | null;
  update_status: 'up_to_date' | 'update_available' | 'check_unavailable';
  latest_version: string | null;
  latest_release_notes_url: string | null;
  latest_release_title: string | null;
  latest_release_summary: string | null;
  latest_release_published_at: string | null;
};

export type AiProviderField = {
  key: string;
  label: string;
  field_type: 'text' | 'secret' | 'number' | 'select' | 'boolean';
  required: boolean;
  placeholder: string | null;
  help_text: string | null;
  default_value: string | number | boolean | null;
  options: AiProviderFieldOption[];
};

export type AiCapability = 'text' | 'intent_recognition' | 'vision' | 'audio_generation' | 'audio_recognition' | 'image_generation';
export type AiProviderModelType = 'llm' | 'embedding' | 'vision' | 'speech' | 'image';

export type AiProviderAdapter = {
  plugin_id: string;
  plugin_name: string;
  adapter_code: string;
  display_name: string;
  description: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  default_privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  default_supported_capabilities: AiCapability[];
  supported_model_types: AiProviderModelType[];
  llm_workflow: string;
  supports_model_discovery: boolean;
  field_schema: AiProviderField[];
};

export type AiProviderDiscoveredModel = {
  id: string;
  label: string;
};

export type AiProviderModelDiscoveryPayload = {
  values: Record<string, unknown>;
};

export type AiProviderModelDiscoveryResult = {
  adapter_code: string;
  models: AiProviderDiscoveredModel[];
};

export type AiProviderProfile = {
  id: string;
  provider_code: string;
  display_name: string;
  plugin_id: string | null;
  plugin_enabled: boolean | null;
  plugin_disabled_reason: string | null;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: AiCapability[];
  privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type AiProviderProfileCreatePayload = {
  provider_code?: string | null;
  display_name: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: AiCapability[];
  privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
};

export type AiProviderProfileUpdatePayload = Partial<Omit<AiProviderProfileCreatePayload, 'provider_code'>>;

export type AiCapabilityRoute = {
  id: string;
  capability: AiCapability;
  household_id: string | null;
  primary_provider_profile_id: string | null;
  fallback_provider_profile_ids: string[];
  routing_mode: string;
  timeout_ms: number;
  max_retry_count: number;
  allow_remote: boolean;
  prompt_policy: Record<string, unknown>;
  response_policy: Record<string, unknown>;
  enabled: boolean;
  updated_at: string;
};

export type AiCapabilityRouteUpsertPayload = {
  capability: AiCapability;
  household_id: string | null;
  primary_provider_profile_id: string | null;
  fallback_provider_profile_ids: string[];
  routing_mode: string;
  timeout_ms: number;
  max_retry_count: number;
  allow_remote: boolean;
  prompt_policy: Record<string, unknown>;
  response_policy: Record<string, unknown>;
  enabled: boolean;
};

export type AgentType = 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
export type AgentStatus = 'draft' | 'active' | 'inactive';

export type AgentModelBinding = {
  capability: AiCapability;
  provider_profile_id: string;
};

export type AgentSkillModelBinding = {
  plugin_id: string;
  capability: AiCapability;
  provider_profile_id: string;
};

export type AgentRuntimePolicy = {
  agent_id: string;
  conversation_enabled: boolean;
  default_entry: boolean;
  routing_tags: string[];
  memory_scope: Record<string, unknown> | null;
  autonomous_action_policy: {
    memory: 'ask' | 'notify' | 'auto';
    config: 'ask' | 'notify' | 'auto';
    action: 'ask' | 'notify' | 'auto';
  };
  model_bindings: AgentModelBinding[];
  agent_skill_model_bindings: AgentSkillModelBinding[];
  updated_at: string;
};

export type AgentMemberCognition = {
  id: string;
  agent_id: string;
  member_id: string;
  display_address: string | null;
  closeness_level: number;
  service_priority: number;
  communication_style: string | null;
  care_notes: Record<string, unknown> | null;
  prompt_notes: string | null;
  version: number;
  updated_at: string;
};

export type AgentSoulProfile = {
  id: string;
  agent_id: string;
  version: number;
  self_identity: string;
  role_summary: string;
  intro_message: string | null;
  speaking_style: string | null;
  personality_traits: string[];
  service_focus: string[];
  service_boundaries: Record<string, unknown> | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
};

export type AgentSummary = {
  id: string;
  household_id: string;
  code: string;
  agent_type: AgentType;
  display_name: string;
  status: AgentStatus;
  is_primary: boolean;
  sort_order: number;
  summary: string | null;
  conversation_enabled: boolean;
  default_entry: boolean;
  updated_at: string;
};

export type AgentDetail = {
  id: string;
  household_id: string;
  code: string;
  agent_type: AgentType;
  display_name: string;
  status: AgentStatus;
  is_primary: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  soul: AgentSoulProfile | null;
  member_cognitions: AgentMemberCognition[];
  runtime_policy: AgentRuntimePolicy | null;
};

export type AgentListResponse = {
  household_id: string;
  items: AgentSummary[];
};

export type VoiceprintEnrollmentStatus = 'pending' | 'recording' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type VoiceprintConversationMode = 'public' | 'voiceprint_member';
export type VoiceprintMemberSummaryStatus = 'not_enrolled' | 'pending' | 'active' | 'failed' | 'disabled';

export type VoiceprintEnrollmentRead = {
  id: string;
  household_id: string;
  member_id: string;
  terminal_id: string;
  status: VoiceprintEnrollmentStatus;
  expected_phrase: string | null;
  sample_goal: number;
  sample_count: number;
  expires_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type PendingVoiceprintEnrollmentRead = {
  enrollment_id: string;
  target_member_id: string;
  expected_phrase: string | null;
  sample_goal: number;
  sample_count: number;
  expires_at: string | null;
};

export type HouseholdVoiceprintMemberSummaryRead = {
  member_id: string;
  member_name: string;
  member_role: Member['role'];
  status: VoiceprintMemberSummaryStatus;
  sample_count: number;
  updated_at: string | null;
  pending_enrollment_id: string | null;
  active_profile_id: string | null;
  error_message: string | null;
};

export type HouseholdVoiceprintSummaryRead = {
  household_id: string;
  terminal_id: string;
  voiceprint_identity_enabled: boolean;
  conversation_mode: VoiceprintConversationMode;
  pending_enrollment: PendingVoiceprintEnrollmentRead | null;
  members: HouseholdVoiceprintMemberSummaryRead[];
};

export type ChannelAccountStatus = 'draft' | 'active' | 'degraded' | 'disabled';
export type ChannelConnectionMode = 'webhook' | 'polling' | 'websocket';
export type ChannelBindingStatus = 'active' | 'disabled';
export type ChannelInboundEventStatus = 'received' | 'matched' | 'dispatched' | 'ignored' | 'failed';
export type ChannelDeliveryStatus = 'pending' | 'sent' | 'failed' | 'skipped';
export type ChannelDeliveryType = 'reply' | 'notice' | 'error';

export type ChannelAccountRead = {
  id: string;
  household_id: string;
  plugin_id: string;
  platform_code: string;
  account_code: string;
  display_name: string;
  connection_mode: ChannelConnectionMode;
  config: Record<string, unknown>;
  status: ChannelAccountStatus;
  last_probe_status: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_inbound_at: string | null;
  last_outbound_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChannelAccountCreate = {
  plugin_id: string;
  account_code?: string | null;
  display_name: string;
  connection_mode: ChannelConnectionMode;
  config?: Record<string, unknown>;
  status?: ChannelAccountStatus;
};

export type ChannelAccountUpdate = {
  display_name?: string;
  connection_mode?: ChannelConnectionMode;
  config?: Record<string, unknown>;
  status?: ChannelAccountStatus;
};

export type MemberChannelBindingRead = {
  id: string;
  household_id: string;
  member_id: string;
  channel_account_id: string;
  platform_code: string;
  external_user_id: string;
  external_chat_id: string | null;
  display_hint: string | null;
  binding_status: ChannelBindingStatus;
  created_at: string;
  updated_at: string;
};

export type MemberChannelBindingCreate = {
  channel_account_id: string;
  member_id: string;
  external_user_id: string;
  external_chat_id?: string | null;
  display_hint?: string | null;
  binding_status?: ChannelBindingStatus;
};

export type MemberChannelBindingUpdate = {
  external_user_id?: string;
  external_chat_id?: string | null;
  display_hint?: string | null;
  binding_status?: ChannelBindingStatus;
};

export type ChannelBindingCandidateRead = {
  external_user_id: string;
  external_chat_id: string | null;
  sender_display_name: string | null;
  username: string | null;
  chat_type: 'direct' | 'group';
  last_message_text: string | null;
  last_seen_at: string;
  inbound_event_id: string;
  platform_code: string;
  channel_account_id: string;
};

export type ChannelDeliveryFailureSummaryRead = {
  channel_account_id: string;
  platform_code: string;
  recent_failure_count: number;
  last_delivery_id: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_failed_at: string | null;
};

export type ChannelDeliveryRead = {
  id: string;
  household_id: string;
  channel_account_id: string;
  platform_code: string;
  conversation_session_id: string | null;
  assistant_message_id: string | null;
  external_conversation_key: string;
  delivery_type: ChannelDeliveryType;
  request_payload: Record<string, unknown>;
  provider_message_ref: string | null;
  status: ChannelDeliveryStatus;
  attempt_count: number;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ChannelInboundEventRead = {
  id: string;
  household_id: string;
  channel_account_id: string;
  platform_code: string;
  external_event_id: string;
  event_type: string;
  external_user_id: string | null;
  external_conversation_key: string | null;
  normalized_payload: Record<string, unknown>;
  status: ChannelInboundEventStatus;
  conversation_session_id: string | null;
  error_code: string | null;
  error_message: string | null;
  received_at: string;
  processed_at: string | null;
};

export type ChannelAccountStatusRead = {
  account: ChannelAccountRead;
  recent_failure_summary: ChannelDeliveryFailureSummaryRead;
  latest_delivery: ChannelDeliveryRead | null;
  latest_inbound_event: ChannelInboundEventRead | null;
  latest_failed_inbound_event: ChannelInboundEventRead | null;
  recent_delivery_count: number;
  recent_inbound_count: number;
};

export type PluginSourceType = 'builtin' | 'official' | 'third_party';
export type PluginRiskLevel = 'low' | 'medium' | 'high';
export type PluginVersionGovernanceSourceType = 'builtin' | 'marketplace' | 'manual';
export type PluginVersionCompatibilityStatus = 'compatible' | 'host_too_old' | 'unknown';
export type PluginVersionUpdateState =
  | 'up_to_date'
  | 'upgrade_available'
  | 'upgrade_blocked'
  | 'installed_newer_than_market'
  | 'not_market_managed'
  | 'unknown';
export type PluginVersionOperationType = 'upgrade' | 'rollback';
export type PluginManifestType =
  | 'connector'
  | 'memory-ingestor'
  | 'action'
  | 'agent-skill'
  | 'channel'
  | 'locale-pack'
  | 'region-provider'
  | 'theme-pack'
  | 'ai-provider';
export type PluginConfigScopeType = 'plugin' | 'channel_account' | 'device' | 'integration_instance';
export type PluginConfigFieldType = 'string' | 'text' | 'integer' | 'number' | 'boolean' | 'enum' | 'multi_enum' | 'secret' | 'json';
export type PluginConfigWidgetType = 'input' | 'password' | 'textarea' | 'switch' | 'select' | 'multi_select' | 'json_editor';
export type PluginConfigVisibleOperator = 'equals' | 'not_equals' | 'in' | 'truthy';
export type PluginConfigDynamicOptionSourceType = 'region_provider_list' | 'region_catalog_children';
export type RegionCatalogAdminLevel = 'province' | 'city' | 'district';

export type PluginConfigEnumOption = {
  label: string;
  label_key?: string | null;
  value: string;
};

export type PluginManifestConfigFieldOptionSource = {
  source: PluginConfigDynamicOptionSourceType;
  country_code?: string | null;
  provider_code?: string | null;
  provider_field?: string | null;
  parent_field?: string | null;
  admin_level?: RegionCatalogAdminLevel | null;
};

export type PluginManifestConfigField = {
  key: string;
  label: string;
  label_key?: string | null;
  type: PluginConfigFieldType;
  required: boolean;
  description?: string | null;
  description_key?: string | null;
  default?: unknown;
  enum_options?: PluginConfigEnumOption[];
  option_source?: PluginManifestConfigFieldOptionSource | null;
  depends_on?: string[];
  clear_on_dependency_change?: boolean;
  min_length?: number | null;
  max_length?: number | null;
  minimum?: number | null;
  maximum?: number | null;
  pattern?: string | null;
  nullable?: boolean;
};

export type PluginManifestVisibilityRule = {
  field: string;
  operator: PluginConfigVisibleOperator;
  value?: unknown;
};

export type PluginManifestFieldUiSchema = {
  widget?: PluginConfigWidgetType | null;
  placeholder?: string | null;
  placeholder_key?: string | null;
  help_text?: string | null;
  help_text_key?: string | null;
  visible_when?: PluginManifestVisibilityRule[];
};

export type PluginManifestUiSection = {
  id: string;
  title: string;
  title_key?: string | null;
  description?: string | null;
  description_key?: string | null;
  fields: string[];
};

export type PluginManifestConfigSpec = {
  scope_type: PluginConfigScopeType;
  title: string;
  title_key?: string | null;
  description?: string | null;
  description_key?: string | null;
  schema_version: number;
  config_schema: {
    fields: PluginManifestConfigField[];
  };
  ui_schema: {
    sections: PluginManifestUiSection[];
    field_order?: string[];
    submit_text?: string | null;
    submit_text_key?: string | null;
    widgets?: Record<string, PluginManifestFieldUiSchema>;
  };
};

export type PluginConfigState = 'unconfigured' | 'configured' | 'invalid';

export type PluginConfigSecretFieldRead = {
  has_value: boolean;
  masked: string | null;
};

export type PluginConfigView = {
  scope_type: PluginConfigScopeType;
  scope_key: string;
  schema_version: number;
  state: PluginConfigState;
  values: Record<string, unknown>;
  secret_fields: Record<string, PluginConfigSecretFieldRead>;
  field_errors: Record<string, string>;
};

export type PluginConfigFormRead = {
  plugin_id: string;
  config_spec: PluginManifestConfigSpec;
  view: PluginConfigView;
};

export type PluginConfigResolveRequest = {
  scope_type: PluginConfigScopeType;
  scope_key?: string | null;
  values: Record<string, unknown>;
};

export type PluginVersionGovernanceRead = {
  source_type: PluginVersionGovernanceSourceType;
  installed_version: string | null;
  declared_version: string | null;
  latest_version: string | null;
  latest_compatible_version: string | null;
  compatibility_status: PluginVersionCompatibilityStatus;
  update_state: PluginVersionUpdateState;
  blocked_reason: string | null;
};

export type PluginRegistryItem = {
  id: string;
  name: string;
  version: string;
  installed_version?: string | null;
  compatibility?: Record<string, unknown> | null;
  update_state?: string | null;
  types: PluginManifestType[];
  permissions: string[];
  risk_level: PluginRiskLevel;
  triggers: string[];
  base_enabled: boolean;
  household_enabled: boolean | null;
  enabled: boolean;
  disabled_reason: string | null;
  manifest_path: string;
  entrypoints: {
    connector?: string | null;
    memory_ingestor?: string | null;
    action?: string | null;
    agent_skill?: string | null;
    channel?: string | null;
    region_provider?: string | null;
  };
  capabilities: {
    context_reads?: {
      household_region_context?: boolean;
    } | null;
    device_detail_tabs?: Array<{
      tab_key: string;
      title: string;
      description?: string | null;
      config_scope_type: 'device';
    }>;
    channel?: {
      ui?: {
        account_config_fields?: Array<{
          key: string;
          label: string;
          type: 'text' | 'password';
          required: boolean;
          placeholder?: string | null;
          help_text?: string | null;
        }>;
        binding?: {
          identity_label?: string | null;
          identity_placeholder?: string | null;
          identity_help_text?: string | null;
          chat_label?: string | null;
          chat_placeholder?: string | null;
          chat_help_text?: string | null;
          candidate_title?: string | null;
          candidate_help_text?: string | null;
        } | null;
      } | null;
      platform_code?: string | null;
      inbound_modes?: string[];
      delivery_modes?: string[];
      supports_member_binding?: boolean;
      supports_group_chat?: boolean;
      supports_threading?: boolean;
    } | null;
    region_provider?: {
      provider_code?: string | null;
      country_codes?: string[];
    } | null;
    theme_pack?: {
      theme_id: string;
      display_name: string;
      description?: string | null;
      tokens_resource: string;
      preview?: Record<string, unknown>;
      fallback_theme_id?: string | null;
    } | null;
    ai_provider?: {
      adapter_code: string;
      display_name: string;
      field_schema: Array<Record<string, unknown>>;
      supported_model_types: string[];
      llm_workflow: string;
      runtime_capability?: Record<string, unknown>;
    } | null;
  };
  config_specs?: PluginManifestConfigSpec[];
  locales: Array<{
    id: string;
    label: string;
    native_label: string;
    resource: string;
    fallback?: string | null;
  }>;
  schedule_templates: Array<{
    code: string;
    name: string;
    description?: string | null;
    default_definition: Record<string, unknown>;
    enabled_by_default: boolean;
  }>;
  source_type: PluginSourceType;
  install_status?: string | null;
  config_status?: PluginConfigState | null;
  marketplace_instance_id?: string | null;
  version_governance?: PluginVersionGovernanceRead | null;
};

export type PluginRegistrySnapshot = {
  items: PluginRegistryItem[];
};

export type PluginStateUpdateRequest = {
  enabled: boolean;
};

export type PluginPackageInstallAction = 'installed' | 'upgraded' | 'reinstalled';

export type PluginPackageInstallRead = {
  household_id: string;
  plugin_id: string;
  plugin_name: string;
  version: string;
  previous_version: string | null;
  install_action: PluginPackageInstallAction;
  overwritten: boolean;
  enabled: boolean;
  source_type: PluginSourceType;
  execution_backend: string | null;
  plugin_root: string;
  manifest_path: string;
  message: string;
};

export type IntegrationResourceType = 'device' | 'entity' | 'helper';
export type IntegrationInstanceStatus = 'draft' | 'active' | 'degraded' | 'disabled' | 'deleted';
export type IntegrationResourceStatus = 'active' | 'offline' | 'inactive' | 'degraded' | 'disabled' | 'deleted' | 'pending';
export type IntegrationActionType = 'configure' | 'sync' | 'repair' | 'enable' | 'disable' | 'delete' | 'claim';
export type IntegrationDiscoveryStatus = 'pending' | 'claimed' | 'dismissed';

export type IntegrationResourceSupport = {
  device: boolean;
  entity: boolean;
  helper: boolean;
};

export type IntegrationSyncState = {
  last_synced_at: string | null;
  last_job_id: string | null;
  last_job_status: string | null;
  pending_job_id: string | null;
};

export type IntegrationErrorSummary = {
  code: string;
  message: string;
  detail?: string | null;
  occurred_at?: string | null;
};

export type IntegrationActionRead = {
  action: IntegrationActionType;
  label: string;
  destructive: boolean;
  disabled: boolean;
  disabled_reason?: string | null;
};

export type IntegrationResourceCounts = {
  device: number;
  entity: number;
  helper: number;
};

export type IntegrationConfigBindingRead = {
  scope_type: PluginConfigScopeType;
  scope_key: string;
  state: PluginConfigState;
  form_available: boolean;
  config_spec?: PluginManifestConfigSpec | null;
};

export type IntegrationCatalogItem = {
  plugin_id: string;
  name: string;
  description?: string | null;
  icon_url?: string | null;
  source_type: PluginSourceType;
  risk_level: PluginRiskLevel;
  resource_support: IntegrationResourceSupport;
  config_schema_available: boolean;
  config_spec?: PluginManifestConfigSpec | null;
  already_added: boolean;
  supported_actions: IntegrationActionType[];
  tags: string[];
};

export type IntegrationInstance = {
  id: string;
  household_id: string;
  plugin_id: string;
  display_name: string;
  description?: string | null;
  icon_url?: string | null;
  source_type: PluginSourceType;
  status: IntegrationInstanceStatus;
  config_state: PluginConfigState;
  resource_support: IntegrationResourceSupport;
  resource_counts: IntegrationResourceCounts;
  sync_state: IntegrationSyncState;
  config_bindings: IntegrationConfigBindingRead[];
  allowed_actions: IntegrationActionRead[];
  last_error?: IntegrationErrorSummary | null;
  created_at: string;
  updated_at: string;
};

export type IntegrationResource = {
  id: string;
  household_id: string;
  integration_instance_id: string;
  plugin_id: string;
  resource_type: IntegrationResourceType;
  resource_key: string;
  name: string;
  description?: string | null;
  category?: string | null;
  status: IntegrationResourceStatus;
  room_id?: string | null;
  room_name?: string | null;
  device_id?: string | null;
  parent_resource_id?: string | null;
  capabilities: Record<string, unknown>;
  metadata: Record<string, unknown>;
  last_error?: IntegrationErrorSummary | null;
  updated_at: string;
};

export type IntegrationDiscoveryItem = {
  id: string;
  household_id: string | null;
  plugin_id: string;
  integration_instance_id?: string | null;
  discovery_type: string;
  status: IntegrationDiscoveryStatus;
  title: string;
  subtitle?: string | null;
  resource_type: IntegrationResourceType;
  suggested_room_id?: string | null;
  capability_tags: string[];
  metadata: Record<string, unknown>;
  discovered_at: string;
  updated_at: string;
};

export type IntegrationCatalogListRead = {
  household_id: string;
  items: IntegrationCatalogItem[];
};

export type IntegrationInstanceListRead = {
  household_id: string;
  items: IntegrationInstance[];
};

export type IntegrationResourceListRead = {
  household_id: string;
  resource_type: IntegrationResourceType;
  items: IntegrationResource[];
};

export type IntegrationDiscoveryListRead = {
  household_id: string;
  items: IntegrationDiscoveryItem[];
};

export type IntegrationPageViewModel = {
  household_id: string;
  catalog: IntegrationCatalogItem[];
  instances: IntegrationInstance[];
  discoveries: IntegrationDiscoveryItem[];
  resources: Record<IntegrationResourceType, IntegrationResource[]>;
};

export type IntegrationInstanceCreateRequest = {
  household_id: string;
  plugin_id: string;
  display_name: string;
  config: Record<string, unknown>;
  clear_fields: string[];
  clear_secret_fields: string[];
};

export type IntegrationInstanceUpdateRequest = {
  display_name: string;
  config: Record<string, unknown>;
  clear_fields: string[];
  clear_secret_fields: string[];
};

export type IntegrationInstanceActionRequest = {
  action: IntegrationActionType;
  payload: Record<string, unknown>;
};

export type IntegrationActionResult = {
  action: IntegrationActionType;
  execution_mode: 'immediate' | 'queued';
  message: string | null;
  instance: IntegrationInstance | null;
  config_form: PluginConfigFormRead | null;
  job: PluginJobRead | null;
  output: Record<string, unknown>;
};

export type DeviceEntityControlKind = 'none' | 'toggle' | 'range' | 'action_set';

export type DeviceEntityControlOption = {
  label: string;
  value: string;
  action: string;
  params: Record<string, unknown>;
};

export type DeviceEntityControl = {
  kind: DeviceEntityControlKind;
  value: unknown;
  unit: string | null;
  min_value: number | null;
  max_value: number | null;
  step: number | null;
  action: string | null;
  action_on: string | null;
  action_off: string | null;
  options: DeviceEntityControlOption[];
  disabled: boolean;
  disabled_reason: string | null;
};

export type DeviceEntity = {
  device_id: string;
  integration_instance_id: string | null;
  entity_id: string;
  name: string;
  domain: string;
  state: string;
  state_display: string;
  unit: string | null;
  favorite: boolean;
  read_only: boolean;
  control: DeviceEntityControl;
  metadata: Record<string, unknown>;
  updated_at: string;
};

export type DeviceEntityListRead = {
  device: Device;
  view: 'favorites' | 'all';
  items: DeviceEntity[];
};

export type DeviceDetailCapabilityRead = {
  supports_voice_terminal: boolean;
  supports_voiceprint: boolean;
  adapter_type: string | null;
  plugin_id: string | null;
  vendor_code: string | null;
  capability_tags: string[];
};

export type DeviceDetailBuiltinTabRead = {
  key: 'voiceprint';
};

export type DeviceDetailPluginTabRead = {
  tab_key: string;
  title: string;
  description: string | null;
  plugin_id: string;
  plugin_name: string;
  config_form: PluginConfigFormRead;
};

export type DeviceDetailViewRead = {
  device: Device;
  capabilities: DeviceDetailCapabilityRead;
  builtin_tabs: DeviceDetailBuiltinTabRead[];
  plugin_tabs: DeviceDetailPluginTabRead[];
};

export type DeviceActionExecuteRequest = {
  household_id: string;
  device_id: string;
  entity_id?: string;
  action: string;
  params: Record<string, unknown>;
  reason?: string;
  confirm_high_risk?: boolean;
  idempotency_key?: string | null;
};

export type DeviceActionExecuteResponse = {
  household_id: string;
  device: Device;
  action: string;
  platform: string;
  service_domain: string;
  service_name: string;
  entity_id: string;
  params: Record<string, unknown>;
  result: 'success';
  executed_at: string;
};

export type DeviceActionLogRead = {
  id: string;
  action: string;
  target_type: string;
  result: string;
  actor_type: string;
  actor_id: string | null;
  entity_id: string | null;
  entity_name: string | null;
  message: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type DeviceActionLogListRead = {
  device: Device;
  items: DeviceActionLogRead[];
  page: number;
  page_size: number;
  total: number;
};

export type PluginJobRead = {
  id: string;
  household_id: string;
  plugin_id: string;
  plugin_type: string;
  trigger: string;
  status: 'queued' | 'running' | 'retry_waiting' | 'waiting_response' | 'succeeded' | 'failed' | 'cancelled';
  request_payload: unknown;
  payload_summary: unknown | null;
  idempotency_key: string | null;
  current_attempt: number;
  max_attempts: number;
  last_error_code: string | null;
  last_error_message: string | null;
  retry_after_at: string | null;
  response_deadline_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
  created_at: string;
};

export type PluginJobListItemRead = {
  job: PluginJobRead;
  allowed_actions: Array<'retry' | 'confirm' | 'cancel' | 'provide_input'>;
};

export type PluginJobListRead = {
  items: PluginJobListItemRead[];
  total: number;
  page: number;
  page_size: number;
};

export type MarketplaceTrustedLevel = 'official' | 'third_party';
export type MarketplaceSyncStatus = 'idle' | 'syncing' | 'success' | 'failed';
export type MarketplaceEntrySyncStatus = 'ready' | 'invalid';
export type MarketplaceRepoProvider = 'github' | 'gitlab' | 'gitee' | 'gitea';
export type MarketplaceInstallStatus =
  | 'not_installed'
  | 'queued'
  | 'resolving'
  | 'downloading'
  | 'validating'
  | 'installing'
  | 'installed'
  | 'install_failed'
  | 'uninstalled';

export type MarketplaceSourceRead = {
  source_id: string;
  market_id: string | null;
  name: string;
  owner: string | null;
  repo_url: string;
  repo_provider: MarketplaceRepoProvider;
  api_base_url: string | null;
  mirror_repo_url: string | null;
  mirror_repo_provider: MarketplaceRepoProvider | null;
  mirror_api_base_url: string | null;
  effective_repo_url: string;
  branch: string;
  entry_root: string;
  trusted_level: MarketplaceTrustedLevel;
  enabled: boolean;
  last_sync_status: MarketplaceSyncStatus | null;
  last_sync_error: Record<string, unknown> | null;
  last_synced_at: string | null;
};

export type MarketplaceSourceCreateRequest = {
  repo_url: string;
  repo_provider?: MarketplaceRepoProvider | null;
  api_base_url?: string | null;
  branch?: string | null;
  entry_root?: string | null;
  mirror_repo_url?: string | null;
  mirror_repo_provider?: MarketplaceRepoProvider | null;
  mirror_api_base_url?: string | null;
};

export type MarketplaceSourceSyncResultRead = {
  source: MarketplaceSourceRead;
  total_entries: number;
  ready_entries: number;
  invalid_entries: number;
  errors: Array<{
    plugin_id: string;
    error_code: string;
    detail: string;
  }>;
};

export type MarketplaceRepositoryMetricAvailability = {
  stargazers_count: boolean;
  forks_count: boolean;
  subscribers_count: boolean;
  open_issues_count: boolean;
  views_count: boolean;
};

export type MarketplaceRepositoryMetrics = {
  stargazers_count: number | null;
  forks_count: number | null;
  subscribers_count: number | null;
  open_issues_count: number | null;
  views_count: number | null;
  views_period_days: number | null;
  fetched_at: string;
  availability: MarketplaceRepositoryMetricAvailability;
};

export type MarketplaceInstallStateRead = {
  instance_id: string | null;
  install_status: MarketplaceInstallStatus;
  enabled: boolean;
  config_status: PluginConfigState | null;
  installed_version: string | null;
};

export type MarketplaceVersionEntry = {
  version: string;
  git_ref: string;
  artifact_type: 'release_asset' | 'source_archive';
  artifact_url: string;
  checksum: string | null;
  published_at: string | null;
  min_app_version: string | null;
};

export type MarketplacePublisher = {
  name: string;
  url: string | null;
};

export type MarketplaceMaintainer = {
  name: string;
  url: string | null;
};

export type MarketplaceEntryInstallSpec = {
  package_root: string | null;
  requirements_path: string;
  readme_path: string;
};

export type MarketplaceCatalogItemRead = {
  source_id: string;
  plugin_id: string;
  name: string;
  summary: string;
  source_repo: string;
  readme_url: string;
  risk_level: PluginRiskLevel;
  latest_version: string;
  trusted_level: MarketplaceTrustedLevel;
  sync_status: MarketplaceEntrySyncStatus;
  sync_error: Record<string, unknown> | null;
  categories: string[];
  permissions: string[];
  repository_metrics: MarketplaceRepositoryMetrics | null;
  source_name: string;
  install_state: MarketplaceInstallStateRead;
  version_governance: PluginVersionGovernanceRead | null;
};

export type MarketplaceCatalogListRead = {
  items: MarketplaceCatalogItemRead[];
};

export type MarketplaceEntryDetailRead = {
  source: MarketplaceSourceRead;
  plugin: MarketplaceCatalogItemRead;
  manifest_path: string;
  publisher: MarketplacePublisher;
  versions: MarketplaceVersionEntry[];
  install: MarketplaceEntryInstallSpec;
  maintainers: MarketplaceMaintainer[];
  raw_entry: Record<string, unknown>;
};

export type MarketplaceInstallTaskRead = {
  task_id: string;
  household_id: string;
  source_id: string;
  plugin_id: string;
  requested_version: string | null;
  installed_version: string | null;
  install_status: MarketplaceInstallStatus;
  failure_stage: string | null;
  error_code: string | null;
  error_message: string | null;
  source_repo: string | null;
  market_repo: string | null;
  artifact_url: string | null;
  plugin_root: string | null;
  manifest_path: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type MarketplaceInstallTaskCreateRequest = {
  household_id: string;
  source_id: string;
  plugin_id: string;
  version?: string | null;
};

export type PluginVersionOperationRequest = {
  household_id: string;
  source_id: string;
  plugin_id: string;
  target_version: string;
  operation: PluginVersionOperationType;
};

export type MarketplaceInstanceRead = {
  instance_id: string;
  household_id: string;
  source_id: string;
  plugin_id: string;
  installed_version: string;
  install_status: MarketplaceInstallStatus;
  enabled: boolean;
  config_status: PluginConfigState;
  source_repo: string;
  market_repo: string;
  plugin_root: string;
  manifest_path: string;
  python_path: string;
  working_dir: string | null;
  installed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PluginVersionOperationResultRead = {
  instance: MarketplaceInstanceRead;
  governance: PluginVersionGovernanceRead;
  previous_version: string;
  target_version: string;
  state_changed: boolean;
  state_change_reason: string | null;
};
