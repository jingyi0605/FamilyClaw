import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  DEFAULT_LOCALE_ID,
  buildLocaleDefinitions,
  persistHouseholdId,
  resolveSupportedLocale,
  type Household,
  type PluginLocale,
} from '@familyclaw/user-core';
import { coreApiClient, loadUserAppBootstrap, taroStorage } from './core';

type HouseholdContextValue = {
  currentHouseholdId: string;
  currentHousehold: Household | null;
  households: Household[];
  locales: PluginLocale[];
  locale: string;
  householdsLoading: boolean;
  householdsError: string;
  setCurrentHouseholdId: (id: string) => void;
  refreshHouseholds: (preferredHouseholdId?: string) => Promise<void>;
  refreshCurrentHousehold: (householdId?: string) => Promise<void>;
};

const HouseholdContext = createContext<HouseholdContextValue | null>(null);

export function HouseholdProvider(props: { children: ReactNode }) {
  const [currentHouseholdId, setCurrentHouseholdIdState] = useState('');
  const [households, setHouseholds] = useState<Household[]>([]);
  const [currentHousehold, setCurrentHousehold] = useState<Household | null>(null);
  const [locales, setLocales] = useState<PluginLocale[]>([]);
  const [locale, setLocale] = useState(DEFAULT_LOCALE_ID);
  const [householdsLoading, setHouseholdsLoading] = useState(true);
  const [householdsError, setHouseholdsError] = useState('');

  async function loadLocales(householdId: string, householdLocale?: string | null) {
    if (!householdId) {
      setLocales([]);
      setLocale(DEFAULT_LOCALE_ID);
      return;
    }

    const nextLocales = await coreApiClient
      .listHouseholdLocales(householdId)
      .then(result => result.items)
      .catch(() => []);

    setLocales(nextLocales);
    const definitions = buildLocaleDefinitions(nextLocales);
    setLocale(resolveSupportedLocale(householdLocale ?? currentHousehold?.locale, definitions, DEFAULT_LOCALE_ID));
  }

  const setCurrentHouseholdId = (id: string) => {
    setCurrentHouseholdIdState(id);
    const nextCurrentHousehold = households.find(item => item.id === id) ?? null;
    setCurrentHousehold(nextCurrentHousehold);

    if (id) {
      void persistHouseholdId(taroStorage, id);
      void loadLocales(id, nextCurrentHousehold?.locale);
      return;
    }

    setLocales([]);
    setLocale(DEFAULT_LOCALE_ID);
  };

  const refreshHouseholds = useMemo(() => async (preferredHouseholdId?: string) => {
    setHouseholdsLoading(true);
    setHouseholdsError('');

    try {
      const response = await coreApiClient.listHouseholds();
      const nextHouseholds = response.items;
      setHouseholds(nextHouseholds);

      const resolvedHouseholdId = nextHouseholds.some(item => item.id === (preferredHouseholdId ?? currentHouseholdId))
        ? (preferredHouseholdId ?? currentHouseholdId)
        : nextHouseholds[0]?.id ?? '';
      setCurrentHouseholdIdState(resolvedHouseholdId);

      const nextCurrentHousehold = nextHouseholds.find(item => item.id === resolvedHouseholdId) ?? null;
      setCurrentHousehold(nextCurrentHousehold);

      if (resolvedHouseholdId) {
        await persistHouseholdId(taroStorage, resolvedHouseholdId);
        await loadLocales(resolvedHouseholdId, nextCurrentHousehold?.locale);
      } else {
        setLocales([]);
        setLocale(DEFAULT_LOCALE_ID);
      }
    } catch (error) {
      setHouseholds([]);
      setCurrentHousehold(null);
      setLocales([]);
      setLocale(DEFAULT_LOCALE_ID);
      setHouseholdsError(error instanceof Error ? error.message : '加载家庭列表失败');
    } finally {
      setHouseholdsLoading(false);
    }
  }, [currentHouseholdId]);

  const refreshCurrentHousehold = useMemo(() => async (householdId = currentHouseholdId) => {
    if (!householdId) {
      setCurrentHousehold(null);
      setLocales([]);
      setLocale(DEFAULT_LOCALE_ID);
      return;
    }

    const household = await coreApiClient.getHousehold(householdId);
    setCurrentHousehold(household);
    setHouseholds(current => current.map(item => item.id === householdId ? household : item));

    const nextLocales = await coreApiClient
      .listHouseholdLocales(householdId)
      .then(result => result.items)
      .catch(() => []);

    setLocales(nextLocales);
    setLocale(resolveSupportedLocale(household.locale, buildLocaleDefinitions(nextLocales), DEFAULT_LOCALE_ID));
  }, [currentHouseholdId]);

  useEffect(() => {
    let cancelled = false;
    setHouseholdsLoading(true);
    setHouseholdsError('');

    void loadUserAppBootstrap()
      .then(snapshot => {
        if (cancelled) {
          return;
        }

        setHouseholds(snapshot.households);
        setCurrentHousehold(snapshot.currentHousehold);
        setCurrentHouseholdIdState(snapshot.currentHousehold?.id ?? '');
        setLocales(snapshot.locales);
        setLocale(resolveSupportedLocale(snapshot.currentHousehold?.locale, buildLocaleDefinitions(snapshot.locales), DEFAULT_LOCALE_ID));
      })
      .catch(error => {
        if (!cancelled) {
          setHouseholdsError(error instanceof Error ? error.message : '家庭上下文初始化失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHouseholdsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<HouseholdContextValue>(() => ({
    currentHouseholdId,
    currentHousehold,
    households,
    locales,
    locale,
    householdsLoading,
    householdsError,
    setCurrentHouseholdId,
    refreshHouseholds,
    refreshCurrentHousehold,
  }), [
    currentHousehold,
    currentHouseholdId,
    households,
    householdsError,
    householdsLoading,
    locale,
    locales,
    refreshCurrentHousehold,
    refreshHouseholds,
  ]);

  return (
    <HouseholdContext.Provider value={value}>
      {props.children}
    </HouseholdContext.Provider>
  );
}

export function useHouseholdContext() {
  const context = useContext(HouseholdContext);
  if (!context) {
    throw new Error('useHouseholdContext 必须在 HouseholdProvider 内使用');
  }
  return context;
}

export function useOptionalHouseholdContext() {
  return useContext(HouseholdContext);
}
