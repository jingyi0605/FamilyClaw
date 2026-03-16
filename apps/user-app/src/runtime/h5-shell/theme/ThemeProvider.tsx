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
  userAppThemeList,
  userAppThemes,
} from '@familyclaw/user-ui';
import { applyThemeDocument } from './applyThemeDocument';

type ThemeId = SharedThemeId;
type UserAppTheme = (typeof userAppThemeList)[number];

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

export function ThemeProvider(props: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<ThemeId>(getStoredThemeId);
  const theme = userAppThemes[themeId] ?? userAppThemes[DEFAULT_THEME_ID];

  useEffect(() => {
    applyThemeDocument(theme);
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
