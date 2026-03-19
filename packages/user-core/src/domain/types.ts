export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type AppPlatformTarget = {
  platform: 'h5' | 'rn-ios' | 'rn-android' | 'harmony';
  runtime: 'h5' | 'rn' | 'harmony';
  supports_push: boolean;
  supports_file_picker: boolean;
  supports_camera: boolean;
  supports_share: boolean;
  supports_deeplink: boolean;
};

export type AuthActor = {
  account_id: string;
  username: string;
  account_type: string;
  account_status: string;
  household_id: string | null;
  member_id: string | null;
  member_role: string | null;
  role: string;
  actor_type: string;
  actor_id: string | null;
  must_change_password: boolean;
  authenticated: boolean;
};

export type LoginResponse = {
  actor: AuthActor;
};

export type AccountRead = {
  id: string;
  username: string;
  account_type: string;
  status: string;
  household_id: string | null;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
};

export type AccountMemberBindingRead = {
  account_id: string;
  member_id: string;
  household_id: string;
  binding_status: string;
  created_at: string;
  updated_at: string;
};

export type HouseholdAccountCreateResponse = {
  account: AccountRead;
  binding: AccountMemberBindingRead;
};

export type AccountWithBinding = {
  account: AccountRead;
  binding: AccountMemberBindingRead | null;
};

export type HouseholdAccountListResponse = {
  items: AccountWithBinding[];
  total: number;
};

export type HouseholdAccountUpdatePayload = {
  status?: 'active' | 'disabled' | 'locked';
  must_change_password?: boolean;
};

export type HouseholdAccountResetPasswordPayload = {
  new_password: string;
  must_change_password?: boolean;
};

export type PluginLocale = {
  plugin_id: string;
  locale_id: string;
  label: string;
  native_label: string;
  fallback: string | null;
  source_type: 'builtin' | 'official' | 'third_party';
  messages: Record<string, string>;
  overridden_plugin_ids: string[];
};

