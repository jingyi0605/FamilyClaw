export type Household = {
  id: string;
  name: string;
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
  relation_type: "spouse" | "parent" | "child" | "guardian" | "caregiver";
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
  updated_at: string;
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
  room_type: "living_room" | "bedroom" | "study" | "entrance";
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

export type HomeAssistantSyncResponse = {
  household_id: string;
  created_devices: number;
  updated_devices: number;
  created_bindings: number;
  skipped_entities: number;
  failed_entities: number;
  devices: Device[];
  failures: { entity_id: string | null; reason: string }[];
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
