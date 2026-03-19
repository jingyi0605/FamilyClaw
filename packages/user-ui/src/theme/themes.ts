export type ThemeId = string;

export interface UserAppTheme {
  id: ThemeId;
  label: string;
  description: string;
  emoji: string;
  bgApp: string;
  bgSurface: string;
  bgCard: string;
  bgCardHover: string;
  bgSidebar: string;
  bgInput: string;
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textInverse: string;
  brandPrimary: string;
  brandPrimaryHover: string;
  brandPrimaryLight: string;
  brandSecondary: string;
  success: string;
  successLight: string;
  warning: string;
  warningLight: string;
  danger: string;
  dangerLight: string;
  info: string;
  infoLight: string;
  border: string;
  borderLight: string;
  divider: string;
  shadowSm: string;
  shadowMd: string;
  shadowLg: string;
  radiusSm: string;
  radiusMd: string;
  radiusLg: string;
  radiusXl: string;
  fontSizeXs: string;
  fontSizeSm: string;
  fontSizeMd: string;
  fontSizeLg: string;
  fontSizeXl: string;
  fontSizeXxl: string;
  fontSizeHero: string;
  spacingXs: string;
  spacingSm: string;
  spacingMd: string;
  spacingLg: string;
  spacingXl: string;
  spacingXxl: string;
  navWidth: string;
  navBg: string;
  navText: string;
  navTextActive: string;
  navItemHover: string;
  navItemActive: string;
  transition: string;
  glowColor: string;
  gradientPrimary: string;
  gradientCard: string;
  animationSpeed: string;
}

export type PluginThemeResourcePayload = {
  plugin_id?: string;
  theme_id: string;
  display_name?: string | null;
  description?: string | null;
  preview?: Record<string, unknown> | null;
  tokens: Record<string, unknown>;
};

export const userAppThemeFoundation = {
  radiusSm: '6px',
  radiusMd: '10px',
  radiusLg: '14px',
  radiusXl: '20px',
  fontSizeXs: '12px',
  fontSizeSm: '13px',
  fontSizeMd: '15px',
  fontSizeLg: '18px',
  fontSizeXl: '22px',
  fontSizeXxl: '28px',
  fontSizeHero: '36px',
  spacingXs: '4px',
  spacingSm: '8px',
  spacingMd: '16px',
  spacingLg: '24px',
  spacingXl: '32px',
  spacingXxl: '48px',
  navWidth: '240px',
  transition: '0.2s ease',
  animationSpeed: '0.3s',
} as const;

const RUNTIME_THEME_PLACEHOLDER_ID = '__runtime-theme-placeholder__';

const runtimePlaceholderTheme: UserAppTheme = {
  ...userAppThemeFoundation,
  id: RUNTIME_THEME_PLACEHOLDER_ID,
  label: 'Theme placeholder',
  description: 'Waiting for theme plugin resource',
  emoji: 'T',
  bgApp: '',
  bgSurface: '',
  bgCard: '',
  bgCardHover: '',
  bgSidebar: '',
  bgInput: '',
  textPrimary: '',
  textSecondary: '',
  textTertiary: '',
  textInverse: '',
  brandPrimary: '',
  brandPrimaryHover: '',
  brandPrimaryLight: '',
  brandSecondary: '',
  success: '',
  successLight: '',
  warning: '',
  warningLight: '',
  danger: '',
  dangerLight: '',
  info: '',
  infoLight: '',
  border: '',
  borderLight: '',
  divider: '',
  shadowSm: '',
  shadowMd: '',
  shadowLg: '',
  navBg: '',
  navText: '',
  navTextActive: '',
  navItemHover: '',
  navItemActive: '',
  glowColor: '',
  gradientPrimary: '',
  gradientCard: '',
};

