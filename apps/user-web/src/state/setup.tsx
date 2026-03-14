/* ============================================================
 * 初始化状态上下文 - 管理当前家庭的 setup status 读模型
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
import type { HouseholdSetupStatus } from '../lib/types';
import { useHouseholdContext } from './household';
import { loadHouseholdSetupStatus } from './compat';

interface SetupContextValue {
  setupStatus: HouseholdSetupStatus | null;
  setupStatusLoading: boolean;
  setupStatusError: string;
  refreshSetupStatus: (householdId?: string) => Promise<HouseholdSetupStatus | null>;
}

const SetupContext = createContext<SetupContextValue | null>(null);

export function SetupProvider({ children }: { children: ReactNode }) {
  const { currentHouseholdId } = useHouseholdContext();
  const [setupStatus, setSetupStatus] = useState<HouseholdSetupStatus | null>(null);
  const [setupStatusLoading, setSetupStatusLoading] = useState(false);
  const [setupStatusError, setSetupStatusError] = useState('');

  const refreshSetupStatus = useCallback(async (householdId = currentHouseholdId) => {
    if (!householdId) {
      setSetupStatus(null);
      setSetupStatusError('');
      return null;
    }

    setSetupStatusLoading(true);
    setSetupStatusError('');

    try {
      const result = await loadHouseholdSetupStatus(api, householdId);
      setSetupStatus(result);
      return result;
    } catch (error) {
      setSetupStatus(null);
      setSetupStatusError(error instanceof Error ? error.message : '加载初始化状态失败');
      return null;
    } finally {
      setSetupStatusLoading(false);
    }
  }, [currentHouseholdId]);

  useEffect(() => {
    let cancelled = false;

    if (!currentHouseholdId) {
      setSetupStatus(null);
      setSetupStatusError('');
      return () => {
        cancelled = true;
      };
    }

    const loadCurrentSetupStatus = async () => {
      setSetupStatusLoading(true);
      setSetupStatusError('');

      try {
        const result = await loadHouseholdSetupStatus(api, currentHouseholdId);
        if (!cancelled) {
          setSetupStatus(result);
        }
      } catch (error) {
        if (!cancelled) {
          setSetupStatus(null);
          setSetupStatusError(error instanceof Error ? error.message : '加载初始化状态失败');
        }
      } finally {
        if (!cancelled) {
          setSetupStatusLoading(false);
        }
      }
    };

    void loadCurrentSetupStatus();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  const value = useMemo<SetupContextValue>(
    () => ({
      setupStatus,
      setupStatusLoading,
      setupStatusError,
      refreshSetupStatus,
    }),
    [refreshSetupStatus, setupStatus, setupStatusError, setupStatusLoading],
  );

  return <SetupContext.Provider value={value}>{children}</SetupContext.Provider>;
}

export function useSetupContext(): SetupContextValue {
  const context = useContext(SetupContext);
  if (!context) {
    throw new Error('useSetupContext 必须在 SetupProvider 内使用');
  }
  return context;
}
