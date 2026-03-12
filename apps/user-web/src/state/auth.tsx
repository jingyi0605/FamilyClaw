import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, api } from '../lib/api';
import type { AuthActor } from '../lib/types';

const CLIENT_ONLY_STORAGE_PREFIXES = [
  'familyclaw-conversation-sessions',
  'familyclaw-assistant-sessions',
];

interface AuthContextValue {
  actor: AuthActor | null;
  authLoading: boolean;
  loginPending: boolean;
  loginError: string;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [actor, setActor] = useState<AuthActor | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginPending, setLoginPending] = useState(false);
  const [loginError, setLoginError] = useState('');

  async function refreshAuth() {
    try {
      const response = await api.getAuthMe();
      setActor(response.actor);
      setLoginError('');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setActor(null);
        return;
      }
      if (error instanceof Error) {
        setLoginError(error.message);
      }
      throw error;
    } finally {
      setAuthLoading(false);
    }
  }

  async function login(username: string, password: string) {
    setLoginPending(true);
    setLoginError('');
    try {
      const response = await api.login({ username, password });
      setActor(response.actor);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : '登录失败');
      throw error;
    } finally {
      setLoginPending(false);
    }
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      try {
        const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index)).filter(Boolean) as string[];
        for (const key of keys) {
          if (CLIENT_ONLY_STORAGE_PREFIXES.some(prefix => key.startsWith(prefix))) {
            window.localStorage.removeItem(key);
          }
        }
      } catch {
        // 忽略本地存储清理异常
      }
      setActor(null);
      setLoginError('');
    }
  }

  useEffect(() => {
    refreshAuth().catch(() => {
      setActor(null);
      setAuthLoading(false);
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      actor,
      authLoading,
      loginPending,
      loginError,
      login,
      logout,
      refreshAuth,
    }),
    [actor, authLoading, loginPending, loginError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext 必须在 AuthProvider 内使用');
  }
  return context;
}
