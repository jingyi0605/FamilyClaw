import { userAppThemeList } from './themes';

const isH5 = typeof process !== 'undefined' && process.env.TARO_ENV === 'h5';
const fallbackTheme = userAppThemeList[0];

function themeVar(cssVarName: string, fallbackValue: string) {
  return isH5 ? `var(${cssVarName})` : fallbackValue;
}

export const userAppFoundationTokens = {
  radius: {
    sm: themeVar('--radius-sm', fallbackTheme.radiusSm),
    md: themeVar('--radius-md', fallbackTheme.radiusMd),
    lg: themeVar('--radius-lg', fallbackTheme.radiusLg),
    xl: themeVar('--radius-xl', fallbackTheme.radiusXl),
    full: themeVar('--radius-full', '999px'),
  },
  fontSize: {
    xs: themeVar('--font-size-xs', fallbackTheme.fontSizeXs),
    sm: themeVar('--font-size-sm', fallbackTheme.fontSizeSm),
    md: themeVar('--font-size-md', fallbackTheme.fontSizeMd),
    lg: themeVar('--font-size-lg', fallbackTheme.fontSizeLg),
    xl: themeVar('--font-size-xl', fallbackTheme.fontSizeXl),
    xxl: themeVar('--font-size-xxl', fallbackTheme.fontSizeXxl),
    hero: themeVar('--font-size-hero', fallbackTheme.fontSizeHero),
  },
  spacing: {
    xs: themeVar('--spacing-xs', fallbackTheme.spacingXs),
    sm: themeVar('--spacing-sm', fallbackTheme.spacingSm),
    md: themeVar('--spacing-md', fallbackTheme.spacingMd),
    lg: themeVar('--spacing-lg', fallbackTheme.spacingLg),
    xl: themeVar('--spacing-xl', fallbackTheme.spacingXl),
    xxl: themeVar('--spacing-xxl', fallbackTheme.spacingXxl),
  },
  shadow: {
    sm: themeVar('--shadow-sm', fallbackTheme.shadowSm),
    md: themeVar('--shadow-md', fallbackTheme.shadowMd),
    lg: themeVar('--shadow-lg', fallbackTheme.shadowLg),
  },
  motion: {
    transition: themeVar('--transition', fallbackTheme.transition),
    animationSpeed: themeVar('--animation-speed', fallbackTheme.animationSpeed),
  },
  layout: {
    navWidth: themeVar('--nav-width', fallbackTheme.navWidth),
  },
} as const;

export const userAppSemanticTokens = {
  surface: {
    page: themeVar('--bg-app', fallbackTheme.bgApp),
    shell: themeVar('--bg-surface', fallbackTheme.bgSurface),
    card: themeVar('--bg-card', fallbackTheme.bgCard),
    cardHover: themeVar('--bg-card-hover', fallbackTheme.bgCardHover),
    sidebar: themeVar('--bg-sidebar', fallbackTheme.bgSidebar),
    muted: themeVar('--bg-input', fallbackTheme.bgInput),
  },
  text: {
    primary: themeVar('--text-primary', fallbackTheme.textPrimary),
    secondary: themeVar('--text-secondary', fallbackTheme.textSecondary),
    tertiary: themeVar('--text-tertiary', fallbackTheme.textTertiary),
    inverse: themeVar('--text-inverse', fallbackTheme.textInverse),
  },
  border: {
    default: themeVar('--border-default', fallbackTheme.border),
    subtle: themeVar('--border-light', fallbackTheme.borderLight),
    divider: themeVar('--divider', fallbackTheme.divider),
  },
  action: {
    primary: themeVar('--brand-primary', fallbackTheme.brandPrimary),
    primaryHover: themeVar('--brand-primary-hover', fallbackTheme.brandPrimaryHover),
    primaryLight: themeVar('--brand-primary-light', fallbackTheme.brandPrimaryLight),
    secondary: themeVar('--brand-secondary', fallbackTheme.brandSecondary),
  },
  state: {
    success: themeVar('--color-success', fallbackTheme.success),
    successLight: themeVar('--color-success-light', fallbackTheme.successLight),
    warning: themeVar('--color-warning', fallbackTheme.warning),
    warningLight: themeVar('--color-warning-light', fallbackTheme.warningLight),
    danger: themeVar('--color-danger', fallbackTheme.danger),
    dangerLight: themeVar('--color-danger-light', fallbackTheme.dangerLight),
    info: themeVar('--color-info', fallbackTheme.info),
    infoLight: themeVar('--color-info-light', fallbackTheme.infoLight),
  },
  nav: {
    background: themeVar('--nav-bg', fallbackTheme.navBg),
    text: themeVar('--nav-text', fallbackTheme.navText),
    textActive: themeVar('--nav-text-active', fallbackTheme.navTextActive),
    itemHover: themeVar('--nav-item-hover', fallbackTheme.navItemHover),
    itemActive: themeVar('--nav-item-active', fallbackTheme.navItemActive),
  },
  gradient: {
    primary: themeVar('--gradient-primary', fallbackTheme.gradientPrimary),
    card: themeVar('--gradient-card', fallbackTheme.gradientCard),
    glow: themeVar('--glow-color', fallbackTheme.glowColor),
  },
  shadow: userAppFoundationTokens.shadow,
} as const;

