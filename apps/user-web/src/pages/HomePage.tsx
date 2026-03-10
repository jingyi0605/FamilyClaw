/* ============================================================
 * 首页 - 可编辑家庭仪表盘
 * 支持卡片添加、移除、拖拽排列
 * ============================================================ */
import { useState, useRef, useCallback, useEffect, type DragEvent } from 'react';
import { 
  CloudSun, BarChart2, Home, Users, ClipboardList, Zap, Bot, Smartphone, 
  Droplets, Wind, Thermometer, Umbrella, Sun,
  MessageSquareText, BookOpenText, Settings, ShieldCheck, Airplay, Lightbulb, Lock, User
} from 'lucide-react';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { Card, StatCard, EmptyState } from '../components/base';
import { api } from '../lib/api';
import { formatRoomType } from '../lib/roomTypes';
import type { ContextOverviewMemberState, ContextOverviewRead, Device, Member, ReminderOverviewRead, Room } from '../lib/types';

/* ---- 所有可用的仪表盘卡片类型 ---- */
type CardType = 'weather' | 'stats' | 'rooms' | 'members' | 'events' | 'quickActions' | 'aiSummary' | 'devices';

interface DashboardCard {
  type: CardType;
  label: string;
  icon: React.ReactNode;
  width: 'half' | 'full';
}

const ALL_CARDS: Record<CardType, DashboardCard> = {
  weather: { type: 'weather', label: '天气状态', icon: <CloudSun size={18} />, width: 'half' },
  stats: { type: 'stats', label: '关键指标', icon: <BarChart2 size={18} />, width: 'full' },
  rooms: { type: 'rooms', label: '房间状态', icon: <Home size={18} />, width: 'half' },
  members: { type: 'members', label: '成员状态', icon: <Users size={18} />, width: 'half' },
  events: { type: 'events', label: '最近事件', icon: <ClipboardList size={18} />, width: 'half' },
  quickActions: { type: 'quickActions', label: '快捷操作', icon: <Zap size={18} />, width: 'half' },
  aiSummary: { type: 'aiSummary', label: 'AI 今日摘要', icon: <Bot size={18} />, width: 'full' },
  devices: { type: 'devices', label: '设备状态', icon: <Smartphone size={18} />, width: 'half' },
};

const DEFAULT_LAYOUT: CardType[] = ['weather', 'stats', 'rooms', 'members', 'events', 'quickActions'];

const STORAGE_KEY = 'familyclaw-dashboard-layout';

function getStoredLayout(): CardType[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as CardType[];
  } catch { /* noop */ }
  return DEFAULT_LAYOUT;
}

type DashboardData = {
  overview: ContextOverviewRead | null;
  rooms: Room[];
  members: Member[];
  devices: Device[];
  reminders: ReminderOverviewRead | null;
  errors: string[];
};

type DashboardRoomCard = {
  id: string;
  name: string;
  isActive: boolean;
  secondary: string;
  deviceCount: number;
};

type DashboardMemberCard = {
  id: string;
  name: string;
  roleLabel: string;
  badgeStatus: 'home' | 'away' | 'resting';
};

