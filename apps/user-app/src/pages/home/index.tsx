import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  ContextOverviewRead,
  Device,
  Member,
  ReminderOverviewRead,
  Room,
  formatRoomType,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import { EmptyStateCard, SectionNote } from '../../components/AppUi';
import { MainShellPage } from '../../components/MainShellPage';
import { coreApiClient, needsBlockingSetup, useAppRuntime } from '../../runtime';

type DashboardData = {
  overview: ContextOverviewRead | null;
  rooms: Room[];
  members: Member[];
  devices: Device[];
  reminders: ReminderOverviewRead | null;
  errors: string[];
};

function formatMode(mode: ContextOverviewRead['home_mode'] | undefined) {
  switch (mode) {
    case 'home':
      return '居家模式';
    case 'away':
      return '离家模式';
    case 'night':
      return '夜间模式';
    case 'sleep':
      return '睡眠模式';
    case 'custom':
      return '自定义模式';
    default:
      return '未设置';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined) {
  switch (mode) {
    case 'balanced':
      return '平衡保护';
    case 'strict':
      return '严格保护';
    case 'care':
      return '关怀优先';
    default:
      return '未设置';
  }
}

function formatAutomationLevel(level: ContextOverviewRead['automation_level'] | undefined) {
  switch (level) {
    case 'manual':
      return '手动优先';
    case 'assisted':
      return '辅助自动';
    case 'automatic':
      return '自动优先';
    default:
      return '未设置';
  }
}

function formatRole(role: Member['role']) {
  switch (role) {
    case 'admin':
      return '管理员';
    case 'adult':
      return '成人';
    case 'child':
      return '儿童';
    case 'elder':
      return '长辈';
    case 'guest':
      return '访客';
  }
}

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '刚刚';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }

  return `${Math.round(diffHours / 24)} 天前`;
}

