import type {
  ContextConfigRead,
  ContextConfigUpsertPayload,
  Member,
  Room,
} from "../types";

const STORAGE_PREFIX = "familyclaw.context-center";

const HOME_MODE_VALUES = ["home", "away", "night", "sleep", "custom"] as const;
const PRIVACY_MODE_VALUES = ["balanced", "strict", "care"] as const;
const AUTOMATION_LEVEL_VALUES = ["manual", "assisted", "automatic"] as const;
const HOME_ASSISTANT_STATUS_VALUES = ["healthy", "degraded", "offline"] as const;
const PRESENCE_VALUES = ["home", "away", "unknown"] as const;
const ACTIVITY_VALUES = ["active", "focused", "resting", "sleeping", "idle"] as const;
const ROOM_SCENE_PRESET_VALUES = ["auto", "welcome", "focus", "rest", "quiet"] as const;
const CLIMATE_POLICY_VALUES = ["follow_member", "follow_room", "manual"] as const;

export type HouseholdMode = (typeof HOME_MODE_VALUES)[number];
export type PrivacyMode = (typeof PRIVACY_MODE_VALUES)[number];
export type AutomationLevel = (typeof AUTOMATION_LEVEL_VALUES)[number];
export type HomeAssistantStatus = (typeof HOME_ASSISTANT_STATUS_VALUES)[number];
export type PresenceStatus = (typeof PRESENCE_VALUES)[number];
export type ActivityStatus = (typeof ACTIVITY_VALUES)[number];
export type RoomScenePreset = (typeof ROOM_SCENE_PRESET_VALUES)[number];
export type ClimatePolicy = (typeof CLIMATE_POLICY_VALUES)[number];

export type ContextMemberDraft = {
  member_id: string;
  presence: PresenceStatus;
  activity: ActivityStatus;
  current_room_id: string | null;
  confidence: number;
  last_seen_minutes: number;
  highlight: string;
};

export type ContextRoomSetting = {
  room_id: string;
  scene_preset: RoomScenePreset;
  climate_policy: ClimatePolicy;
  privacy_guard_enabled: boolean;
  announcement_enabled: boolean;
};

export type ContextCenterDraft = {
  home_mode: HouseholdMode;
  privacy_mode: PrivacyMode;
  automation_level: AutomationLevel;
  home_assistant_status: HomeAssistantStatus;
  active_member_id: string | null;
  voice_fast_path_enabled: boolean;
  guest_mode_enabled: boolean;
  child_protection_enabled: boolean;
  elder_care_watch_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  member_states: ContextMemberDraft[];
  room_settings: ContextRoomSetting[];
};

type RawContextMemberDraft = Partial<ContextMemberDraft> & { member_id?: unknown };
type RawContextRoomSetting = Partial<ContextRoomSetting> & { room_id?: unknown };
type RawContextCenterDraft = Partial<ContextCenterDraft> & {
  member_states?: RawContextMemberDraft[];
  room_settings?: RawContextRoomSetting[];
};

export const HOME_MODE_LABELS: Record<HouseholdMode, string> = {
  home: "居家模式",
  away: "离家模式",
  night: "夜间模式",
  sleep: "睡眠模式",
  custom: "自定义模式",
};

export const PRIVACY_MODE_LABELS: Record<PrivacyMode, string> = {
  balanced: "平衡保护",
  strict: "严格保护",
  care: "关怀优先",
};

export const AUTOMATION_LEVEL_LABELS: Record<AutomationLevel, string> = {
  manual: "手动优先",
  assisted: "辅助自动",
  automatic: "自动优先",
};

export const HOME_ASSISTANT_STATUS_LABELS: Record<HomeAssistantStatus, string> = {
  healthy: "连接健康",
  degraded: "部分降级",
  offline: "连接离线",
};

export const PRESENCE_LABELS: Record<PresenceStatus, string> = {
  home: "在家",
  away: "外出",
  unknown: "未知",
};

export const ACTIVITY_LABELS: Record<ActivityStatus, string> = {
  active: "活跃中",
  focused: "专注中",
  resting: "休息中",
  sleeping: "睡眠中",
  idle: "空闲中",
};

export const ROOM_SCENE_PRESET_LABELS: Record<RoomScenePreset, string> = {
  auto: "自动",
  welcome: "欢迎",
  focus: "专注",
  rest: "休息",
  quiet: "安静",
};

export const CLIMATE_POLICY_LABELS: Record<ClimatePolicy, string> = {
  follow_member: "跟随成员",
  follow_room: "跟随房间",
  manual: "手动固定",
};

function getStorageKey(householdId: string) {
  return `${STORAGE_PREFIX}.${householdId}`;
}

