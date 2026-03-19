/**
 * RN 首页
 *
 * 仪表盘卡片式布局，展示家庭状态、指标和快捷操作。
 * 视觉风格与 H5 品牌保持一致：温暖、层次分明、家庭感。
 */
import { View, StyleSheet } from 'react-native';
import { GuideAnchor, USER_GUIDE_ANCHOR_IDS, useI18n } from '../../runtime/index.rn';
import {
  buildCardMap,
  buildVisibleLayoutItems,
  formatRelativeTime,
  useHomeDashboardData,
  type HomeDashboardCardRead,
} from './page.shared';
import {
  RnPageShell,
  RnSection,
  RnCard,
  RnText,
  RnEmptyState,
  RnTabBar,
  rnFoundationTokens,
  rnSemanticTokens,
} from '../../runtime/rn-shell';

/* ─── 辅助函数 ─── */

type T = ReturnType<typeof useI18n>['t'];

const STATE_TONE: Record<string, 'secondary' | 'tertiary' | 'danger' | 'warning'> = {
  ready: 'secondary',
  stale: 'warning',
  error: 'danger',
  empty: 'tertiary',
};

function getCardStateLabel(card: HomeDashboardCardRead, t: T) {
  switch (card.state) {
    case 'ready': return t('home.cardState.ready');
    case 'stale': return t('home.cardState.stale');
    case 'error': return t('home.cardState.error');
    case 'empty': return t('home.cardState.empty');
    default: return '';
  }
}

function getCardStateHint(card: HomeDashboardCardRead, t: T) {
  switch (card.state) {
    case 'stale': return t('home.cardHint.stale');
    case 'error': return t('home.cardHint.error');
    case 'empty': return t('home.cardHint.empty');
    default: return null;
  }
}

function renderMetricCard(card: HomeDashboardCardRead): { value: string; context?: string; trend?: string } {
  const { value, unit, context, trend } = card.payload;
  return {
    value: `${String(value ?? '-')}${unit ? ` ${String(unit)}` : ''}`,
    context: context ? String(context) : undefined,
    trend: trend && typeof trend === 'object' && 'label' in trend ? String(trend.label) : undefined,
  };
}

function renderCollectionLines(
  card: HomeDashboardCardRead,
  formatter: (item: Record<string, unknown>) => string | null,
  t: T,
): string[] {
  const items = Array.isArray(card.payload.items) ? card.payload.items : [];
  const lines = items
    .map(item => formatter(item as Record<string, unknown>))
    .filter((line): line is string => Boolean(line));
  return lines.length > 0 ? lines : [t('home.cardHint.empty')];
}

function getCardLines(card: HomeDashboardCardRead, t: T): string[] {
  switch (card.template_type) {
    case 'insight': {
      const { message, highlights } = card.payload;
      const lines = [String(message ?? t('home.cardHint.empty'))];
      if (Array.isArray(highlights) && highlights.length > 0) {
        lines.push(highlights.map(String).join(' · '));
      }
      return lines;
    }
    case 'timeline':
      return renderCollectionLines(card, item => {
        const title = String(item.title ?? '').trim();
        const desc = String(item.description ?? '').trim();
        const ts = String(item.timestamp ?? '').trim();
        if (!title && !desc && !ts) return null;
        const rel = ts ? formatRelativeTime(ts) : '';
        return [title, desc, rel].filter(Boolean).join(' · ');
      }, t);
    case 'action_group':
      return renderCollectionLines(card, item => {
        const label = String(item.label ?? '').trim();
        const desc = String(item.description ?? '').trim();
        return (label || desc) ? [label, desc].filter(Boolean).join(' · ') : null;
      }, t);
    case 'status_list':
    default:
      return renderCollectionLines(card, item => {
        const title = String(item.title ?? '').trim();
        const subtitle = String(item.subtitle ?? '').trim();
        const value = String(item.value ?? '').trim();
        return (title || subtitle || value) ? [title, subtitle, value].filter(Boolean).join(' · ') : null;
      }, t);
  }
}

/* ─── 仪表盘卡片 ─── */

