import { PropsWithChildren, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  BootstrapSnapshot,
  clearClientOnlyStorage,
  persistHouseholdId,
} from '@familyclaw/user-core';
import { coreApiClient, loadUserAppBootstrap, taroStorage } from './client';

type AppRuntimeContextValue = {
  bootstrap: BootstrapSnapshot | null;
  error: string;
  loading: boolean;
  refreshing: boolean;
  login: (username: string, password: string) => Promise<BootstrapSnapshot | null>;
  logout: () => Promise<void>;
  refresh: () => Promise<BootstrapSnapshot | null>;
  switchHousehold: (householdId: string) => Promise<BootstrapSnapshot | null>;
};

const AppRuntimeContext = createContext<AppRuntimeContextValue | null>(null);

function toErrorMessage(error: unknown, fallbackMessage: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallbackMessage;
}

export function AppRuntimeProvider({ children }: PropsWithChildren) {
  const [bootstrap, setBootstrap] = useState<BootstrapSnapshot | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    const firstLoad = bootstrap === null && loading;
    if (!firstLoad) {
      setRefreshing(true);
    }

    setError('');

    try {
      const nextBootstrap = await loadUserAppBootstrap();
      setBootstrap(nextBootstrap);
      return nextBootstrap;
    } catch (refreshError) {
      setError(toErrorMessage(refreshError, '应用启动信息加载失败'));
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [bootstrap, loading]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    await coreApiClient.login({
      username,
      password,
    });

    const nextBootstrap = await refresh();
    if (!nextBootstrap) {
      throw new Error('登录成功，但启动摘要刷新失败，请重试');
    }

    return nextBootstrap;
  }, [refresh]);

  const logout = useCallback(async () => {
    try {
      await coreApiClient.logout();
    } catch {
      // 退出登录时即使后端会话已失效，也继续清理本地上下文。
    }

    await Promise.all([
      clearClientOnlyStorage(taroStorage),
      persistHouseholdId(taroStorage, ''),
    ]);

    await refresh();
  }, [refresh]);

  const switchHousehold = useCallback(async (householdId: string) => {
    await persistHouseholdId(taroStorage, householdId);
    return refresh();
  }, [refresh]);

  const value = useMemo<AppRuntimeContextValue>(() => ({
    bootstrap,
    error,
    loading,
    refreshing,
    login,
    logout,
    refresh,
    switchHousehold,
  }), [bootstrap, error, loading, refreshing, login, logout, refresh, switchHousehold]);

  return (
    <AppRuntimeContext.Provider value={value}>
      {children}
    </AppRuntimeContext.Provider>
  );
}

export function useAppRuntime() {
  const context = useContext(AppRuntimeContext);
  if (!context) {
    throw new Error('useAppRuntime 必须在 AppRuntimeProvider 内使用');
  }

  return context;
}