function isEnumValue<T extends string>(values: readonly T[], input: unknown): input is T {
  return typeof input === "string" && values.includes(input as T);
}

function clampNumber(value: unknown, fallback: number, min: number, max: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return Math.max(min, Math.min(max, Math.round(value)));
}

function normalizeTime(value: unknown, fallback: string) {
  if (typeof value !== "string") {
    return fallback;
  }

  return /^\d{2}:\d{2}$/.test(value) ? value : fallback;
}

function findRoomIdByType(rooms: Room[], roomTypes: Room["room_type"][]) {
  for (const roomType of roomTypes) {
    const match = rooms.find((room) => room.room_type === roomType);
    if (match) {
      return match.id;
    }
  }

  return rooms[0]?.id ?? null;
}

function getDefaultPresence(member: Member): PresenceStatus {
  if (member.status !== "active") {
    return "away";
  }

  if (member.role === "guest") {
    return "away";
  }

  return "home";
}

function getDefaultActivity(member: Member): ActivityStatus {
  switch (member.role) {
    case "admin":
      return "focused";
    case "adult":
      return "active";
    case "child":
      return "resting";
    case "elder":
      return "idle";
    case "guest":
      return "idle";
  }
}

function getDefaultConfidence(member: Member) {
  switch (member.role) {
    case "admin":
      return 92;
    case "adult":
      return 88;
    case "child":
      return 84;
    case "elder":
      return 80;
    case "guest":
      return 65;
  }
}

function getDefaultLastSeen(member: Member) {
  switch (member.role) {
    case "admin":
      return 4;
    case "adult":
      return 8;
    case "child":
      return 6;
    case "elder":
      return 12;
    case "guest":
      return 45;
  }
}

function getDefaultHighlight(member: Member) {
  switch (member.role) {
    case "admin":
      return "偏好与权限配置最完整，适合作为默认服务对象。";
    case "adult":
      return "优先联动公共空间设备与家庭提醒。";
    case "child":
      return "需结合儿童保护与作息规则处理内容和设备控制。";
    case "elder":
      return "优先关注健康提醒、低打扰播报与安全确认。";
    case "guest":
      return "默认只暴露公共信息与有限控制范围。";
  }
}

function getDefaultRoomId(member: Member, rooms: Room[]) {
  switch (member.role) {
    case "admin":
      return findRoomIdByType(rooms, ["study", "living_room", "bedroom"]);
    case "adult":
      return findRoomIdByType(rooms, ["living_room", "study", "bedroom"]);
    case "child":
      return findRoomIdByType(rooms, ["bedroom", "living_room"]);
    case "elder":
      return findRoomIdByType(rooms, ["living_room", "bedroom"]);
    case "guest":
      return findRoomIdByType(rooms, ["entrance", "living_room"]);
  }
}

function createDefaultMemberDraft(member: Member, rooms: Room[]): ContextMemberDraft {
  const presence = getDefaultPresence(member);

  return {
    member_id: member.id,
    presence,
    activity: presence === "away" ? "idle" : getDefaultActivity(member),
    current_room_id: presence === "away" ? null : getDefaultRoomId(member, rooms),
    confidence: getDefaultConfidence(member),
    last_seen_minutes: getDefaultLastSeen(member),
    highlight: getDefaultHighlight(member),
  };
}

function getDefaultScenePreset(room: Room): RoomScenePreset {
  switch (room.room_type) {
    case "living_room":
      return "welcome";
    case "bedroom":
      return "rest";
    case "study":
      return "focus";
    case "entrance":
      return "auto";
  }
}

function getDefaultClimatePolicy(room: Room): ClimatePolicy {
  switch (room.room_type) {
    case "living_room":
      return "follow_room";
    case "bedroom":
      return "follow_member";
    case "study":
      return "follow_member";
    case "entrance":
      return "manual";
  }
}

function createDefaultRoomSetting(room: Room): ContextRoomSetting {
  return {
    room_id: room.id,
    scene_preset: getDefaultScenePreset(room),
    climate_policy: getDefaultClimatePolicy(room),
    privacy_guard_enabled: room.privacy_level !== "public",
    announcement_enabled: room.privacy_level === "public",
  };
}

function getDefaultDraft(members: Member[], rooms: Room[]): ContextCenterDraft {
  const member_states = members.map((member) => createDefaultMemberDraft(member, rooms));
  const firstHomeMember = member_states.find((item) => item.presence === "home");

  return {
    home_mode: "home",
    privacy_mode: "balanced",
    automation_level: "assisted",
    home_assistant_status: "healthy",
    active_member_id: firstHomeMember?.member_id ?? members[0]?.id ?? null,
    voice_fast_path_enabled: true,
    guest_mode_enabled: false,
    child_protection_enabled: true,
    elder_care_watch_enabled: true,
    quiet_hours_enabled: true,
    quiet_hours_start: "22:00",
    quiet_hours_end: "07:00",
    member_states,
    room_settings: rooms.map((room) => createDefaultRoomSetting(room)),
  };
}

