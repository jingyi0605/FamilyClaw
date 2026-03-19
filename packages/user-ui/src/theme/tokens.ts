import { userAppThemeFoundation } from './themes';

const canUseCssVariables = typeof document !== 'undefined';

function themeVar(cssVarName: string, fallbackValue = '') {
  if (canUseCssVariables) {
    return fallbackValue ? `var(${cssVarName}, ${fallbackValue})` : `var(${cssVarName})`;
  }
  return fallbackValue;
}

export const userAppFoundationTokens = {
  radius: {
    sm: themeVar('--radius-sm'),
    md: themeVar('--radius-md'),
    lg: themeVar('--radius-lg'),
    xl: themeVar('--radius-xl'),
    full: themeVar('--radius-full', '999px'),
  },
  fontSize: {
    xs: themeVar('--font-size-xs'),
    sm: themeVar('--font-size-sm'),
    md: themeVar('--font-size-md'),
    lg: themeVar('--font-size-lg'),
    xl: themeVar('--font-size-xl'),
    xxl: themeVar('--font-size-xxl'),
    hero: themeVar('--font-size-hero'),
  },
  spacing: {
    xs: themeVar('--spacing-xs'),
    sm: themeVar('--spacing-sm'),
    md: themeVar('--spacing-md'),
    lg: themeVar('--spacing-lg'),
    xl: themeVar('--spacing-xl'),
    xxl: themeVar('--spacing-xxl'),
  },
  shadow: {
    sm: themeVar('--shadow-sm'),
    md: themeVar('--shadow-md'),
    lg: themeVar('--shadow-lg'),
  },
  motion: {
    transition: themeVar('--transition', userAppThemeFoundation.transition),
    animationSpeed: themeVar('--animation-speed', userAppThemeFoundation.animationSpeed),
  },
  layout: {
    navWidth: themeVar('--nav-width', userAppThemeFoundation.navWidth),
  },
} as const;

export const userAppSemanticTokens = {
  surface: {
    page: themeVar('--bg-app'),
    shell: themeVar('--bg-surface'),
    card: themeVar('--bg-card'),
    cardHover: themeVar('--bg-card-hover'),
    sidebar: themeVar('--bg-sidebar'),
    muted: themeVar('--bg-input'),
  },
  text: {
    primary: themeVar('--text-primary'),
    secondary: themeVar('--text-secondary'),
    tertiary: themeVar('--text-tertiary'),
    inverse: themeVar('--text-inverse'),
  },
  border: {
    default: themeVar('--border-default'),
    subtle: themeVar('--border-light'),
    divider: themeVar('--divider'),
  },
  action: {
    primary: themeVar('--brand-primary'),
    primaryHover: themeVar('--brand-primary-hover'),
    primaryLight: themeVar('--brand-primary-light'),
    secondary: themeVar('--brand-secondary'),
  },
  state: {
    success: themeVar('--color-success'),
    successLight: themeVar('--color-success-light'),
    warning: themeVar('--color-warning'),
    warningLight: themeVar('--color-warning-light'),
    danger: themeVar('--color-danger'),
    dangerLight: themeVar('--color-danger-light'),
    info: themeVar('--color-info'),
    infoLight: themeVar('--color-info-light'),
  },
  nav: {
    background: themeVar('--nav-bg'),
    text: themeVar('--nav-text'),
    textActive: themeVar('--nav-text-active'),
    itemHover: themeVar('--nav-item-hover'),
    itemActive: themeVar('--nav-item-active'),
  },
  gradient: {
    primary: themeVar('--gradient-primary'),
    card: themeVar('--gradient-card'),
    glow: themeVar('--glow-color'),
  },
  shadow: userAppFoundationTokens.shadow,
} as const;

