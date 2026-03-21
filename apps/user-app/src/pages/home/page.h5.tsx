import { useEffect, useRef, useState, type DragEvent, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import { EmptyStateCard, PageHeader, UiCard } from '@familyclaw/user-ui';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpenText,
  Bot,
  CalendarClock,
  CheckCircle2,
  CloudRain,
  CloudSun,
  ClipboardList,
  Droplets,
  Gauge,
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
import './styles-entry';
import { GuideAnchor, USER_GUIDE_ANCHOR_IDS } from '../../runtime';
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
type ResizeAxis = 'width' | 'height';
type ResizeSession = {
  cardRef: string;
  axis: ResizeAxis;
  startX: number;
  startY: number;
  startSize: MemberDashboardLayoutItem['size'];
  startHeight: MemberDashboardLayoutItem['height'];
  nextSize: MemberDashboardLayoutItem['size'];
  nextHeight: MemberDashboardLayoutItem['height'];
};

const HEIGHT_ORDER: MemberDashboardLayoutItem['height'][] = ['compact', 'regular', 'tall'];
const WIDTH_RESIZE_STEP = 72;
const HEIGHT_RESIZE_STEP = 64;
const MOBILE_LAYOUT_BREAKPOINT = 900;

function isMobileDashboardLayout() {
  if (typeof window === 'undefined') {
    return false;
  }
  if (window.innerWidth <= MOBILE_LAYOUT_BREAKPOINT) {
    return true;
  }
  return window.matchMedia?.('(pointer: coarse)').matches ?? false;
}

function clampIndex(value: number, max: number) {
  return Math.min(Math.max(value, 0), max);
}

function resolveWidthByDelta(
  startSize: MemberDashboardLayoutItem['size'],
  deltaX: number,
): MemberDashboardLayoutItem['size'] {
  if (Math.abs(deltaX) < WIDTH_RESIZE_STEP / 2) {
    return startSize;
  }
  return deltaX > 0 ? 'full' : 'half';
}

function resolveHeightByDelta(
  startHeight: MemberDashboardLayoutItem['height'],
  deltaY: number,
): MemberDashboardLayoutItem['height'] {
  const startIndex = HEIGHT_ORDER.indexOf(startHeight);
  const deltaStep = Math.round(deltaY / HEIGHT_RESIZE_STEP);
  return HEIGHT_ORDER[clampIndex(startIndex + deltaStep, HEIGHT_ORDER.length - 1)];
}

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

function isWeatherDashboardCard(card: HomeDashboardCardRead) {
  return card.payload.card_kind === 'weather';
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

function getPayloadNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatWeatherNumber(value: number | null, unit?: string) {
  if (value === null) {
    return null;
  }
  const normalized = Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
  return unit ? `${normalized} ${unit}` : normalized;
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

function getWeatherConditionIcon(card: HomeDashboardCardRead) {
  if (card.state === 'error') {
    return <TriangleAlert size={48} />;
  }

  const conditionCode = getPayloadText(card.payload.condition_code).toLowerCase();
  if (conditionCode.includes('rain') || conditionCode.includes('drizzle')) {
    return <CloudRain size={48} />;
  }
  if (conditionCode.includes('clear') || conditionCode.includes('sun')) {
    return <Sun size={48} className="text-warning" />;
  }
  if (conditionCode.includes('wind')) {
    return <Wind size={48} />;
  }
  return <CloudSun size={48} />;
}

function getPayloadObjectArray(value: unknown): DashboardPayloadItem[] {
  return Array.isArray(value)
    ? value.filter(item => typeof item === 'object' && item !== null) as DashboardPayloadItem[]
    : [];
}

function resolvePayloadLabel(
  item: DashboardPayloadItem,
  t: (key: ShellMessageKey) => string,
  fallbackKey?: ShellMessageKey,
  hardFallback = '',
) {
  const labelKey = getPayloadText(item.label_key);
  if (labelKey) {
    const translated = t(labelKey);
    if (translated && translated !== labelKey) {
      return translated;
    }
  }

  const label = getPayloadText(item.label);
  if (label) {
    return label;
  }

  if (fallbackKey) {
    const fallback = t(fallbackKey);
    if (fallback && fallback !== fallbackKey) {
      return fallback;
    }
  }

  return hardFallback;
}

function resolvePayloadValue(item: DashboardPayloadItem) {
  const valueDisplay = getPayloadText(item.value_display);
  if (valueDisplay) {
    return valueDisplay;
  }

  const rawValue = item.value;
  const valueType = getPayloadText(item.value_type);
  const numericValue = getPayloadNumber(rawValue);
  if (numericValue !== null) {
    return formatWeatherNumber(numericValue, getPayloadText(item.unit) || undefined) ?? '';
  }

  const textValue = getPayloadText(rawValue);
  if (valueType === 'relative_time') {
    return formatRelativeTime(textValue);
  }
  return textValue;
}

function getWeatherMetricIconByKey(key: string) {
  switch (key) {
    case 'humidity':
      return <Droplets size={16} />;
    case 'wind_speed':
    case 'wind':
      return <Wind size={16} />;
    case 'precipitation_next_1h':
    case 'precipitation':
      return <CloudRain size={16} />;
    case 'pressure':
      return <Gauge size={16} />;
    default:
      return <Info size={16} />;
  }
}

function buildWeatherForecastText(card: HomeDashboardCardRead, t: (key: ShellMessageKey) => string) {
  const forecast = typeof card.payload.forecast_6h === 'object' && card.payload.forecast_6h !== null
    ? card.payload.forecast_6h as Record<string, unknown>
    : null;
  if (!forecast) {
    return null;
  }

  const conditionText = getPayloadText(forecast.condition_text);
  const minTemperature = formatWeatherNumber(getPayloadNumber(forecast.min_temperature), '°C');
  const maxTemperature = formatWeatherNumber(getPayloadNumber(forecast.max_temperature), '°C');
  const range = [minTemperature, maxTemperature].filter(Boolean).join(' ~ ');
  if (conditionText && range) {
    return `${conditionText} · ${range}`;
  }
  if (conditionText) {
    return conditionText;
  }
  if (range) {
    return range;
  }
  return translateWeatherLabel(
    t,
    'official_weather.dashboard.no_data',
    'home.weather.noData',
    '暂无数据',
  );
}

function translateWeatherLabel(
  t: (key: ShellMessageKey) => string,
  pluginKey: string,
  fallbackKey: ShellMessageKey,
  hardFallback: string,
) {
  const pluginText = t(pluginKey);
  if (pluginText && pluginText !== pluginKey) {
    return pluginText;
  }

  const fallbackText = t(fallbackKey);
  if (fallbackText && fallbackText !== fallbackKey) {
    return fallbackText;
  }

  return hardFallback;
}

function buildWeatherDetailItems(card: HomeDashboardCardRead, t: (key: ShellMessageKey) => string) {
  const payloadItems = getPayloadObjectArray(card.payload.detail_items);
  if (payloadItems.length > 0) {
    return payloadItems
      .map(item => {
        const value = resolvePayloadValue(item);
        if (!value) {
          return null;
        }
        const key = getPayloadText(item.key, 'detail');
        return {
          key,
          label: resolvePayloadLabel(item, t),
          value,
          icon: getWeatherMetricIconByKey(key),
        };
      })
      .filter(Boolean) as Array<{ key: string; label: string; value: string; icon: ReactNode }>;
  }

  const humidity = formatWeatherNumber(getPayloadNumber(card.payload.humidity), '%');
  const windSpeed = formatWeatherNumber(getPayloadNumber(card.payload.wind_speed), 'm/s');
  const precipitation = formatWeatherNumber(getPayloadNumber(card.payload.precipitation_next_1h), 'mm');
  const pressure = formatWeatherNumber(getPayloadNumber(card.payload.pressure), 'hPa');

  return [
    humidity ? {
      key: 'humidity',
      label: translateWeatherLabel(t, 'official_weather.dashboard.fields.humidity', 'home.weather.humidity', '湿度'),
      value: humidity,
      icon: <Droplets size={16} />,
    } : null,
    windSpeed ? {
      key: 'wind',
      label: translateWeatherLabel(t, 'official_weather.dashboard.fields.wind_speed', 'home.weather.windSpeed', '风速'),
      value: windSpeed,
      icon: <Wind size={16} />,
    } : null,
    precipitation ? {
      key: 'precipitation',
      label: translateWeatherLabel(
        t,
        'official_weather.dashboard.fields.precipitation_next_1h',
        'home.weather.precipitationNext1h',
        '未来 1 小时降水',
      ),
      value: precipitation,
      icon: <CloudRain size={16} />,
    } : null,
    pressure ? {
      key: 'pressure',
      label: translateWeatherLabel(t, 'official_weather.dashboard.fields.pressure', 'home.weather.pressure', '气压'),
      value: pressure,
      icon: <Gauge size={16} />,
    } : null,
  ].filter(Boolean) as Array<{ key: string; label: string; value: string; icon: ReactNode }>;
}

function buildWeatherFooterItems(card: HomeDashboardCardRead, t: (key: ShellMessageKey) => string) {
  const payloadItems = getPayloadObjectArray(card.payload.footer_items);
  if (payloadItems.length > 0) {
    return payloadItems
      .map(item => {
        const value = resolvePayloadValue(item);
        if (!value) {
          return null;
        }
        return {
          key: getPayloadText(item.key, 'footer'),
          label: resolvePayloadLabel(item, t),
          value,
        };
      })
      .filter(Boolean) as Array<{ key: string; label: string; value: string }>;
  }

  const forecastText = buildWeatherForecastText(card, t);
  const updatedAt = getPayloadText(card.payload.updated_at);
  return [
    forecastText
      ? {
        key: 'forecast_6h',
        label: translateWeatherLabel(
          t,
          'official_weather.dashboard.fields.forecast_6h',
          'home.weather.forecast6h',
          '未来 6 小时摘要',
        ),
        value: forecastText,
      }
      : null,
    updatedAt
      ? {
        key: 'updated_at',
        label: translateWeatherLabel(
          t,
          'official_weather.dashboard.fields.updated_at',
          'home.weather.updated',
          '更新时间',
        ),
        value: formatRelativeTime(updatedAt),
      }
      : null,
  ].filter(Boolean) as Array<{ key: string; label: string; value: string }>;
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

function PluginWeatherCard({ card, t }: { card: HomeDashboardCardRead; t: (key: ShellMessageKey) => string }) {
  const location = getPayloadText(card.payload.location, card.title);
  const noDataText = translateWeatherLabel(
    t,
    'official_weather.dashboard.no_data',
    'home.weather.noData',
    '暂无数据',
  );
  const conditionText = getPayloadText(card.payload.condition_text, getPayloadText(card.payload.message, noDataText));
  const temperature = formatWeatherNumber(getPayloadNumber(card.payload.temperature), '°C') ?? noDataText;
  const detailItems = buildWeatherDetailItems(card, t);
  const footerItems = buildWeatherFooterItems(card, t);
  const displayTemperature = temperature.replace('掳C', '°C');
  const displayFooterItems = footerItems.map(item => ({
    ...item,
    value: item.value.replace('掳C', '°C').replace(' 路 ', ' · '),
  }));
  const statusMessage = getPayloadText(card.payload.message);

  return (
    <Card className={`dashboard-card weather-card ${getStateToneClass(card.state)}`}>
      <div className="weather-card__header-copy">
        <span className="weather-card__eyebrow">{location}</span>
        <span className="weather-card__kind">{card.subtitle ?? ''}</span>
      </div>
      <div className="weather-card__main">
        <div className="weather-card__icon-area">
          <span className="weather-icon-animated weather-icon-animated--static">
            <span className="weather-sun weather-sun--card">{getWeatherConditionIcon(card)}</span>
          </span>
        </div>
        <div className="weather-card__summary">
          <span className="weather-temp-value">{displayTemperature}</span>
          <span className="weather-temp-desc">{conditionText}</span>
        </div>
      </div>
      <DashboardCardState card={card} t={t} />
      {statusMessage && card.state !== 'ready' ? (
        <p className="dashboard-card__hint">{statusMessage}</p>
      ) : null}
      {detailItems.length > 0 ? (
        <div className="weather-card__details">
          {detailItems.map(detail => (
            <div key={detail.key} className="weather-detail weather-detail--metric">
              <span className="weather-detail__icon">{detail.icon}</span>
              <span className="weather-detail__label">{detail.label}</span>
              <strong className="weather-detail__value">{detail.value}</strong>
            </div>
          ))}
        </div>
      ) : null}
      {displayFooterItems.length > 0 ? (
        <div className="weather-card__forecast">
          {displayFooterItems.map(item => (
            <div key={item.key} className="weather-forecast-item weather-forecast-item--wide">
              <span className="weather-forecast-day">{item.label}</span>
              <span className="weather-forecast-temp">{item.value}</span>
            </div>
          ))}
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
  if (isWeatherDashboardCard(card)) {
    return <PluginWeatherCard card={card} t={t} />;
  }

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
  t,
  onHide,
  onDragStart,
  onDragEnd,
  onStartResize,
  resizingAxis,
}: {
  t: (key: ShellMessageKey) => string;
  onHide: () => void;
  onDragStart: (event: DragEvent<HTMLSpanElement>) => void;
  onDragEnd: () => void;
  onStartResize: (event: ReactMouseEvent<HTMLButtonElement>, axis: ResizeAxis) => void;
  resizingAxis: ResizeAxis | null;
}) {
  return (
    <div className="dashboard-item-controls">
      <span
        className="drag-handle"
        draggable
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        title={t('home.dragCard')}
      >
          <GripVertical size={18} />
      </span>
      <button className="remove-card-btn" type="button" onClick={onHide} title={t('home.hideCard')}>
        <X size={14} />
      </button>
      <button
        className={`dashboard-resize-handle dashboard-resize-handle--width ${resizingAxis === 'width' ? 'is-active' : ''}`}
        type="button"
        title={t('home.resizeWidth')}
        onMouseDown={event => onStartResize(event, 'width')}
      >
        <span className="dashboard-resize-handle__line" />
      </button>
      <button
        className={`dashboard-resize-handle dashboard-resize-handle--height ${resizingAxis === 'height' ? 'is-active' : ''}`}
        type="button"
        title={t('home.resizeHeight')}
        onMouseDown={event => onStartResize(event, 'height')}
      >
        <span className="dashboard-resize-handle__line" />
      </button>
    </div>
  );
}

export default function HomePage() {
  const { t } = useI18n();
  const { memberDisplayName, dashboard, layoutItems, loading, savingLayout, error, saveLayout } = useHomeDashboardData();
  const [editMode, setEditMode] = useState(false);
  const [mobileLayout, setMobileLayout] = useState(isMobileDashboardLayout);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [resizeSession, setResizeSession] = useState<ResizeSession | null>(null);
  const isResizing = resizeSession !== null;
  const dragRef = useRef<number | null>(null);
  const resizeSessionRef = useRef<ResizeSession | null>(null);
  const previewLayoutItems = resizeSession
    ? layoutItems.map(item => (
      item.card_ref === resizeSession.cardRef
        ? { ...item, size: resizeSession.nextSize, height: resizeSession.nextHeight }
        : item
    ))
    : layoutItems;
  const cardMap = buildCardMap(dashboard?.cards ?? []);
  const visibleItems = buildVisibleLayoutItems(previewLayoutItems, cardMap);
  const hiddenItems = layoutItems.filter(item => !item.visible);

  useEffect(() => {
    resizeSessionRef.current = resizeSession;
  }, [resizeSession]);

  useEffect(() => {
    if (mobileLayout || !resizeSessionRef.current) {
      return undefined;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const session = resizeSessionRef.current;
      if (!session) {
        return;
      }
      const deltaX = event.clientX - session.startX;
      const deltaY = event.clientY - session.startY;
      const nextSize = session.axis === 'width' ? resolveWidthByDelta(session.startSize, deltaX) : session.startSize;
      const nextHeight = session.axis === 'height' ? resolveHeightByDelta(session.startHeight, deltaY) : session.startHeight;
      const nextSession = {
        ...session,
        nextSize,
        nextHeight,
      };
      resizeSessionRef.current = nextSession;
      setResizeSession(nextSession);
    };

    const handleMouseUp = () => {
      const session = resizeSessionRef.current;
      resizeSessionRef.current = null;
      setResizeSession(null);
      if (!session) {
        return;
      }
      const changed = session.nextSize !== session.startSize || session.nextHeight !== session.startHeight;
      if (!changed) {
        return;
      }
      const nextItems = layoutItems.map(item => (
        item.card_ref === session.cardRef
          ? { ...item, size: session.nextSize, height: session.nextHeight }
          : item
      ));
      void persistLayout(nextItems);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    document.body.classList.add('dashboard-resizing');

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('dashboard-resizing');
    };
  }, [isResizing, layoutItems, mobileLayout]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const updateLayoutMode = () => {
      setMobileLayout(isMobileDashboardLayout());
    };

    updateLayoutMode();
    window.addEventListener('resize', updateLayoutMode);
    return () => window.removeEventListener('resize', updateLayoutMode);
  }, []);

  useEffect(() => {
    if (!mobileLayout) {
      return;
    }
    setResizeSession(null);
    resizeSessionRef.current = null;
    setDragIdx(null);
    setDragOverIdx(null);
    dragRef.current = null;
  }, [mobileLayout]);

  const persistLayout = async (nextItems: MemberDashboardLayoutItem[]) => {
    const success = await saveLayout(nextItems);
    if (!success) {
      void Taro.showToast({ title: t('home.layoutSaveFailed'), icon: 'none' });
    }
  };

  const handleDragStart = (idx: number) => (event: DragEvent<HTMLSpanElement>) => {
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

  const handleResizeStart = (
    item: MemberDashboardLayoutItem,
    event: ReactMouseEvent<HTMLButtonElement>,
    axis: ResizeAxis,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const session: ResizeSession = {
      cardRef: item.card_ref,
      axis,
      startX: event.clientX,
      startY: event.clientY,
      startSize: item.size,
      startHeight: item.height,
      nextSize: item.size,
      nextHeight: item.height,
    };
    resizeSessionRef.current = session;
    setResizeSession(session);
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

  const [activeTab, setActiveTab] = useState('home');
  const desktopEditMode = editMode && !mobileLayout;
  const mobileManageMode = editMode && mobileLayout;

  const tabs = [{ id: 'home', label: t('dashboard.tab.home') }];

  return (
    <div className="page page--home">
      <PageHeader title={t('dashboard.title')} />

      <div className="memory-main-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            type="button"
            className={`memory-main-tab ${activeTab === tab.id ? 'memory-main-tab--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
        {desktopEditMode && (
          <button
            type="button"
            className="memory-main-tab memory-main-tab--add"
            title={t('dashboard.tab.add')}
          >
            <Plus size={16} />
          </button>
        )}
      </div>

      <GuideAnchor anchorId={USER_GUIDE_ANCHOR_IDS.homeOverview}>
        <div className="dashboard-header-bar">
          <div className="dashboard-header-bar__left">
            <span className="dashboard-header-bar__greeting">
              {t('home.welcome')}，{memberDisplayName}
            </span>
            {error ? <span className="text-text-secondary">{error}</span> : null}
          </div>
          <div className="dashboard-header-bar__right">
            <span className="dashboard-header-bar__time">
              {new Date().toLocaleDateString('zh-CN', { weekday: 'long', month: 'long', day: 'numeric' })}
            </span>
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
      </GuideAnchor>

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
              className={`dashboard-grid__item dashboard-grid__item--${item.size} dashboard-grid__item--${item.height} ${desktopEditMode ? 'dashboard-grid__item--editing' : ''} ${dragIdx === idx ? 'dashboard-grid__item--dragging' : ''} ${dragOverIdx === idx ? 'dashboard-grid__item--drag-over' : ''} ${resizeSession?.cardRef === item.card_ref ? 'dashboard-grid__item--resizing' : ''}`}
              onDragOver={desktopEditMode ? handleDragOver(idx) : undefined}
              onDrop={desktopEditMode ? handleDrop(idx) : undefined}
            >
              {desktopEditMode ? (
                <DashboardItemControls
                  t={t}
                  onHide={() => void hideCard(item.card_ref)}
                  onDragStart={handleDragStart(idx)}
                  onDragEnd={handleDragEnd}
                  onStartResize={(event, axis) => handleResizeStart(item, event, axis)}
                  resizingAxis={resizeSession?.cardRef === item.card_ref ? resizeSession.axis : null}
                />
              ) : null}
              <DashboardCardPanel card={card} t={t} />
              {mobileManageMode ? (
                <div className="dashboard-mobile-actions">
                  <button
                    className="remove-card-btn remove-card-btn--mobile"
                    type="button"
                    onClick={() => void hideCard(item.card_ref)}
                    title={t('home.hideCard')}
                  >
                    <X size={14} />
                    <span>{t('home.hideCard')}</span>
                  </button>
                </div>
              ) : null}
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
