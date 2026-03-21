import { createSharedThemeContract } from './contract';
import { userAppThemeFoundation } from './themes';

const canUseCssVariables = typeof document !== 'undefined';

function themeVar(cssVarName: string, fallbackValue = '') {
  if (canUseCssVariables) {
    return fallbackValue ? `var(${cssVarName}, ${fallbackValue})` : `var(${cssVarName})`;
  }
  return fallbackValue;
}

const sharedThemeContract = createSharedThemeContract({
  bgApp: themeVar('--bg-app'),
  bgSurface: themeVar('--bg-surface'),
  bgCard: themeVar('--bg-card'),
  bgCardHover: themeVar('--bg-card-hover'),
  bgSidebar: themeVar('--bg-sidebar'),
  bgInput: themeVar('--bg-input'),
  textPrimary: themeVar('--text-primary'),
  textSecondary: themeVar('--text-secondary'),
  textTertiary: themeVar('--text-tertiary'),
  textInverse: themeVar('--text-inverse'),
  brandPrimary: themeVar('--brand-primary'),
  brandPrimaryHover: themeVar('--brand-primary-hover'),
  brandPrimaryLight: themeVar('--brand-primary-light'),
  brandSecondary: themeVar('--brand-secondary'),
  success: themeVar('--color-success'),
  successLight: themeVar('--color-success-light'),
  warning: themeVar('--color-warning'),
  warningLight: themeVar('--color-warning-light'),
  danger: themeVar('--color-danger'),
  dangerLight: themeVar('--color-danger-light'),
  info: themeVar('--color-info'),
  infoLight: themeVar('--color-info-light'),
  border: themeVar('--border-default'),
  borderLight: themeVar('--border-light'),
  divider: themeVar('--divider'),
  shadowSm: themeVar('--shadow-sm'),
  shadowMd: themeVar('--shadow-md'),
  shadowLg: themeVar('--shadow-lg'),
  radiusSm: themeVar('--radius-sm'),
  radiusMd: themeVar('--radius-md'),
  radiusLg: themeVar('--radius-lg'),
  radiusXl: themeVar('--radius-xl'),
  fontSizeXs: themeVar('--font-size-xs'),
  fontSizeSm: themeVar('--font-size-sm'),
  fontSizeMd: themeVar('--font-size-md'),
  fontSizeLg: themeVar('--font-size-lg'),
  fontSizeXl: themeVar('--font-size-xl'),
  fontSizeXxl: themeVar('--font-size-xxl'),
  fontSizeHero: themeVar('--font-size-hero'),
  spacingXs: themeVar('--spacing-xs'),
  spacingSm: themeVar('--spacing-sm'),
  spacingMd: themeVar('--spacing-md'),
  spacingLg: themeVar('--spacing-lg'),
  spacingXl: themeVar('--spacing-xl'),
  spacingXxl: themeVar('--spacing-xxl'),
  navWidth: themeVar('--nav-width', userAppThemeFoundation.navWidth),
  navBg: themeVar('--nav-bg'),
  navText: themeVar('--nav-text'),
  navTextActive: themeVar('--nav-text-active'),
  navItemHover: themeVar('--nav-item-hover'),
  navItemActive: themeVar('--nav-item-active'),
  transition: themeVar('--transition', userAppThemeFoundation.transition),
  glowColor: themeVar('--glow-color'),
  gradientPrimary: themeVar('--gradient-primary'),
  gradientCard: themeVar('--gradient-card'),
  animationSpeed: themeVar('--animation-speed', userAppThemeFoundation.animationSpeed),
});

export const userAppFoundationTokens = sharedThemeContract.foundation;
export const userAppSemanticTokens = sharedThemeContract.semantic;
export const userAppComponentTokens = sharedThemeContract.component;
export const userAppPagePatternTokens = sharedThemeContract.patterns;

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
