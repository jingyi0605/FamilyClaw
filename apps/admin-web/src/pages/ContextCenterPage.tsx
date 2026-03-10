import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import {
  ACTIVITY_LABELS,
  AUTOMATION_LEVEL_LABELS,
  CLIMATE_POLICY_LABELS,
  HOME_ASSISTANT_STATUS_LABELS,
  HOME_MODE_LABELS,
  PRIVACY_MODE_LABELS,
  PRESENCE_LABELS,
  ROOM_SCENE_PRESET_LABELS,
  createDraftFromContextConfig,
  createFreshContextDraft,
  loadContextDraft,
  saveContextDraft,
  toContextConfigPayload,
  type ActivityStatus,
  type AutomationLevel,
  type ClimatePolicy,
  type ContextCenterDraft,
  type ContextMemberDraft,
  type ContextRoomSetting,
  type HomeAssistantStatus,
  type HouseholdMode,
  type PresenceStatus,
  type PrivacyMode,
  type RoomScenePreset,
} from "../lib/contextDraft";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type {
  AiCapabilityRoute,
  AuditLog,
  ContextOverviewMemberState,
  ContextOverviewRead,
  ContextOverviewRoomOccupancy,
  ContextStateSource,
  Device,
  FamilyQaSuggestionItem,
  Member,
  ReminderOverviewRead,
  Room,
  SceneExecution,
} from "../types";

type Tone = "default" | "success" | "warning" | "danger";

type SelectionOption<T extends string> = {
  value: T;
  label: string;
  description: string;
};

type InsightCardData = {
  key: string;
  title: string;
  detail: string;
  tone: Tone;
};

const homeModeOptions: SelectionOption<HouseholdMode>[] = [
  { value: "home", label: "居家模式", description: "面向正常在家服务，强调舒适和响应速度。" },
  { value: "away", label: "离家模式", description: "降低设备活跃度，优先安全与节能。" },
  { value: "night", label: "夜间模式", description: "压低播报与灯光强度，减少打扰。" },
  { value: "sleep", label: "睡眠模式", description: "面向休息时段，严格限制主动打扰。" },
  { value: "custom", label: "自定义", description: "为特殊家庭状态保留人工覆盖空间。" },
];

const privacyModeOptions: SelectionOption<PrivacyMode>[] = [
  { value: "balanced", label: "平衡保护", description: "兼顾体验和保护，适合日常默认。" },
  { value: "strict", label: "严格保护", description: "优先最小暴露，敏感房间与敏感信息更保守。" },
  { value: "care", label: "关怀优先", description: "优先老人和儿童服务，但仍保留风险边界。" },
];

const automationOptions: SelectionOption<AutomationLevel>[] = [
  { value: "manual", label: "手动优先", description: "系统只建议，不主动动作。" },
  { value: "assisted", label: "辅助自动", description: "系统给建议并执行低风险动作。" },
  { value: "automatic", label: "自动优先", description: "系统在高置信场景下直接执行。" },
];

const haStatusOptions: SelectionOption<HomeAssistantStatus>[] = [
  { value: "healthy", label: "连接健康", description: "设备同步与动作执行预计正常。" },
  { value: "degraded", label: "部分降级", description: "允许继续运行，但需关注失败项。" },
  { value: "offline", label: "连接离线", description: "设备状态与执行将退化为只读或不可用。" },
];

const presenceOptions: SelectionOption<PresenceStatus>[] = [
  { value: "home", label: "在家", description: "可参与当前房间与服务决策。" },
  { value: "away", label: "外出", description: "不参与房间占用与即时服务。" },
  { value: "unknown", label: "未知", description: "系统不确定，保持保守处理。" },
];

const activityOptions: SelectionOption<ActivityStatus>[] = [
  { value: "active", label: "活跃中", description: "适合即时响应与互动。" },
  { value: "focused", label: "专注中", description: "减少打扰，优先静默式服务。" },
  { value: "resting", label: "休息中", description: "偏低打扰，设备联动更柔和。" },
  { value: "sleeping", label: "睡眠中", description: "除高优先级事项外避免主动触达。" },
  { value: "idle", label: "空闲中", description: "可作为公共空间优先服务对象。" },
];

const roomSceneOptions: SelectionOption<RoomScenePreset>[] = [
  { value: "auto", label: "自动", description: "按成员和时间动态决定房间氛围。" },
  { value: "welcome", label: "欢迎", description: "偏亮、偏开放，适合公共空间。" },
  { value: "focus", label: "专注", description: "偏安静、偏定向，适合书房。" },
  { value: "rest", label: "休息", description: "弱提醒、柔和灯光，适合卧室。" },
  { value: "quiet", label: "安静", description: "尽量不播报、不打扰。" },
];

const climatePolicyOptions: SelectionOption<ClimatePolicy>[] = [
  { value: "follow_member", label: "跟随成员", description: "优先参考当前在场成员偏好。" },
  { value: "follow_room", label: "跟随房间", description: "按房间基准策略维持环境。" },
  { value: "manual", label: "手动固定", description: "保持人工设定，不做自动调整。" },
];

function formatRole(role: Member["role"]) {
  switch (role) {
    case "admin":
      return "管理员";
    case "adult":
      return "成人";
    case "child":
      return "儿童";
    case "elder":
      return "长辈";
    case "guest":
      return "访客";
  }
}

function formatRoomType(roomType: Room["room_type"]) {
  switch (roomType) {
    case "living_room":
      return "客厅";
    case "bedroom":
      return "卧室";
    case "study":
      return "书房";
    case "entrance":
      return "玄关";
    case "kitchen":
      return "厨房";
    case "bathroom":
      return "卫生间";
    case "gym":
      return "健身房";
    case "garage":
      return "车库";
  }
}

