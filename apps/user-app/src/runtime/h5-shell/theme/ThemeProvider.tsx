import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  DEFAULT_THEME_ID,
  THEME_STORAGE_KEY,
  resolveThemeId,
  type ThemeId as SharedThemeId,
} from '@familyclaw/user-core';
import {
  getThemeCssVariables,
  userAppThemeList,
  userAppThemes,
  type UserAppTheme,
} from '@familyclaw/user-ui';

type ThemeId = SharedThemeId;

type ThemeContextValue = {
  theme: UserAppTheme;
  themeId: ThemeId;
  themeList: UserAppTheme[];
  setTheme: (id: ThemeId) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getStoredThemeId(): ThemeId {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME_ID;
  }

  try {
    return resolveThemeId(window.localStorage.getItem(THEME_STORAGE_KEY), DEFAULT_THEME_ID);
  } catch {
    return DEFAULT_THEME_ID;
  }
}

function applyCssVariables(theme: UserAppTheme) {
  if (typeof document === 'undefined') {
    return;
  }

  const root = document.documentElement;
  const variables = getThemeCssVariables(theme);

  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  root.setAttribute('data-theme', theme.id);
}

export function ThemeProvider(props: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<ThemeId>(getStoredThemeId);
  const theme = userAppThemes[themeId] ?? userAppThemes[DEFAULT_THEME_ID];

  useEffect(() => {
    applyCssVariables(theme);
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, themeId);
    } catch {
      // 忽略本地持久化失败，不影响界面切换
    }
  }, [theme, themeId]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      themeId,
      themeList: userAppThemeList,
      setTheme: id => setThemeId(resolveThemeId(id, DEFAULT_THEME_ID)),
    }),
    [theme, themeId],
  );

  return <ThemeContext.Provider value={value}>{props.children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme 必须在 ThemeProvider 内使用');
  }
  return context;
}
