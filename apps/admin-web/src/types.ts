import type { RoomType } from "./lib/roomTypes";

export type Household = {
  id: string;
  name: string;
  city?: string | null;
  timezone: string;
  locale: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Member = {
  id: string;
  household_id: string;
  name: string;
  nickname: string | null;
  gender?: "male" | "female" | null;
  role: "admin" | "adult" | "child" | "elder" | "guest";
  age_group: "toddler" | "child" | "teen" | "adult" | "elder" | null;
  birthday: string | null;
  phone: string | null;
  status: "active" | "inactive";
  guardian_member_id: string | null;
  created_at: string;
  updated_at: string;
};

export type MemberRelationship = {
  id: string;
  household_id: string;
  source_member_id: string;
  target_member_id: string;
  relation_type:
    | "husband"
    | "wife"
    | "spouse"
    | "father"
    | "mother"
    | "son"
    | "daughter"
    | "parent"
    | "child"
    | "older_brother"
    | "older_sister"
    | "younger_brother"
    | "younger_sister"
    | "grandfather_paternal"
    | "grandmother_paternal"
    | "grandfather_maternal"
    | "grandmother_maternal"
    | "grandson"
    | "granddaughter"
    | "guardian"
    | "ward"
    | "caregiver";
  visibility_scope: "public" | "family" | "private";
  delegation_scope: "none" | "reminder" | "health" | "device";
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
  birthday_is_lunar?: boolean;
  updated_at: string | null;
};

export type MemberPermissionRule = {
  resource_type: "memory" | "health" | "device" | "photo" | "scenario";
  resource_scope: "self" | "children" | "family" | "public";
  action: "read" | "write" | "execute" | "manage";
  effect: "allow" | "deny";
};

export type MemberPermission = MemberPermissionRule & {
  id: string;
  household_id: string;
  member_id: string;
  created_at: string;
};

export type MemberPermissionListResponse = {
  member_id: string;
  household_id: string;
  items: MemberPermission[];
};

export type Room = {
  id: string;
  household_id: string;
  name: string;
  room_type: RoomType;
  privacy_level: "public" | "private" | "sensitive";
  created_at: string;
};

export type Device = {
  id: string;
  household_id: string;
  room_id: string | null;
  name: string;
  device_type: "light" | "ac" | "curtain" | "speaker" | "camera" | "sensor" | "lock";
  vendor: "xiaomi" | "ha" | "other";
  status: "active" | "offline" | "inactive";
  controllable: boolean;
  created_at: string;
  updated_at: string;
};

export type AuditLog = {
  id: string;
  household_id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  result: string;
  details: string | null;
  created_at: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
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

export type ContextHomeMode = "home" | "away" | "night" | "sleep" | "custom";
export type ContextPrivacyMode = "balanced" | "strict" | "care";
export type ContextAutomationLevel = "manual" | "assisted" | "automatic";
export type ContextHomeAssistantStatus = "healthy" | "degraded" | "offline";
export type ContextPresenceStatus = "home" | "away" | "unknown";
export type ContextActivityStatus = "active" | "focused" | "resting" | "sleeping" | "idle";
export type ContextRoomScenePreset = "auto" | "welcome" | "focus" | "rest" | "quiet";
export type ContextClimatePolicy = "follow_member" | "follow_room" | "manual";
export type ContextInsightTone = "info" | "success" | "warning" | "danger";
export type ContextStateSource = "snapshot" | "configured" | "default";

export type ContextConfigMemberState = {
  member_id: string;
  presence: ContextPresenceStatus;
  activity: ContextActivityStatus;
  current_room_id: string | null;
  confidence: number;
  last_seen_minutes: number;
  highlight: string;
};

export type ContextConfigRoomSetting = {
  room_id: string;
  scene_preset: ContextRoomScenePreset;
  climate_policy: ContextClimatePolicy;
  privacy_guard_enabled: boolean;
  announcement_enabled: boolean;
};

export type ContextConfigUpsertPayload = {
  home_mode: ContextHomeMode;
  privacy_mode: ContextPrivacyMode;
  automation_level: ContextAutomationLevel;
  home_assistant_status: ContextHomeAssistantStatus;
  active_member_id: string | null;
  voice_fast_path_enabled: boolean;
  guest_mode_enabled: boolean;
  child_protection_enabled: boolean;
  elder_care_watch_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  member_states: ContextConfigMemberState[];
  room_settings: ContextConfigRoomSetting[];
};

export type ContextConfigRead = ContextConfigUpsertPayload & {
  household_id: string;
  version: number;
  updated_by: string | null;
  updated_at: string;
};

export type ContextOverviewActiveMember = {
  member_id: string;
  name: string;
  role: Member["role"];
  presence: ContextPresenceStatus;
  activity: ContextActivityStatus;
  current_room_id: string | null;
  current_room_name: string | null;
  confidence: number;
  source: ContextStateSource;
};

export type ContextOverviewMemberState = {
  member_id: string;
  name: string;
  role: Member["role"];
  presence: ContextPresenceStatus;
  activity: ContextActivityStatus;
  current_room_id: string | null;
  current_room_name: string | null;
  confidence: number;
  last_seen_minutes: number;
  highlight: string;
  source: ContextStateSource;
  source_summary: unknown | null;
  updated_at: string | null;
};

export type ContextOverviewRoomOccupant = {
  member_id: string;
  name: string;
  role: Member["role"];
  presence: ContextPresenceStatus;
  activity: ContextActivityStatus;
};

export type ContextOverviewRoomOccupancy = {
  room_id: string;
  name: string;
  room_type: Room["room_type"];
  privacy_level: Room["privacy_level"];
  occupant_count: number;
  occupants: ContextOverviewRoomOccupant[];
  device_count: number;
  online_device_count: number;
  scene_preset: ContextRoomScenePreset;
  climate_policy: ContextClimatePolicy;
  privacy_guard_enabled: boolean;
  announcement_enabled: boolean;
};

export type ContextOverviewDeviceSummary = {
  total: number;
  active: number;
  offline: number;
  inactive: number;
  controllable: number;
};

export type ContextOverviewInsight = {
  code: string;
  title: string;
  message: string;
  tone: ContextInsightTone;
};

export type ContextOverviewRead = {
  household_id: string;
  household_name: string;
  home_mode: ContextHomeMode;
  privacy_mode: ContextPrivacyMode;
  automation_level: ContextAutomationLevel;
  home_assistant_status: ContextHomeAssistantStatus;
  voice_fast_path_enabled: boolean;
  guest_mode_enabled: boolean;
  child_protection_enabled: boolean;
  elder_care_watch_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  active_member: ContextOverviewActiveMember | null;
  member_states: ContextOverviewMemberState[];
  room_occupancy: ContextOverviewRoomOccupancy[];
  device_summary: ContextOverviewDeviceSummary;
  insights: ContextOverviewInsight[];
  degraded: boolean;
  generated_at: string;
};

export type QaFactReference = {
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
  facts: QaFactReference[];
  degraded: boolean;
  suggestions: string[];
  ai_trace_id: string | null;
  ai_provider_code: string | null;
  ai_degraded: boolean;
};

export type FamilyQaSuggestionItem = {
  question: string;
  answer_type: string;
  reason: string;
};

export type FamilyQaSuggestionsResponse = {
  household_id: string;
  items: FamilyQaSuggestionItem[];
};

export type MemoryEventProcessingStatus = "pending" | "processed" | "failed" | "ignored";
export type MemoryType = "fact" | "event" | "preference" | "relation" | "growth";
export type MemoryStatus = "active" | "pending_review" | "invalidated" | "deleted";
export type MemoryVisibility = "public" | "family" | "private" | "sensitive";
export type MemoryRelationRole = "subject" | "participant" | "mentioned" | "owner";

export type MemoryEventRecord = {
  id: string;
  household_id: string;
  event_type: string;
  source_type: string;
  source_ref: string | null;
  subject_member_id: string | null;
  room_id: string | null;
  payload: Record<string, unknown> | null;
  dedupe_key: string | null;
  processing_status: MemoryEventProcessingStatus;
  generate_memory_card: boolean;
  failure_reason: string | null;
  occurred_at: string;
  created_at: string;
  processed_at: string | null;
};

export type MemoryEventWriteResponse = {
  event_id: string;
  accepted: boolean;
  duplicate_detected: boolean;
  processing_status: MemoryEventProcessingStatus;
};

export type MemoryCardMemberLink = {
  member_id: string;
  relation_role: MemoryRelationRole;
};

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
  related_members: {
    memory_id: string;
    member_id: string;
    relation_role: string;
  }[];
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

export type MemoryDebugOverviewRead = {
  household_id: string;
  total_events: number;
  pending_events: number;
  processed_events: number;
  failed_events: number;
  ignored_events: number;
  total_cards: number;
  active_cards: number;
  pending_cards: number;
  invalidated_cards: number;
  deleted_cards: number;
  latest_event_at: string | null;
  latest_card_at: string | null;
};

export type MemoryQueryHit = {
  card: MemoryCard;
  score: number;
  matched_terms: string[];
};

export type MemoryQueryResponse = {
  household_id: string;
  requester_member_id: string | null;
  total: number;
  query: string | null;
  items: MemoryQueryHit[];
};

export type MemoryHotSummaryItem = {
  title: string;
  memory_id: string;
  memory_type: string;
  summary: string;
  updated_at: string;
};

export type MemoryHotSummaryRead = {
  household_id: string;
  requester_member_id: string | null;
  generated_at: string;
  total_visible_cards: number;
  top_memories: MemoryHotSummaryItem[];
  preference_highlights: string[];
  recent_event_highlights: string[];
};

export type MemoryContextLiveSummary = {
  active_member_name: string | null;
  active_member_id: string | null;
  pending_reminders: number;
  running_scenes: number;
  visible_member_count: number;
  room_count: number;
  degraded: boolean;
};

export type MemoryContextBundleRead = {
  household_id: string;
  requester_member_id: string | null;
  capability: string;
  question: string | null;
  generated_at: string;
  live_summary: MemoryContextLiveSummary;
  hot_summary: MemoryHotSummaryRead;
  query_result: MemoryQueryResponse;
  masked_sections: string[];
  degraded: boolean;
};

export type ReminderTask = {
  id: string;
  household_id: string;
  owner_member_id: string | null;
  title: string;
  description: string | null;
  reminder_type: "personal" | "family" | "medication" | "course" | "announcement";
  target_member_ids: string[];
  preferred_room_ids: string[];
  schedule_kind: "once" | "recurring" | "contextual";
  schedule_rule: Record<string, unknown>;
  priority: "low" | "normal" | "high" | "urgent";
  delivery_channels: string[];
  ack_required: boolean;
  escalation_policy: Record<string, unknown>;
  enabled: boolean;
  version: number;
  updated_by: string | null;
  updated_at: string;
};

export type ReminderOverviewItem = {
  task_id: string;
  title: string;
  reminder_type: ReminderTask["reminder_type"];
  enabled: boolean;
  next_trigger_at: string | null;
  latest_run_status: string | null;
  latest_run_planned_at: string | null;
  latest_ack_action: "heard" | "done" | "dismissed" | "delegated" | null;
};

export type ReminderOverviewRead = {
  household_id: string;
  total_tasks: number;
  enabled_tasks: number;
  pending_runs: number;
  ack_required_tasks: number;
  items: ReminderOverviewItem[];
};

export type ReminderRun = {
  id: string;
  task_id: string;
  household_id: string;
  schedule_slot_key: string;
  trigger_reason: string;
  planned_at: string;
  started_at: string | null;
  finished_at: string | null;
  status: "pending" | "delivering" | "acked" | "expired" | "cancelled" | "failed";
  context_snapshot: Record<string, unknown>;
  result_summary: Record<string, unknown>;
};

export type ReminderDeliveryAttempt = {
  id: string;
  run_id: string;
  target_member_id: string | null;
  target_room_id: string | null;
  channel: string;
  attempt_index: number;
  planned_at: string;
  sent_at: string | null;
  status: "queued" | "sent" | "heard" | "failed" | "skipped";
  provider_result: Record<string, unknown>;
  failure_reason: string | null;
};

export type ReminderTriggerResponse = {
  run: ReminderRun;
  delivery_attempts: ReminderDeliveryAttempt[];
  escalated: boolean;
};

export type ReminderAckEvent = {
  id: string;
  run_id: string;
  member_id: string | null;
  action: "heard" | "done" | "dismissed" | "delegated";
  note: string | null;
  created_at: string;
};

export type ReminderAckResponse = {
  run: ReminderRun;
  ack_event: ReminderAckEvent;
  delivery_attempts: ReminderDeliveryAttempt[];
};

export type ReminderSchedulerDispatchResponse = {
  household_id: string;
  created_runs: ReminderRun[];
  escalated_runs: ReminderRun[];
};

export type SceneTemplate = {
  id: string;
  household_id: string;
  template_code: string;
  name: string;
  description: string | null;
  enabled: boolean;
  priority: number;
  cooldown_seconds: number;
  trigger: Record<string, unknown>;
  conditions: Record<string, unknown>[];
  guards: Record<string, unknown>[];
  actions: Record<string, unknown>[];
  rollout_policy: Record<string, unknown>;
  version: number;
  updated_by: string | null;
  updated_at: string;
};

export type ScenePreviewStep = {
  step_index: number;
  step_type: "reminder" | "broadcast" | "device_action" | "context_update";
  target_ref: string | null;
  status: "planned" | "success" | "skipped" | "failed" | "blocked";
  summary: string;
  request: Record<string, unknown>;
};

export type ScenePreviewResponse = {
  household_id: string;
  template: SceneTemplate;
  trigger_key: string;
  matched_conditions: string[];
  blocked_guards: string[];
  requires_confirmation: boolean;
  steps: ScenePreviewStep[];
  explanation: string | null;
  degraded: boolean;
};

export type SceneExecution = {
  id: string;
  template_id: string;
  household_id: string;
  trigger_key: string;
  trigger_source: string;
  started_at: string;
  finished_at: string | null;
  status: "planned" | "running" | "success" | "partial" | "skipped" | "blocked" | "failed";
  guard_result: Record<string, unknown>;
  conflict_result: Record<string, unknown>;
  context_snapshot: Record<string, unknown>;
  summary: Record<string, unknown>;
};

export type SceneExecutionStep = {
  id: string;
  execution_id: string;
  step_index: number;
  step_type: "reminder" | "broadcast" | "device_action" | "context_update";
  target_ref: string | null;
  request: Record<string, unknown>;
  result: Record<string, unknown>;
  status: "planned" | "success" | "skipped" | "failed" | "blocked";
  started_at: string | null;
  finished_at: string | null;
};

export type SceneExecutionDetailRead = {
  execution: SceneExecution;
  steps: SceneExecutionStep[];
};

export type SceneTemplatePresetItem = {
  template_code: string;
  name: string;
  description: string;
  payload: Omit<SceneTemplate, "id" | "version" | "updated_at"> & {
    updated_by: string | null;
  };
};

export type AiProviderProfile = {
  id: string;
  provider_code: string;
  display_name: string;
  transport_type: "openai_compatible" | "native_sdk" | "local_gateway";
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: "local_only" | "private_cloud" | "public_cloud";
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type AiProviderProfileCreatePayload = {
  provider_code: string;
  display_name: string;
  transport_type: "openai_compatible" | "native_sdk" | "local_gateway";
  base_url: string | null;
  api_version: string | null;
  secret_ref: string | null;
  enabled: boolean;
  supported_capabilities: string[];
  privacy_level: "local_only" | "private_cloud" | "public_cloud";
  latency_budget_ms: number | null;
  cost_policy: Record<string, unknown>;
  extra_config: Record<string, unknown>;
};

export type AiProviderProfileUpdatePayload = Partial<AiProviderProfileCreatePayload>;

export type AgentType =
  | "butler"
  | "nutritionist"
  | "fitness_coach"
  | "study_coach"
  | "custom";

export type AgentStatus = "draft" | "active" | "inactive";

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

export type AgentSoulProfileUpsertPayload = {
  self_identity: string;
  role_summary: string;
  intro_message: string | null;
  speaking_style: string | null;
  personality_traits: string[];
  service_focus: string[];
  service_boundaries: Record<string, unknown> | null;
  created_by: string;
};

export type AgentMemberCognitionUpsertItemPayload = {
  member_id: string;
  display_address: string | null;
  closeness_level: number;
  service_priority: number;
  communication_style: string | null;
  care_notes: Record<string, unknown> | null;
  prompt_notes: string | null;
};

export type AgentMemberCognitionsUpsertPayload = {
  items: AgentMemberCognitionUpsertItemPayload[];
};

export type AgentRuntimePolicyUpsertPayload = {
  conversation_enabled: boolean;
  default_entry: boolean;
  routing_tags: string[];
  memory_scope: Record<string, unknown> | null;
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

export type AiCallLog = {
  id: string;
  capability: string;
  provider_code: string;
  model_name: string;
  household_id: string | null;
  requester_member_id: string | null;
  trace_id: string;
  input_policy: string;
  masked_fields: string[];
  latency_ms: number | null;
  usage: Record<string, unknown>;
  status: string;
  fallback_used: boolean;
  error_code: string | null;
  created_at: string;
};

export type AiGatewayAttemptResult = {
  provider_code: string;
  model_name: string;
  status: string;
  latency_ms: number | null;
  error_code: string | null;
  fallback_used: boolean;
};

export type AiGatewayInvokeResponse = {
  capability: string;
  household_id: string | null;
  requester_member_id: string | null;
  trace_id: string;
  status: string;
  degraded: boolean;
  provider_code: string;
  model_name: string;
  finish_reason: string;
  normalized_output: Record<string, unknown>;
  raw_response_ref: string | null;
  blocked_reason: string | null;
  attempts: AiGatewayAttemptResult[];
};
