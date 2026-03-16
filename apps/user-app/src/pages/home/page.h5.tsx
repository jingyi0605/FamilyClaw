import { useRef, useState, type DragEvent, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import { EmptyStateCard, UiCard } from '@familyclaw/user-ui';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpenText,
  Bot,
  CalendarClock,
  CheckCircle2,
  CloudSun,
  ClipboardList,
  GripVertical,
  Home,
  Info,
  LayoutGrid,
  ListChecks,
  MessageSquareText,
  Plus,
  Settings,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Sun,
  TriangleAlert,
  User,
  Users,
  Wind,
  X,
} from 'lucide-react';
import './index.h5.scss';
import { useI18n } from '../../runtime/h5-shell';
import type { ShellMessageKey } from '../../runtime/h5-shell/i18n/I18nProvider';
import {
  buildCardMap,
  buildVisibleLayoutItems,
  formatRelativeTime,
  resolveCardLabel,
  useHomeDashboardData,
  type HomeDashboardCardActionRead,
  type HomeDashboardCardRead,
  type MemberDashboardLayoutItem,
} from './page.shared';

type DashboardPayloadItem = Record<string, unknown>;
type MemberBadgeTone = 'home' | 'away' | 'resting';
type DashboardLayoutOption<T extends string> = {
  value: T;
  labelKey: ShellMessageKey;
};

const DASHBOARD_WIDTH_OPTIONS: Array<DashboardLayoutOption<MemberDashboardLayoutItem['size']>> = [
  { value: 'half', labelKey: 'home.cardWidth.half' },
  { value: 'full', labelKey: 'home.cardWidth.full' },
];

const DASHBOARD_HEIGHT_OPTIONS: Array<DashboardLayoutOption<MemberDashboardLayoutItem['height']>> = [
  { value: 'compact', labelKey: 'home.cardHeight.compact' },
  { value: 'regular', labelKey: 'home.cardHeight.regular' },
  { value: 'tall', labelKey: 'home.cardHeight.tall' },
];

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <UiCard className={`card ${className}`.trim()}>{children}</UiCard>;
}

function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return <EmptyStateCard className="empty-state" icon={icon} title={title} description={description ?? ''} action={action} />;
}

function getTemplateIcon(card: HomeDashboardCardRead) {
  switch (card.template_type) {
    case 'metric':
      return <Activity size={18} />;
    case 'status_list':
      return <LayoutGrid size={18} />;
    case 'timeline':
      return <CalendarClock size={18} />;
    case 'insight':
      return <Sparkles size={18} />;
    case 'action_group':
      return <ListChecks size={18} />;
    default:
      return <Info size={18} />;
  }
}

function getStateToneClass(state: HomeDashboardCardRead['state']) {
  switch (state) {
    case 'ready':
      return 'is-ready';
    case 'stale':
      return 'is-stale';
    case 'error':
      return 'is-error';
    case 'empty':
      return 'is-empty';
    default:
      return 'is-empty';
  }
}

function getStateLabel(state: HomeDashboardCardRead['state'], t: (key: ShellMessageKey) => string) {
  switch (state) {
    case 'ready':
      return t('home.cardState.ready');
    case 'stale':
      return t('home.cardState.stale');
    case 'error':
      return t('home.cardState.error');
    case 'empty':
      return t('home.cardState.empty');
  }
}

function isBuiltinCard(card: HomeDashboardCardRead) {
  return card.source_type === 'builtin' && card.card_ref.startsWith('builtin:');
}

function getPayloadItems(card: HomeDashboardCardRead): DashboardPayloadItem[] {
  return Array.isArray(card.payload.items) ? card.payload.items.filter(item => typeof item === 'object' && item !== null) as DashboardPayloadItem[] : [];
}

function getPayloadText(value: unknown, fallback = '') {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return fallback;
}

function resolveActionByKey(card: HomeDashboardCardRead, actionKey: string | undefined) {
  if (!actionKey) {
    return null;
  }
  return card.actions.find(item => item.action_key === actionKey) ?? null;
}

async function handleCardAction(action: HomeDashboardCardActionRead, t: (key: ShellMessageKey) => string) {
  if (action.action_type === 'navigate' && action.target) {
    await Taro.navigateTo({ url: action.target });
    return;
  }

  if (action.action_type === 'open_plugin_detail') {
    await Taro.navigateTo({ url: '/pages/settings/index' });
    return;
  }

  await Taro.showToast({
    title: t('home.pluginActionPending'),
    icon: 'none',
  });
}