export default function HomePage() {
  const { bootstrap, loading } = useAppRuntime();
  const [dashboard, setDashboard] = useState<DashboardData>({
    overview: null,
    rooms: [],
    members: [],
    devices: [],
    reminders: null,
    errors: [],
  });
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const loadRequestIdRef = useRef(0);
  const activeHouseholdIdRef = useRef('');

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';

  const loadDashboard = useCallback(async () => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      setDashboard({
        overview: null,
        rooms: [],
        members: [],
        devices: [],
        reminders: null,
        errors: [],
      });
      setPageError('');
    }

    activeHouseholdIdRef.current = householdId;

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setPageError('');

    const [overviewResult, roomsResult, membersResult, devicesResult, remindersResult] = await Promise.allSettled([
      coreApiClient.getContextOverview(householdId),
      coreApiClient.listRooms(householdId),
      coreApiClient.listMembers(householdId),
      coreApiClient.listDevices(householdId),
      coreApiClient.getReminderOverview(householdId),
    ]);

    if (requestId !== loadRequestIdRef.current) {
      return;
    }

    const errors = [overviewResult, roomsResult, membersResult, devicesResult, remindersResult]
      .filter(result => result.status === 'rejected')
      .map(result => result.reason instanceof Error ? result.reason.message : '首页数据加载失败');

    setDashboard({
      overview: overviewResult.status === 'fulfilled' ? overviewResult.value : null,
      rooms: roomsResult.status === 'fulfilled' ? roomsResult.value.items : [],
      members: membersResult.status === 'fulfilled' ? membersResult.value.items : [],
      devices: devicesResult.status === 'fulfilled' ? devicesResult.value.items : [],
      reminders: remindersResult.status === 'fulfilled' ? remindersResult.value : null,
      errors,
    });

    if (errors.length > 0) {
      setPageError('部分首页数据加载失败，页面已按可用数据降级显示。');
    }

    setPageLoading(false);
  }, [currentHouseholdId]);

  useEffect(() => {
    if (loading || !bootstrap?.actor?.authenticated || needsBlockingSetup(bootstrap.setupStatus)) {
      return;
    }

    void loadDashboard();
  }, [bootstrap, loadDashboard, loading]);

  useDidShow(() => {
    if (!loading && bootstrap?.actor?.authenticated && !needsBlockingSetup(bootstrap.setupStatus)) {
      void loadDashboard();
    }
  });

  const homeStats = useMemo(() => {
    const memberStates = dashboard.overview?.member_states ?? [];
    const roomOccupancy = dashboard.overview?.room_occupancy ?? [];
    const warningCount = dashboard.overview?.insights.filter(item => item.tone === 'warning' || item.tone === 'danger').length ?? 0;

    return {
      membersAtHome: memberStates.filter(item => item.presence === 'home').length,
      activeRooms: roomOccupancy.filter(item => item.occupant_count > 0 || item.online_device_count > 0).length || dashboard.rooms.length,
      onlineDevices: dashboard.overview?.device_summary.active ?? dashboard.devices.filter(item => item.status === 'active').length,
      alerts: warningCount + (dashboard.reminders?.pending_runs ?? 0),
    };
  }, [dashboard.devices, dashboard.overview, dashboard.reminders, dashboard.rooms.length]);

  const recentEvents = useMemo(() => {
    const insightEvents = (dashboard.overview?.insights ?? []).slice(0, 3).map(item => ({
      id: item.code,
      title: item.title,
      detail: item.message,
      time: formatRelativeTime(dashboard.overview?.generated_at),
    }));
    const reminderEvents = (dashboard.reminders?.items ?? []).slice(0, 3).map(item => ({
      id: item.task_id,
      title: item.title,
      detail: item.latest_ack_action === 'done' ? '最近一次已完成' : '仍待处理',
      time: formatRelativeTime(item.latest_run_planned_at ?? item.next_trigger_at),
    }));

    return [...insightEvents, ...reminderEvents].slice(0, 5);
  }, [dashboard.overview, dashboard.reminders]);

  return (
    <MainShellPage currentNav="home" title="首页已迁到新主壳" description="这一页已经不再是摘要占位，而是直接走共享 API 拉家庭仪表盘数据。">
      <PageSection title={`欢迎回来，${currentHouseholdName}`} description="先把用户最常看的首页搬实：家庭模式、关键指标、房间、成员和提醒都直接落在新应用里。">
        <StatusCard label="在家成员" value={`${homeStats.membersAtHome}`} tone="info" />
        <StatusCard label="活跃房间" value={`${homeStats.activeRooms}`} tone="success" />
        <StatusCard label="在线设备" value={`${homeStats.onlineDevices}`} tone="info" />
        <StatusCard label="待关注事项" value={`${homeStats.alerts}`} tone="warning" />
        {pageLoading ? <SectionNote>正在加载首页仪表盘...</SectionNote> : null}
        {pageError ? <SectionNote tone="warning">{pageError}</SectionNote> : null}
      </PageSection>

      <PageSection title="家庭状态" description="这里对齐 user-web 首页最核心的家庭上下文摘要。">
        <StatusCard label="家庭模式" value={formatMode(dashboard.overview?.home_mode)} tone="info" />
        <StatusCard label="隐私模式" value={formatPrivacyMode(dashboard.overview?.privacy_mode)} tone="success" />
        <StatusCard label="自动化等级" value={formatAutomationLevel(dashboard.overview?.automation_level)} tone="info" />
        <StatusCard label="安静时段" value={dashboard.overview?.quiet_hours_enabled ? `${dashboard.overview.quiet_hours_start} - ${dashboard.overview.quiet_hours_end}` : '未开启'} tone="warning" />
        <SectionNote>
          {dashboard.overview?.guest_mode_enabled ? '访客模式已开启。' : '访客模式未开启。'}
          {dashboard.overview?.child_protection_enabled ? ' 儿童保护已开启。' : ' 儿童保护未开启。'}
          {dashboard.overview?.elder_care_watch_enabled ? ' 长辈关怀已开启。' : ' 长辈关怀未开启。'}
        </SectionNote>
      </PageSection>

      <PageSection title="AI 今日摘要" description="首页需要一个真正可用的摘要区，不是再写一段“后面再迁”的文案。">
        <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', lineHeight: '1.7' }}>
          {dashboard.overview?.insights.slice(0, 2).map(item => item.message).join(' ') || '当前还没有新的家庭洞察，等更多上下文进入后这里会自动更新。'}
        </Text>
      </PageSection>

      <PageSection title="房间状态" description="房间、成员、提醒这几个块是首页高频信息，先搬最有价值的部分。">
        {dashboard.rooms.length === 0 && !pageLoading ? (
          <EmptyStateCard
            title="当前还没有房间"
            description="先去家庭页建几个房间，首页这里就会立刻接上。"
            actionLabel="去家庭页"
            onAction={() => void Taro.reLaunch({ url: '/pages/family/index' })}
          />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(dashboard.overview?.room_occupancy.length ? dashboard.overview.room_occupancy : dashboard.rooms).slice(0, 4).map(room => (
              <View
                key={'room_id' in room ? room.room_id : room.id}
                style={{
                  background: '#f9fbff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusMd,
                  padding: userAppTokens.spacingSm,
                }}
              >
                <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                  {room.name}
                </Text>
                <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                  {'room_id' in room
                    ? `${formatRoomType(room.room_type)} · ${room.device_count} 台设备 · ${room.occupant_count} 位成员`
                    : `${formatRoomType(room.room_type)} · ${room.privacy_level}`}
                </Text>
              </View>
            ))}
          </View>
        )}
      </PageSection>

      <PageSection title="成员状态" description="成员状态卡是旧首页高频卡片，这里直接接真实数据。">
        {dashboard.members.length === 0 && !pageLoading ? (
          <EmptyStateCard
            title="当前还没有成员"
            description="先去家庭页补成员资料，首页这里就能显示状态。"
            actionLabel="去家庭页"
            onAction={() => void Taro.reLaunch({ url: '/pages/family/index' })}
          />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {dashboard.members.slice(0, 4).map(member => {
              const memberState = dashboard.overview?.member_states.find(item => item.member_id === member.id);
              return (
                <View
                  key={member.id}
                  style={{
                    background: '#f9fbff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusMd,
                    padding: userAppTokens.spacingSm,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                    {member.name}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    {formatRole(member.role)} · {memberState?.presence === 'home' ? '在家' : memberState?.presence === 'away' ? '离家' : '状态未知'}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="最近事件" description="提醒和洞察一起收口到首页，先保证用户能看到最新变化。">
        {recentEvents.length === 0 ? (
          <EmptyStateCard title="还没有最近事件" description="当前家庭还没有可展示的提醒或洞察。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {recentEvents.map(event => (
              <View
                key={event.id}
                style={{
                  background: '#f9fbff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusMd,
                  padding: userAppTokens.spacingSm,
                }}
              >
                <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                  {event.title}
                </Text>
                <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                  {event.detail}
                </Text>
                <Text style={{ color: userAppTokens.colorPrimary, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                  {event.time}
                </Text>
              </View>
            ))}
          </View>
        )}
      </PageSection>

      <PageSection title="快捷入口" description="首页不只是展示页，常用入口要直接从这里跳。">
        <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '12px' }}>
          {[
            { label: '去家庭页', url: '/pages/family/index' },
            { label: '去设置页', url: '/pages/settings/index' },
            { label: '去助手页', url: '/pages/assistant/index' },
            { label: '去记忆页', url: '/pages/memories/index' },
          ].map(action => (
            <Button
              key={action.url}
              onClick={() => void Taro.reLaunch({ url: action.url })}
              style={{
                background: userAppTokens.colorSurface,
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusMd,
                color: userAppTokens.colorText,
                fontSize: '22px',
                minWidth: '150px',
              }}
            >
              {action.label}
            </Button>
          ))}
        </View>
      </PageSection>
    </MainShellPage>
  );
}
