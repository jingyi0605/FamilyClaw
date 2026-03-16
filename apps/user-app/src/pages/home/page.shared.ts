import { useEffect, useState } from 'react';
import { coreApiClient, useHouseholdContext } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type {
  HomeDashboardCardActionRead,
  HomeDashboardCardRead,
  HomeDashboardRead,
  MemberDashboardLayoutItem,
} from '@familyclaw/user-core';

const BUILTIN_CARD_MESSAGE_KEYS = {
  'builtin:weather': 'home.builtinCard.weather',
  'builtin:stats': 'home.builtinCard.stats',
  'builtin:rooms': 'home.builtinCard.rooms',
  'builtin:members': 'home.builtinCard.members',
  'builtin:events': 'home.builtinCard.events',
  'builtin:quick-actions': 'home.builtinCard.quickActions',
} as const;

type BuiltinCardRef = keyof typeof BUILTIN_CARD_MESSAGE_KEYS;
type HomePageMessageKey =
  | (typeof BUILTIN_CARD_MESSAGE_KEYS)[BuiltinCardRef]
  | 'home.loadFailed'
  | 'home.layoutSaveFailed'
  | 'home.time.justNow'
  | 'home.time.minutesAgo'
  | 'home.time.hoursAgo'
  | 'home.time.daysAgo';

let currentHomeLocale: string | undefined;

function resolveHomeLocale(locale?: string) {
  if (locale) {
    return locale;
  }
  if (currentHomeLocale) {
    return currentHomeLocale;
  }
  if (typeof navigator !== 'undefined' && navigator.language) {
    return navigator.language;
  }
  return 'zh-CN';
}

function getHomePageMessage(
  key: HomePageMessageKey,
  params?: Record<string, string | number>,
  locale?: string,
) {
  return getPageMessage(resolveHomeLocale(locale), key, params);
}

export function formatRelativeTime(value: string | null | undefined, locale?: string) {
  if (!value) {
    return getHomePageMessage('home.time.justNow', undefined, locale);
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return getHomePageMessage('home.time.minutesAgo', { count: diffMinutes }, locale);
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return getHomePageMessage('home.time.hoursAgo', { count: diffHours }, locale);
  }

  return getHomePageMessage('home.time.daysAgo', { count: Math.round(diffHours / 24) }, locale);
}

export function resolveCardLabel(
  cardRef: string,
  cardMap: Record<string, HomeDashboardCardRead>,
  locale?: string,
) {
  const visibleCard = cardMap[cardRef];
  if (visibleCard?.title) {
    return visibleCard.title;
  }

  const builtinMessageKey = BUILTIN_CARD_MESSAGE_KEYS[cardRef as BuiltinCardRef];
  if (builtinMessageKey) {
    return getHomePageMessage(builtinMessageKey, undefined, locale);
  }

  const parts = cardRef.split(':');
  const raw = parts[parts.length - 1] ?? cardRef;
  return raw.replace(/[-_]/g, ' ').trim() || cardRef;
}

export function buildCardMap(cards: HomeDashboardCardRead[]) {
  return Object.fromEntries(cards.map(card => [card.card_ref, card])) as Record<string, HomeDashboardCardRead>;
}

export function buildVisibleLayoutItems(
  layoutItems: MemberDashboardLayoutItem[],
  cardMap: Record<string, HomeDashboardCardRead>,
) {
  return layoutItems
    .filter(item => item.visible && Boolean(cardMap[item.card_ref]))
    .sort((left, right) => left.order - right.order);
}

function buildDefaultLayoutFromDashboard(dashboard: HomeDashboardRead): MemberDashboardLayoutItem[] {
  return dashboard.cards.map((card, index) => ({
    card_ref: card.card_ref,
    visible: true,
    order: (index + 1) * 10,
    size: card.size,
  }));
}

export function useHomeDashboardData() {
  const { currentHousehold, locale } = useHouseholdContext();
  currentHomeLocale = locale ?? currentHousehold?.locale ?? currentHomeLocale;

  const familyName = currentHousehold?.name ?? '';
  const currentHouseholdId = currentHousehold?.id ?? '';
  const [dashboard, setDashboard] = useState<HomeDashboardRead | null>(null);
  const [layoutItems, setLayoutItems] = useState<MemberDashboardLayoutItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingLayout, setSavingLayout] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadDashboard = async () => {
      if (!currentHouseholdId) {
        setDashboard(null);
        setLayoutItems([]);
        setError(null);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const [dashboardResult, layoutResult] = await Promise.all([
          coreApiClient.getHomeDashboard(currentHouseholdId),
          coreApiClient.getHomeDashboardLayout(currentHouseholdId),
        ]);
        if (cancelled) {
          return;
        }
        setDashboard(dashboardResult);
        setLayoutItems(layoutResult.items.length > 0 ? layoutResult.items : buildDefaultLayoutFromDashboard(dashboardResult));
      } catch (nextError) {
        if (cancelled) {
          return;
        }
        setDashboard(null);
        setLayoutItems([]);
        setError(nextError instanceof Error ? nextError.message : getHomePageMessage('home.loadFailed', undefined, locale));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, locale]);

  const saveLayout = async (nextItems: MemberDashboardLayoutItem[]) => {
    if (!currentHouseholdId) {
      return false;
    }

    setSavingLayout(true);
    setError(null);

    try {
      const savedLayout = await coreApiClient.updateHomeDashboardLayout(currentHouseholdId, nextItems);
      const latestDashboard = await coreApiClient.getHomeDashboard(currentHouseholdId);
      setLayoutItems(savedLayout.items);
      setDashboard(latestDashboard);
      return true;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : getHomePageMessage('home.layoutSaveFailed', undefined, locale));
      return false;
    } finally {
      setSavingLayout(false);
    }
  };

  return {
    familyName,
    currentHouseholdId,
    dashboard,
    layoutItems,
    loading,
    savingLayout,
    error,
    saveLayout,
  };
}

export type { HomeDashboardCardActionRead, HomeDashboardCardRead, HomeDashboardRead, MemberDashboardLayoutItem };