function getBuiltinStatIcon(title: string) {
  if (title.includes('成员')) {
    return <Users size={20} />;
  }
  if (title.includes('房间')) {
    return <Home size={20} />;
  }
  if (title.includes('设备')) {
    return <Smartphone size={20} />;
  }
  if (title.includes('提醒') || title.includes('事件')) {
    return <ClipboardList size={20} />;
  }
  return <Activity size={20} />;
}

function getQuickActionIcon(actionKey: string, label: string) {
  if (actionKey === 'assistant' || label.includes('对话')) {
    return <MessageSquareText size={16} />;
  }
  if (actionKey === 'memories' || label.includes('记忆')) {
    return <BookOpenText size={16} />;
  }
  if (actionKey === 'settings' || label.includes('设置')) {
    return <Settings size={16} />;
  }
  if (actionKey === 'family' || label.includes('家庭')) {
    return <Users size={16} />;
  }
  return <ArrowRight size={16} />;
}

function getWeatherDetailIcon(detail: string) {
  if (detail.includes('隐私')) {
    return <ShieldCheck size={16} />;
  }
  if (detail.includes('自动化')) {
    return <Wind size={16} />;
  }
  if (detail.includes('安静')) {
    return <CalendarClock size={16} />;
  }
  if (detail.includes('提醒')) {
    return <ClipboardList size={16} />;
  }
  return <Info size={16} />;
}

function splitHighlight(detail: string) {
  const parts = detail.split(/[:：]/);
  if (parts.length >= 2) {
    return {
      label: parts[0]?.trim() ?? '',
      value: parts.slice(1).join('：').trim(),
    };
  }
  return {
    label: detail,
    value: '',
  };
}

function getMemberBadgeTone(value: string): MemberBadgeTone {
  if (value.includes('在家')) {
    return 'home';
  }
  if (value.includes('休息') || value.includes('睡')) {
    return 'resting';
  }
  return 'away';
}