function formatPrivacyLevel(level: Room["privacy_level"]) {
  switch (level) {
    case "public":
      return "公共";
    case "private":
      return "私密";
    case "sensitive":
      return "敏感";
  }
}

function formatDeviceType(deviceType: Device["device_type"]) {
  switch (deviceType) {
    case "light":
      return "灯光";
    case "ac":
      return "空调";
    case "curtain":
      return "窗帘";
    case "speaker":
      return "音箱";
    case "camera":
      return "摄像头";
    case "sensor":
      return "传感器";
    case "lock":
      return "门锁";
  }
}

function formatLastSeen(minutes: number) {
  if (minutes <= 0) {
    return "刚刚更新";
  }

  if (minutes < 60) {
    return `${minutes} 分钟前更新`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours} 小时前更新`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "暂无记录";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatStateSource(source: ContextStateSource) {
  switch (source) {
    case "snapshot":
      return "实时快照";
    case "configured":
      return "配置回填";
    case "default":
      return "默认值";
  }
}

function toInsightTone(tone: "info" | "success" | "warning" | "danger"): Tone {
  if (tone === "info") {
    return "default";
  }

  return tone;
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "未知错误";
}

function buildFallbackMembers(householdId: string, overview: ContextOverviewRead | null) {
  if (!overview) {
    return [] as Member[];
  }

  return overview.member_states.map((item) => ({
    id: item.member_id,
    household_id: householdId,
    name: item.name,
    nickname: null,
    role: item.role,
    age_group: null,
    birthday: null,
    phone: null,
    status: "active" as const,
    guardian_member_id: null,
    created_at: overview.generated_at,
    updated_at: item.updated_at ?? overview.generated_at,
  }));
}

function buildFallbackRooms(householdId: string, overview: ContextOverviewRead | null) {
  if (!overview) {
    return [] as Room[];
  }

  return overview.room_occupancy.map((item) => ({
    id: item.room_id,
    household_id: householdId,
    name: item.name,
    room_type: item.room_type,
    privacy_level: item.privacy_level,
    created_at: overview.generated_at,
  }));
}

function MetricCard(props: {
  label: string;
  value: string;
  detail: string;
  tone?: Tone;
}) {
  const tone = props.tone ?? "default";

  return (
    <article className={`metric-card ${tone}`}>
      <span className="metric-label">{props.label}</span>
      <strong className="metric-value">{props.value}</strong>
      <small className="metric-detail">{props.detail}</small>
    </article>
  );
}

function InsightCard({ title, detail, tone }: Omit<InsightCardData, "key">) {
  return (
    <article className={`insight-card ${tone}`}>
      <strong>{title}</strong>
      <p>{detail}</p>
    </article>
  );
}

function SelectionGroup<T extends string>(props: {
  title: string;
  value: T;
  options: SelectionOption<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="selection-group">
      <div className="selection-group-head">
        <strong>{props.title}</strong>
      </div>
      <div className="option-group">
        {props.options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`option-pill${props.value === option.value ? " active" : ""}`}
            onClick={() => props.onChange(option.value)}
            title={option.description}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ToggleField(props: {
  label: string;
  description: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="toggle-row">
      <div>
        <strong>{props.label}</strong>
        <p>{props.description}</p>
      </div>
      <button
        type="button"
        className={`toggle-switch${props.checked ? " enabled" : ""}`}
        onClick={props.onToggle}
        aria-pressed={props.checked}
      >
        <span />
      </button>
    </div>
  );
}

export function ContextCenterPage() {
  const { household } = useHousehold();
  const [members, setMembers] = useState<Member[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [overview, setOverview] = useState<ContextOverviewRead | null>(null);
  const [draft, setDraft] = useState<ContextCenterDraft | null>(null);
  const [configVersion, setConfigVersion] = useState<number | null>(null);
  const [configUpdatedAt, setConfigUpdatedAt] = useState<string | null>(null);
  const [reminderOverview, setReminderOverview] = useState<ReminderOverviewRead | null>(null);
  const [sceneExecutions, setSceneExecutions] = useState<SceneExecution[]>([]);
  const [qaSuggestions, setQaSuggestions] = useState<FamilyQaSuggestionItem[]>([]);
  const [aiRoutes, setAiRoutes] = useState<AiCapabilityRoute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  async function loadPageData(successMessage = "") {
    if (!household?.id) {
      setMembers([]);
      setRooms([]);
      setDevices([]);
      setLogs([]);
      setOverview(null);
      setDraft(null);
      setConfigVersion(null);
      setConfigUpdatedAt(null);
      setReminderOverview(null);
      setSceneExecutions([]);
      setQaSuggestions([]);
      setAiRoutes([]);
      setError("");
      setStatus("");
      return;
    }

    setLoading(true);
    setError("");
    if (!successMessage) {
      setStatus("");
    }

    const [
      overviewResult,
      configResult,
      membersResult,
      roomsResult,
      devicesResult,
      logsResult,
      remindersResult,
      scenesResult,
      suggestionsResult,
      aiRoutesResult,
    ] = await Promise.allSettled([
      api.getContextOverview(household.id),
      api.getContextConfig(household.id),
      api.listMembers(household.id),
      api.listRooms(household.id),
      api.listDevices(household.id),
      api.listAuditLogs(household.id),
      api.getReminderOverview(household.id),
      api.listSceneExecutions(household.id),
      api.listFamilyQaSuggestions(household.id),
      api.listAiRoutes(household.id),
    ]);

    const nextOverview = overviewResult.status === "fulfilled" ? overviewResult.value : null;
    const overviewFallbackMembers = buildFallbackMembers(household.id, nextOverview);
    const overviewFallbackRooms = buildFallbackRooms(household.id, nextOverview);

    const nextMembers =
      membersResult.status === "fulfilled"
        ? membersResult.value.items
        : overviewFallbackMembers.length > 0
          ? overviewFallbackMembers
          : members;
    const nextRooms =
      roomsResult.status === "fulfilled"
        ? roomsResult.value.items
        : overviewFallbackRooms.length > 0
          ? overviewFallbackRooms
          : rooms;
    const nextDevices =
      devicesResult.status === "fulfilled" ? devicesResult.value.items : devices;
    const nextLogs = logsResult.status === "fulfilled" ? logsResult.value.items : logs;
    const nextDraft =
      configResult.status === "fulfilled"
        ? createDraftFromContextConfig(configResult.value, nextMembers, nextRooms)
        : loadContextDraft(household.id, nextMembers, nextRooms);

    setMembers(nextMembers);
    setRooms(nextRooms);
    setDevices(nextDevices);
    setLogs(nextLogs);
    setOverview(nextOverview);
    setDraft(nextDraft);
    setReminderOverview(remindersResult.status === "fulfilled" ? remindersResult.value : null);
    setSceneExecutions(scenesResult.status === "fulfilled" ? scenesResult.value : []);
    setQaSuggestions(suggestionsResult.status === "fulfilled" ? suggestionsResult.value.items : []);
    setAiRoutes(aiRoutesResult.status === "fulfilled" ? aiRoutesResult.value : []);

    if (configResult.status === "fulfilled") {
      setConfigVersion(configResult.value.version);
      setConfigUpdatedAt(configResult.value.updated_at);
      saveContextDraft(household.id, nextDraft);
    } else {
      setConfigVersion(null);
      setConfigUpdatedAt(null);
    }

    const failedMessages = [
      overviewResult.status === "rejected" ? "上下文总览加载失败" : "",
      configResult.status === "rejected" ? "上下文配置加载失败（已回退本地草稿）" : "",
      membersResult.status === "rejected" ? "成员数据加载失败" : "",
      roomsResult.status === "rejected" ? "房间数据加载失败" : "",
      devicesResult.status === "rejected" ? "设备数据加载失败" : "",
      logsResult.status === "rejected" ? "审计日志加载失败" : "",
      remindersResult.status === "rejected" ? "提醒总览加载失败" : "",
      scenesResult.status === "rejected" ? "场景执行摘要加载失败" : "",
      suggestionsResult.status === "rejected" ? "问答建议加载失败" : "",
      aiRoutesResult.status === "rejected" ? "AI 路由摘要加载失败" : "",
    ].filter(Boolean);

    if (failedMessages.length > 0) {
      setError(`部分数据未加载成功：${failedMessages.join("；")}。页面继续展示当前可用内容。`);
    }

    if (successMessage) {
      setStatus(successMessage);
    } else if (configResult.status === "rejected") {
      setStatus("后端 context configs 暂不可用，当前已回退到浏览器本地草稿。保存时仍会优先尝试回写后端。");
    } else if (overviewResult.status === "rejected") {
      setStatus("上下文配置已从后端加载，但总览接口暂不可用，页面会尽量用基础数据补齐。");
    }

    setLoading(false);
  }

  useEffect(() => {
    void loadPageData();
  }, [household?.id]);

  const memberById = useMemo(
    () => new Map(members.map((member) => [member.id, member] as const)),
    [members],
  );
  const roomById = useMemo(
    () => new Map(rooms.map((room) => [room.id, room] as const)),
    [rooms],
  );

  const sortedLogs = useMemo(
    () => [...logs].sort((left, right) => right.created_at.localeCompare(left.created_at)),
    [logs],
  );

  const deviceCountsByRoom = useMemo(() => {
    const counts = new Map<string, Device[]>();

    for (const device of devices) {
      if (!device.room_id) {
        continue;
      }

      const current = counts.get(device.room_id) ?? [];
      current.push(device);
      counts.set(device.room_id, current);
    }

    return counts;
  }, [devices]);

  const localMemberStates = useMemo<ContextOverviewMemberState[]>(() => {
    if (!draft) {
      return [];
    }

    return draft.member_states.map((item) => {
      const member = memberById.get(item.member_id);
      const roomName = item.current_room_id ? roomById.get(item.current_room_id)?.name ?? null : null;

      return {
        member_id: item.member_id,
        name: member?.name ?? "未知成员",
        role: member?.role ?? "adult",
        presence: item.presence,
        activity: item.activity,
        current_room_id: item.current_room_id,
        current_room_name: roomName,
        confidence: item.confidence,
        last_seen_minutes: item.last_seen_minutes,
        highlight: item.highlight,
        source: "configured",
        source_summary: null,
        updated_at: configUpdatedAt,
      };
    });
  }, [configUpdatedAt, draft, memberById, roomById]);

  const localRoomOccupancy = useMemo<ContextOverviewRoomOccupancy[]>(() => {
    if (!draft) {
      return [];
    }

    return rooms.map((room) => {
      const roomSetting = draft.room_settings.find((item) => item.room_id === room.id);
      const occupants = localMemberStates
        .filter((item) => item.presence === "home" && item.current_room_id === room.id)
        .map((item) => ({
          member_id: item.member_id,
          name: item.name,
          role: item.role,
          presence: item.presence,
          activity: item.activity,
        }));
      const roomDevices = deviceCountsByRoom.get(room.id) ?? [];

      return {
        room_id: room.id,
        name: room.name,
        room_type: room.room_type,
        privacy_level: room.privacy_level,
        occupant_count: occupants.length,
        occupants,
        device_count: roomDevices.length,
        online_device_count: roomDevices.filter((device) => device.status === "active").length,
        scene_preset: roomSetting?.scene_preset ?? "auto",
        climate_policy: roomSetting?.climate_policy ?? "follow_room",
        privacy_guard_enabled: roomSetting?.privacy_guard_enabled ?? (room.privacy_level !== "public"),
        announcement_enabled: roomSetting?.announcement_enabled ?? (room.privacy_level === "public"),
      };
    });
  }, [deviceCountsByRoom, draft, localMemberStates, rooms]);

  const displayMemberStates = overview?.member_states ?? localMemberStates;
  const displayRoomOccupancy = overview?.room_occupancy ?? localRoomOccupancy;
  const activeMember = overview?.active_member
    ? overview.active_member
    : draft?.active_member_id
      ? localMemberStates.find((item) => item.member_id === draft.active_member_id) ?? null
      : null;

  const onlineDeviceCount = devices.filter((device) => device.status === "active").length;
  const offlineDeviceCount = devices.filter((device) => device.status === "offline").length;
  const inactiveDeviceCount = devices.filter((device) => device.status === "inactive").length;
  const controllableDeviceCount = devices.filter((device) => device.controllable).length;
  const deviceSummary =
    overview?.device_summary ??
    ({
      total: devices.length,
      active: onlineDeviceCount,
      offline: offlineDeviceCount,
      inactive: inactiveDeviceCount,
      controllable: controllableDeviceCount,
    } as const);

  const homeMemberCount = displayMemberStates.filter((item) => item.presence === "home").length;
  const unknownMemberCount = displayMemberStates.filter((item) => item.presence === "unknown").length;
  const occupiedRoomCount = displayRoomOccupancy.filter((item) => item.occupant_count > 0).length;
  const memberTotal = members.length > 0 ? members.length : displayMemberStates.length;
  const roomTotal = rooms.length > 0 ? rooms.length : displayRoomOccupancy.length;
  const focusMemberCount = displayMemberStates.filter(
    (item) => item.presence === "home" && (item.role === "child" || item.role === "elder"),
  ).length;
  const latestSyncLog = sortedLogs.find((log) => log.action === "device.sync.home_assistant") ?? null;

  const displayInsights = useMemo<InsightCardData[]>(() => {
    if (overview) {
      return overview.insights.map((item) => ({
        key: item.code,
        title: item.title,
        detail: item.message,
        tone: toInsightTone(item.tone),
      }));
    }

    if (!draft) {
      return [];
    }

    const childAtHome = displayMemberStates.some(
      (item) => item.role === "child" && item.presence === "home",
    );
    const elderAtHome = displayMemberStates.some(
      (item) => item.role === "elder" && item.presence === "home",
    );
    const sensitiveOccupied = displayRoomOccupancy.some(
      (item) => item.privacy_level === "sensitive" && item.occupant_count > 0 && !item.privacy_guard_enabled,
    );

    return [
      {
        key: "guest-mode",
        title: "访客与隐私",
        detail: draft.guest_mode_enabled
          ? "访客模式已开启，页面应默认收紧公共信息展示与高风险控制。"
          : "当前未开启访客模式，默认按家庭成员规则运行。",
        tone: draft.guest_mode_enabled ? "warning" : "default",
      },
      {
        key: "child-protection",
        title: "儿童保护",
        detail: childAtHome
          ? draft.child_protection_enabled
            ? "家中有儿童且儿童保护已开启，内容和控制链路应保持保守。"
            : "家中有儿童但儿童保护未开启，这很危险。别让系统乱播、乱控。"
          : "当前没有儿童在家，儿童保护处于待命状态。",
        tone: childAtHome ? (draft.child_protection_enabled ? "success" : "danger") : "default",
      },
      {
        key: "elder-care",
        title: "老人关怀",
        detail: elderAtHome
          ? draft.elder_care_watch_enabled
            ? "家中有长辈且关怀模式开启，提醒与播报应优先低打扰。"
            : "家中有长辈但关怀模式未启用，提醒策略需要补上。"
          : "当前没有长辈在家，关怀链路无需提到最高优先级。",
        tone: elderAtHome ? (draft.elder_care_watch_enabled ? "success" : "warning") : "default",
      },
      {
        key: "privacy-guard",
        title: "敏感房间风险",
        detail: sensitiveOccupied
          ? "敏感房间有人且隐私保护被关闭，这会把系统推到很蠢的位置。赶紧收紧策略。"
          : "敏感房间当前没有明显暴露风险。",
        tone: sensitiveOccupied ? "danger" : "success",
      },
    ];
  }, [displayMemberStates, displayRoomOccupancy, draft, overview]);

  const sourceMessage = useMemo(() => {
    if (overview && configVersion !== null) {
      return `当前页面已经切到后端 context overview / configs：总览生成于 ${formatDateTime(overview.generated_at)}，配置版本 v${configVersion}${overview.degraded ? "，当前处于降级聚合模式" : ""}。上方总览展示已落库状态，下方配置区是可编辑草稿，保存后才会回写后端。`;
    }

    if (configVersion !== null) {
      return `配置已从后端加载（v${configVersion}），但总览接口暂不可用，页面会尽量用基础主数据补齐展示。`;
    }

    return "后端上下文配置暂不可用，当前使用浏览器本地草稿兜底；保存时会先尝试回写后端，失败时再退回本地。";
  }, [configVersion, overview]);

  function updateDraft(updater: (current: ContextCenterDraft) => ContextCenterDraft) {
    setDraft((current) => {
      if (!current) {
        return current;
      }

      return updater(current);
    });
    setStatus("");
  }

  function updateMemberState(memberId: string, updater: (current: ContextMemberDraft) => ContextMemberDraft) {
    updateDraft((current) => {
      const nextMemberStates = current.member_states.map((item) =>
        item.member_id === memberId ? updater(item) : item,
      );
      const nextHomeMemberIds = new Set(
        nextMemberStates
          .filter((item) => item.presence === "home")
          .map((item) => item.member_id),
      );

      return {
        ...current,
        member_states: nextMemberStates,
        active_member_id:
          current.active_member_id && nextHomeMemberIds.has(current.active_member_id)
            ? current.active_member_id
            : nextMemberStates.find((item) => item.presence === "home")?.member_id ?? null,
      };
    });
  }

  function updateRoomSetting(roomId: string, updater: (current: ContextRoomSetting) => ContextRoomSetting) {
    updateDraft((current) => ({
      ...current,
      room_settings: current.room_settings.map((item) =>
        item.room_id === roomId ? updater(item) : item,
      ),
    }));
  }

  async function handleSaveDraft() {
    if (!household?.id || !draft) {
      return;
    }

    setLoading(true);
    setStatus("");
    setError("");

    try {
      const saved = await api.updateContextConfig(household.id, toContextConfigPayload(draft));
      const normalizedDraft = createDraftFromContextConfig(saved, members, rooms);
      saveContextDraft(household.id, normalizedDraft);
      setDraft(normalizedDraft);
      setConfigVersion(saved.version);
      setConfigUpdatedAt(saved.updated_at);

      const [overviewResult, logsResult] = await Promise.allSettled([
        api.getContextOverview(household.id),
        api.listAuditLogs(household.id),
      ]);

      if (overviewResult.status === "fulfilled") {
        setOverview(overviewResult.value);
      }
      if (logsResult.status === "fulfilled") {
        setLogs(logsResult.value.items);
      }

      if (overviewResult.status === "rejected") {
        setError(`配置已保存，但总览刷新失败：${getErrorMessage(overviewResult.reason)}`);
        setStatus("上下文配置已保存到后端，总览暂时保留上一版数据。");
      } else {
        setStatus("上下文配置已保存到后端，并已刷新家庭总览。");
      }
    } catch (saveError) {
      saveContextDraft(household.id, draft);
      setError(`后端保存失败：${getErrorMessage(saveError)}`);
      setStatus("后端保存失败，已回退保存到浏览器本地草稿。");
    }

    setLoading(false);
  }

  function handleResetDraft() {
    if (!household?.id) {
      return;
    }

    const fresh = createFreshContextDraft(members, rooms);
    setDraft(fresh);
    saveContextDraft(household.id, fresh);
    setStatus("已重置当前编辑草稿；如需真正生效，请继续保存到后端。");
    setError("");
  }

  async function handleReload() {
    await loadPageData("数据已刷新。");
  }

  if (!household?.id) {
    return <StatusMessage tone="info" message="请先在“家庭管理”页面创建或加载当前家庭。" />;
  }

  if (!draft) {
    return <StatusMessage tone="info" message="正在加载家居上下文页面，请稍等。" />;
  }

  return (
    <div className="page-grid context-center-page">
      <section className="context-hero">
        <div>
          <div className="hero-kicker">Spec 002 · 家居接入与上下文中心</div>
          <h3>{overview?.household_name ?? household.name}</h3>
          <p>
            这不是设备清单页，而是当前家庭运行状态的总控面板。先把数据结构看清楚，
            才能谈后面的提醒、问答和场景编排。
          </p>
          <div className="hero-chip-row">
            <span className="hero-chip">{HOME_MODE_LABELS[overview?.home_mode ?? draft.home_mode]}</span>
            <span className="hero-chip">{PRIVACY_MODE_LABELS[overview?.privacy_mode ?? draft.privacy_mode]}</span>
            <span className="hero-chip">
              {AUTOMATION_LEVEL_LABELS[overview?.automation_level ?? draft.automation_level]}
            </span>
            <span className={`hero-chip ${overview?.home_assistant_status ?? draft.home_assistant_status}`}>
              {
                HOME_ASSISTANT_STATUS_LABELS[
                  overview?.home_assistant_status ?? draft.home_assistant_status
                ]
              }
            </span>
          </div>
        </div>
        <div className="context-hero-side">
          <div className="hero-spotlight">
            <span>当前活跃成员</span>
            <strong>{activeMember?.name ?? "未指定"}</strong>
            <small>
              {activeMember
                ? `${PRESENCE_LABELS[activeMember.presence]} · ${ACTIVITY_LABELS[activeMember.activity]} · ${formatStateSource(activeMember.source)}`
                : "请在配置区指定当前优先服务对象"}
            </small>
          </div>
          <div className="hero-actions">
            <button type="button" onClick={() => void handleReload()} disabled={loading}>
              {loading ? "刷新中..." : "刷新数据"}
            </button>
            <button type="button" className="ghost" onClick={() => void handleSaveDraft()} disabled={loading}>
              {configVersion !== null ? "保存到后端" : "保存配置"}
            </button>
          </div>
        </div>
      </section>

      <div className="metric-grid">
        <MetricCard
          label="在家成员"
          value={`${homeMemberCount}`}
          detail={`共 ${memberTotal} 名成员，其中 ${unknownMemberCount} 名状态未知`}
          tone="success"
        />
        <MetricCard
          label="已占用房间"
          value={`${occupiedRoomCount}/${roomTotal}`}
          detail={overview ? "按后端 context overview 聚合统计" : "按当前草稿与主数据推导"}
        />
        <MetricCard
          label="在线设备"
          value={`${deviceSummary.active}/${deviceSummary.total}`}
          detail={`离线 ${deviceSummary.offline} 台，可控 ${deviceSummary.controllable} 台`}
          tone={deviceSummary.offline > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="重点关注"
          value={`${focusMemberCount}`}
          detail="在家儿童与长辈数量，决定提醒与保护优先级"
        />
      </div>

      {error ? <StatusMessage tone="error" message={error} /> : null}
      {status ? <StatusMessage tone="success" message={status} /> : null}
      <StatusMessage tone="info" message={sourceMessage} />

      <PageSection
        title="关键洞察"
        description="把最容易出问题的地方亮出来，别等系统做错事了才发现。"
      >
        <div className="insight-grid">
          {displayInsights.map((insight) => (
            <InsightCard key={insight.key} title={insight.title} detail={insight.detail} tone={insight.tone} />
          ))}
        </div>
      </PageSection>

      <PageSection
        title="成员状态面板"
        description="成员状态既是展示面，也是后续问答、提醒和设备联动的上下文输入。"
      >
        <div className="member-card-grid">
          {displayMemberStates.map((memberState) => (
            <article key={memberState.member_id} className="member-card">
              <div className="member-card-head">
                <div>
                  <strong>{memberState.name}</strong>
                  <p>
                    {formatRole(memberState.role)} · {formatStateSource(memberState.source)}
                  </p>
                </div>
                <div className="pill-stack">
                  <span className={`status-pill ${memberState.presence}`}>
                    {PRESENCE_LABELS[memberState.presence]}
                  </span>
                  <span className="status-pill neutral">{ACTIVITY_LABELS[memberState.activity]}</span>
                </div>
              </div>
              <div className="member-card-body">
                <div className="member-meta-grid">
                  <div>
                    <span>所在房间</span>
                    <strong>{memberState.current_room_name ?? "未在房间中"}</strong>
                  </div>
                  <div>
                    <span>最近更新</span>
                    <strong>{formatLastSeen(memberState.last_seen_minutes)}</strong>
                  </div>
                  <div>
                    <span>状态来源</span>
                    <strong>{formatStateSource(memberState.source)}</strong>
                  </div>
                  <div>
                    <span>更新时间</span>
                    <strong>{formatDateTime(memberState.updated_at)}</strong>
                  </div>
                </div>
                <div className="confidence-row">
                  <div>
                    <span>识别置信度</span>
                    <strong>{memberState.confidence}%</strong>
                  </div>
                  <div className="confidence-bar">
                    <span style={{ width: `${memberState.confidence}%` }} />
                  </div>
                </div>
                <p className="member-highlight">{memberState.highlight}</p>
              </div>
            </article>
          ))}
        </div>
      </PageSection>

      <PageSection
        title="房间热区与设备状态"
        description="房间是上下文决策的关键枢纽。别把成员、房间、设备拆成三张互不相干的表。"
      >
        <div className="room-card-grid">
          {displayRoomOccupancy.map((roomState) => {
            const roomDevices = deviceCountsByRoom.get(roomState.room_id) ?? [];

            return (
              <article key={roomState.room_id} className="room-card">
                <div className="room-card-head">
                  <div>
                    <strong>{roomState.name}</strong>
                    <p>
                      {formatRoomType(roomState.room_type)} · {formatPrivacyLevel(roomState.privacy_level)}
                    </p>
                  </div>
                  <span className={`status-pill ${roomState.occupant_count > 0 ? "home" : "neutral"}`}>
                    {roomState.occupant_count > 0 ? `${roomState.occupant_count} 人在场` : "当前空闲"}
                  </span>
                </div>
                <div className="room-stat-list">
                  <div>
                    <span>房间策略</span>
                    <strong>{ROOM_SCENE_PRESET_LABELS[roomState.scene_preset]}</strong>
                  </div>
                  <div>
                    <span>空调策略</span>
                    <strong>{CLIMATE_POLICY_LABELS[roomState.climate_policy]}</strong>
                  </div>
                  <div>
                    <span>设备数量</span>
                    <strong>{roomState.device_count}</strong>
                  </div>
                  <div>
                    <span>在线设备</span>
                    <strong>{roomState.online_device_count}</strong>
                  </div>
                  <div>
                    <span>当前成员</span>
                    <strong>
                      {roomState.occupants.length > 0
                        ? roomState.occupants.map((item) => item.name).join("、")
                        : "暂无"}
                    </strong>
                  </div>
                </div>
                <div className="device-chip-row">
                  {roomDevices.length > 0 ? (
                    roomDevices.map((device) => (
                      <span key={device.id} className={`device-chip ${device.status}`}>
                        {formatDeviceType(device.device_type)} · {device.name}
                      </span>
                    ))
                  ) : roomState.device_count > 0 ? (
                    <span className="device-chip inactive">设备明细未加载，但总览中已有统计</span>
                  ) : (
                    <span className="device-chip empty">暂无设备</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </PageSection>

      <PageSection
        title="上下文配置界面"
        description="上半部分展示当前已生效状态，下半部分是可编辑草稿。页面会优先保存到后端 context configs，失败时再回退本地。"
        actions={
          <div className="panel-actions-inline">
            <button type="button" className="ghost" onClick={handleResetDraft} disabled={loading}>
              重置草稿
            </button>
            <button type="button" onClick={() => void handleSaveDraft()} disabled={loading}>
              {loading ? "保存中..." : "保存到后端"}
            </button>
          </div>
        }
      >
        <div className="config-layout">
          <article className="config-card">
            <div className="config-card-head">
              <h4>家庭级策略</h4>
              <p>
                控制全局模式、隐私强度和自动化边界。
                {configVersion !== null
                  ? ` 当前后端版本 v${configVersion}，最近更新于 ${formatDateTime(configUpdatedAt)}。`
                  : " 当前尚未拿到后端配置版本，页面正使用本地草稿。"}
              </p>
            </div>
            <div className="config-section-grid">
              <SelectionGroup
                title="家庭模式"
                value={draft.home_mode}
                options={homeModeOptions}
                onChange={(value) => updateDraft((current) => ({ ...current, home_mode: value }))}
              />
              <SelectionGroup
                title="隐私模式"
                value={draft.privacy_mode}
                options={privacyModeOptions}
                onChange={(value) => updateDraft((current) => ({ ...current, privacy_mode: value }))}
              />
              <SelectionGroup
                title="自动化等级"
                value={draft.automation_level}
                options={automationOptions}
                onChange={(value) =>
                  updateDraft((current) => ({ ...current, automation_level: value }))
                }
              />
              <SelectionGroup
                title="HA 连接状态"
                value={draft.home_assistant_status}
                options={haStatusOptions}
                onChange={(value) =>
                  updateDraft((current) => ({ ...current, home_assistant_status: value }))
                }
              />
              <ToggleField
                label="访客模式"
                description="开启后优先收紧公共信息展示，并限制高风险控制能力。"
                checked={draft.guest_mode_enabled}
                onToggle={() =>
                  updateDraft((current) => ({
                    ...current,
                    guest_mode_enabled: !current.guest_mode_enabled,
                  }))
                }
              />
              <ToggleField
                label="儿童保护"
                description="控制内容暴露、播报强度和儿童相关设备动作边界。"
                checked={draft.child_protection_enabled}
                onToggle={() =>
                  updateDraft((current) => ({
                    ...current,
                    child_protection_enabled: !current.child_protection_enabled,
                  }))
                }
              />
              <ToggleField
                label="老人关怀"
                description="开启后优先低打扰提醒、安全确认和关键状态关注。"
                checked={draft.elder_care_watch_enabled}
                onToggle={() =>
                  updateDraft((current) => ({
                    ...current,
                    elder_care_watch_enabled: !current.elder_care_watch_enabled,
                  }))
                }
              />
              <ToggleField
                label="语音快路径"
                description="高置信、低风险的请求可以更快响应，但别越过边界。"
                checked={draft.voice_fast_path_enabled}
                onToggle={() =>
                  updateDraft((current) => ({
                    ...current,
                    voice_fast_path_enabled: !current.voice_fast_path_enabled,
                  }))
                }
              />
              <label>
                当前优先服务成员
                <select
                  value={draft.active_member_id ?? ""}
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      active_member_id: event.target.value || null,
                    }))
                  }
                >
                  <option value="">未指定</option>
                  {draft.member_states
                    .filter((item) => item.presence === "home")
                    .map((item) => {
                      const member = memberById.get(item.member_id);
                      if (!member) {
                        return null;
                      }

                      return (
                        <option key={member.id} value={member.id}>
                          {member.name} · {formatRole(member.role)}
                        </option>
                      );
                    })}
                </select>
              </label>
              <div className="time-window-grid">
                <label>
                  静默开始时间
                  <input
                    type="time"
                    value={draft.quiet_hours_start}
                    disabled={!draft.quiet_hours_enabled}
                    onChange={(event) =>
                      updateDraft((current) => ({
                        ...current,
                        quiet_hours_start: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  静默结束时间
                  <input
                    type="time"
                    value={draft.quiet_hours_end}
                    disabled={!draft.quiet_hours_enabled}
                    onChange={(event) =>
                      updateDraft((current) => ({
                        ...current,
                        quiet_hours_end: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>
              <ToggleField
                label="静默时段"
                description="控制夜间播报和主动提醒的打扰级别。"
                checked={draft.quiet_hours_enabled}
                onToggle={() =>
                  updateDraft((current) => ({
                    ...current,
                    quiet_hours_enabled: !current.quiet_hours_enabled,
                  }))
                }
              />
            </div>
          </article>

          <article className="config-card">
            <div className="config-card-head">
              <h4>成员状态草稿</h4>
              <p>这里编辑的是将要写回后端的结构，不是已经生效的实时快照。</p>
            </div>
            <div className="member-editor-list">
              {draft.member_states.map((memberState) => {
                const member = memberById.get(memberState.member_id);
                if (!member) {
                  return null;
                }

                return (
                  <section key={member.id} className="member-editor-card">
                    <div className="member-editor-head">
                      <div>
                        <strong>{member.name}</strong>
                        <p>{formatRole(member.role)}</p>
                      </div>
                      <div className="pill-stack">
                        <span className={`status-pill ${memberState.presence}`}>
                          {PRESENCE_LABELS[memberState.presence]}
                        </span>
                        <span className="status-pill neutral">
                          {memberState.confidence}% 置信度
                        </span>
                      </div>
                    </div>
                    <div className="editor-grid">
                      <label>
                        在家状态
                        <select
                          value={memberState.presence}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              presence: event.target.value as PresenceStatus,
                              current_room_id:
                                event.target.value === "home" ? current.current_room_id : null,
                            }))
                          }
                        >
                          {presenceOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        活动状态
                        <select
                          value={memberState.activity}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              activity: event.target.value as ActivityStatus,
                            }))
                          }
                        >
                          {activityOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        当前房间
                        <select
                          value={memberState.current_room_id ?? ""}
                          disabled={memberState.presence !== "home"}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              current_room_id: event.target.value || null,
                            }))
                          }
                        >
                          <option value="">未指定</option>
                          {rooms.map((room) => (
                            <option key={room.id} value={room.id}>
                              {room.name} · {formatRoomType(room.room_type)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        置信度
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={memberState.confidence}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              confidence: Number(event.target.value),
                            }))
                          }
                        />
                      </label>
                      <label>
                        最近更新时间（分钟）
                        <input
                          type="number"
                          min="0"
                          max="720"
                          value={memberState.last_seen_minutes}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              last_seen_minutes: Number(event.target.value),
                            }))
                          }
                        />
                      </label>
                      <label className="editor-wide">
                        说明高亮
                        <textarea
                          value={memberState.highlight}
                          onChange={(event) =>
                            updateMemberState(member.id, (current) => ({
                              ...current,
                              highlight: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>
                  </section>
                );
              })}
            </div>
          </article>

          <article className="config-card">
            <div className="config-card-head">
              <h4>房间策略草稿</h4>
              <p>房间策略决定广播、隐私保护与环境联动的边界。</p>
            </div>
            <div className="room-setting-list">
              {draft.room_settings.map((roomSetting) => {
                const room = roomById.get(roomSetting.room_id);
                if (!room) {
                  return null;
                }

                return (
                  <section key={room.id} className="room-setting-card">
                    <div className="member-editor-head">
                      <div>
                        <strong>{room.name}</strong>
                        <p>
                          {formatRoomType(room.room_type)} · {formatPrivacyLevel(room.privacy_level)}
                        </p>
                      </div>
                      <div className="pill-stack">
                        <span className="status-pill neutral">
                          {ROOM_SCENE_PRESET_LABELS[roomSetting.scene_preset]}
                        </span>
                      </div>
                    </div>
                    <div className="editor-grid">
                      <label>
                        房间场景
                        <select
                          value={roomSetting.scene_preset}
                          onChange={(event) =>
                            updateRoomSetting(room.id, (current) => ({
                              ...current,
                              scene_preset: event.target.value as RoomScenePreset,
                            }))
                          }
                        >
                          {roomSceneOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        环境策略
                        <select
                          value={roomSetting.climate_policy}
                          onChange={(event) =>
                            updateRoomSetting(room.id, (current) => ({
                              ...current,
                              climate_policy: event.target.value as ClimatePolicy,
                            }))
                          }
                        >
                          {climatePolicyOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <ToggleField
                        label="隐私保护"
                        description="开启后，优先压制敏感信息播报与主动联动。"
                        checked={roomSetting.privacy_guard_enabled}
                        onToggle={() =>
                          updateRoomSetting(room.id, (current) => ({
                            ...current,
                            privacy_guard_enabled: !current.privacy_guard_enabled,
                          }))
                        }
                      />
                      <ToggleField
                        label="允许房间播报"
                        description="控制房间是否接受广播、提醒与解释性反馈。"
                        checked={roomSetting.announcement_enabled}
                        onToggle={() =>
                          updateRoomSetting(room.id, (current) => ({
                            ...current,
                            announcement_enabled: !current.announcement_enabled,
                          }))
                        }
                      />
                    </div>
                  </section>
                );
              })}
            </div>
          </article>
        </div>
      </PageSection>

      <PageSection
        title="服务中心摘要"
        description="这里只放轻量入口，不把服务管理全塞进这个页面。重操作去服务中心。"
      >
        <div className="summary-grid context-summary-grid">
          <div className="summary-card">
            <span>待确认提醒</span>
            <strong>{reminderOverview ? String(reminderOverview.pending_runs) : "暂无"}</strong>
            <small>{reminderOverview ? `${reminderOverview.enabled_tasks} 条启用任务` : "提醒总览暂不可用。"}</small>
          </div>
          <div className="summary-card">
            <span>最近场景执行</span>
            <strong>{sceneExecutions[0] ? sceneExecutions[0].status : "暂无"}</strong>
            <small>{sceneExecutions[0] ? formatDateTime(sceneExecutions[0].started_at) : "还没有场景执行记录。"}</small>
          </div>
          <div className="summary-card">
            <span>常见问答入口</span>
            <strong>{qaSuggestions[0]?.question ?? "暂无建议"}</strong>
            <small>{qaSuggestions[0]?.reason ?? "问答建议接口当前不可用。"}</small>
          </div>
          <div className="summary-card">
            <span>AI 路由摘要</span>
            <strong>{aiRoutes[0]?.capability ?? "暂无配置"}</strong>
            <small>{aiRoutes[0] ? `${aiRoutes[0].routing_mode} · ${aiRoutes[0].allow_remote ? "允许远端" : "仅本地"}` : "当前家庭暂无专属路由。"} </small>
          </div>
        </div>
        <div className="inline-note">
          更完整的问答、提醒、场景和 AI 摘要，请去左侧导航的“服务中心”页面。
        </div>
      </PageSection>

      <PageSection
        title="最近活动与同步线索"
        description="别只看漂亮页面，最近到底发生过什么，也要能一眼看出来。"
      >
        <div className="summary-grid context-summary-grid">
          <div className="summary-card">
            <span>上下文总览</span>
            <strong>{overview ? formatDateTime(overview.generated_at) : "本地草稿"}</strong>
            <small>{overview ? (overview.degraded ? "后端聚合已降级" : "后端聚合正常") : "总览接口当前不可用。"}</small>
          </div>
          <div className="summary-card">
            <span>配置版本</span>
            <strong>{configVersion !== null ? `v${configVersion}` : "本地草稿"}</strong>
            <small>
              {configVersion !== null
                ? `最近更新：${formatDateTime(configUpdatedAt)}`
                : "当前尚未加载到后端配置元数据。"}
            </small>
          </div>
          <div className="summary-card">
            <span>最近 HA 同步</span>
            <strong>{latestSyncLog ? formatDateTime(latestSyncLog.created_at) : "暂无记录"}</strong>
            <small>
              {latestSyncLog
                ? `${latestSyncLog.result} · ${latestSyncLog.action}`
                : "还没有设备同步日志，健康状态只能依赖当前上下文接口与设备主数据。"}
            </small>
          </div>
          <div className="summary-card">
            <span>家庭时区</span>
            <strong>{household.timezone}</strong>
            <small>{household.locale}</small>
          </div>
        </div>
        <div className="audit-list compact">
          {sortedLogs.slice(0, 6).map((log) => (
            <article key={log.id} className="audit-item">
              <div className="audit-item-top">
                <strong>{log.action}</strong>
                <span className={`audit-result ${log.result}`}>{log.result}</span>
              </div>
              <div className="audit-meta">
                <span>{log.target_type}</span>
                <span>{log.actor_type}</span>
                <span>{formatDateTime(log.created_at)}</span>
              </div>
            </article>
          ))}
        </div>
      </PageSection>
    </div>
  );
}
