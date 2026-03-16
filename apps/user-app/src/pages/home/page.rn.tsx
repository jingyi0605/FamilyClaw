import type { ReactNode } from 'react';
import { Text, View } from '@tarojs/components';
import { useI18n } from '../../runtime';
import {
  buildCardMap,
  buildVisibleLayoutItems,
  formatRelativeTime,
  useHomeDashboardData,
  type HomeDashboardCardRead,
} from './page.shared';
import './index.rn.scss';

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View className="home-rn-card">
      <Text className="home-rn-card__title">{title}</Text>
      {children}
    </View>
  );
}

function getCardStateLabel(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  switch (card.state) {
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

function getCardStateHint(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  switch (card.state) {
    case 'stale':
      return t('home.cardHint.stale');
    case 'error':
      return t('home.cardHint.error');
    case 'empty':
      return t('home.cardHint.empty');
    default:
      return null;
  }
}

function renderMetricCard(card: HomeDashboardCardRead) {
  const lines: string[] = [];
  const value = card.payload.value;
  const unit = card.payload.unit;
  const context = card.payload.context;
  const trend = card.payload.trend;

  lines.push(`${String(value ?? '-')}${unit ? ` ${String(unit)}` : ''}`);
  if (context) {
    lines.push(String(context));
  }
  if (trend && typeof trend === 'object' && 'label' in trend && trend.label) {
    lines.push(String(trend.label));
  }
  return lines;
}

function renderInsightCard(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  const lines: string[] = [];
  const message = card.payload.message;
  const highlights = Array.isArray(card.payload.highlights) ? card.payload.highlights : [];

  lines.push(String(message ?? t('home.cardHint.empty')));
  if (highlights.length > 0) {
    lines.push(highlights.map(item => String(item)).join(' · '));
  }
  return lines;
}

function renderCollectionCard(
  card: HomeDashboardCardRead,
  itemFormatter: (item: Record<string, unknown>) => string | null,
  t: ReturnType<typeof useI18n>['t'],
) {
  const items = Array.isArray(card.payload.items) ? card.payload.items : [];
  const lines = items
    .map(item => itemFormatter(item as Record<string, unknown>))
    .filter((line): line is string => Boolean(line));

  return lines.length > 0 ? lines : [t('home.cardHint.empty')];
}

function renderStatusListCard(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  return renderCollectionCard(
    card,
    item => {
      const title = String(item.title ?? '').trim();
      const subtitle = String(item.subtitle ?? '').trim();
      const value = String(item.value ?? '').trim();
      if (!title && !subtitle && !value) {
        return null;
      }
      return [title, subtitle, value].filter(Boolean).join(' · ');
    },
    t,
  );
}

function renderTimelineCard(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  return renderCollectionCard(
    card,
    item => {
      const title = String(item.title ?? '').trim();
      const description = String(item.description ?? '').trim();
      const timestamp = String(item.timestamp ?? '').trim();
      if (!title && !description && !timestamp) {
        return null;
      }
      const relativeTime = timestamp ? formatRelativeTime(timestamp) : '';
      return [title, description, relativeTime].filter(Boolean).join(' · ');
    },
    t,
  );
}

function renderActionGroupCard(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  return renderCollectionCard(
    card,
    item => {
      const label = String(item.label ?? '').trim();
      const description = String(item.description ?? '').trim();
      if (!label && !description) {
        return null;
      }
      return [label, description].filter(Boolean).join(' · ');
    },
    t,
  );
}

function getCardLines(card: HomeDashboardCardRead, t: ReturnType<typeof useI18n>['t']) {
  switch (card.template_type) {
    case 'metric':
      return renderMetricCard(card);
    case 'insight':
      return renderInsightCard(card, t);
    case 'timeline':
      return renderTimelineCard(card, t);
    case 'action_group':
      return renderActionGroupCard(card, t);
    case 'status_list':
    default:
      return renderStatusListCard(card, t);
  }
}

export default function HomePage() {
  const { t } = useI18n();
  const { familyName, dashboard, layoutItems, loading, error } = useHomeDashboardData();
  const cardMap = buildCardMap(dashboard?.cards ?? []);
  const visibleItems = buildVisibleLayoutItems(layoutItems, cardMap);

  return (
    <View className="home-rn-page">
      <View className="home-rn-banner">
        <Text className="home-rn-banner__title">{`${t('home.welcome')}，${familyName}`}</Text>
        <Text className="home-rn-banner__sub">{t('home.greeting')}</Text>
        {dashboard?.warnings.length ? <Text className="home-rn-banner__error">{t('home.partialDegraded')}</Text> : null}
        {error ? <Text className="home-rn-banner__error">{error}</Text> : null}
      </View>

      {loading && !dashboard ? (
        <SectionCard title={t('common.loading')}>
          <Text className="home-rn-line">{t('common.loading')}</Text>
        </SectionCard>
      ) : null}

      {!loading && visibleItems.length === 0 ? (
        <SectionCard title={t('home.emptyDashboard')}>
          <Text className="home-rn-line">{t('home.emptyDashboardDesc')}</Text>
        </SectionCard>
      ) : null}

      {visibleItems.map(item => {
        const card = cardMap[item.card_ref];
        if (!card) {
          return null;
        }

        const cardLines = getCardLines(card, t);
        const stateHint = getCardStateHint(card, t);

        return (
          <SectionCard key={item.card_ref} title={card.title}>
            {card.subtitle ? <Text className="home-rn-line">{card.subtitle}</Text> : null}
            <Text className="home-rn-line">{getCardStateLabel(card, t)}</Text>
            {stateHint ? <Text className="home-rn-line">{stateHint}</Text> : null}
            {cardLines.map((line, index) => (
              <Text key={`${item.card_ref}-${index}`} className="home-rn-line">
                {line}
              </Text>
            ))}
          </SectionCard>
        );
      })}
    </View>
  );
}