function DashboardCard({ card, t }: { card: HomeDashboardCardRead; t: T }) {
  const stateHint = getCardStateHint(card, t);
  const stateTone = STATE_TONE[card.state ?? ''] ?? 'secondary';
  const isMetric = card.template_type === 'metric';

  return (
    <RnCard>
      {/* 标题行 */}
      <View style={styles.cardHeader}>
        <RnText variant="label" style={styles.flex1}>{card.title}</RnText>
        <View style={[styles.stateBadge, { backgroundColor: stateTone === 'secondary' ? rnSemanticTokens.state.successLight : stateTone === 'danger' ? rnSemanticTokens.state.dangerLight : stateTone === 'warning' ? rnSemanticTokens.state.warningLight : rnSemanticTokens.surface.muted }]}>
          <RnText variant="caption" tone={stateTone === 'secondary' ? 'success' : stateTone}>
            {getCardStateLabel(card, t)}
          </RnText>
        </View>
      </View>

      {card.subtitle ? (
        <RnText variant="caption" tone="tertiary" style={styles.cardSubtitle}>
          {card.subtitle}
        </RnText>
      ) : null}

      {/* 指标卡片：数值大号展示 */}
      {isMetric ? (
        <View style={styles.metricBlock}>
          {(() => {
            const m = renderMetricCard(card);
            return (
              <>
                <RnText variant="hero" style={styles.metricValue}>{m.value}</RnText>
                {m.context ? <RnText variant="caption" tone="secondary">{m.context}</RnText> : null}
                {m.trend ? <RnText variant="caption" tone="success">{m.trend}</RnText> : null}
              </>
            );
          })()}
        </View>
      ) : (
        <View style={styles.cardContent}>
          {getCardLines(card, t).map((line, i) => (
            <RnText key={i} variant="body" style={styles.cardLine}>{line}</RnText>
          ))}
        </View>
      )}

      {stateHint ? (
        <RnText variant="caption" tone="tertiary" style={styles.stateHint}>{stateHint}</RnText>
      ) : null}
    </RnCard>
  );
}

/* ─── 欢迎横幅 ─── */

function WelcomeBanner({ memberDisplayName, t }: { memberDisplayName: string; t: T }) {
  return (
    <View style={styles.banner}>
      <RnText variant="caption" style={styles.bannerEmoji}>🐾</RnText>
      <RnText variant="hero" style={styles.bannerTitle}>
        {t('home.welcome')}，{memberDisplayName}
      </RnText>
      <RnText variant="body" tone="secondary">{t('home.greeting')}</RnText>
    </View>
  );
}

/* ─── 样式 ─── */

const styles = StyleSheet.create({
  banner: {
    backgroundColor: rnSemanticTokens.action.primaryLight,
    borderRadius: rnFoundationTokens.radius.lg,
    padding: rnFoundationTokens.spacing.lg,
    marginBottom: rnFoundationTokens.spacing.md,
  },
  bannerEmoji: {
    fontSize: 28,
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  bannerTitle: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  flex1: {
    flex: 1,
  },
  stateBadge: {
    borderRadius: rnFoundationTokens.radius.sm,
    paddingHorizontal: rnFoundationTokens.spacing.sm,
    paddingVertical: 2,
  },
  cardSubtitle: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  metricBlock: {
    marginTop: rnFoundationTokens.spacing.sm,
    alignItems: 'flex-start',
  },
  metricValue: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  cardContent: {
    marginTop: rnFoundationTokens.spacing.sm,
  },
  cardLine: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  stateHint: {
    marginTop: rnFoundationTokens.spacing.sm,
  },

  guideAnchor: {
    flex: 1,
  },
});

/* ─── 页面主体 ─── */

function HomeContent() {
  const { t } = useI18n();
  const { memberDisplayName, dashboard, layoutItems, loading, error } = useHomeDashboardData();
  const cardMap = buildCardMap(dashboard?.cards ?? []);
  const visibleItems = buildVisibleLayoutItems(layoutItems, cardMap);

  return (
    <RnPageShell safeAreaBottom={false}>
      <GuideAnchor anchorId={USER_GUIDE_ANCHOR_IDS.homeOverview} style={styles.guideAnchor}>
        <WelcomeBanner memberDisplayName={memberDisplayName} t={t} />

        {error ? (
          <RnCard variant="warning">
            <RnText variant="body" tone="warning">{error}</RnText>
          </RnCard>
        ) : null}

        {loading && !dashboard ? (
          <RnSection title={t('common.loading')}>
            <RnText variant="body" tone="secondary">{t('common.loading')}</RnText>
          </RnSection>
        ) : null}

      {!loading && visibleItems.length === 0 ? (
        <RnEmptyState
          icon="📊"
          title={t('home.emptyDashboard')}
          description={t('home.emptyDashboardDesc')}
        />
      ) : null}

      {visibleItems.map(item => {
        const card = cardMap[item.card_ref];
        if (!card) return null;
        return <DashboardCard key={item.card_ref} card={card} t={t} />;
      })}

        <RnTabBar />
      </GuideAnchor>
    </RnPageShell>
  );
}

export default HomeContent;