function parseStoredDraft(householdId: string): RawContextCenterDraft | null {
  try {
    const raw = window.localStorage.getItem(getStorageKey(householdId));
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    return parsed as RawContextCenterDraft;
  } catch {
    return null;
  }
}

export function normalizeContextDraft(
  rawDraft: RawContextCenterDraft | null,
  members: Member[],
  rooms: Room[],
): ContextCenterDraft {
  const fallback = getDefaultDraft(members, rooms);
  const roomIds = new Set(rooms.map((room) => room.id));
  const memberIds = new Set(members.map((member) => member.id));
  const rawMemberMap = new Map<string, RawContextMemberDraft>();
  const rawRoomMap = new Map<string, RawContextRoomSetting>();

  if (Array.isArray(rawDraft?.member_states)) {
    for (const item of rawDraft.member_states) {
      if (typeof item?.member_id === "string") {
        rawMemberMap.set(item.member_id, item);
      }
    }
  }

  if (Array.isArray(rawDraft?.room_settings)) {
    for (const item of rawDraft.room_settings) {
      if (typeof item?.room_id === "string") {
        rawRoomMap.set(item.room_id, item);
      }
    }
  }

  const member_states = members.map((member) => {
    const defaults = createDefaultMemberDraft(member, rooms);
    const saved = rawMemberMap.get(member.id);

    const presence = isEnumValue(PRESENCE_VALUES, saved?.presence)
      ? saved.presence
      : defaults.presence;
    const currentRoomId =
      presence === "away"
        ? null
        : typeof saved?.current_room_id === "string" && roomIds.has(saved.current_room_id)
          ? saved.current_room_id
          : defaults.current_room_id;

    return {
      member_id: member.id,
      presence,
      activity: isEnumValue(ACTIVITY_VALUES, saved?.activity) ? saved.activity : defaults.activity,
      current_room_id: currentRoomId,
      confidence: clampNumber(saved?.confidence, defaults.confidence, 0, 100),
      last_seen_minutes: clampNumber(saved?.last_seen_minutes, defaults.last_seen_minutes, 0, 720),
      highlight:
        typeof saved?.highlight === "string" && saved.highlight.trim().length > 0
          ? saved.highlight.trim()
          : defaults.highlight,
    } satisfies ContextMemberDraft;
  });

  const room_settings = rooms.map((room) => {
    const defaults = createDefaultRoomSetting(room);
    const saved = rawRoomMap.get(room.id);

    return {
      room_id: room.id,
      scene_preset: isEnumValue(ROOM_SCENE_PRESET_VALUES, saved?.scene_preset)
        ? saved.scene_preset
        : defaults.scene_preset,
      climate_policy: isEnumValue(CLIMATE_POLICY_VALUES, saved?.climate_policy)
        ? saved.climate_policy
        : defaults.climate_policy,
      privacy_guard_enabled:
        typeof saved?.privacy_guard_enabled === "boolean"
          ? saved.privacy_guard_enabled
          : defaults.privacy_guard_enabled,
      announcement_enabled:
        typeof saved?.announcement_enabled === "boolean"
          ? saved.announcement_enabled
          : defaults.announcement_enabled,
    } satisfies ContextRoomSetting;
  });

  const activeMemberId =
    typeof rawDraft?.active_member_id === "string" && memberIds.has(rawDraft.active_member_id)
      ? rawDraft.active_member_id
      : member_states.find((item) => item.presence === "home")?.member_id ?? null;

  return {
    home_mode: isEnumValue(HOME_MODE_VALUES, rawDraft?.home_mode)
      ? rawDraft.home_mode
      : fallback.home_mode,
    privacy_mode: isEnumValue(PRIVACY_MODE_VALUES, rawDraft?.privacy_mode)
      ? rawDraft.privacy_mode
      : fallback.privacy_mode,
    automation_level: isEnumValue(AUTOMATION_LEVEL_VALUES, rawDraft?.automation_level)
      ? rawDraft.automation_level
      : fallback.automation_level,
    home_assistant_status: isEnumValue(
      HOME_ASSISTANT_STATUS_VALUES,
      rawDraft?.home_assistant_status,
    )
      ? rawDraft.home_assistant_status
      : fallback.home_assistant_status,
    active_member_id: activeMemberId,
    voice_fast_path_enabled:
      typeof rawDraft?.voice_fast_path_enabled === "boolean"
        ? rawDraft.voice_fast_path_enabled
        : fallback.voice_fast_path_enabled,
    guest_mode_enabled:
      typeof rawDraft?.guest_mode_enabled === "boolean"
        ? rawDraft.guest_mode_enabled
        : fallback.guest_mode_enabled,
    child_protection_enabled:
      typeof rawDraft?.child_protection_enabled === "boolean"
        ? rawDraft.child_protection_enabled
        : fallback.child_protection_enabled,
    elder_care_watch_enabled:
      typeof rawDraft?.elder_care_watch_enabled === "boolean"
        ? rawDraft.elder_care_watch_enabled
        : fallback.elder_care_watch_enabled,
    quiet_hours_enabled:
      typeof rawDraft?.quiet_hours_enabled === "boolean"
        ? rawDraft.quiet_hours_enabled
        : fallback.quiet_hours_enabled,
    quiet_hours_start: normalizeTime(rawDraft?.quiet_hours_start, fallback.quiet_hours_start),
    quiet_hours_end: normalizeTime(rawDraft?.quiet_hours_end, fallback.quiet_hours_end),
    member_states,
    room_settings,
  };
}

