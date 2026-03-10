/* ============================================================
 * 首页 - 可编辑家庭仪表盘
 * 支持卡片添加、移除、拖拽排列
 * ============================================================ */
import { useState, useRef, useCallback, type DragEvent } from 'react';
import { 
  CloudSun, BarChart2, Home, Users, ClipboardList, Zap, Bot, Smartphone, 
  Droplets, Wind, Thermometer, Umbrella, CloudRain, Sun,
  MessageSquareText, BookOpenText, Settings, ShieldCheck, Airplay, Lightbulb, Lock, User
} from 'lucide-react';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { Card, StatCard, EmptyState } from '../components/base';

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

/* ---- 模拟数据 ---- */
const MOCK_ROOMS = [
  { id: '1', name: '客厅', type: '生活区', devices: 5, active: true, temp: '24°C' },
  { id: '2', name: '主卧', type: '卧室', devices: 3, active: false, temp: '22°C' },
  { id: '3', name: '厨房', type: '功能区', devices: 4, active: true, temp: '25°C' },
  { id: '4', name: '书房', type: '工作区', devices: 2, active: false, temp: '23°C' },
];

const MOCK_MEMBERS = [
  { id: '1', name: '爸爸', avatar: <User size={20} />, status: 'home', role: '管理员' },
  { id: '2', name: '妈妈', avatar: <User size={20} />, status: 'home', role: '成员' },
  { id: '3', name: '小明', avatar: <User size={20} />, status: 'away', role: '成员' },
  { id: '4', name: '奶奶', avatar: <User size={20} />, status: 'home', role: '成员' },
];

const MOCK_EVENTS = [
  { id: '1', time: '10 分钟前', icon: <Lightbulb size={16} />, text: '客厅灯光已自动调节' },
  { id: '2', time: '30 分钟前', icon: <ClipboardList size={16} />, text: '提醒：奶奶该吃药了' },
  { id: '3', time: '1 小时前', icon: <Home size={16} />, text: '小明离开了家' },
  { id: '4', time: '2 小时前', icon: <Bot size={16} />, text: 'AI 助手回答了关于晚餐的问题' },
];

const MOCK_DEVICES = [
  { name: '客厅主灯', status: 'on', icon: <Lightbulb size={16} /> },
  { name: '空调', status: 'on', icon: <Airplay size={16} /> },
  { name: '门锁', status: 'locked', icon: <Lock size={16} /> },
  { name: '扫地机', status: 'off', icon: <Bot size={16} /> },
];

