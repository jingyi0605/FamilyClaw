import type {
  AuthActor,
  Household,
  HouseholdRegion,
  HouseholdRegionNodeRef,
  HouseholdSetupLifecycleStatus,
  HouseholdSetupStatus,
  HouseholdSetupStepCode,
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
  RelationType,
  Room,
} from '@familyclaw/user-core';

export type {
  AuthActor,
  Household,
  HouseholdRegion,
  HouseholdRegionNodeRef,
  HouseholdSetupLifecycleStatus,
  HouseholdSetupStatus,
  HouseholdSetupStepCode,
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
  RelationType,
  Room,
};

export type AiProviderFieldOption = { label: string; value: string };
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

export type AiProviderDiscoveredModel = { id: string; label: string };
export type AiProviderModelDiscoveryPayload = { values: Record<string, unknown> };
export type AiProviderModelDiscoveryResult = { adapter_code: string; models: AiProviderDiscoveredModel[] };
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
export type AgentStatus = 'active' | 'inactive';
export type AgentMemberCognition = Record<string, unknown>;
export type AgentRuntimePolicy = Record<string, unknown>;
export type AgentSoulProfile = Record<string, unknown>;
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

export type ButlerBootstrapStatus = 'collecting' | 'reviewing' | 'completed' | 'cancelled';
export type ButlerBootstrapField = 'display_name' | 'speaking_style' | 'personality_traits';
export type ButlerBootstrapDraft = {
  household_id: string;
  display_name: string;
  speaking_style: string;
  personality_traits: string[];
};
export type ButlerBootstrapMessage = {
  id?: string;
  request_id?: string | null;
  role: 'assistant' | 'user';
  content: string;
  seq?: number;
  created_at?: string;
};
export type ButlerBootstrapSession = {
  session_id: string;
  status: ButlerBootstrapStatus;
  pending_field: ButlerBootstrapField | null;
  draft: ButlerBootstrapDraft;
  assistant_message: string;
  messages: ButlerBootstrapMessage[];
  can_confirm: boolean;
  current_request_id?: string | null;
  last_event_seq?: number;
};
