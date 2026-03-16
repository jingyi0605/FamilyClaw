import type {
  ContextConfigRead,
  ContextOverviewRead,
  Device,
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
  ContextConfigRead,
  ContextOverviewRead,
  Device,
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

export type AiProviderFieldOption = {
  label: string;
  value: string;
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

export type AiProviderAdapter = {
  adapter_code: string;
  display_name: string;
  description: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  default_privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  default_supported_capabilities: string[];
  field_schema: AiProviderField[];
};

export type AiProviderProfile = {
  id: string;
  provider_code: string;
  display_name: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type AiProviderProfileCreatePayload = {
  provider_code: string;
  display_name: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
  api_family: 'openai_chat_completions' | 'anthropic_messages' | 'gemini_generate_content';
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: 'local_only' | 'private_cloud' | 'public_cloud';
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
};

export type AiProviderProfileUpdatePayload = Partial<Omit<AiProviderProfileCreatePayload, 'provider_code'>>;

export type AiCapabilityRoute = {
  id: string;
  capability: string;
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
  capability: string;
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

export type HomeAssistantSyncResponse = {
  household_id: string;
  created_devices: number;
  updated_devices: number;
  created_bindings: number;
  created_rooms: number;
  assigned_rooms: number;
  skipped_entities: number;
  failed_entities: number;
  devices: Device[];
  failures: Array<{ entity_id: string | null; reason: string }>;
};

export type HomeAssistantDeviceCandidate = {
  external_device_id: string;
  primary_entity_id: string;
  name: string;
  room_name: string | null;
  device_type: string;
  entity_count: number;
  already_synced: boolean;
};

export type HomeAssistantDeviceCandidatesResponse = {
  household_id: string;
  items: HomeAssistantDeviceCandidate[];
};

export type HomeAssistantConfig = {
  household_id: string;
  base_url: string | null;
  token_configured: boolean;
  sync_rooms_enabled: boolean;
  last_device_sync_at: string | null;
  updated_at: string | null;
};

export type HomeAssistantRoomSyncResponse = {
  household_id: string;
  created_rooms: number;
  matched_entities: number;
  skipped_entities: number;
  rooms: Array<{ id: string; name: string }>;
};

export type HomeAssistantRoomCandidate = {
  name: string;
  entity_count: number;
  exists_locally: boolean;
  can_sync: boolean;
};

export type HomeAssistantRoomCandidatesResponse = {
  household_id: string;
  items: HomeAssistantRoomCandidate[];
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

export type VoiceDiscoveryTerminal = {
  fingerprint: string;
  model: string;
  sn: string;
  runtime_version: string;
  capabilities: string[];
  discovered_at: string;
  last_seen_at: string;
  connection_status: 'online' | 'offline' | 'unknown';
  remote_addr: string | null;
};

export type VoiceDiscoveryListResponse = {
  household_id: string;
  items: VoiceDiscoveryTerminal[];
};

export type VoiceDiscoveryBinding = {
  household_id: string;
  terminal_id: string;
  room_id: string | null;
  terminal_name: string;
  voice_auto_takeover_enabled: boolean;
  voice_takeover_prefixes: string[];
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
export type PluginManifestType =
  | 'connector'
  | 'memory-ingestor'
  | 'action'
  | 'agent-skill'
  | 'channel'
  | 'locale-pack'
  | 'region-provider';
export type PluginConfigScopeType = 'plugin' | 'channel_account';
export type PluginConfigFieldType = 'string' | 'text' | 'integer' | 'number' | 'boolean' | 'enum' | 'multi_enum' | 'secret' | 'json';
export type PluginConfigWidgetType = 'input' | 'password' | 'textarea' | 'switch' | 'select' | 'multi_select' | 'json_editor';
export type PluginConfigVisibleOperator = 'equals' | 'not_equals' | 'in' | 'truthy';

export type PluginConfigEnumOption = {
  label: string;
  value: string;
};

export type PluginManifestConfigField = {
  key: string;
  label: string;
  type: PluginConfigFieldType;
  required: boolean;
  description?: string | null;
  default?: unknown;
  enum_options?: PluginConfigEnumOption[];
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
  help_text?: string | null;
  visible_when?: PluginManifestVisibilityRule[];
};

export type PluginManifestUiSection = {
  id: string;
  title: string;
  description?: string | null;
  fields: string[];
};

export type PluginManifestConfigSpec = {
  scope_type: PluginConfigScopeType;
  title: string;
  description?: string | null;
  schema_version: number;
  config_schema: {
    fields: PluginManifestConfigField[];
  };
  ui_schema: {
    sections: PluginManifestUiSection[];
    field_order?: string[];
    submit_text?: string | null;
    widgets?: Record<string, PluginManifestFieldUiSchema>;
  };
};

export type PluginRegistryItem = {
  id: string;
  name: string;
  version: string;
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
};

export type PluginRegistrySnapshot = {
  items: PluginRegistryItem[];
};

export type PluginStateUpdateRequest = {
  enabled: boolean;
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
