import { type SharedThemeContract } from './contract';

function toPxNumber(value: string, fallback: number): number {
  const normalized = value.trim().toLowerCase();
  if (normalized.endsWith('px')) {
    const parsed = Number.parseFloat(normalized.slice(0, -2));
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function mapThemeContractToCssVariables(contract: SharedThemeContract) {
  return {
    '--bg-app': contract.semantic.surface.page,
    '--bg-surface': contract.semantic.surface.shell,
    '--bg-card': contract.semantic.surface.card,
    '--bg-card-hover': contract.semantic.surface.cardHover,
    '--bg-sidebar': contract.semantic.surface.sidebar,
    '--bg-input': contract.semantic.surface.muted,
    '--bg-tertiary': contract.semantic.surface.muted,
    '--text-primary': contract.semantic.text.primary,
    '--text-secondary': contract.semantic.text.secondary,
    '--text-tertiary': contract.semantic.text.tertiary,
    '--text-inverse': contract.semantic.text.inverse,
    '--brand-primary': contract.semantic.action.primary,
    '--brand-primary-hover': contract.semantic.action.primaryHover,
    '--brand-primary-light': contract.semantic.action.primaryLight,
    '--brand-secondary': contract.semantic.action.secondary,
    '--color-success': contract.semantic.state.success,
    '--color-success-light': contract.semantic.state.successLight,
    '--color-warning': contract.semantic.state.warning,
    '--color-warning-light': contract.semantic.state.warningLight,
    '--color-danger': contract.semantic.state.danger,
    '--color-danger-light': contract.semantic.state.dangerLight,
    '--color-info': contract.semantic.state.info,
    '--color-info-light': contract.semantic.state.infoLight,
    '--border': contract.semantic.border.default,
    '--border-default': contract.semantic.border.default,
    '--border-light': contract.semantic.border.subtle,
    '--divider': contract.semantic.border.divider,
    '--shadow-sm': contract.foundation.shadow.sm,
    '--shadow-md': contract.foundation.shadow.md,
    '--shadow-lg': contract.foundation.shadow.lg,
    '--radius-sm': contract.foundation.radius.sm,
    '--radius-md': contract.foundation.radius.md,
    '--radius-lg': contract.foundation.radius.lg,
    '--radius-xl': contract.foundation.radius.xl,
    '--radius-full': contract.foundation.radius.full,
    '--font-size-xs': contract.foundation.fontSize.xs,
    '--font-size-sm': contract.foundation.fontSize.sm,
    '--font-size-md': contract.foundation.fontSize.md,
    '--font-size-lg': contract.foundation.fontSize.lg,
    '--font-size-xl': contract.foundation.fontSize.xl,
    '--font-size-xxl': contract.foundation.fontSize.xxl,
    '--font-size-hero': contract.foundation.fontSize.hero,
    '--spacing-xs': contract.foundation.spacing.xs,
    '--spacing-sm': contract.foundation.spacing.sm,
    '--spacing-md': contract.foundation.spacing.md,
    '--spacing-lg': contract.foundation.spacing.lg,
    '--spacing-xl': contract.foundation.spacing.xl,
    '--spacing-xxl': contract.foundation.spacing.xxl,
    '--nav-width': contract.foundation.layout.navWidth,
    '--nav-bg': contract.semantic.nav.background,
    '--nav-text': contract.semantic.nav.text,
    '--nav-text-active': contract.semantic.nav.textActive,
    '--nav-item-hover': contract.semantic.nav.itemHover,
    '--nav-item-active': contract.semantic.nav.itemActive,
    '--transition': contract.foundation.motion.transition,
    '--glow-color': contract.semantic.gradient.glow,
    '--gradient-primary': contract.semantic.gradient.primary,
    '--gradient-card': contract.semantic.gradient.card,
    '--animation-speed': contract.foundation.motion.animationSpeed,
    '--page-content-max-width': contract.patterns.page.contentMaxWidth,
    '--app-shell-gutter': contract.patterns.page.shellMainGutter,
    '--settings-nav-width': contract.patterns.settings.navWidth,
    '--settings-content-padding': contract.patterns.settings.contentPadding,
    '--assistant-panel-width': contract.patterns.assistant.panelWidth,
    '--assistant-panel-width-mobile': contract.patterns.assistant.mobilePanelWidth,
    '--assistant-header-bar-height': contract.patterns.assistant.headerBarHeight,
  } as const;
}

export function mapThemeContractToRnTokens(contract: SharedThemeContract) {
  const foundation = {
    spacing: {
      xs: toPxNumber(contract.foundation.spacing.xs, 4),
      sm: toPxNumber(contract.foundation.spacing.sm, 8),
      md: toPxNumber(contract.foundation.spacing.md, 16),
      lg: toPxNumber(contract.foundation.spacing.lg, 24),
      xl: toPxNumber(contract.foundation.spacing.xl, 32),
      xxl: toPxNumber(contract.foundation.spacing.xxl, 48),
    },
    radius: {
      sm: toPxNumber(contract.foundation.radius.sm, 6),
      md: toPxNumber(contract.foundation.radius.md, 10),
      lg: toPxNumber(contract.foundation.radius.lg, 14),
      xl: toPxNumber(contract.foundation.radius.xl, 20),
      full: 999,
    },
    fontSize: {
      xs: toPxNumber(contract.foundation.fontSize.xs, 12),
      sm: toPxNumber(contract.foundation.fontSize.sm, 13),
      md: toPxNumber(contract.foundation.fontSize.md, 15),
      lg: toPxNumber(contract.foundation.fontSize.lg, 18),
      xl: toPxNumber(contract.foundation.fontSize.xl, 22),
      xxl: toPxNumber(contract.foundation.fontSize.xxl, 28),
      hero: toPxNumber(contract.foundation.fontSize.hero, 36),
    },
    lineHeight: {
      tight: 1.3,
      normal: 1.5,
      relaxed: 1.6,
    },
    layout: {
      navWidth: toPxNumber(contract.foundation.layout.navWidth, 240),
    },
  } as const;

  const semantic = {
    surface: {
      page: contract.semantic.surface.page,
      shell: contract.semantic.surface.shell,
      card: contract.semantic.surface.card,
      cardHover: contract.semantic.surface.cardHover,
      sidebar: contract.semantic.surface.sidebar,
      muted: contract.semantic.surface.muted,
    },
    text: {
      primary: contract.semantic.text.primary,
      secondary: contract.semantic.text.secondary,
      tertiary: contract.semantic.text.tertiary,
      inverse: contract.semantic.text.inverse,
    },
    border: {
      default: contract.semantic.border.default,
      subtle: contract.semantic.border.subtle,
      divider: contract.semantic.border.divider,
    },
    action: {
      primary: contract.semantic.action.primary,
      primaryHover: contract.semantic.action.primaryHover,
      primaryLight: contract.semantic.action.primaryLight,
      secondary: contract.semantic.action.secondary,
    },
    state: {
      success: contract.semantic.state.success,
      successLight: contract.semantic.state.successLight,
      warning: contract.semantic.state.warning,
      warningLight: contract.semantic.state.warningLight,
      danger: contract.semantic.state.danger,
      dangerLight: contract.semantic.state.dangerLight,
      info: contract.semantic.state.info,
      infoLight: contract.semantic.state.infoLight,
    },
    nav: {
      background: contract.semantic.nav.background,
      text: contract.semantic.nav.text,
      textActive: contract.semantic.nav.textActive,
    },
  } as const;

  const component = {
    text: {
      body: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.md,
        fontWeight: '400' as const,
        lineHeight: foundation.fontSize.md * foundation.lineHeight.relaxed,
      },
      caption: {
        color: semantic.text.secondary,
        fontSize: foundation.fontSize.sm,
        fontWeight: '400' as const,
        lineHeight: foundation.fontSize.sm * foundation.lineHeight.normal,
      },
      label: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.md,
        fontWeight: '600' as const,
        lineHeight: foundation.fontSize.md * foundation.lineHeight.normal,
      },
      title: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.xl,
        fontWeight: '600' as const,
        lineHeight: foundation.fontSize.xl * foundation.lineHeight.tight,
      },
      hero: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.hero,
        fontWeight: '700' as const,
        lineHeight: foundation.fontSize.hero * foundation.lineHeight.tight,
      },
    },
    card: {
      default: {
        backgroundColor: semantic.surface.card,
        borderColor: semantic.border.subtle,
        borderWidth: 1,
        borderRadius: foundation.radius.lg,
        padding: foundation.spacing.md,
      },
      muted: {
        backgroundColor: semantic.surface.muted,
        borderColor: semantic.border.subtle,
        borderWidth: 1,
        borderRadius: foundation.radius.md,
        padding: foundation.spacing.sm,
      },
      warning: {
        backgroundColor: semantic.state.warningLight,
        borderColor: semantic.state.warning,
        borderWidth: 1,
        borderRadius: foundation.radius.lg,
        padding: foundation.spacing.md,
      },
    },
    button: {
      minHeight: 48,
      borderRadius: foundation.radius.md,
      paddingHorizontal: foundation.spacing.md,
      fontSize: foundation.fontSize.md,
      fontWeight: '600' as const,
    },
    input: {
      minHeight: 48,
      borderRadius: foundation.radius.md,
      borderWidth: 1,
      paddingHorizontal: 14,
      paddingVertical: 10,
      fontSize: foundation.fontSize.md,
      backgroundColor: semantic.surface.card,
      borderColor: semantic.border.default,
      color: semantic.text.primary,
    },
    shadow: {
      sm: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.06,
        shadowRadius: 3,
        elevation: 1,
      },
      md: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.08,
        shadowRadius: 8,
        elevation: 3,
      },
      lg: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 20,
        elevation: 6,
      },
    },
  } as const;

  const patterns = {
    page: {
      contentMaxWidth: toPxNumber(contract.patterns.page.contentMaxWidth, 1440),
      shellMainGutter: 24,
    },
    dashboard: {
      desktopColumns: contract.patterns.dashboard.desktopColumns,
      mobileColumns: contract.patterns.dashboard.mobileColumns,
      mobileBreakpoint: contract.patterns.dashboard.mobileBreakpoint,
      allowMouseResize: false,
      allowDragSort: false,
    },
    settings: {
      navWidth: 0,
      contentPadding: toPxNumber(contract.foundation.spacing.md, 16),
      mobileBreakpoint: contract.patterns.settings.mobileBreakpoint,
    },
    assistant: {
      panelWidth: toPxNumber(contract.patterns.assistant.panelWidth, 320),
      mobilePanelWidth: toPxNumber(contract.patterns.assistant.mobilePanelWidth, 280),
      headerBarHeight: toPxNumber(contract.patterns.assistant.headerBarHeight, 70),
      mobileBreakpoint: contract.patterns.assistant.mobileBreakpoint,
    },
  } as const;

  return {
    foundation,
    semantic,
    component,
    patterns,
  };
}