function DashboardCardState({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  if (card.state === 'ready') {
    return null;
  }

  const Icon = card.state === 'error' ? TriangleAlert : card.state === 'stale' ? AlertTriangle : Info;
  const messageKey =
    card.state === 'error'
      ? 'home.cardHint.error'
      : card.state === 'stale'
        ? 'home.cardHint.stale'
        : 'home.cardHint.empty';

  return (
    <div className={`dashboard-card__state ${getStateToneClass(card.state)}`}>
      <Icon size={16} />
      <span>{t(messageKey)}</span>
    </div>
  );
}

function DashboardCardHeader({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  return (
    <div className="dashboard-card__header">
      <div>
        <div className="dashboard-card__title">
          {getTemplateIcon(card)}
          <span>{card.title}</span>
        </div>
        {card.subtitle ? <p className="dashboard-card__subtitle">{card.subtitle}</p> : null}
      </div>
      <span className={`dashboard-state-chip ${getStateToneClass(card.state)}`}>{getStateLabel(card.state, t)}</span>
    </div>
  );
}

function DashboardTemplateBody({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  if (card.template_type === 'metric') {
    return (
      <div className="dashboard-metric">
        <div className="dashboard-metric__value">
          <span>{getPayloadText(card.payload.value, '-')}</span>
          {card.payload.unit ? <small>{getPayloadText(card.payload.unit)}</small> : null}
        </div>
        {card.payload.context ? <p className="dashboard-card__hint">{getPayloadText(card.payload.context)}</p> : null}
        {card.payload.trend && typeof card.payload.trend === 'object' ? (
          <div className="dashboard-card__meta">
            <CheckCircle2 size={14} />
            <span>{getPayloadText((card.payload.trend as Record<string, unknown>).label)}</span>
          </div>
        ) : null}
      </div>
    );
  }

  if (card.template_type === 'insight') {
    const highlights = Array.isArray(card.payload.highlights) ? card.payload.highlights : [];
    return (
      <div className="dashboard-insight">
        <p className="dashboard-insight__message">{getPayloadText(card.payload.message, t('home.cardHint.empty'))}</p>
        {highlights.length > 0 ? (
          <div className="dashboard-tag-list">
            {highlights.map(item => (
              <span key={String(item)} className="dashboard-tag">
                {String(item)}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (card.template_type === 'action_group') {
    const items = getPayloadItems(card);
    return (
      <div className="dashboard-action-list">
        {items.map(item => {
          const action = resolveActionByKey(card, getPayloadText(item.action_key));
          return (
            <button
              key={`${card.card_ref}-${getPayloadText(item.label)}`}
              className="dashboard-action-button"
              type="button"
              disabled={!action}
              onClick={() => action ? void handleCardAction(action, t) : undefined}
            >
              <div>
                <strong>{getPayloadText(item.label)}</strong>
                {item.description ? <span>{getPayloadText(item.description)}</span> : null}
              </div>
              <ArrowRight size={16} />
            </button>
          );
        })}
      </div>
    );
  }

  const items = getPayloadItems(card);
  if (card.template_type === 'timeline') {
    return (
      <div className="dashboard-list">
        {items.map(item => (
          <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="dashboard-list__item">
            <div>
              <strong>{getPayloadText(item.title)}</strong>
              {item.description ? <p>{getPayloadText(item.description)}</p> : null}
            </div>
            <span>{formatRelativeTime(getPayloadText(item.timestamp))}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="dashboard-list">
      {items.map(item => (
        <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="dashboard-list__item">
          <div>
            <strong>{getPayloadText(item.title)}</strong>
            {item.subtitle ? <p>{getPayloadText(item.subtitle)}</p> : null}
          </div>
          {item.value ? <span>{getPayloadText(item.value)}</span> : null}
        </div>
      ))}
    </div>
  );
}

function BuiltinWeatherCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const message = getPayloadText(card.payload.message, t('home.cardHint.empty'));
  const messageParts = message
    .split(/[，。]/)
    .map(part => part.trim())
    .filter(Boolean);
  const headline = messageParts[0] ?? card.title;
  const description = messageParts.slice(1).join('，') || card.subtitle || t('home.cardHint.empty');
  const highlights = Array.isArray(card.payload.highlights) ? card.payload.highlights.map(item => String(item)) : [];

  return (
    <Card className={`dashboard-card weather-card ${getStateToneClass(card.state)}`}>
      <div className="weather-card__main">
        <div className="weather-card__icon-area">
          <span className="weather-icon-animated">
            <span className="weather-sun"><Sun size={48} className="text-warning" /></span>
            <span className="weather-cloud"><CloudSun size={32} /></span>
          </span>
        </div>
        <div className="weather-card__summary">
          <span className="weather-temp-value">{headline}</span>
          <span className="weather-temp-desc">{description}</span>
        </div>
      </div>
      <DashboardCardState card={card} t={t} />
      {highlights.length > 0 ? (
        <div className="weather-card__details">
          {highlights.slice(0, 4).map(detail => (
            <div key={detail} className="weather-detail">
              <span className="weather-detail__icon">{getWeatherDetailIcon(detail)}</span>
              <span>{detail}</span>
            </div>
          ))}
        </div>
      ) : null}
      {highlights.length > 0 ? (
        <div className="weather-card__forecast">
          {highlights.slice(0, 3).map(detail => {
            const { label, value } = splitHighlight(detail);
            return (
              <div key={`forecast-${detail}`} className="weather-forecast-item">
                <span className="weather-forecast-day">{label}</span>
                <span className="weather-forecast-temp">{value || label}</span>
              </div>
            );
          })}
        </div>
      ) : null}
    </Card>
  );
}

function BuiltinStatsCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const items = getPayloadItems(card);

  return (
    <div className="stats-section">
      <div className="stats-section__header">
        <div>
          <h3 className="stats-section__title">{card.title}</h3>
          {card.subtitle ? <p className="stats-section__subtitle">{card.subtitle}</p> : null}
        </div>
        <span className={`dashboard-state-chip ${getStateToneClass(card.state)}`}>{getStateLabel(card.state, t)}</span>
      </div>
      <DashboardCardState card={card} t={t} />
      <div className="stats-grid">
        {items.map(item => (
          <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="dashboard-stat-card">
            <span className={`dashboard-stat-card__icon dashboard-stat-card__icon--${getPayloadText(item.tone, 'info')}`}>
              {getBuiltinStatIcon(getPayloadText(item.title))}
            </span>
            <div className="dashboard-stat-card__content">
              <strong>{getPayloadText(item.value, '0')}</strong>
              <span>{getPayloadText(item.title)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BuiltinRoomsCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const items = getPayloadItems(card);
  return (
    <Card className="dashboard-card dashboard-card--builtin">
      <div className="dashboard-card__title">
        <Home size={20} />
        <span>{card.title}</span>
      </div>
      {card.subtitle ? <p className="dashboard-card__subtitle">{card.subtitle}</p> : null}
      <DashboardCardState card={card} t={t} />
      <div className="room-cards">
        {items.map(item => {
          const tone = getPayloadText(item.tone);
          return (
            <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="mini-room-card">
              <div className="mini-room-card__header">
                <span className="mini-room-card__name">{getPayloadText(item.title)}</span>
                <span className={`status-dot ${tone === 'success' ? 'status-dot--active' : ''}`} />
              </div>
              <div className="mini-room-card__meta">
                <span>{getPayloadText(item.subtitle)}</span>
              </div>
              <div className="mini-room-card__value">{getPayloadText(item.value)}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function BuiltinMembersCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const items = getPayloadItems(card);

  return (
    <Card className="dashboard-card dashboard-card--builtin">
      <div className="dashboard-card__title">
        <Users size={20} />
        <span>{card.title}</span>
      </div>
      {card.subtitle ? <p className="dashboard-card__subtitle">{card.subtitle}</p> : null}
      <DashboardCardState card={card} t={t} />
      <div className="member-cards">
        {items.map(item => {
          const badgeText = getPayloadText(item.value);
          const badgeTone = getMemberBadgeTone(badgeText);
          return (
            <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="mini-member-card">
              <span className="mini-member-card__avatar"><User size={18} /></span>
              <div className="mini-member-card__info">
                <span className="mini-member-card__name">{getPayloadText(item.title)}</span>
                <span className="mini-member-card__role">{getPayloadText(item.subtitle)}</span>
              </div>
              <span className={`member-status-badge member-status-badge--${badgeTone}`}>{badgeText}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function BuiltinEventsCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const items = getPayloadItems(card);

  return (
    <Card className="dashboard-card dashboard-card--builtin">
      <div className="dashboard-card__title">
        <ClipboardList size={20} />
        <span>{card.title}</span>
      </div>
      {card.subtitle ? <p className="dashboard-card__subtitle">{card.subtitle}</p> : null}
      <DashboardCardState card={card} t={t} />
      <div className="event-list">
        {items.map(item => (
          <div key={`${card.card_ref}-${getPayloadText(item.title)}`} className="event-item">
            <span className={`event-item__icon event-item__icon--${getPayloadText(item.tone, 'neutral')}`}>
              {getPayloadText(item.tone) === 'danger' ? <ShieldCheck size={16} /> : <CalendarClock size={16} />}
            </span>
            <div className="event-item__content">
              <span className="event-item__text">{getPayloadText(item.title)}</span>
              {item.description ? <span className="event-item__desc">{getPayloadText(item.description)}</span> : null}
            </div>
            <span className="event-item__time">{formatRelativeTime(getPayloadText(item.timestamp))}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function BuiltinQuickActionsCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const items = getPayloadItems(card);

  return (
    <Card className="dashboard-card dashboard-card--builtin">
      <div className="dashboard-card__title">
        <ListChecks size={20} />
        <span>{card.title}</span>
      </div>
      {card.subtitle ? <p className="dashboard-card__subtitle">{card.subtitle}</p> : null}
      <DashboardCardState card={card} t={t} />
      <div className="quick-actions">
        {items.map(item => {
          const actionKey = getPayloadText(item.action_key);
          const action = resolveActionByKey(card, actionKey);
          const label = getPayloadText(item.label);
          return (
            <button
              key={`${card.card_ref}-${label}`}
              className="quick-action-btn"
              type="button"
              disabled={!action}
              onClick={() => action ? void handleCardAction(action, t) : undefined}
            >
              <span className="quick-action-btn__icon">{getQuickActionIcon(actionKey, label)}</span>
              <span className="quick-action-btn__copy">
                <strong>{label}</strong>
                {item.description ? <span>{getPayloadText(item.description)}</span> : null}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function BuiltinDashboardCardPanel({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  switch (card.card_ref) {
    case 'builtin:weather':
      return <BuiltinWeatherCard card={card} t={t} />;
    case 'builtin:stats':
      return <BuiltinStatsCard card={card} t={t} />;
    case 'builtin:rooms':
      return <BuiltinRoomsCard card={card} t={t} />;
    case 'builtin:members':
      return <BuiltinMembersCard card={card} t={t} />;
    case 'builtin:events':
      return <BuiltinEventsCard card={card} t={t} />;
    case 'builtin:quick-actions':
      return <BuiltinQuickActionsCard card={card} t={t} />;
    default:
      return (
        <Card className={`dashboard-card dashboard-card--template ${getStateToneClass(card.state)}`}>
          <DashboardCardHeader card={card} t={t} />
          <DashboardCardState card={card} t={t} />
          <DashboardTemplateBody card={card} t={t} />
        </Card>
      );
  }
}

function DashboardCardPanel({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  if (isBuiltinCard(card)) {
    return <BuiltinDashboardCardPanel card={card} t={t} />;
  }

  return (
    <Card className={`dashboard-card dashboard-card--template ${getStateToneClass(card.state)}`}>
      <DashboardCardHeader card={card} t={t} />
      <DashboardCardState card={card} t={t} />
      <DashboardTemplateBody card={card} t={t} />
    </Card>
  );
}

function DashboardItemControls({
  item,
  t,
  onHide,
  onResize,
}: {
  item: MemberDashboardLayoutItem;
  t: (key: ShellMessageKey) => string;
  onHide: () => void;
  onResize: (patch: Partial<Pick<MemberDashboardLayoutItem, 'size' | 'height'>>) => void;
}) {
  return (
    <div className="dashboard-item-controls">
      <div className="dashboard-item-controls__top">
        <span className="drag-handle">
          <GripVertical size={18} />
          <span>{t('home.dragCard')}</span>
        </span>
        <button className="remove-card-btn" type="button" onClick={onHide}>
          <X size={14} />
          <span>{t('home.hideCard')}</span>
        </button>
      </div>
      <div className="dashboard-layout-editor">
        <div className="dashboard-layout-editor__group">
          <span className="dashboard-layout-editor__label">{t('home.cardWidth')}</span>
          <div className="dashboard-segmented-control">
            {DASHBOARD_WIDTH_OPTIONS.map(option => (
              <button
                key={`${item.card_ref}-width-${option.value}`}
                className={`dashboard-segmented-control__item ${item.size === option.value ? 'is-active' : ''}`}
                type="button"
                onClick={() => onResize({ size: option.value })}
              >
                {t(option.labelKey)}
              </button>
            ))}
          </div>
        </div>
        <div className="dashboard-layout-editor__group">
          <span className="dashboard-layout-editor__label">{t('home.cardHeight')}</span>
          <div className="dashboard-segmented-control">
            {DASHBOARD_HEIGHT_OPTIONS.map(option => (
              <button
                key={`${item.card_ref}-height-${option.value}`}
                className={`dashboard-segmented-control__item ${item.height === option.value ? 'is-active' : ''}`}
                type="button"
                onClick={() => onResize({ height: option.value })}
              >
                {t(option.labelKey)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const { t } = useI18n();
  const { familyName, dashboard, layoutItems, loading, savingLayout, error, saveLayout } = useHomeDashboardData();
  const [editMode, setEditMode] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const dragRef = useRef<number | null>(null);
  const cardMap = buildCardMap(dashboard?.cards ?? []);
  const visibleItems = buildVisibleLayoutItems(layoutItems, cardMap);
  const hiddenItems = layoutItems.filter(item => !item.visible);

  const persistLayout = async (nextItems: MemberDashboardLayoutItem[]) => {
    const success = await saveLayout(nextItems);
    if (!success) {
      void Taro.showToast({ title: t('home.layoutSaveFailed'), icon: 'none' });
    }
  };

  const handleDragStart = (idx: number) => (event: DragEvent<HTMLDivElement>) => {
    dragRef.current = idx;
    setDragIdx(idx);
    event.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (idx: number) => (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = (dropIdx: number) => async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const fromIdx = dragRef.current;
    if (fromIdx === null || fromIdx === dropIdx) {
      return;
    }

    const reorderedVisible = [...visibleItems];
    const [moved] = reorderedVisible.splice(fromIdx, 1);
    reorderedVisible.splice(dropIdx, 0, moved);
    const nextVisible = reorderedVisible.map((item, index) => ({ ...item, order: (index + 1) * 10 }));
    const nextVisibleMap = new Map(nextVisible.map(item => [item.card_ref, item]));
    const nextItems = layoutItems.map(item => nextVisibleMap.get(item.card_ref) ?? item);
    await persistLayout(nextItems);
    setDragIdx(null);
    setDragOverIdx(null);
  };

  const handleDragEnd = () => {
    setDragIdx(null);
    setDragOverIdx(null);
  };

  const hideCard = async (cardRef: string) => {
    const nextItems = layoutItems.map(item => item.card_ref === cardRef ? { ...item, visible: false } : item);
    await persistLayout(nextItems);
  };

  const showCard = async (cardRef: string) => {
    const nextOrder = visibleItems.length > 0 ? Math.max(...visibleItems.map(item => item.order)) + 10 : 10;
    const nextItems = layoutItems.map(item => (
      item.card_ref === cardRef ? { ...item, visible: true, order: nextOrder } : item
    ));
    await persistLayout(nextItems);
  };

  const resizeCard = async (
    cardRef: string,
    patch: Partial<Pick<MemberDashboardLayoutItem, 'size' | 'height'>>,
  ) => {
    const nextItems = layoutItems.map(item => item.card_ref === cardRef ? { ...item, ...patch } : item);
    await persistLayout(nextItems);
  };

  return (
    <div className="page page--home">
      <div className="welcome-banner">
        <div className="welcome-banner__text">
          <h1 className="welcome-banner__title animate-slide-in flex items-center gap-3">
            {t('home.welcome')}，{familyName} <Home size={32} className="text-brand-primary" />
          </h1>
          <p className="welcome-banner__sub">{t('home.greeting')}</p>
          {dashboard?.warnings.length ? <p className="text-text-secondary">{t('home.partialDegraded')}</p> : null}
          {error ? <p className="text-text-secondary">{error}</p> : null}
        </div>
        <div className="welcome-banner__right">
          <div className="welcome-banner__time">
            {new Date().toLocaleDateString('zh-CN', { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <button
            className={`edit-dashboard-btn ${editMode ? 'edit-dashboard-btn--active' : ''}`}
            type="button"
            disabled={savingLayout}
            onClick={() => setEditMode(!editMode)}
          >
            {editMode ? t('home.finishEditDashboard') : t('home.editDashboard')}
          </button>
        </div>
      </div>

      {editMode && hiddenItems.length > 0 ? (
        <div className="add-cards-bar animate-slide-down">
          <span className="add-cards-bar__label">{t('home.addCards')}</span>
          <div className="add-cards-bar__list">
            {hiddenItems.map(item => (
              <button key={item.card_ref} className="add-card-chip" type="button" onClick={() => void showCard(item.card_ref)}>
                <Plus size={14} />
                <span>{resolveCardLabel(item.card_ref, cardMap)}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="dashboard-grid">
        {visibleItems.map((item, idx) => {
          const card = cardMap[item.card_ref];
          if (!card) {
            return null;
          }
          return (
            <div
              key={item.card_ref}
              className={`dashboard-grid__item dashboard-grid__item--${item.size} dashboard-grid__item--${item.height} ${editMode ? 'dashboard-grid__item--editing' : ''} ${dragIdx === idx ? 'dashboard-grid__item--dragging' : ''} ${dragOverIdx === idx ? 'dashboard-grid__item--drag-over' : ''}`}
              draggable={editMode}
              onDragStart={editMode ? handleDragStart(idx) : undefined}
              onDragOver={editMode ? handleDragOver(idx) : undefined}
              onDrop={editMode ? handleDrop(idx) : undefined}
              onDragEnd={editMode ? handleDragEnd : undefined}
            >
              {editMode ? (
                <DashboardItemControls
                  item={item}
                  t={t}
                  onHide={() => void hideCard(item.card_ref)}
                  onResize={patch => void resizeCard(item.card_ref, patch)}
                />
              ) : null}
              <DashboardCardPanel card={card} t={t} />
            </div>
          );
        })}
      </div>

      {!loading && visibleItems.length === 0 ? (
        <EmptyState
          icon={<Bot size={56} className="text-text-tertiary opacity-50" />}
          title={t('home.emptyDashboard')}
          description={t('home.emptyDashboardDesc')}
          action={
            <button className="btn btn--primary" type="button" onClick={() => setEditMode(true)}>
              {t('home.editDashboard')}
            </button>
          }
        />
      ) : null}
    </div>
  );
}
