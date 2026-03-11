import type { RoomType } from './roomTypes';

export type Household = {
  id: string;
  name: string;
  city: string | null;
  timezone: string;
  locale: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type HouseholdSetupStepCode =
  | 'family_profile'
  | 'first_member'
  | 'provider_setup'
  | 'first_butler_agent'
  | 'finish';

export type HouseholdSetupLifecycleStatus = 'pending' | 'in_progress' | 'completed' | 'blocked';

export type HouseholdSetupStatus = {
  household_id: string;
  status: HouseholdSetupLifecycleStatus;
  current_step: HouseholdSetupStepCode;
  completed_steps: HouseholdSetupStepCode[];
  missing_requirements: HouseholdSetupStepCode[];
  is_required: boolean;
  resume_token: string | null;
  updated_at: string;
};

export type AiProviderProfile = {
  id: string;
  provider_code: string;
  display_name: string;
  transport_type: 'openai_compatible' | 'native_sdk' | 'local_gateway';
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

export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type Member = {
  id: string;
  household_id: string;
  name: string;
  nickname: string | null;
  gender: 'male' | 'female' | null;
  role: 'admin' | 'adult' | 'child' | 'elder' | 'guest';
  age_group: 'toddler' | 'child' | 'teen' | 'adult' | 'elder' | null;
  birthday: string | null;
  phone: string | null;
  status: 'active' | 'inactive';
  guardian_member_id: string | null;
  created_at: string;
  updated_at: string;
};

export type RelationType =
  | 'husband' | 'wife' | 'spouse'
  | 'father' | 'mother' | 'son' | 'daughter' | 'parent' | 'child'
  | 'older_brother' | 'older_sister' | 'younger_brother' | 'younger_sister'
  | 'grandfather_paternal' | 'grandmother_paternal'
  | 'grandfather_maternal' | 'grandmother_maternal'
  | 'grandson' | 'granddaughter'
  | 'guardian' | 'ward'
  | 'caregiver';

export type MemberRelationship = {
  id: string;
  household_id: string;
  source_member_id: string;
  target_member_id: string;
  relation_type: RelationType;
  visibility_scope: 'public' | 'family' | 'private';
  delegation_scope: 'none' | 'reminder' | 'health' | 'device';
  created_at: string;
};

export type MemberPreference = {
  member_id: string;
  preferred_name: string | null;
  light_preference: unknown | null;
  climate_preference: unknown | null;
  content_preference: unknown | null;
  reminder_channel_preference: unknown | null;
  sleep_schedule: unknown | null;
  birthday_is_lunar: boolean;
  updated_at: string;
};

export type Room = {
  id: string;
  household_id: string;
  name: string;
  room_type: RoomType;
  privacy_level: 'public' | 'private' | 'sensitive';
  created_at: string;
};

export type Device = {
  id: string;
  household_id: string;
  room_id: string | null;
  name: string;
  device_type: 'light' | 'ac' | 'curtain' | 'speaker' | 'camera' | 'sensor' | 'lock';
  vendor: 'xiaomi' | 'ha' | 'other';
  status: 'active' | 'offline' | 'inactive';
  controllable: boolean;
  created_at: string;
  updated_at: string;
};

export type ContextOverviewMemberState = {
  member_id: string;
  name: string;
  role: Member['role'];
  presence: 'home' | 'away' | 'unknown';
  activity: 'active' | 'focused' | 'resting' | 'sleeping' | 'idle';
  current_room_id: string | null;
  current_room_name: string | null;
  confidence: number;
  last_seen_minutes: number;
  highlight: string;
  source: 'snapshot' | 'configured' | 'default';
  source_summary: unknown | null;
  updated_at: string | null;
};

export type ContextOverviewRoomOccupancy = {
  room_id: string;
  name: string;
  room_type: Room['room_type'];
  privacy_level: Room['privacy_level'];
  occupant_count: number;
  occupants: Array<{
    member_id: string;
    name: string;
    role: Member['role'];
    presence: 'home' | 'away' | 'unknown';
    activity: 'active' | 'focused' | 'resting' | 'sleeping' | 'idle';
  }>;
  device_count: number;
  online_device_count: number;
  scene_preset: 'auto' | 'welcome' | 'focus' | 'rest' | 'quiet';
  climate_policy: 'follow_member' | 'follow_room' | 'manual';
  privacy_guard_enabled: boolean;
  announcement_enabled: boolean;
};

export type ContextOverviewRead = {
  household_id: string;
  household_name: string;
  home_mode: 'home' | 'away' | 'night' | 'sleep' | 'custom';
  privacy_mode: 'balanced' | 'strict' | 'care';
  automation_level: 'manual' | 'assisted' | 'automatic';
  home_assistant_status: 'healthy' | 'degraded' | 'offline';
  voice_fast_path_enabled: boolean;
  guest_mode_enabled: boolean;
  child_protection_enabled: boolean;
  elder_care_watch_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  active_member: {
    member_id: string;
    name: string;
    role: Member['role'];
    presence: 'home' | 'away' | 'unknown';
    activity: 'active' | 'focused' | 'resting' | 'sleeping' | 'idle';
    current_room_id: string | null;
    current_room_name: string | null;
    confidence: number;
    source: 'snapshot' | 'configured' | 'default';
  } | null;
  member_states: ContextOverviewMemberState[];
  room_occupancy: ContextOverviewRoomOccupancy[];
  device_summary: {
    total: number;
    active: number;
    offline: number;
    inactive: number;
    controllable: number;
  };
  insights: Array<{
    code: string;
    title: string;
    message: string;
    tone: 'info' | 'success' | 'warning' | 'danger';
  }>;
  degraded: boolean;
  generated_at: string;
};

export type ContextConfigRead = {
  household_id: string;
  home_mode: 'home' | 'away' | 'night' | 'sleep' | 'custom';
  privacy_mode: 'balanced' | 'strict' | 'care';
  automation_level: 'manual' | 'assisted' | 'automatic';
  home_assistant_status: 'healthy' | 'degraded' | 'offline';
  active_member_id: string | null;
  voice_fast_path_enabled: boolean;
  guest_mode_enabled: boolean;
  child_protection_enabled: boolean;
  elder_care_watch_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  member_states: Array<{
    member_id: string;
    presence: 'home' | 'away' | 'unknown';
    activity: 'active' | 'focused' | 'resting' | 'sleeping' | 'idle';
    current_room_id: string | null;
    confidence: number;
    last_seen_minutes: number;
    highlight: string;
  }>;
  room_settings: Array<{
    room_id: string;
    scene_preset: 'auto' | 'welcome' | 'focus' | 'rest' | 'quiet';
    climate_policy: 'follow_member' | 'follow_room' | 'manual';
    privacy_guard_enabled: boolean;
    announcement_enabled: boolean;
  }>;
  version: number;
  updated_by: string | null;
  updated_at: string;
};

export type ReminderOverviewRead = {
  household_id: string;
  total_tasks: number;
  enabled_tasks: number;
  pending_runs: number;
  ack_required_tasks: number;
  items: Array<{
    task_id: string;
    title: string;
    reminder_type: 'personal' | 'family' | 'medication' | 'course' | 'announcement';
    enabled: boolean;
    next_trigger_at: string | null;
    latest_run_status: string | null;
    latest_run_planned_at: string | null;
    latest_ack_action: 'heard' | 'done' | 'dismissed' | 'delegated' | null;
  }>;
};

export type ReminderTask = {
  id: string;
  household_id: string;
  owner_member_id: string | null;
  title: string;
  description: string | null;
  reminder_type: 'personal' | 'family' | 'medication' | 'course' | 'announcement';
  target_member_ids: string[];
  preferred_room_ids: string[];
  schedule_kind: 'once' | 'recurring' | 'contextual';
  schedule_rule: Record<string, unknown>;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  delivery_channels: string[];
  ack_required: boolean;
  escalation_policy: Record<string, unknown>;
  enabled: boolean;
  version: number;
  updated_by: string | null;
  updated_at: string;
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
  failures: { entity_id: string | null; reason: string }[];
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

export type FamilyQaFactReference = {
  type: string;
  label: string;
  source: string;
  occurred_at: string | null;
  visibility: string;
  inferred: boolean;
  extra: Record<string, unknown>;
};

export type FamilyQaQueryResponse = {
  answer_type: string;
  answer: string;
  confidence: number;
  facts: FamilyQaFactReference[];
  degraded: boolean;
  suggestions: string[];
  effective_agent_id: string | null;
  effective_agent_type: string | null;
  effective_agent_name: string | null;
  ai_trace_id: string | null;
  ai_provider_code: string | null;
  ai_degraded: boolean;
};

export type FamilyQaSuggestionsResponse = {
  household_id: string;
  effective_agent_id: string | null;
  effective_agent_type: string | null;
  effective_agent_name: string | null;
  items: Array<{
    question: string;
    answer_type: string;
    reason: string;
  }>;
};

export type AgentType = 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
export type AgentStatus = 'draft' | 'active' | 'inactive';

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

export type AgentRuntimePolicy = {
  agent_id: string;
  conversation_enabled: boolean;
  default_entry: boolean;
  routing_tags: string[];
  memory_scope: Record<string, unknown> | null;
  updated_at: string;
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

export type MemoryType = 'fact' | 'event' | 'preference' | 'relation' | 'growth';
export type MemoryStatus = 'active' | 'pending_review' | 'invalidated' | 'deleted';
export type MemoryVisibility = 'public' | 'family' | 'private' | 'sensitive';

export type MemoryCard = {
  id: string;
  household_id: string;
  memory_type: MemoryType;
  title: string;
  summary: string;
  normalized_text: string | null;
  content: Record<string, unknown> | null;
  status: MemoryStatus;
  visibility: MemoryVisibility;
  importance: number;
  confidence: number;
  subject_member_id: string | null;
  source_event_id: string | null;
  dedupe_key: string | null;
  effective_at: string | null;
  last_observed_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  invalidated_at: string | null;
  related_members: Array<{
    memory_id: string;
    member_id: string;
    relation_role: string;
  }>;
};

export type MemoryCardRevision = {
  id: string;
  memory_id: string;
  revision_no: number;
  action: string;
  before_json: string | null;
  after_json: string | null;
  reason: string | null;
  actor_type: string;
  actor_id: string | null;
  created_at: string;
};
