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