export type PluginLocaleListResponse = {
  household_id: string;
  items: PluginLocale[];
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
  | 'region-provider'
  | 'theme-pack'
  | 'ai-provider';
export type PluginJobStatus =
  | 'queued'
  | 'running'
  | 'retry_waiting'
  | 'waiting_response'
  | 'succeeded'
  | 'failed'
  | 'cancelled';
export type PluginJobResponseAction = 'retry' | 'confirm' | 'cancel' | 'provide_input';

export type PluginManifestEntrypoints = {
  connector?: string | null;
  memory_ingestor?: string | null;
  action?: string | null;
  agent_skill?: string | null;
  channel?: string | null;
  region_provider?: string | null;
};

export type PluginManifestCapabilities = {
  context_reads?: {
    household_region_context?: boolean;
  } | null;
  channel?: {
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
    tokens_resource?: string;
    entry_resource?: string;
    resource_source?: 'builtin_bundle' | 'managed_plugin_dir';
    resource_version?: string;
    platform_targets?: Array<'h5' | 'rn'>;
    theme_schema_version?: number;
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
  entrypoints: PluginManifestEntrypoints;
  capabilities: PluginManifestCapabilities;
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
  execution_backend?: string | null;
  runner_config?: {
    plugin_root?: string | null;
    python_path?: string | null;
    working_dir?: string | null;
    timeout_seconds?: number;
    stdout_limit_bytes?: number;
    stderr_limit_bytes?: number;
  } | null;
};

export type PluginRegistrySnapshot = {
  items: PluginRegistryItem[];
};

export type PluginThemeRegistryItem = {
  plugin_id: string;
  theme_id: string;
  display_name: string;
  source_type: PluginSourceType;
  enabled: boolean;
  state: 'ready' | 'disabled' | 'invalid' | 'stale' | 'missing';
  disabled_reason: string | null;
  resource_source: 'builtin_bundle' | 'managed_plugin_dir';
  resource_version: string;
  theme_schema_version: number;
  platform_targets: Array<'h5' | 'rn'>;
  preview: Record<string, unknown>;
};

export type PluginThemeRegistrySnapshot = {
  household_id: string;
  items: PluginThemeRegistryItem[];
};

export type PluginThemeResourceResponse = {
  plugin_id: string;
  theme_id: string;
  resource_version: string;
  theme_schema_version: number;
  tokens: Record<string, unknown>;
  source_type: PluginSourceType;
  resource_source: 'builtin_bundle' | 'managed_plugin_dir';
};

export type PluginStateUpdateRequest = {
  enabled: boolean;
};

export type HomeDashboardCardTemplateType = 'metric' | 'status_list' | 'timeline' | 'insight' | 'action_group';
export type HomeDashboardCardSize = 'half' | 'full';
export type HomeDashboardCardHeight = 'compact' | 'regular' | 'tall';
export type HomeDashboardCardState = 'ready' | 'empty' | 'stale' | 'error';
export type HomeDashboardCardActionType = 'navigate' | 'open_plugin_detail' | 'trigger_plugin_action';

export type HomeDashboardCardActionRead = {
  action_key?: string | null;
  action_type: HomeDashboardCardActionType;
  label: string;
  target?: string | null;
  payload?: Record<string, unknown> | null;
};

export type HomeDashboardCardRead = {
  card_ref: string;
  source_type: 'builtin' | 'plugin';
  template_type: HomeDashboardCardTemplateType;
  size: HomeDashboardCardSize;
  state: HomeDashboardCardState;
  title: string;
  subtitle?: string | null;
  payload: Record<string, unknown>;
  actions: HomeDashboardCardActionRead[];
};

export type HomeDashboardRead = {
  household_id: string;
  member_id: string;
  member_name: string;
  member_nickname: string | null;
  layout_version: number;
  cards: HomeDashboardCardRead[];
  warnings: string[];
};

export type MemberDashboardLayoutItem = {
  card_ref: string;
  visible: boolean;
  order: number;
  size: HomeDashboardCardSize;
  height: HomeDashboardCardHeight;
};

export type MemberDashboardLayoutRead = {
  member_id: string;
  placement: 'home';
  layout_version: number;
  items: MemberDashboardLayoutItem[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type PluginMountRead = {
  id: string;
  household_id: string;
  plugin_id: string;
  name: string;
  version: string;
  types: PluginManifestType[];
  permissions: string[];
  risk_level: PluginRiskLevel;
  triggers: string[];
  entrypoints: PluginManifestEntrypoints;
  capabilities: PluginManifestCapabilities;
  locales: Array<{
    id: string;
    label: string;
    native_label: string;
    resource: string;
    fallback?: string | null;
  }>;
  source_type: 'official' | 'third_party';
  execution_backend: 'subprocess_runner';
  manifest_path: string;
  plugin_root: string;
  python_path: string;
  working_dir: string | null;
  timeout_seconds: number;
  stdout_limit_bytes: number;
  stderr_limit_bytes: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type PluginMountCreate = {
  source_type: 'official' | 'third_party';
  execution_backend?: 'subprocess_runner';
  plugin_root: string;
  manifest_path?: string | null;
  python_path: string;
  working_dir?: string | null;
  timeout_seconds?: number;
  stdout_limit_bytes?: number;
  stderr_limit_bytes?: number;
  enabled?: boolean;
};

export type PluginMountUpdate = {
  source_type?: 'official' | 'third_party' | null;
  python_path?: string | null;
  working_dir?: string | null;
  timeout_seconds?: number | null;
  stdout_limit_bytes?: number | null;
  stderr_limit_bytes?: number | null;
  enabled?: boolean | null;
};

export type PluginJobRead = {
  id: string;
  household_id: string;
  plugin_id: string;
  plugin_type: string;
  trigger: string;
  status: PluginJobStatus;
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
  allowed_actions: PluginJobResponseAction[];
};

export type PluginJobListRead = {
  items: PluginJobListItemRead[];
  total: number;
  page: number;
  page_size: number;
};

export type RegionSelection = {
  provider_code: string;
  country_code: string;
  region_code: string;
};

export type RegionNode = {
  provider_code: string;
  country_code: string;
  region_code: string;
  parent_region_code: string | null;
  admin_level: 'province' | 'city' | 'district';
  name: string;
  full_name: string;
  path_codes: string[];
  path_names: string[];
  timezone: string | null;
  source_version: string | null;
};

export type HouseholdRegionNodeRef = {
  code: string;
  name: string;
};

export type HouseholdRegion = {
  status: 'configured' | 'unconfigured' | 'provider_unavailable';
  provider_code: string | null;
  country_code: string | null;
  region_code: string | null;
  admin_level: 'province' | 'city' | 'district' | null;
  province: HouseholdRegionNodeRef | null;
  city: HouseholdRegionNodeRef | null;
  district: HouseholdRegionNodeRef | null;
  display_name: string | null;
  timezone: string | null;
};

export type Household = {
  id: string;
  name: string;
  city: string | null;
  timezone: string;
  locale: string;
  status: string;
  region: HouseholdRegion;
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

export type MemberGuideStatus = {
  member_id: string;
  user_app_guide_version: number | null;
  updated_at: string | null;
};

export type UserGuidePlacement = 'auto' | 'top' | 'bottom' | 'left' | 'right' | 'center';
export type UserGuideRuntimeStatus =
  | 'idle'
  | 'pending_start'
  | 'navigating'
  | 'waiting_anchor'
  | 'showing'
  | 'completing'
  | 'finished';

export type UserGuideManifestStep = {
  step_id: string;
  route: string;
  anchor_id: string | null;
  title_key: string;
  content_key: string;
  placement: UserGuidePlacement;
  required_role: Member['role'] | null;
  optional: boolean;
  runtime_targets?: Array<AppPlatformTarget['runtime']>;
};

export type UserGuideManifest = {
  version: number;
  steps: UserGuideManifestStep[];
};

export const ROOM_TYPE_OPTIONS = [
  { value: 'living_room', label: '客厅' },
  { value: 'bedroom', label: '卧室' },
  { value: 'study', label: '书房' },
  { value: 'entrance', label: '玄关' },
  { value: 'kitchen', label: '厨房' },
  { value: 'bathroom', label: '卫生间' },
  { value: 'gym', label: '健身房' },
  { value: 'garage', label: '车库' },
  { value: 'dining_room', label: '餐厅' },
  { value: 'balcony', label: '阳台' },
  { value: 'kids_room', label: '儿童房' },
  { value: 'storage_room', label: '储物间' },
] as const;

export type RoomType = (typeof ROOM_TYPE_OPTIONS)[number]['value'];

const ROOM_TYPE_LABELS: Record<RoomType, string> = Object.fromEntries(
  ROOM_TYPE_OPTIONS.map(option => [option.value, option.label]),
) as Record<RoomType, string>;

export function formatRoomType(roomType: RoomType) {
  return ROOM_TYPE_LABELS[roomType];
}

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
  voice_auto_takeover_enabled: boolean;
  voiceprint_identity_enabled: boolean;
  voice_takeover_prefixes: string[];
  created_at: string;
  updated_at: string;
};

export type PlatformHealthStatus = 'healthy' | 'degraded' | 'offline';

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
  platform_health_status: PlatformHealthStatus;
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
  platform_health_status: PlatformHealthStatus;
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

export type FamilyQaFactReference = {
  type: string;
  label: string;
  source: string;
  occurred_at: string | null;
  visibility: string;
  inferred: boolean;
  extra: Record<string, unknown>;
};

export type AgentType = 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
export type AgentStatus = 'draft' | 'active' | 'inactive';

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

export type AgentListResponse = {
  household_id: string;
  items: AgentSummary[];
};

export type AgentAutonomousActionPolicy = {
  memory: 'ask' | 'notify' | 'auto';
  config: 'ask' | 'notify' | 'auto';
  action: 'ask' | 'notify' | 'auto';
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
  autonomous_action_policy: AgentAutonomousActionPolicy;
  updated_at: string;
};

export type AgentUpdatePayload = {
  display_name?: string;
  status?: AgentStatus;
  sort_order?: number;
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
  summary: string | null;
  conversation_enabled: boolean;
  default_entry: boolean;
  created_at: string;
  updated_at: string;
  soul: AgentSoulProfile | null;
  member_cognitions: AgentMemberCognition[];
  runtime_policy: AgentRuntimePolicy | null;
};

export type AiProviderTransportType = 'openai_compatible' | 'native_sdk' | 'local_gateway';
export type AiProviderApiFamily =
  | 'openai_chat_completions'
  | 'anthropic_messages'
  | 'gemini_generate_content';
export type AiProviderPrivacyLevel = 'local_only' | 'private_cloud' | 'public_cloud';

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

export type AiProviderModelType = 'llm' | 'embedding' | 'vision' | 'speech' | 'image';

export type AiProviderAdapter = {
  plugin_id: string;
  plugin_name: string;
  adapter_code: string;
  display_name: string;
  description: string;
  transport_type: AiProviderTransportType;
  api_family: AiProviderApiFamily;
  default_privacy_level: AiProviderPrivacyLevel;
  default_supported_capabilities: string[];
  supported_model_types: AiProviderModelType[];
  llm_workflow: string;
  field_schema: AiProviderField[];
};

export type AiProviderProfile = {
  id: string;
  provider_code: string;
  display_name: string;
  transport_type: AiProviderTransportType;
  api_family: AiProviderApiFamily;
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: AiProviderPrivacyLevel;
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type AiProviderProfileCreatePayload = {
  provider_code?: string | null;
  display_name: string;
  transport_type: AiProviderTransportType;
  api_family: AiProviderApiFamily;
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: AiProviderPrivacyLevel;
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

export type ConversationSessionMode = 'family_chat' | 'agent_bootstrap' | 'agent_config';
export type ConversationSessionStatus = 'active' | 'archived' | 'failed';
export type ConversationMessageRole = 'user' | 'assistant' | 'system';
export type ConversationMessageType = 'text' | 'error' | 'memory_candidate_notice';
export type ConversationMessageStatus = 'pending' | 'streaming' | 'completed' | 'failed';
export type ConversationCandidateStatus = 'pending_review' | 'confirmed' | 'dismissed';
export type ConversationActionCategory = 'memory' | 'config' | 'action';
export type ConversationActionPolicyMode = 'ask' | 'notify' | 'auto';
export type ConversationActionStatus = 'pending_confirmation' | 'completed' | 'failed' | 'dismissed' | 'undone' | 'undo_failed';
export type ConversationProposalPolicyCategory = 'ask' | 'notify' | 'auto' | 'ignore';
export type ConversationProposalStatus = 'pending_policy' | 'pending_confirmation' | 'completed' | 'dismissed' | 'ignored' | 'failed';

export type ConversationMessage = {
  id: string;
  session_id: string;
  request_id: string | null;
  seq: number;
  role: ConversationMessageRole;
  message_type: ConversationMessageType;
  content: string;
  status: ConversationMessageStatus;
  effective_agent_id: string | null;
  ai_provider_code: string | null;
  ai_trace_id: string | null;
  degraded: boolean;
  error_code: string | null;
  facts: FamilyQaFactReference[];
  suggestions: string[];
  created_at: string;
  updated_at: string;
};

export type ConversationMemoryCandidate = {
  id: string;
  session_id: string;
  source_message_id: string | null;
  requester_member_id: string | null;
  status: ConversationCandidateStatus;
  memory_type: string;
  title: string;
  summary: string;
  content: Record<string, unknown>;
  confidence: number;
  created_at: string;
  updated_at: string;
};

export type ConversationActionRecord = {
  id: string;
  session_id: string;
  request_id: string | null;
  trigger_message_id: string | null;
  source_message_id: string | null;
  intent: string;
  action_category: ConversationActionCategory;
  action_name: string;
  policy_mode: ConversationActionPolicyMode;
  status: ConversationActionStatus;
  title: string;
  summary: string | null;
  target_ref: string | null;
  plan_payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
  undo_payload: Record<string, unknown>;
  created_at: string;
  executed_at: string | null;
  undone_at: string | null;
  updated_at: string;
};

export type ConversationProposalItem = {
  id: string;
  batch_id: string;
  proposal_kind: string;
  policy_category: ConversationProposalPolicyCategory;
  status: ConversationProposalStatus;
  title: string;
  summary: string | null;
  evidence_message_ids: string[];
  evidence_roles: string[];
  dedupe_key: string | null;
  confidence: number;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ConversationProposalBatch = {
  id: string;
  session_id: string;
  request_id: string | null;
  source_message_ids: string[];
  source_roles: string[];
  lane: Record<string, unknown>;
  status: ConversationProposalStatus | string;
  created_at: string;
  updated_at: string;
  items: ConversationProposalItem[];
};

export type ConversationSession = {
  id: string;
  household_id: string;
  requester_member_id: string | null;
  session_mode: ConversationSessionMode;
  active_agent_id: string | null;
  active_agent_name: string | null;
  active_agent_type: string | null;
  title: string;
  status: ConversationSessionStatus;
  last_message_at: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  latest_message_preview: string | null;
};

export type ConversationSessionDetail = ConversationSession & {
  messages: ConversationMessage[];
  memory_candidates: ConversationMemoryCandidate[];
  action_records: ConversationActionRecord[];
  proposal_batches: ConversationProposalBatch[];
};

export type ConversationSessionListResponse = {
  household_id: string;
  requester_member_id: string | null;
  items: ConversationSession[];
};

export type ConversationTurnResponse = {
  request_id: string;
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  outcome: 'completed' | 'failed';
  error_message: string | null;
  session: ConversationSessionDetail;
};

export type ConversationActionExecutionResponse = {
  action: ConversationActionRecord;
};

export type ConversationProposalExecutionResponse = {
  item: ConversationProposalItem;
  affected_target_id: string | null;
};

export type ButlerBootstrapStatus = 'collecting' | 'reviewing' | 'completed' | 'cancelled';
export type ButlerBootstrapField =
  | 'display_name'
  | 'speaking_style'
  | 'personality_traits';

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
  account_code: string;
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

export type FeatureParityStatus =
  | 'not_started'
  | 'in_progress'
  | 'ready'
  | 'blocked'
  | 'dropped';

export type FeatureParityItem = {
  feature_key: string;
  legacy_entry: string;
  new_entry: string | null;
  status: FeatureParityStatus;
  blocking_reason: string | null;
  owner: string | null;
};