export const userAppComponentTokens = {
  text: {
    body: {
      color: userAppSemanticTokens.text.primary,
      fontSize: userAppFoundationTokens.fontSize.md,
      fontWeight: '400',
      lineHeight: '1.6',
    },
    caption: {
      color: userAppSemanticTokens.text.secondary,
      fontSize: userAppFoundationTokens.fontSize.sm,
      fontWeight: '400',
      lineHeight: '1.5',
    },
    label: {
      color: userAppSemanticTokens.text.primary,
      fontSize: userAppFoundationTokens.fontSize.md,
      fontWeight: '600',
      lineHeight: '1.5',
    },
    title: {
      color: userAppSemanticTokens.text.primary,
      fontSize: userAppFoundationTokens.fontSize.xl,
      fontWeight: '600',
      lineHeight: '1.4',
    },
    sectionTitle: {
      color: userAppSemanticTokens.text.primary,
      fontSize: userAppFoundationTokens.fontSize.xl,
      fontWeight: '600',
      lineHeight: '1.4',
    },
  },
  card: {
    default: {
      background: userAppSemanticTokens.surface.card,
      borderColor: userAppSemanticTokens.border.subtle,
      radius: userAppFoundationTokens.radius.lg,
      padding: userAppFoundationTokens.spacing.md,
    },
    muted: {
      background: userAppSemanticTokens.surface.muted,
      borderColor: userAppSemanticTokens.border.subtle,
      radius: userAppFoundationTokens.radius.md,
      padding: userAppFoundationTokens.spacing.sm,
    },
    warning: {
      background: userAppSemanticTokens.state.warningLight,
      borderColor: userAppSemanticTokens.state.warning,
      radius: userAppFoundationTokens.radius.lg,
      padding: userAppFoundationTokens.spacing.md,
    },
  },
  button: {
    size: {
      sm: {
        fontSize: userAppFoundationTokens.fontSize.sm,
        minHeight: '36px',
        paddingInline: '12px',
        radius: userAppFoundationTokens.radius.md,
      },
      md: {
        fontSize: userAppFoundationTokens.fontSize.md,
        minHeight: '44px',
        paddingInline: '16px',
        radius: userAppFoundationTokens.radius.md,
      },
    },
    variant: {
      primary: {
        background: userAppSemanticTokens.action.primary,
        borderColor: userAppSemanticTokens.action.primary,
        textColor: userAppSemanticTokens.text.inverse,
      },
      secondary: {
        background: userAppSemanticTokens.surface.card,
        borderColor: userAppSemanticTokens.border.default,
        textColor: userAppSemanticTokens.text.primary,
      },
      warning: {
        background: userAppSemanticTokens.state.warningLight,
        borderColor: userAppSemanticTokens.state.warning,
        textColor: userAppSemanticTokens.state.warning,
      },
    },
  },
  input: {
    background: userAppSemanticTokens.surface.card,
    borderColor: userAppSemanticTokens.border.default,
    radius: userAppFoundationTokens.radius.md,
    textColor: userAppSemanticTokens.text.primary,
    fontSize: userAppFoundationTokens.fontSize.md,
    minHeight: '44px',
    paddingBlock: '10px',
    paddingInline: '14px',
  },
  tag: {
    radius: userAppFoundationTokens.radius.md,
    fontSize: userAppFoundationTokens.fontSize.sm,
    paddingBlock: '2px',
    paddingInline: '10px',
    variant: {
      neutral: {
        background: userAppSemanticTokens.surface.muted,
        borderColor: userAppSemanticTokens.border.default,
        textColor: userAppSemanticTokens.text.secondary,
      },
      info: {
        background: userAppSemanticTokens.action.primaryLight,
        borderColor: userAppSemanticTokens.action.primary,
        textColor: userAppSemanticTokens.action.primary,
      },
      success: {
        background: userAppSemanticTokens.state.successLight,
        borderColor: userAppSemanticTokens.state.success,
        textColor: userAppSemanticTokens.state.success,
      },
      warning: {
        background: userAppSemanticTokens.state.warningLight,
        borderColor: userAppSemanticTokens.state.warning,
        textColor: userAppSemanticTokens.state.warning,
      },
    },
  },
  field: {
    gap: '10px',
    hintMarginTop: userAppFoundationTokens.spacing.xs,
  },
  emptyState: {
    background: userAppSemanticTokens.action.primaryLight,
    borderColor: userAppSemanticTokens.border.default,
    radius: userAppFoundationTokens.radius.lg,
    gap: userAppFoundationTokens.spacing.sm,
    padding: userAppFoundationTokens.spacing.md,
    titleFontSize: userAppFoundationTokens.fontSize.xxl,
    actionMarginTop: userAppFoundationTokens.spacing.xs,
  },
  pageHeader: {
    gap: userAppFoundationTokens.spacing.sm,
    titleGap: userAppFoundationTokens.spacing.xs,
    actionGap: userAppFoundationTokens.spacing.xs,
    marginBottom: userAppFoundationTokens.spacing.sm,
    titleFontSize: userAppFoundationTokens.fontSize.hero,
    descriptionFontSize: userAppFoundationTokens.fontSize.md,
    descriptionColor: userAppSemanticTokens.text.secondary,
  },
  pageSection: {
    background: userAppSemanticTokens.surface.card,
    borderColor: userAppSemanticTokens.border.subtle,
    radius: userAppFoundationTokens.radius.lg,
    marginBottom: userAppFoundationTokens.spacing.sm,
    padding: userAppFoundationTokens.spacing.md,
    titleColor: userAppSemanticTokens.text.primary,
    titleFontSize: userAppFoundationTokens.fontSize.xl,
    titleFontWeight: '600',
    descriptionColor: userAppSemanticTokens.text.primary,
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
  toggleSwitch: {
    gap: userAppFoundationTokens.spacing.sm,
    trackWidth: '52px',
    trackHeight: '30px',
    trackRadius: userAppFoundationTokens.radius.full,
    trackPadding: '3px',
    trackBackground: userAppSemanticTokens.border.default,
    trackBackgroundActive: userAppSemanticTokens.action.primary,
    trackBackgroundDisabled: userAppSemanticTokens.border.subtle,
    thumbSize: '24px',
    thumbRadius: userAppFoundationTokens.radius.full,
    thumbBackground: userAppSemanticTokens.surface.card,
    thumbShadow: userAppFoundationTokens.shadow.sm,
    descriptionMarginTop: userAppFoundationTokens.spacing.xs,
    opacityDisabled: '0.6',
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