function pickToken(tokens: Record<string, unknown>, key: keyof UserAppTheme, fallback: string): string {
  const value = tokens[key];
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

export function normalizePluginThemeTokens(payload: PluginThemeResourcePayload): UserAppTheme {
  const tokens = payload.tokens ?? {};
  const previewEmoji =
    payload.preview && typeof payload.preview.emoji === 'string' && payload.preview.emoji.trim()
      ? payload.preview.emoji.trim()
      : runtimePlaceholderTheme.emoji;

  return {
    ...runtimePlaceholderTheme,
    id: payload.theme_id.trim() || runtimePlaceholderTheme.id,
    label: (payload.display_name ?? '').trim() || payload.theme_id.trim() || runtimePlaceholderTheme.label,
    description: (payload.description ?? '').trim() || runtimePlaceholderTheme.description,
    emoji: previewEmoji,
    bgApp: pickToken(tokens, 'bgApp', runtimePlaceholderTheme.bgApp),
    bgSurface: pickToken(tokens, 'bgSurface', runtimePlaceholderTheme.bgSurface),
    bgCard: pickToken(tokens, 'bgCard', runtimePlaceholderTheme.bgCard),
    bgCardHover: pickToken(tokens, 'bgCardHover', runtimePlaceholderTheme.bgCardHover),
    bgSidebar: pickToken(tokens, 'bgSidebar', runtimePlaceholderTheme.bgSidebar),
    bgInput: pickToken(tokens, 'bgInput', runtimePlaceholderTheme.bgInput),
    textPrimary: pickToken(tokens, 'textPrimary', runtimePlaceholderTheme.textPrimary),
    textSecondary: pickToken(tokens, 'textSecondary', runtimePlaceholderTheme.textSecondary),
    textTertiary: pickToken(tokens, 'textTertiary', runtimePlaceholderTheme.textTertiary),
    textInverse: pickToken(tokens, 'textInverse', runtimePlaceholderTheme.textInverse),
    brandPrimary: pickToken(tokens, 'brandPrimary', runtimePlaceholderTheme.brandPrimary),
    brandPrimaryHover: pickToken(tokens, 'brandPrimaryHover', runtimePlaceholderTheme.brandPrimaryHover),
    brandPrimaryLight: pickToken(tokens, 'brandPrimaryLight', runtimePlaceholderTheme.brandPrimaryLight),
    brandSecondary: pickToken(tokens, 'brandSecondary', runtimePlaceholderTheme.brandSecondary),
    success: pickToken(tokens, 'success', runtimePlaceholderTheme.success),
    successLight: pickToken(tokens, 'successLight', runtimePlaceholderTheme.successLight),
    warning: pickToken(tokens, 'warning', runtimePlaceholderTheme.warning),
    warningLight: pickToken(tokens, 'warningLight', runtimePlaceholderTheme.warningLight),
    danger: pickToken(tokens, 'danger', runtimePlaceholderTheme.danger),
    dangerLight: pickToken(tokens, 'dangerLight', runtimePlaceholderTheme.dangerLight),
    info: pickToken(tokens, 'info', runtimePlaceholderTheme.info),
    infoLight: pickToken(tokens, 'infoLight', runtimePlaceholderTheme.infoLight),
    border: pickToken(tokens, 'border', runtimePlaceholderTheme.border),
    borderLight: pickToken(tokens, 'borderLight', runtimePlaceholderTheme.borderLight),
    divider: pickToken(tokens, 'divider', runtimePlaceholderTheme.divider),
    shadowSm: pickToken(tokens, 'shadowSm', runtimePlaceholderTheme.shadowSm),
    shadowMd: pickToken(tokens, 'shadowMd', runtimePlaceholderTheme.shadowMd),
    shadowLg: pickToken(tokens, 'shadowLg', runtimePlaceholderTheme.shadowLg),
    radiusSm: pickToken(tokens, 'radiusSm', runtimePlaceholderTheme.radiusSm),
    radiusMd: pickToken(tokens, 'radiusMd', runtimePlaceholderTheme.radiusMd),
    radiusLg: pickToken(tokens, 'radiusLg', runtimePlaceholderTheme.radiusLg),
    radiusXl: pickToken(tokens, 'radiusXl', runtimePlaceholderTheme.radiusXl),
    fontSizeXs: pickToken(tokens, 'fontSizeXs', runtimePlaceholderTheme.fontSizeXs),
    fontSizeSm: pickToken(tokens, 'fontSizeSm', runtimePlaceholderTheme.fontSizeSm),
    fontSizeMd: pickToken(tokens, 'fontSizeMd', runtimePlaceholderTheme.fontSizeMd),
    fontSizeLg: pickToken(tokens, 'fontSizeLg', runtimePlaceholderTheme.fontSizeLg),
    fontSizeXl: pickToken(tokens, 'fontSizeXl', runtimePlaceholderTheme.fontSizeXl),
    fontSizeXxl: pickToken(tokens, 'fontSizeXxl', runtimePlaceholderTheme.fontSizeXxl),
    fontSizeHero: pickToken(tokens, 'fontSizeHero', runtimePlaceholderTheme.fontSizeHero),
    spacingXs: pickToken(tokens, 'spacingXs', runtimePlaceholderTheme.spacingXs),
    spacingSm: pickToken(tokens, 'spacingSm', runtimePlaceholderTheme.spacingSm),
    spacingMd: pickToken(tokens, 'spacingMd', runtimePlaceholderTheme.spacingMd),
    spacingLg: pickToken(tokens, 'spacingLg', runtimePlaceholderTheme.spacingLg),
    spacingXl: pickToken(tokens, 'spacingXl', runtimePlaceholderTheme.spacingXl),
    spacingXxl: pickToken(tokens, 'spacingXxl', runtimePlaceholderTheme.spacingXxl),
    navWidth: pickToken(tokens, 'navWidth', runtimePlaceholderTheme.navWidth),
    navBg: pickToken(tokens, 'navBg', runtimePlaceholderTheme.navBg),
    navText: pickToken(tokens, 'navText', runtimePlaceholderTheme.navText),
    navTextActive: pickToken(tokens, 'navTextActive', runtimePlaceholderTheme.navTextActive),
    navItemHover: pickToken(tokens, 'navItemHover', runtimePlaceholderTheme.navItemHover),
    navItemActive: pickToken(tokens, 'navItemActive', runtimePlaceholderTheme.navItemActive),
    transition: pickToken(tokens, 'transition', runtimePlaceholderTheme.transition),
    glowColor: pickToken(tokens, 'glowColor', runtimePlaceholderTheme.glowColor),
    gradientPrimary: pickToken(tokens, 'gradientPrimary', runtimePlaceholderTheme.gradientPrimary),
    gradientCard: pickToken(tokens, 'gradientCard', runtimePlaceholderTheme.gradientCard),
    animationSpeed: pickToken(tokens, 'animationSpeed', runtimePlaceholderTheme.animationSpeed),
  };
}

const runtimeThemeMap: Record<ThemeId, UserAppTheme> = {};
export const userAppThemes: Record<ThemeId, UserAppTheme> = runtimeThemeMap;
export const userAppThemeList: UserAppTheme[] = [];

function syncThemeList() {
  userAppThemeList.splice(0, userAppThemeList.length, ...Object.values(runtimeThemeMap));
}

export function registerRuntimeTheme(theme: UserAppTheme): void {
  runtimeThemeMap[theme.id] = theme;
  syncThemeList();
}

export function resolveRuntimeTheme(themeId: string | null | undefined): UserAppTheme | null {
  const normalized = (themeId ?? '').trim();
  if (!normalized) {
    return null;
  }
  return runtimeThemeMap[normalized] ?? null;
}

export function upsertRuntimeThemeFromPluginResource(payload: PluginThemeResourcePayload): UserAppTheme {
  const normalized = normalizePluginThemeTokens(payload);
  registerRuntimeTheme(normalized);
  return normalized;
}

export function replaceRuntimeThemes(themes: UserAppTheme[]): void {
  for (const key of Object.keys(runtimeThemeMap)) {
    delete runtimeThemeMap[key];
  }
  for (const theme of themes) {
    runtimeThemeMap[theme.id] = theme;
  }
  syncThemeList();
}

export function clearRuntimeThemes(): void {
  replaceRuntimeThemes([]);
}

export function getRuntimeThemePlaceholder(): UserAppTheme {
  return runtimePlaceholderTheme;
}

export function getThemeCssVariables(theme: UserAppTheme) {
  return {
    '--bg-app': theme.bgApp,
    '--bg-surface': theme.bgSurface,
    '--bg-card': theme.bgCard,
    '--bg-card-hover': theme.bgCardHover,
    '--bg-sidebar': theme.bgSidebar,
    '--bg-input': theme.bgInput,
    '--bg-tertiary': theme.bgInput,
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
    '--border-default': theme.border,
    '--border-light': theme.borderLight,
    '--divider': theme.divider,
    '--shadow-sm': theme.shadowSm,
    '--shadow-md': theme.shadowMd,
    '--shadow-lg': theme.shadowLg,
    '--radius-sm': theme.radiusSm,
    '--radius-md': theme.radiusMd,
    '--radius-lg': theme.radiusLg,
    '--radius-xl': theme.radiusXl,
    '--radius-full': '999px',
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
  } as const;
}
