import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  ApiError,
  clearClientOnlyStorage,
  type AuthActor,
  type LoginResponse,
} from '@familyclaw/user-core';
import { coreApiClient, appStorage } from './core';

type AuthContextValue = {
  actor: AuthActor | null;
  authLoading: boolean;
  loginPending: boolean;
  loginError: string;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function requireAuthActor(response: unknown, endpoint: '/auth/me' | '/auth/login'): AuthActor {
  if (!response || typeof response !== 'object') {
    throw new Error(
      `认证接口 ${endpoint} 返回了空响应。请确认 H5 的 /api 代理仍然指向 http://127.0.0.1:8000，且后端返回的是 JSON。`,
    );
  }

  const actor = (response as Partial<LoginResponse>).actor;
  if (!actor || typeof actor !== 'object') {
    throw new Error(
      `认证接口 ${endpoint} 返回体缺少 actor。这个错误不该再表现成 undefined.actor，请检查 /api 代理和后端鉴权响应。`,
    );
  }

  return actor as AuthActor;
}

export function AuthProvider(props: { children: ReactNode }) {
  const [actor, setActor] = useState<AuthActor | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginPending, setLoginPending] = useState(false);
  const [loginError, setLoginError] = useState('');

  async function refreshAuth() {
    try {
      const response = await coreApiClient.getAuthMe();
      const nextActor = requireAuthActor(response, '/auth/me');
      setActor(nextActor);
      setLoginError('');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setActor(null);
        setLoginError('');
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
      const response = await coreApiClient.login({ username, password });
      const nextActor = requireAuthActor(response, '/auth/login');
      setActor(nextActor);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : '登录失败');
      throw error;
    } finally {
      setLoginPending(false);
    }
  }

  async function logout() {
    try {
      await coreApiClient.logout();
    } finally {
      try {
        await clearClientOnlyStorage(appStorage);
      } catch {
        // 本地清理失败不能阻断退出流程。
      }
      setActor(null);
      setLoginError('');
    }
  }

  useEffect(() => {
    void refreshAuth().catch(() => {
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

  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext 必须在 AuthProvider 内使用。');
  }
  return context;
}
