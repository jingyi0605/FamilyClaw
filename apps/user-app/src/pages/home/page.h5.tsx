import { useCallback, useRef, useState, type DragEvent, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import {
  Airplay,
  BarChart2,
  BookOpenText,
  Bot,
  ClipboardList,
  CloudSun,
  Droplets,
  Home,
  Lightbulb,
  Lock,
  MessageSquareText,
  Settings,
  ShieldCheck,
  Smartphone,
  Sun,
  Thermometer,
  Umbrella,
  User,
  Users,
  Wind,
  Zap,
} from 'lucide-react';
import './index.h5.scss';
import { useI18n } from '../../runtime/h5-shell';
import type { ShellMessageKey } from '../../runtime/h5-shell/i18n/I18nProvider';
import {
  DEFAULT_LAYOUT,
  STORAGE_KEY,
  type CardType,
  type DashboardData,
  formatAutomationLevel,
  formatHomeAssistantStatus,
  formatMode,
  formatPrivacyMode,
  formatRelativeTime,
  getMemberCards,
  getRoomCards,
  useHomeDashboardData,
} from './page.shared';

type DashboardCard = {
  type: CardType;
  label: string;
  icon: React.ReactNode;
  width: 'half' | 'full';
};

function getStoredLayout(): CardType[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as CardType[];
  } catch {
    // noop
  }
  return DEFAULT_LAYOUT;
}

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

function StatCard({ icon, label, value, color }: { icon: ReactNode; label: string; value: string | number; color?: string }) {
  return (
    <div className="stat-card" style={color ? ({ ['--stat-accent' as string]: color }) : undefined}>
      <div className="stat-card__icon">{icon}</div>
      <div className="stat-card__info">
        <span className="stat-card__value">{value}</span>
        <span className="stat-card__label">{label}</span>
      </div>
    </div>
  );
}

function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state__icon">{icon}</div>}
      <h3 className="empty-state__title">{title}</h3>
      {description && <p className="empty-state__desc">{description}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  );
}

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

function renderDashboardCard(type: CardType, data: DashboardData, loading: boolean, t: (key: ShellMessageKey) => string) {
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
    case 'rooms': {
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
    }
    case 'members': {
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
    }
    case 'events': {
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
    }
    case 'quickActions':
      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Zap size={20} /> {t('home.quickActions')}</h3>
          <div className="quick-actions">
            <button className="quick-action-btn hover-lift flex items-center gap-2" type="button" onClick={() => void Taro.navigateTo({ url: '/pages/assistant/index' })}><MessageSquareText size={16} /> {t('nav.assistant')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2" type="button" onClick={() => void Taro.navigateTo({ url: '/pages/memories/index' })}><BookOpenText size={16} /> {t('nav.memories')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2" type="button" onClick={() => void Taro.navigateTo({ url: '/pages/settings/index' })}><Settings size={16} /> {t('nav.settings')}</button>
            <button className="quick-action-btn hover-lift flex items-center gap-2" type="button" onClick={() => void Taro.navigateTo({ url: '/pages/family/index' })}><Users size={16} /> {t('nav.family')}</button>
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

export default function HomePage() {
  const { t } = useI18n();
  const { familyName, dashboardData, loading } = useHomeDashboardData();
  const [layout, setLayout] = useState<CardType[]>(getStoredLayout);
  const [editMode, setEditMode] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const dragRef = useRef<number | null>(null);

  const ALL_CARDS: Record<CardType, DashboardCard> = {
    weather: { type: 'weather', label: '天气状态', icon: <CloudSun size={18} />, width: 'half' },
    stats: { type: 'stats', label: '关键指标', icon: <BarChart2 size={18} />, width: 'full' },
    rooms: { type: 'rooms', label: t('home.roomStatus'), icon: <Home size={18} />, width: 'half' },
    members: { type: 'members', label: t('home.memberStatus'), icon: <Users size={18} />, width: 'half' },
    events: { type: 'events', label: t('home.recentEvents'), icon: <ClipboardList size={18} />, width: 'half' },
    quickActions: { type: 'quickActions', label: t('home.quickActions'), icon: <Zap size={18} />, width: 'half' },
    aiSummary: { type: 'aiSummary', label: 'AI 今日摘要', icon: <Bot size={18} />, width: 'full' },
    devices: { type: 'devices', label: '设备状态', icon: <Smartphone size={18} />, width: 'half' },
  };

  const saveLayout = useCallback((newLayout: CardType[]) => {
    setLayout(newLayout);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newLayout));
    } catch {
      // noop
    }
  }, []);

  const handleDragStart = (idx: number) => (event: DragEvent<HTMLDivElement>) => {
    dragRef.current = idx;
    setDragIdx(idx);
    event.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (idx: number) => (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = (dropIdx: number) => (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const fromIdx = dragRef.current;
    if (fromIdx === null || fromIdx === dropIdx) {
      return;
    }

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

  const removeCard = (idx: number) => {
    const newLayout = layout.filter((_, index) => index !== idx);
    saveLayout(newLayout);
  };

  const addCard = (type: CardType) => {
    if (!layout.includes(type)) {
      saveLayout([...layout, type]);
    }
  };

  const unusedCards = (Object.keys(ALL_CARDS) as CardType[]).filter(key => !layout.includes(key));

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
                type="button"
                onClick={() => setEditMode(!editMode)}
              >
                {editMode ? '✓ 完成编辑' : '✏️ 编辑仪表盘'}
              </button>
            </div>
          </div>

          {editMode && unusedCards.length > 0 && (
            <div className="add-cards-bar animate-slide-down">
              <span className="add-cards-bar__label">添加卡片：</span>
              <div className="add-cards-bar__list">
                {unusedCards.map(type => (
                  <button key={type} className="add-card-chip hover-lift" type="button" onClick={() => addCard(type)}>
                    <span>{ALL_CARDS[type].icon}</span>
                    <span>{ALL_CARDS[type].label}</span>
                    <span className="add-card-chip__plus">+</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="dashboard-grid">
            {layout.map((type, idx) => {
              const card = ALL_CARDS[type];
              if (!card) {
                return null;
              }

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
                      <button className="remove-card-btn" type="button" onClick={() => removeCard(idx)}>✕</button>
                    </div>
                  )}
                  {renderDashboardCard(type, dashboardData, loading, t)}
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
            <button className="btn btn--primary" type="button" onClick={() => setEditMode(true)}>
              编辑仪表盘
            </button>
          }
        />
      )}
    </div>
  );
}
