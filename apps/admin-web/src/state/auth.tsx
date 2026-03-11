import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { ApiError, api } from "../lib/api";
import type { AuthActor } from "../types";

type AuthContextValue = {
  actor: AuthActor | null;
  authLoading: boolean;
  loginPending: boolean;
  loginError: string;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [actor, setActor] = useState<AuthActor | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginPending, setLoginPending] = useState(false);
  const [loginError, setLoginError] = useState("");

  async function refreshAuth() {
    try {
      const response = await api.getAuthMe();
      setActor(response.actor);
      setLoginError("");
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
    setLoginError("");
    try {
      const response = await api.login({ username, password });
      setActor(response.actor);
    } catch (error) {
      if (error instanceof Error) {
        setLoginError(error.message);
      } else {
        setLoginError("登录失败");
      }
      throw error;
    } finally {
      setLoginPending(false);
    }
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      setActor(null);
      setLoginError("");
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

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