export const userAppComponentTokens = {
  pageSection: {
    background: userAppSemanticTokens.surface.card,
    borderColor: userAppSemanticTokens.border.subtle,
    radius: userAppFoundationTokens.radius.lg,
    marginBottom: userAppFoundationTokens.spacing.sm,
    padding: userAppFoundationTokens.spacing.md,
    titleColor: userAppSemanticTokens.text.primary,
    titleFontSize: userAppFoundationTokens.fontSize.xl,
    descriptionColor: userAppSemanticTokens.text.secondary,
    descriptionFontSize: userAppFoundationTokens.fontSize.md,
    descriptionMarginTop: userAppFoundationTokens.spacing.xs,
    contentMarginTop: userAppFoundationTokens.spacing.sm,
  },
  statusCard: {
    background: userAppSemanticTokens.surface.muted,
    borderColor: userAppSemanticTokens.border.subtle,
    radius: userAppFoundationTokens.radius.md,
    marginBottom: userAppFoundationTokens.spacing.xs,
    padding: userAppFoundationTokens.spacing.sm,
    labelColor: userAppSemanticTokens.text.secondary,
    labelFontSize: userAppFoundationTokens.fontSize.sm,
    valueFontSize: userAppFoundationTokens.fontSize.lg,
    valueMarginTop: userAppFoundationTokens.spacing.xs,
  },
} as const;

// 兼容旧入口，避免第一轮收口时把现有页面全部打碎。
export const userAppTokens = {
  colorBg: userAppSemanticTokens.surface.page,
  colorSurface: userAppSemanticTokens.surface.card,
  colorSurfaceMuted: userAppSemanticTokens.surface.muted,
  colorBorder: userAppSemanticTokens.border.subtle,
  colorText: userAppSemanticTokens.text.primary,
  colorMuted: userAppSemanticTokens.text.secondary,
  colorPrimary: userAppSemanticTokens.action.primary,
  colorPrimaryHover: userAppSemanticTokens.action.primaryHover,
  colorPrimaryLight: userAppSemanticTokens.action.primaryLight,
  colorSuccess: userAppSemanticTokens.state.success,
  colorWarning: userAppSemanticTokens.state.warning,
  colorDanger: userAppSemanticTokens.state.danger,
  colorInfo: userAppSemanticTokens.state.info,
  spacingXs: userAppFoundationTokens.spacing.xs,
  spacingSm: userAppFoundationTokens.spacing.sm,
  spacingMd: userAppFoundationTokens.spacing.md,
  spacingLg: userAppFoundationTokens.spacing.lg,
  spacingXl: userAppFoundationTokens.spacing.xl,
  spacingXxl: userAppFoundationTokens.spacing.xxl,
  radiusSm: userAppFoundationTokens.radius.sm,
  radiusMd: userAppFoundationTokens.radius.md,
  radiusLg: userAppFoundationTokens.radius.lg,
  radiusXl: userAppFoundationTokens.radius.xl,
  fontSizeXs: userAppFoundationTokens.fontSize.xs,
  fontSizeSm: userAppFoundationTokens.fontSize.sm,
  fontSizeMd: userAppFoundationTokens.fontSize.md,
  fontSizeLg: userAppFoundationTokens.fontSize.lg,
  fontSizeXl: userAppFoundationTokens.fontSize.xl,
  fontSizeXxl: userAppFoundationTokens.fontSize.xxl,
  fontSizeHero: userAppFoundationTokens.fontSize.hero,
  shadowSm: userAppFoundationTokens.shadow.sm,
  shadowMd: userAppFoundationTokens.shadow.md,
  shadowLg: userAppFoundationTokens.shadow.lg,
} as const;