function formatMode(mode: ContextOverviewRead['home_mode'] | undefined) {
  switch (mode) {
    case 'home': return '居家模式';
    case 'away': return '离家模式';
    case 'night': return '夜间模式';
    case 'sleep': return '睡眠模式';
    case 'custom': return '自定义模式';
    default: return '未设置';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined) {
  switch (mode) {
    case 'balanced': return '平衡保护';
    case 'strict': return '严格保护';
    case 'care': return '关怀优先';
    default: return '未设置';
  }
}

function formatAutomationLevel(level: ContextOverviewRead['automation_level'] | undefined) {
  switch (level) {
    case 'manual': return '手动优先';
    case 'assisted': return '辅助自动';
    case 'automatic': return '自动优先';
    default: return '未设置';
  }
}

function formatHomeAssistantStatus(status: ContextOverviewRead['home_assistant_status'] | undefined) {
  switch (status) {
    case 'healthy': return '连接健康';
    case 'degraded': return '部分降级';
    case 'offline': return '连接离线';
    default: return '未知';
  }
}

function formatRole(role: Member['role'] | ContextOverviewMemberState['role']) {
  switch (role) {
    case 'admin': return '管理员';
    case 'adult': return '成人';
    case 'child': return '儿童';
    case 'elder': return '长辈';
    case 'guest': return '访客';
  }
}

function getMemberBadgeStatus(memberState: ContextOverviewMemberState | null) {
  if (!memberState) return 'away' as const;
  if (memberState.presence === 'away') return 'away' as const;
  if (memberState.activity === 'resting' || memberState.activity === 'sleeping') return 'resting' as const;
  return 'home' as const;
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
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} 天前`;
}

function buildDashboardData(
  overview: ContextOverviewRead | null,
  rooms: Room[],
  members: Member[],
  devices: Device[],
  reminders: ReminderOverviewRead | null,
  errors: string[],
): DashboardData {
  return { overview, rooms, members, devices, reminders, errors };
}

function getRoomCards(data: DashboardData): DashboardRoomCard[] {
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

function getMemberCards(data: DashboardData): DashboardMemberCard[] {
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

/* ---- 家庭状态卡片组件 ---- */
function WeatherCard({ data }: { data: DashboardData }) {
  const membersAtHome = data.overview?.member_states.filter(item => item.presence === 'home').length ?? 0;
  const onlineDevices = data.overview?.device_summary.active ?? data.devices.filter(item => item.status === 'active').length;
  const reminderCount = data.reminders?.pending_runs ?? 0;

  return (
    <Card className="dashboard-card weather-card animate-card">
      <div className="weather-card__main">
        <div className="weather-card__icon-area">
          <span className="weather-icon-animated">
            <span className="weather-sun"><Sun size={48} className="text-warning" /></span>
            <span className="weather-cloud"><CloudSun size={32} /></span>
          </span>
        </div>
        <div className="weather-card__temp">
          <span className="weather-temp-value">{formatMode(data.overview?.home_mode)}</span>
          <span className="weather-temp-desc">{formatHomeAssistantStatus(data.overview?.home_assistant_status)}</span>
        </div>
      </div>
      <div className="weather-card__details">
        <div className="weather-detail">
          <span className="weather-detail__icon"><Droplets size={16} /></span>
          <span>隐私 {formatPrivacyMode(data.overview?.privacy_mode)}</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Wind size={16} /></span>
          <span>自动化 {formatAutomationLevel(data.overview?.automation_level)}</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Thermometer size={16} /></span>
          <span>{data.overview?.quiet_hours_enabled ? `安静时段 ${data.overview.quiet_hours_start}-${data.overview.quiet_hours_end}` : '未开启安静时段'}</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Umbrella size={16} /></span>
          <span>{data.overview?.guest_mode_enabled ? '访客模式已开启' : '访客模式未开启'}</span>
        </div>
      </div>
      <div className="weather-card__forecast">
        <div className="weather-forecast-item">
          <span className="weather-forecast-day">在家成员</span>
          <span className="weather-forecast-icon"><Users size={20} /></span>
          <span className="weather-forecast-temp">{membersAtHome}</span>
        </div>
        <div className="weather-forecast-item">
          <span className="weather-forecast-day">在线设备</span>
          <span className="weather-forecast-icon"><Smartphone size={20} /></span>
          <span className="weather-forecast-temp">{onlineDevices}</span>
        </div>
        <div className="weather-forecast-item">
          <span className="weather-forecast-day">待处理提醒</span>
          <span className="weather-forecast-icon"><ClipboardList size={20} /></span>
          <span className="weather-forecast-temp">{reminderCount}</span>
        </div>
      </div>
    </Card>
  );
}

/* ---- AI 摘要卡片 ---- */
function AiSummaryCard({ data }: { data: DashboardData }) {
  const insightMessages = data.overview?.insights.slice(0, 2).map(item => item.message) ?? [];
  const summaryText = insightMessages.length > 0
    ? insightMessages.join(' ') 
    : '当前还没有新的家庭洞察，系统会在拿到更多上下文后更新这里。';

  return (
    <Card className="dashboard-card ai-summary-card animate-card">
      <div className="ai-summary-card__header">
        <span className="ai-summary-card__icon pulse-glow"><Bot size={24} className="text-brand-primary" /></span>
        <h3>AI 今日摘要</h3>
      </div>
      <p className="ai-summary-card__text">{summaryText}</p>
      <div className="ai-summary-card__tags">
        <span className="ai-tag flex items-center gap-1"><ClipboardList size={12} /> {data.reminders?.pending_runs ?? 0} 条待处理提醒</span>
        <span className="ai-tag flex items-center gap-1"><BookOpenText size={12} /> {data.overview?.member_states.length ?? 0} 位成员已纳入上下文</span>
        <span className="ai-tag flex items-center gap-1"><ShieldCheck size={12} /> {data.overview?.insights.filter(item => item.tone === 'warning' || item.tone === 'danger').length ?? 0} 条需关注洞察</span>
      </div>
    </Card>
  );
}

/* ---- 设备状态卡片 ---- */
function DevicesCard({ data }: { data: DashboardData }) {
  const topDevices = data.devices.slice(0, 4);

  return (
    <Card className="dashboard-card animate-card">
      <h3 className="dashboard-card__title flex items-center gap-2"><Smartphone size={20} /> 设备状态</h3>
      <div className="device-status-grid">
        {topDevices.length > 0 ? topDevices.map(device => {
          const isOff = device.status !== 'active';
          const icon = device.device_type === 'lock'
            ? <Lock size={16} />
            : device.device_type === 'ac'
              ? <Airplay size={16} />
              : device.device_type === 'light'
                ? <Lightbulb size={16} />
                : <Bot size={16} />;

          return (
            <div key={device.id} className={`device-status-item ${isOff ? 'device-status-item--off' : ''}`}>
              <span className="device-status-icon">{icon}</span>
              <span className="device-status-name">{device.name}</span>
              <span className={`device-status-dot ${!isOff ? 'device-status-dot--on' : ''}`} />
            </div>
          );
        }) : <div className="text-text-secondary">当前家庭还没有可展示的设备。</div>}
      </div>
    </Card>
  );
}

/* ---- 渲染单个仪表盘卡片 ---- */
function renderDashboardCard(type: CardType, t: ReturnType<typeof useI18n>['t'], data: DashboardData, loading: boolean) {
  switch (type) {
    case 'weather':
      return <WeatherCard data={data} />;
    case 'stats':
      return (
        <div className="stats-grid animate-card">
          <StatCard icon={<Users size={24} />} label={t('home.membersAtHome')} value={data.overview?.member_states.filter(item => item.presence === 'home').length ?? 0} color="var(--brand-primary)" />
          <StatCard icon={<Home size={24} />} label={t('home.activeRooms')} value={data.overview?.room_occupancy.filter(item => item.occupant_count > 0 || item.online_device_count > 0).length ?? data.rooms.length} color="var(--color-success)" />
          <StatCard icon={<Smartphone size={24} />} label={t('home.devicesOnline')} value={data.overview?.device_summary.active ?? data.devices.filter(item => item.status === 'active').length} color="var(--color-info)" />
          <StatCard icon={<ShieldCheck size={24} />} label={t('home.alerts')} value={(data.reminders?.pending_runs ?? 0) + (data.overview?.insights.filter(item => item.tone === 'warning' || item.tone === 'danger').length ?? 0)} color="var(--color-warning)" />
        </div>
      );
    case 'rooms':
      const roomCards = getRoomCards(data).slice(0, 4);

      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Home size={20} /> {t('home.roomStatus')}</h3>
          <div className="room-cards">
            {loading ? <div className="text-text-secondary">正在加载房间状态...</div> : roomCards.map(room => (
              <div key={room.id} className="mini-room-card">
                <div className="mini-room-card__header">
                  <span className="mini-room-card__name">{room.name}</span>
                  <span className={`status-dot ${room.isActive ? 'status-dot--active' : ''}`} />
                </div>
                <div className="mini-room-card__meta">
                  <span>{room.secondary}</span>
                  <span>{room.deviceCount} 设备</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      );
    case 'members':
      const memberCards = getMemberCards(data).slice(0, 4);

      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Users size={20} /> {t('home.memberStatus')}</h3>
          <div className="member-cards">
            {loading ? <div className="text-text-secondary">正在加载成员状态...</div> : memberCards.map(member => (
              <div key={member.id} className="mini-member-card">
                <span className="mini-member-card__avatar"><User size={20} /></span>
                <div className="mini-member-card__info">
                  <span className="mini-member-card__name">{member.name}</span>
                  <span className="mini-member-card__role">{member.roleLabel}</span>
                </div>
                <span className={`member-status-badge member-status-badge--${member.badgeStatus}`}>
                  {member.badgeStatus === 'resting' ? t('member.resting') : member.badgeStatus === 'home' ? t('member.atHome') : t('member.away')}
                </span>
              </div>
            ))}
          </div>
        </Card>
      );
    case 'events':
      const reminderEvents = data.reminders?.items.slice(0, 3).map(item => ({
        id: item.task_id,
        time: formatRelativeTime(item.latest_run_planned_at ?? item.next_trigger_at),
        icon: <ClipboardList size={16} />,
        text: item.latest_ack_action === 'done' ? `${item.title} 已完成` : `${item.title} 待处理`,
      })) ?? [];
      const insightEvents = data.overview?.insights.slice(0, 3).map(item => ({
        id: item.code,
        time: formatRelativeTime(data.overview?.generated_at),
        icon: item.tone === 'danger' ? <ShieldCheck size={16} /> : <Lightbulb size={16} />,
        text: item.message,
      })) ?? [];
      const recentEvents = [...insightEvents, ...reminderEvents].slice(0, 5);

      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><ClipboardList size={20} /> {t('home.recentEvents')}</h3>
          <div className="event-list">
            {loading ? <div className="text-text-secondary">正在加载最近事件...</div> : recentEvents.length > 0 ? recentEvents.map(ev => (
              <div key={ev.id} className="event-item">
                <span className="event-item__icon">{ev.icon}</span>
                <span className="event-item__text">{ev.text}</span>
                <span className="event-item__time">{ev.time}</span>
              </div>
            )) : <div className="text-text-secondary">{t('home.noEventsHint')}</div>}
          </div>
        </Card>
      );
    case 'quickActions':
      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Zap size={20} /> {t('home.quickActions')}</h3>
          <div className="quick-actions">
            <button className="quick-action-btn hover-lift flex items-center gap-2"><MessageSquareText size={16} /> {t('nav.assistant')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2"><BookOpenText size={16} /> {t('nav.memories')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2"><Settings size={16} /> {t('nav.settings')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2"><Users size={16} /> {t('nav.family')}</button>
          </div>
        </Card>
      );
    case 'aiSummary':
      return <AiSummaryCard data={data} />;
    case 'devices':
      return <DevicesCard data={data} />;
    default:
      return null;
  }
}

/* ---- 首页主组件 ---- */
export function HomePage() {
  const { t } = useI18n();
  const { currentHousehold, currentHouseholdId } = useHouseholdContext();
  const familyName = currentHousehold?.name ?? '';

  const [layout, setLayout] = useState<CardType[]>(getStoredLayout);
  const [editMode, setEditMode] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const dragRef = useRef<number | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData>(() => buildDashboardData(null, [], [], [], null, []));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentHouseholdId) {
      setDashboardData(buildDashboardData(null, [], [], [], null, []));
      return;
    }

    let cancelled = false;

    const loadDashboard = async () => {
      setLoading(true);

      const [overviewResult, roomsResult, membersResult, devicesResult, remindersResult] = await Promise.allSettled([
        api.getContextOverview(currentHouseholdId),
        api.listRooms(currentHouseholdId),
        api.listMembers(currentHouseholdId),
        api.listDevices(currentHouseholdId),
        api.getReminderOverview(currentHouseholdId),
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

  /* 保存布局 */
  const saveLayout = useCallback((newLayout: CardType[]) => {
    setLayout(newLayout);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(newLayout)); } catch { /* noop */ }
  }, []);

  /* 拖拽开始 */
  const handleDragStart = (idx: number) => (e: DragEvent) => {
    dragRef.current = idx;
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  };

  /* 拖拽经过 */
  const handleDragOver = (idx: number) => (e: DragEvent) => {
    e.preventDefault();
    setDragOverIdx(idx);
  };

  /* 拖拽放置 */
  const handleDrop = (dropIdx: number) => (e: DragEvent) => {
    e.preventDefault();
    const fromIdx = dragRef.current;
    if (fromIdx === null || fromIdx === dropIdx) return;

    const newLayout = [...layout];
    const [moved] = newLayout.splice(fromIdx, 1);
    newLayout.splice(dropIdx, 0, moved);
    saveLayout(newLayout);
    setDragIdx(null);
    setDragOverIdx(null);
  };

  const handleDragEnd = () => {
    setDragIdx(null);
    setDragOverIdx(null);
  };

  /* 移除卡片 */
  const removeCard = (idx: number) => {
    const newLayout = layout.filter((_, i) => i !== idx);
    saveLayout(newLayout);
  };

  /* 添加卡片 */
  const addCard = (type: CardType) => {
    if (!layout.includes(type)) {
      saveLayout([...layout, type]);
    }
  };

  /* 未使用的卡片列表 */
  const unusedCards = (Object.keys(ALL_CARDS) as CardType[]).filter(k => !layout.includes(k));

  return (
    <div className="page page--home">
      {/* 欢迎区 */}
      <div className="welcome-banner">
        <div className="welcome-banner__text">
          <h1 className="welcome-banner__title animate-slide-in flex items-center gap-3">
            {t('home.welcome')}，{familyName} <Home size={32} className="text-brand-primary" />
          </h1>
          <p className="welcome-banner__sub">{t('home.greeting')}</p>
          {dashboardData.errors.length > 0 && (
            <p className="text-text-secondary">部分卡片加载失败，页面已自动降级显示可用数据。</p>
          )}
        </div>
        <div className="welcome-banner__right">
          <div className="welcome-banner__time">
            {new Date().toLocaleDateString('zh-CN', { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <button
            className={`edit-dashboard-btn ${editMode ? 'edit-dashboard-btn--active' : ''}`}
            onClick={() => setEditMode(!editMode)}
          >
            {editMode ? '✓ 完成编辑' : '✏️ 编辑仪表盘'}
          </button>
        </div>
      </div>

      {/* 编辑模式：可添加的卡片 */}
      {editMode && unusedCards.length > 0 && (
        <div className="add-cards-bar animate-slide-down">
          <span className="add-cards-bar__label">添加卡片：</span>
          <div className="add-cards-bar__list">
            {unusedCards.map(type => (
              <button key={type} className="add-card-chip hover-lift" onClick={() => addCard(type)}>
                <span>{ALL_CARDS[type].icon}</span>
                <span>{ALL_CARDS[type].label}</span>
                <span className="add-card-chip__plus">+</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 仪表盘卡片区 */}
      <div className="dashboard-grid">
        {layout.map((type, idx) => {
          const card = ALL_CARDS[type];
          if (!card) return null;
          return (
            <div
              key={type}
              className={`dashboard-grid__item dashboard-grid__item--${card.width} ${editMode ? 'dashboard-grid__item--editing' : ''} ${dragIdx === idx ? 'dashboard-grid__item--dragging' : ''} ${dragOverIdx === idx ? 'dashboard-grid__item--drag-over' : ''}`}
              draggable={editMode}
              onDragStart={editMode ? handleDragStart(idx) : undefined}
              onDragOver={editMode ? handleDragOver(idx) : undefined}
              onDrop={editMode ? handleDrop(idx) : undefined}
              onDragEnd={editMode ? handleDragEnd : undefined}
            >
              {editMode && (
                <div className="dashboard-item-controls">
                  <span className="drag-handle">⠿</span>
                  <button className="remove-card-btn" onClick={() => removeCard(idx)}>✕</button>
                </div>
              )}
              {renderDashboardCard(type, t, dashboardData, loading)}
            </div>
          );
        })}
      </div>

      {layout.length === 0 && (
        <EmptyState
          icon={<Home size={64} className="text-text-tertiary opacity-50" />}
          title="仪表盘是空的"
          description={'点击"编辑仪表盘"来添加卡片'}
          action={
            <button className="btn btn--primary" onClick={() => setEditMode(true)}>
              编辑仪表盘
            </button>
          }
        />
      )}
    </div>
  );
}
