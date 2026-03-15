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
import { themeList, themes, type ThemeTokens } from './tokens';

type ThemeId = SharedThemeId;

type ThemeContextValue = {
  theme: ThemeTokens;
  themeId: ThemeId;
  themeList: ThemeTokens[];
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

function applyCssVariables(theme: ThemeTokens) {
  if (typeof document === 'undefined') {
    return;
  }

  const root = document.documentElement;
  const variables: Record<string, string> = {
    '--bg-app': theme.bgApp,
    '--bg-surface': theme.bgSurface,
    '--bg-card': theme.bgCard,
    '--bg-card-hover': theme.bgCardHover,
    '--bg-sidebar': theme.bgSidebar,
    '--bg-input': theme.bgInput,
    '--text-primary': theme.textPrimary,
    '--text-secondary': theme.textSecondary,
    '--text-tertiary': theme.textTertiary,
    '--text-inverse': theme.textInverse,
    '--brand-primary': theme.brandPrimary,
    '--brand-primary-hover': theme.brandPrimaryHover,
    '--brand-primary-light': theme.brandPrimaryLight,
    '--brand-secondary': theme.brandSecondary,
    '--color-success': theme.success,
    '--color-success-light': theme.successLight,
    '--color-warning': theme.warning,
    '--color-warning-light': theme.warningLight,
    '--color-danger': theme.danger,
    '--color-danger-light': theme.dangerLight,
    '--color-info': theme.info,
    '--color-info-light': theme.infoLight,
    '--border': theme.border,
    '--border-light': theme.borderLight,
    '--divider': theme.divider,
    '--shadow-sm': theme.shadowSm,
    '--shadow-md': theme.shadowMd,
    '--shadow-lg': theme.shadowLg,
    '--radius-sm': theme.radiusSm,
    '--radius-md': theme.radiusMd,
    '--radius-lg': theme.radiusLg,
    '--radius-xl': theme.radiusXl,
    '--font-size-xs': theme.fontSizeXs,
    '--font-size-sm': theme.fontSizeSm,
    '--font-size-md': theme.fontSizeMd,
    '--font-size-lg': theme.fontSizeLg,
    '--font-size-xl': theme.fontSizeXl,
    '--font-size-xxl': theme.fontSizeXxl,
    '--font-size-hero': theme.fontSizeHero,
    '--spacing-xs': theme.spacingXs,
    '--spacing-sm': theme.spacingSm,
    '--spacing-md': theme.spacingMd,
    '--spacing-lg': theme.spacingLg,
    '--spacing-xl': theme.spacingXl,
    '--spacing-xxl': theme.spacingXxl,
    '--nav-width': theme.navWidth,
    '--nav-bg': theme.navBg,
    '--nav-text': theme.navText,
    '--nav-text-active': theme.navTextActive,
    '--nav-item-hover': theme.navItemHover,
    '--nav-item-active': theme.navItemActive,
    '--transition': theme.transition,
    '--glow-color': theme.glowColor,
    '--gradient-primary': theme.gradientPrimary,
    '--gradient-card': theme.gradientCard,
    '--animation-speed': theme.animationSpeed,
  };

  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  root.setAttribute('data-theme', theme.id);
}

export function ThemeProvider(props: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<ThemeId>(getStoredThemeId);
  const theme = themes[themeId] ?? themes[DEFAULT_THEME_ID];

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
      themeList,
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
