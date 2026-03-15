import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { loadSetupStatus, type HouseholdSetupStatus } from '@familyclaw/user-core';
import { coreApiClient } from './core';
import { useHouseholdContext } from './household';

type SetupContextValue = {
  setupStatus: HouseholdSetupStatus | null;
  setupStatusLoading: boolean;
  setupStatusError: string;
  refreshSetupStatus: (householdId?: string) => Promise<HouseholdSetupStatus | null>;
};

const SetupContext = createContext<SetupContextValue | null>(null);

export function SetupProvider(props: { children: ReactNode }) {
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
      const result = await loadSetupStatus(coreApiClient, householdId);
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
        const result = await loadSetupStatus(coreApiClient, currentHouseholdId);
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

  const value = useMemo<SetupContextValue>(() => ({
    setupStatus,
    setupStatusLoading,
    setupStatusError,
    refreshSetupStatus,
  }), [refreshSetupStatus, setupStatus, setupStatusError, setupStatusLoading]);

  return <SetupContext.Provider value={value}>{props.children}</SetupContext.Provider>;
}

export function useSetupContext() {
  const context = useContext(SetupContext);
  if (!context) {
    throw new Error('useSetupContext 必须在 SetupProvider 内使用');
  }
  return context;
}

export function useOptionalSetupContext() {
  return useContext(SetupContext);
}