/* ---- 天气卡片组件 ---- */
function WeatherCard() {
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
          <span className="weather-temp-value">24°</span>
          <span className="weather-temp-desc">多云转晴</span>
        </div>
      </div>
      <div className="weather-card__details">
        <div className="weather-detail">
          <span className="weather-detail__icon"><Droplets size={16} /></span>
          <span>湿度 65%</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Wind size={16} /></span>
          <span>东南风 3级</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Thermometer size={16} /></span>
          <span>体感 26°</span>
        </div>
        <div className="weather-detail">
          <span className="weather-detail__icon"><Umbrella size={16} /></span>
          <span>降水概率 10%</span>
        </div>
      </div>
      <div className="weather-card__forecast">
        {['明天', '后天', '大后天'].map((day, i) => {
          const icons = [<CloudSun size={20} />, <CloudRain size={20} />, <Sun size={20} />];
          return (
            <div key={day} className="weather-forecast-item">
              <span className="weather-forecast-day">{day}</span>
              <span className="weather-forecast-icon">{icons[i]}</span>
              <span className="weather-forecast-temp">{[23, 20, 26][i]}°</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ---- AI 摘要卡片 ---- */
function AiSummaryCard() {
  return (
    <Card className="dashboard-card ai-summary-card animate-card">
      <div className="ai-summary-card__header">
        <span className="ai-summary-card__icon pulse-glow"><Bot size={24} className="text-brand-primary" /></span>
        <h3>AI 今日摘要</h3>
      </div>
      <p className="ai-summary-card__text">
        今天家里一切正常。奶奶按时服了药，小明下午三点出门了。客厅温度维持在 24°C，空气质量良好。
        晚餐建议：考虑到奶奶的饮食偏好和妈妈的健康计划，推荐清蒸鱼配时令蔬菜。
      </p>
      <div className="ai-summary-card__tags">
        <span className="ai-tag flex items-center gap-1"><ClipboardList size={12} /> 3 条待处理提醒</span>
        <span className="ai-tag flex items-center gap-1"><BookOpenText size={12} /> 2 条新记忆</span>
        <span className="ai-tag flex items-center gap-1"><ShieldCheck size={12} /> 无异常</span>
      </div>
    </Card>
  );
}

/* ---- 设备状态卡片 ---- */
function DevicesCard() {
  return (
    <Card className="dashboard-card animate-card">
      <h3 className="dashboard-card__title flex items-center gap-2"><Smartphone size={20} /> 设备状态</h3>
      <div className="device-status-grid">
        {MOCK_DEVICES.map((d, i) => (
          <div key={i} className={`device-status-item ${d.status === 'off' ? 'device-status-item--off' : ''}`}>
            <span className="device-status-icon">{d.icon}</span>
            <span className="device-status-name">{d.name}</span>
            <span className={`device-status-dot ${d.status !== 'off' ? 'device-status-dot--on' : ''}`} />
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ---- 渲染单个仪表盘卡片 ---- */
function renderDashboardCard(type: CardType, t: ReturnType<typeof useI18n>['t']) {
  switch (type) {
    case 'weather':
      return <WeatherCard />;
    case 'stats':
      return (
        <div className="stats-grid animate-card">
          <StatCard icon={<Users size={24} />} label={t('home.membersAtHome')} value={3} color="var(--brand-primary)" />
          <StatCard icon={<Home size={24} />} label={t('home.activeRooms')} value={2} color="var(--color-success)" />
          <StatCard icon={<Smartphone size={24} />} label={t('home.devicesOnline')} value={12} color="var(--color-info)" />
          <StatCard icon={<ShieldCheck size={24} />} label={t('home.alerts')} value={1} color="var(--color-warning)" />
        </div>
      );
    case 'rooms':
      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Home size={20} /> {t('home.roomStatus')}</h3>
          <div className="room-cards">
            {MOCK_ROOMS.map(room => (
              <div key={room.id} className="mini-room-card">
                <div className="mini-room-card__header">
                  <span className="mini-room-card__name">{room.name}</span>
                  <span className={`status-dot ${room.active ? 'status-dot--active' : ''}`} />
                </div>
                <div className="mini-room-card__meta">
                  <span>{room.temp}</span>
                  <span>{room.devices} 设备</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      );
    case 'members':
      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><Users size={20} /> {t('home.memberStatus')}</h3>
          <div className="member-cards">
            {MOCK_MEMBERS.map(member => (
              <div key={member.id} className="mini-member-card">
                <span className="mini-member-card__avatar">{member.avatar}</span>
                <div className="mini-member-card__info">
                  <span className="mini-member-card__name">{member.name}</span>
                  <span className="mini-member-card__role">{member.role}</span>
                </div>
                <span className={`member-status-badge member-status-badge--${member.status}`}>
                  {member.status === 'home' ? t('member.atHome') : t('member.away')}
                </span>
              </div>
            ))}
          </div>
        </Card>
      );
    case 'events':
      return (
        <Card className="dashboard-card animate-card">
          <h3 className="dashboard-card__title flex items-center gap-2"><ClipboardList size={20} /> {t('home.recentEvents')}</h3>
          <div className="event-list">
            {MOCK_EVENTS.map(ev => (
              <div key={ev.id} className="event-item">
                <span className="event-item__icon">{ev.icon}</span>
                <span className="event-item__text">{ev.text}</span>
                <span className="event-item__time">{ev.time}</span>
              </div>
            ))}
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
      return <AiSummaryCard />;
    case 'devices':
      return <DevicesCard />;
    default:
      return null;
  }
}

/* ---- 首页主组件 ---- */
export function HomePage() {
  const { t } = useI18n();
  const { currentHousehold } = useHouseholdContext();
  const familyName = currentHousehold?.name ?? '';

  const [layout, setLayout] = useState<CardType[]>(getStoredLayout);
  const [editMode, setEditMode] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const dragRef = useRef<number | null>(null);

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
              {renderDashboardCard(type, t)}
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
