/* ============================================================
 * 家庭上下文 - 管理当前选中的家庭和家庭列表
 * ============================================================ */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../lib/api';
import type { Household } from '../lib/types';

export interface HouseholdSummary {
  id: string;
  name: string;
  timezone?: string;
  locale?: string;
  status?: string;
}

interface HouseholdContextValue {
  currentHouseholdId: string;
  currentHousehold: HouseholdSummary | null;
  households: HouseholdSummary[];
  householdsLoading: boolean;
  householdsError: string;
  setCurrentHouseholdId: (id: string) => void;
  refreshHouseholds: () => Promise<void>;
  refreshCurrentHousehold: (householdId?: string) => Promise<void>;
}

const STORAGE_KEY = 'familyclaw-household';

function getStoredHousehold(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

function toHouseholdSummary(household: Household): HouseholdSummary {
  return {
    id: household.id,
    name: household.name,
    timezone: household.timezone,
    locale: household.locale,
    status: household.status,
  };
}

const HouseholdContext = createContext<HouseholdContextValue | null>(null);

export function HouseholdProvider({ children }: { children: ReactNode }) {
  const [currentHouseholdId, setId] = useState(getStoredHousehold);
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [currentHousehold, setCurrentHousehold] = useState<HouseholdSummary | null>(null);
  const [householdsLoading, setHouseholdsLoading] = useState(false);
  const [householdsError, setHouseholdsError] = useState('');

  const setCurrentHouseholdId = useCallback((id: string) => {
    setId(id);
    if (!id) {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* noop */
      }
      setCurrentHousehold(null);
      return;
    }

    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* noop */
    }
  }, []);

  const refreshHouseholds = useCallback(async () => {
    setHouseholdsLoading(true);
    setHouseholdsError('');

    try {
      const response = await api.listHouseholds();
      const nextHouseholds = response.items.map(toHouseholdSummary);
      setHouseholds(nextHouseholds);

      if (nextHouseholds.length === 0) {
        setCurrentHousehold(null);
        if (currentHouseholdId) {
          setCurrentHouseholdId('');
        }
        return;
      }

      const hasCurrent = currentHouseholdId && nextHouseholds.some(h => h.id === currentHouseholdId);
      if (!hasCurrent) {
        setCurrentHouseholdId(nextHouseholds[0].id);
      }
    } catch (error) {
      setHouseholds([]);
      setCurrentHousehold(null);
      setHouseholdsError(error instanceof Error ? error.message : '加载家庭列表失败');
    } finally {
      setHouseholdsLoading(false);
    }
  }, [currentHouseholdId, setCurrentHouseholdId]);

  const refreshCurrentHousehold = useCallback(async (householdId = currentHouseholdId) => {
    if (!householdId) {
      setCurrentHousehold(null);
      return;
    }

    const household = await api.getHousehold(householdId);
    setCurrentHousehold(toHouseholdSummary(household));
  }, [currentHouseholdId]);

  useEffect(() => {
    void refreshHouseholds();
  }, [refreshHouseholds]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setCurrentHousehold(null);
      return;
    }

    void refreshCurrentHousehold().catch(error => {
      setCurrentHousehold(null);
      setHouseholdsError(error instanceof Error ? error.message : '加载当前家庭失败');
    });
  }, [currentHouseholdId, refreshCurrentHousehold]);

  const value = useMemo<HouseholdContextValue>(
    () => ({
      currentHouseholdId,
      currentHousehold,
      households,
      householdsLoading,
      householdsError,
      setCurrentHouseholdId,
      refreshHouseholds,
      refreshCurrentHousehold,
    }),
    [
      currentHouseholdId,
      currentHousehold,
      households,
      householdsLoading,
      householdsError,
      setCurrentHouseholdId,
      refreshHouseholds,
      refreshCurrentHousehold,
    ],
  );

  return (
    <HouseholdContext.Provider value={value}>
      {children}
    </HouseholdContext.Provider>
  );
}

export function useHouseholdContext(): HouseholdContextValue {
  const ctx = useContext(HouseholdContext);
  if (!ctx) throw new Error('useHouseholdContext 必须在 HouseholdProvider 内使用');
  return ctx;
}
