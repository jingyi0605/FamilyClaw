/* ============================================================
 * 家庭上下文 - 管理当前选中的家庭和家庭列表
 * ============================================================ */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export interface HouseholdSummary {
  id: string;
  name: string;
}

interface HouseholdContextValue {
  currentHouseholdId: string;
  currentHousehold: HouseholdSummary | null;
  households: HouseholdSummary[];
  setCurrentHouseholdId: (id: string) => void;
}

const STORAGE_KEY = 'familyclaw-household';

/* 演示用模拟数据 */
const MOCK_HOUSEHOLDS: HouseholdSummary[] = [
  { id: 'hh-001', name: '温馨小家' },
  { id: 'hh-002', name: '爷爷奶奶家' },
];

function getStoredHousehold(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? MOCK_HOUSEHOLDS[0].id;
  } catch {
    return MOCK_HOUSEHOLDS[0].id;
  }
}

const HouseholdContext = createContext<HouseholdContextValue | null>(null);

export function HouseholdProvider({ children }: { children: ReactNode }) {
  const [currentHouseholdId, setId] = useState(getStoredHousehold);
  const households = MOCK_HOUSEHOLDS;
  const currentHousehold = households.find(h => h.id === currentHouseholdId) ?? null;

  const setCurrentHouseholdId = useCallback((id: string) => {
    setId(id);
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* noop */ }
  }, []);

  return (
    <HouseholdContext.Provider value={{ currentHouseholdId, currentHousehold, households, setCurrentHouseholdId }}>
      {children}
    </HouseholdContext.Provider>
  );
}

export function useHouseholdContext(): HouseholdContextValue {
  const ctx = useContext(HouseholdContext);
  if (!ctx) throw new Error('useHouseholdContext 必须在 HouseholdProvider 内使用');
  return ctx;
}