export function loadContextDraft(householdId: string, members: Member[], rooms: Room[]) {
  return normalizeContextDraft(parseStoredDraft(householdId), members, rooms);
}

export function createFreshContextDraft(members: Member[], rooms: Room[]) {
  return normalizeContextDraft(null, members, rooms);
}

function toRawContextCenterDraft(
  config: ContextConfigRead | ContextConfigUpsertPayload | null,
): RawContextCenterDraft | null {
  if (!config) {
    return null;
  }

  return {
    home_mode: config.home_mode,
    privacy_mode: config.privacy_mode,
    automation_level: config.automation_level,
    home_assistant_status: config.home_assistant_status,
    active_member_id: config.active_member_id,
    voice_fast_path_enabled: config.voice_fast_path_enabled,
    guest_mode_enabled: config.guest_mode_enabled,
    child_protection_enabled: config.child_protection_enabled,
    elder_care_watch_enabled: config.elder_care_watch_enabled,
    quiet_hours_enabled: config.quiet_hours_enabled,
    quiet_hours_start: config.quiet_hours_start,
    quiet_hours_end: config.quiet_hours_end,
    member_states: config.member_states.map((item) => ({
      member_id: item.member_id,
      presence: item.presence,
      activity: item.activity,
      current_room_id: item.current_room_id,
      confidence: item.confidence,
      last_seen_minutes: item.last_seen_minutes,
      highlight: item.highlight,
    })),
    room_settings: config.room_settings.map((item) => ({
      room_id: item.room_id,
      scene_preset: item.scene_preset,
      climate_policy: item.climate_policy,
      privacy_guard_enabled: item.privacy_guard_enabled,
      announcement_enabled: item.announcement_enabled,
    })),
  };
}

export function createDraftFromContextConfig(
  config: ContextConfigRead | ContextConfigUpsertPayload | null,
  members: Member[],
  rooms: Room[],
) {
  return normalizeContextDraft(toRawContextCenterDraft(config), members, rooms);
}

export function toContextConfigPayload(draft: ContextCenterDraft): ContextConfigUpsertPayload {
  return {
    home_mode: draft.home_mode,
    privacy_mode: draft.privacy_mode,
    automation_level: draft.automation_level,
    home_assistant_status: draft.home_assistant_status,
    active_member_id: draft.active_member_id,
    voice_fast_path_enabled: draft.voice_fast_path_enabled,
    guest_mode_enabled: draft.guest_mode_enabled,
    child_protection_enabled: draft.child_protection_enabled,
    elder_care_watch_enabled: draft.elder_care_watch_enabled,
    quiet_hours_enabled: draft.quiet_hours_enabled,
    quiet_hours_start: draft.quiet_hours_start,
    quiet_hours_end: draft.quiet_hours_end,
    member_states: draft.member_states.map((item) => ({
      member_id: item.member_id,
      presence: item.presence,
      activity: item.activity,
      current_room_id: item.current_room_id,
      confidence: item.confidence,
      last_seen_minutes: item.last_seen_minutes,
      highlight: item.highlight,
    })),
    room_settings: draft.room_settings.map((item) => ({
      room_id: item.room_id,
      scene_preset: item.scene_preset,
      climate_policy: item.climate_policy,
      privacy_guard_enabled: item.privacy_guard_enabled,
      announcement_enabled: item.announcement_enabled,
    })),
  };
}

export function saveContextDraft(householdId: string, draft: ContextCenterDraft) {
  window.localStorage.setItem(getStorageKey(householdId), JSON.stringify(draft));
}

export function clearContextDraft(householdId: string) {
  window.localStorage.removeItem(getStorageKey(householdId));
}
