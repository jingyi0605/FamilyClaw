import { useEffect, useState } from 'react';
import {
  coreApiClient,
  useHouseholdContext,
} from '../../runtime';
import type {
  ContextOverviewMemberState,
  ContextOverviewRead,
  Device,
  Member,
  ReminderOverviewRead,
  Room,
} from '@familyclaw/user-core';
import { formatRoomType } from '@familyclaw/user-core';

export type CardType = 'weather' | 'stats' | 'rooms' | 'members' | 'events' | 'quickActions' | 'aiSummary' | 'devices';

export type DashboardData = {
  overview: ContextOverviewRead | null;
  rooms: Room[];
  members: Member[];
  devices: Device[];
  reminders: ReminderOverviewRead | null;
  errors: string[];
};

export type DashboardRoomCard = {
  id: string;
  name: string;
  isActive: boolean;
  secondary: string;
  deviceCount: number;
};

export type DashboardMemberCard = {
  id: string;
  name: string;
  roleLabel: string;
  badgeStatus: 'home' | 'away' | 'resting';
};

export const COPY = {
  'nav.assistant': '对话',
  'nav.family': '家庭',
  'nav.memories': '记忆',
  'nav.settings': '设置',
  'home.welcome': '欢迎回来',
  'home.greeting': '今天有什么可以帮到你的？',
  'home.roomStatus': '房间状态',
  'home.memberStatus': '成员状态',
  'home.recentEvents': '最近事件',
  'home.quickActions': '快捷操作',
  'home.membersAtHome': '在家',
  'home.activeRooms': '活跃房间',
  'home.devicesOnline': '设备在线',
  'home.alerts': '待处理',
  'home.noEventsHint': '当有新的家庭事件发生时，会显示在这里',
  'member.atHome': '在家',
  'member.away': '外出',
  'member.resting': '休息中',
} as const;

export const DEFAULT_LAYOUT: CardType[] = ['weather', 'stats', 'rooms', 'members', 'events', 'quickActions'];

export const STORAGE_KEY = 'familyclaw-dashboard-layout';

export function buildDashboardData(
  overview: ContextOverviewRead | null,
  rooms: Room[],
  members: Member[],
  devices: Device[],
  reminders: ReminderOverviewRead | null,
  errors: string[],
): DashboardData {
  return { overview, rooms, members, devices, reminders, errors };
}

export function formatMode(mode: ContextOverviewRead['home_mode'] | undefined) {
  switch (mode) {
    case 'home': return '居家模式';
    case 'away': return '离家模式';
    case 'night': return '夜间模式';
    case 'sleep': return '睡眠模式';
    case 'custom': return '自定义模式';
    default: return '未设置';
  }
}

export function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined) {
  switch (mode) {
    case 'balanced': return '平衡保护';
    case 'strict': return '严格保护';
    case 'care': return '关怀优先';
    default: return '未设置';
  }
}

export function formatAutomationLevel(level: ContextOverviewRead['automation_level'] | undefined) {
  switch (level) {
    case 'manual': return '手动优先';
    case 'assisted': return '辅助自动';
    case 'automatic': return '自动优先';
    default: return '未设置';
  }
}

export function formatHomeAssistantStatus(status: ContextOverviewRead['home_assistant_status'] | undefined) {
  switch (status) {
    case 'healthy': return '连接健康';
    case 'degraded': return '部分降级';
    case 'offline': return '连接离线';
    default: return '未知';
  }
}

export function formatRole(role: Member['role'] | ContextOverviewMemberState['role']) {
  switch (role) {
    case 'admin': return '管理员';
    case 'adult': return '成人';
    case 'child': return '儿童';
    case 'elder': return '长辈';
    case 'guest': return '访客';
  }
}

export function getMemberBadgeStatus(memberState: ContextOverviewMemberState | null) {
  if (!memberState) return 'away' as const;
  if (memberState.presence === 'away') return 'away' as const;
  if (memberState.activity === 'resting' || memberState.activity === 'sleeping') return 'resting' as const;
  return 'home' as const;
}

export function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '刚刚';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} 天前`;
}

export function getRoomCards(data: DashboardData): DashboardRoomCard[] {
  if (data.overview?.room_occupancy.length) {
    return data.overview.room_occupancy.map(room => ({
      id: room.room_id,
      name: room.name,
      isActive: room.occupant_count > 0 || room.online_device_count > 0,
      secondary: room.privacy_level === 'sensitive' ? '隐私区域' : formatRoomType(room.room_type),
      deviceCount: room.device_count,
    }));
  }

  return data.rooms.map(room => ({
    id: room.id,
    name: room.name,
    isActive: false,
    secondary: room.privacy_level === 'sensitive' ? '隐私区域' : formatRoomType(room.room_type),
    deviceCount: 0,
  }));
}

export function getMemberCards(data: DashboardData): DashboardMemberCard[] {
  if (data.overview?.member_states.length) {
    return data.overview.member_states.map(member => ({
      id: member.member_id,
      name: member.name,
      roleLabel: formatRole(member.role),
      badgeStatus: getMemberBadgeStatus(member),
    }));
  }

  return data.members.map(member => ({
    id: member.id,
    name: member.name,
    roleLabel: formatRole(member.role),
    badgeStatus: 'away',
  }));
}

export function useHomeDashboardData() {
  const { currentHousehold } = useHouseholdContext();
  const [dashboardData, setDashboardData] = useState<DashboardData>(() => buildDashboardData(null, [], [], [], null, []));
  const [loading, setLoading] = useState(false);
  const familyName = currentHousehold?.name ?? '';
  const currentHouseholdId = currentHousehold?.id ?? '';

  useEffect(() => {
    let cancelled = false;

    const loadDashboard = async () => {
      if (!currentHouseholdId) {
        setDashboardData(buildDashboardData(null, [], [], [], null, []));
        setLoading(false);
        return;
      }

      setLoading(true);

      const [overviewResult, roomsResult, membersResult, devicesResult, remindersResult] = await Promise.allSettled([
        coreApiClient.getContextOverview(currentHouseholdId),
        coreApiClient.listRooms(currentHouseholdId),
        coreApiClient.listMembers(currentHouseholdId),
        coreApiClient.listDevices(currentHouseholdId),
        coreApiClient.getReminderOverview(currentHouseholdId),
      ]);

      if (cancelled) {
        return;
      }

      const errors = [overviewResult, roomsResult, membersResult, devicesResult, remindersResult]
        .filter(result => result.status === 'rejected')
        .map(result => result.reason instanceof Error ? result.reason.message : '数据加载失败');

      setDashboardData(buildDashboardData(
        overviewResult.status === 'fulfilled' ? overviewResult.value : null,
        roomsResult.status === 'fulfilled' ? roomsResult.value.items : [],
        membersResult.status === 'fulfilled' ? membersResult.value.items : [],
        devicesResult.status === 'fulfilled' ? devicesResult.value.items : [],
        remindersResult.status === 'fulfilled' ? remindersResult.value : null,
        errors,
      ));
      setLoading(false);
    };

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  return {
    familyName,
    currentHouseholdId,
    dashboardData,
    loading,
  };
}
