const TOKEN_TO_CSS_VAR: Record<string, string> = {
  bgApp: '--bg-app',
  bgSurface: '--bg-surface',
  bgCard: '--bg-card',
  bgCardHover: '--bg-card-hover',
  bgSidebar: '--bg-sidebar',
  bgInput: '--bg-input',
  textPrimary: '--text-primary',
  textSecondary: '--text-secondary',
  textTertiary: '--text-tertiary',
  textInverse: '--text-inverse',
  brandPrimary: '--brand-primary',
  brandPrimaryHover: '--brand-primary-hover',
  brandPrimaryLight: '--brand-primary-light',
  brandSecondary: '--brand-secondary',
  success: '--color-success',
  successLight: '--color-success-light',
  warning: '--color-warning',
  warningLight: '--color-warning-light',
  danger: '--color-danger',
  dangerLight: '--color-danger-light',
  info: '--color-info',
  infoLight: '--color-info-light',
  border: '--border',
  borderLight: '--border-light',
  divider: '--divider',
  shadowSm: '--shadow-sm',
  shadowMd: '--shadow-md',
  shadowLg: '--shadow-lg',
  radiusSm: '--radius-sm',
  radiusMd: '--radius-md',
  radiusLg: '--radius-lg',
  radiusXl: '--radius-xl',
  fontSizeXs: '--font-size-xs',
  fontSizeSm: '--font-size-sm',
  fontSizeMd: '--font-size-md',
  fontSizeLg: '--font-size-lg',
  fontSizeXl: '--font-size-xl',
  fontSizeXxl: '--font-size-xxl',
  fontSizeHero: '--font-size-hero',
  spacingXs: '--spacing-xs',
  spacingSm: '--spacing-sm',
  spacingMd: '--spacing-md',
  spacingLg: '--spacing-lg',
  spacingXl: '--spacing-xl',
  spacingXxl: '--spacing-xxl',
  navWidth: '--nav-width',
  navBg: '--nav-bg',
  navText: '--nav-text',
  navTextActive: '--nav-text-active',
  navItemHover: '--nav-item-hover',
  navItemActive: '--nav-item-active',
  transition: '--transition',
  glowColor: '--glow-color',
  gradientPrimary: '--gradient-primary',
  gradientCard: '--gradient-card',
  animationSpeed: '--animation-speed',
};

function mapTokensToCssVariables(tokens: Record<string, string>) {
  const mapped: Record<string, string> = {};
  for (const [key, value] of Object.entries(tokens)) {
    if (!value) {
      continue;
    }
    if (key.startsWith('--')) {
      mapped[key] = value;
      continue;
    }
    const cssVar = TOKEN_TO_CSS_VAR[key];
    if (cssVar) {
      mapped[cssVar] = value;
    }
  }
  if (mapped['--border']) {
    mapped['--border-default'] = mapped['--border'];
  }
  if (mapped['--bg-input']) {
    mapped['--bg-tertiary'] = mapped['--bg-input'];
  }
  if (!mapped['--radius-full']) {
    mapped['--radius-full'] = '999px';
  }
  return mapped;
}

function resolveThemeTokens(theme: Record<string, unknown>) {
  if ('tokens' in theme && theme.tokens && typeof theme.tokens === 'object') {
    return theme.tokens as Record<string, string>;
  }
  const normalized: Record<string, string> = {};
  for (const [key, value] of Object.entries(theme)) {
    if (typeof value === 'string') {
      normalized[key] = value;
    }
  }
  return normalized;
}

export function applyThemeDocument(theme: unknown) {
  if (typeof document === 'undefined') {
    return;
  }
  if (!theme || typeof theme !== 'object') {
    return;
  }

  const root = document.documentElement;
  const payload = theme as Record<string, unknown>;
  const variables = mapTokensToCssVariables(resolveThemeTokens(payload));
  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  const themeId = typeof payload.id === 'string' ? payload.id : 'unknown';
  root.setAttribute('data-theme', themeId);
  if (typeof payload.plugin_id === 'string') {
    root.setAttribute('data-theme-plugin', payload.plugin_id);
  }
}
