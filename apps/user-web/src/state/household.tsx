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
import {
  HOUSEHOLD_STORAGE_KEY,
  toHouseholdSummary,
  type HouseholdSummary,
} from './compat';

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

function getStoredHousehold(): string {
  try {
    return localStorage.getItem(HOUSEHOLD_STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
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
        localStorage.removeItem(HOUSEHOLD_STORAGE_KEY);
      } catch {
        /* noop */
      }
      setCurrentHousehold(null);
      return;
    }

    try {
      localStorage.setItem(HOUSEHOLD_STORAGE_KEY, id);
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
        setId('');
        try {
          localStorage.removeItem(HOUSEHOLD_STORAGE_KEY);
        } catch {
          /* noop */
        }
        return;
      }

      // 使用函数式更新获取最新的 currentHouseholdId
      setId((prevId) => {
        const hasCurrent = prevId && nextHouseholds.some(h => h.id === prevId);
        if (!hasCurrent && nextHouseholds.length > 0) {
          const newId = nextHouseholds[0].id;
          try {
            localStorage.setItem(HOUSEHOLD_STORAGE_KEY, newId);
          } catch {
            /* noop */
          }
          return newId;
        }
        return prevId;
      });
    } catch (error) {
      setHouseholds([]);
      setCurrentHousehold(null);
      setHouseholdsError(error instanceof Error ? error.message : '加载家庭列表失败');
    } finally {
      setHouseholdsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setCurrentHouseholdId]);

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
