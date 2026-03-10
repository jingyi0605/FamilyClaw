/* ============================================================
 * ThemeProvider - 管理主题切换和 CSS 变量注入
 * ============================================================ */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { themes, type ThemeId, type ThemeTokens } from './tokens';

interface ThemeContextValue {
  theme: ThemeTokens;
  themeId: ThemeId;
  setTheme: (id: ThemeId) => void;
}

const STORAGE_KEY = 'familyclaw-theme';

function getStoredTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored in themes) return stored as ThemeId;
  } catch {
    /* 忽略存储访问失败 */
  }
  return 'chun-he-jing-ming';
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/* 把 theme tokens 注入到 :root 的 CSS 变量 */
function applyCssVariables(t: ThemeTokens) {
  const root = document.documentElement;
  root.style.setProperty('--bg-app', t.bgApp);
  root.style.setProperty('--bg-surface', t.bgSurface);
  root.style.setProperty('--bg-card', t.bgCard);
  root.style.setProperty('--bg-card-hover', t.bgCardHover);
  root.style.setProperty('--bg-sidebar', t.bgSidebar);
  root.style.setProperty('--bg-input', t.bgInput);

  root.style.setProperty('--text-primary', t.textPrimary);
  root.style.setProperty('--text-secondary', t.textSecondary);
  root.style.setProperty('--text-tertiary', t.textTertiary);
  root.style.setProperty('--text-inverse', t.textInverse);

  root.style.setProperty('--brand-primary', t.brandPrimary);
  root.style.setProperty('--brand-primary-hover', t.brandPrimaryHover);
  root.style.setProperty('--brand-primary-light', t.brandPrimaryLight);
  root.style.setProperty('--brand-secondary', t.brandSecondary);

  root.style.setProperty('--color-success', t.success);
  root.style.setProperty('--color-success-light', t.successLight);
  root.style.setProperty('--color-warning', t.warning);
  root.style.setProperty('--color-warning-light', t.warningLight);
  root.style.setProperty('--color-danger', t.danger);
  root.style.setProperty('--color-danger-light', t.dangerLight);
  root.style.setProperty('--color-info', t.info);
  root.style.setProperty('--color-info-light', t.infoLight);

  root.style.setProperty('--border', t.border);
  root.style.setProperty('--border-light', t.borderLight);
  root.style.setProperty('--divider', t.divider);

  root.style.setProperty('--shadow-sm', t.shadowSm);
  root.style.setProperty('--shadow-md', t.shadowMd);
  root.style.setProperty('--shadow-lg', t.shadowLg);

  root.style.setProperty('--radius-sm', t.radiusSm);
  root.style.setProperty('--radius-md', t.radiusMd);
  root.style.setProperty('--radius-lg', t.radiusLg);
  root.style.setProperty('--radius-xl', t.radiusXl);

  root.style.setProperty('--font-size-xs', t.fontSizeXs);
  root.style.setProperty('--font-size-sm', t.fontSizeSm);
  root.style.setProperty('--font-size-md', t.fontSizeMd);
  root.style.setProperty('--font-size-lg', t.fontSizeLg);
  root.style.setProperty('--font-size-xl', t.fontSizeXl);
  root.style.setProperty('--font-size-xxl', t.fontSizeXxl);
  root.style.setProperty('--font-size-hero', t.fontSizeHero);

  root.style.setProperty('--spacing-xs', t.spacingXs);
  root.style.setProperty('--spacing-sm', t.spacingSm);
  root.style.setProperty('--spacing-md', t.spacingMd);
  root.style.setProperty('--spacing-lg', t.spacingLg);
  root.style.setProperty('--spacing-xl', t.spacingXl);
  root.style.setProperty('--spacing-xxl', t.spacingXxl);

  root.style.setProperty('--nav-width', t.navWidth);
  root.style.setProperty('--nav-bg', t.navBg);
  root.style.setProperty('--nav-text', t.navText);
  root.style.setProperty('--nav-text-active', t.navTextActive);
  root.style.setProperty('--nav-item-hover', t.navItemHover);
  root.style.setProperty('--nav-item-active', t.navItemActive);

  root.style.setProperty('--transition', t.transition);

  /* 特效相关 */
  root.style.setProperty('--glow-color', t.glowColor);
  root.style.setProperty('--gradient-primary', t.gradientPrimary);
  root.style.setProperty('--gradient-card', t.gradientCard);
  root.style.setProperty('--animation-speed', t.animationSpeed);

  root.setAttribute('data-theme', t.id);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<ThemeId>(getStoredTheme);
  const theme = themes[themeId];

  useEffect(() => {
    applyCssVariables(theme);
    try { localStorage.setItem(STORAGE_KEY, themeId); } catch { /* noop */ }
  }, [theme, themeId]);

  const setTheme = (id: ThemeId) => setThemeId(id);

  return (
    <ThemeContext.Provider value={{ theme, themeId, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme 必须在 ThemeProvider 内使用');
  return ctx;
}
