import { type UserAppTheme } from './themes';

export const sharedPageLayoutBlueprint = {
  pageContentMaxWidth: '1440px',
  shellMainGutter: 'clamp(1.25rem, 2vw, 2rem)',
  dashboard: {
    desktopColumns: 2,
    mobileColumns: 1,
    mobileBreakpoint: 900,
  },
  settings: {
    navWidth: 'clamp(220px, 16vw, 280px)',
    contentPadding: 'clamp(1rem, 1.8vw, 2rem)',
    mobileBreakpoint: 768,
  },
  assistant: {
    panelWidth: '320px',
    mobilePanelWidth: '280px',
    headerBarHeight: '70px',
    mobileBreakpoint: 900,
  },
} as const;

export type SharedThemeValueSource = Pick<
  UserAppTheme,
  | 'bgApp'
  | 'bgSurface'
  | 'bgCard'
  | 'bgCardHover'
  | 'bgSidebar'
  | 'bgInput'
  | 'textPrimary'
  | 'textSecondary'
  | 'textTertiary'
  | 'textInverse'
  | 'brandPrimary'
  | 'brandPrimaryHover'
  | 'brandPrimaryLight'
  | 'brandSecondary'
  | 'success'
  | 'successLight'
  | 'warning'
  | 'warningLight'
  | 'danger'
  | 'dangerLight'
  | 'info'
  | 'infoLight'
  | 'border'
  | 'borderLight'
  | 'divider'
  | 'shadowSm'
  | 'shadowMd'
  | 'shadowLg'
  | 'radiusSm'
  | 'radiusMd'
  | 'radiusLg'
  | 'radiusXl'
  | 'fontSizeXs'
  | 'fontSizeSm'
  | 'fontSizeMd'
  | 'fontSizeLg'
  | 'fontSizeXl'
  | 'fontSizeXxl'
  | 'fontSizeHero'
  | 'spacingXs'
  | 'spacingSm'
  | 'spacingMd'
  | 'spacingLg'
  | 'spacingXl'
  | 'spacingXxl'
  | 'navWidth'
  | 'navBg'
  | 'navText'
  | 'navTextActive'
  | 'navItemHover'
  | 'navItemActive'
  | 'transition'
  | 'glowColor'
  | 'gradientPrimary'
  | 'gradientCard'
  | 'animationSpeed'
>;

export type SharedThemeContract = ReturnType<typeof createSharedThemeContract>;

export function createSharedThemeContract(source: SharedThemeValueSource) {
  const foundation = {
    radius: {
      sm: source.radiusSm,
      md: source.radiusMd,
      lg: source.radiusLg,
      xl: source.radiusXl,
      full: '999px',
    },
    fontSize: {
      xs: source.fontSizeXs,
      sm: source.fontSizeSm,
      md: source.fontSizeMd,
      lg: source.fontSizeLg,
      xl: source.fontSizeXl,
      xxl: source.fontSizeXxl,
      hero: source.fontSizeHero,
    },
    spacing: {
      xs: source.spacingXs,
      sm: source.spacingSm,
      md: source.spacingMd,
      lg: source.spacingLg,
      xl: source.spacingXl,
      xxl: source.spacingXxl,
    },
    shadow: {
      sm: source.shadowSm,
      md: source.shadowMd,
      lg: source.shadowLg,
    },
    motion: {
      transition: source.transition,
      animationSpeed: source.animationSpeed,
    },
    layout: {
      navWidth: source.navWidth,
      pageContentMaxWidth: sharedPageLayoutBlueprint.pageContentMaxWidth,
      shellMainGutter: sharedPageLayoutBlueprint.shellMainGutter,
    },
  } as const;

  const semantic = {
    surface: {
      page: source.bgApp,
      shell: source.bgSurface,
      card: source.bgCard,
      cardHover: source.bgCardHover,
      sidebar: source.bgSidebar,
      muted: source.bgInput,
    },
    text: {
      primary: source.textPrimary,
      secondary: source.textSecondary,
      tertiary: source.textTertiary,
      inverse: source.textInverse,
    },
    border: {
      default: source.border,
      subtle: source.borderLight,
      divider: source.divider,
    },
    action: {
      primary: source.brandPrimary,
      primaryHover: source.brandPrimaryHover,
      primaryLight: source.brandPrimaryLight,
      secondary: source.brandSecondary,
    },
    state: {
      success: source.success,
      successLight: source.successLight,
      warning: source.warning,
      warningLight: source.warningLight,
      danger: source.danger,
      dangerLight: source.dangerLight,
      info: source.info,
      infoLight: source.infoLight,
    },
    nav: {
      background: source.navBg,
      text: source.navText,
      textActive: source.navTextActive,
      itemHover: source.navItemHover,
      itemActive: source.navItemActive,
    },
    gradient: {
      primary: source.gradientPrimary,
      card: source.gradientCard,
      glow: source.glowColor,
    },
    shadow: foundation.shadow,
  } as const;

  const component = {
    text: {
      body: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.md,
        fontWeight: '400',
        lineHeight: '1.6',
      },
      caption: {
        color: semantic.text.secondary,
        fontSize: foundation.fontSize.sm,
        fontWeight: '400',
        lineHeight: '1.5',
      },
      label: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.md,
        fontWeight: '600',
        lineHeight: '1.5',
      },
      title: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.xl,
        fontWeight: '600',
        lineHeight: '1.4',
      },
      sectionTitle: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.xl,
        fontWeight: '600',
        lineHeight: '1.4',
      },
      hero: {
        color: semantic.text.primary,
        fontSize: foundation.fontSize.hero,
        fontWeight: '700',
        lineHeight: '1.2',
      },
    },
    card: {
      default: {
        background: semantic.surface.card,
        borderColor: semantic.border.subtle,
        radius: foundation.radius.lg,
        padding: foundation.spacing.md,
      },
      muted: {
        background: semantic.surface.muted,
        borderColor: semantic.border.subtle,
        radius: foundation.radius.md,
        padding: foundation.spacing.sm,
      },
      warning: {
        background: semantic.state.warningLight,
        borderColor: semantic.state.warning,
        radius: foundation.radius.lg,
        padding: foundation.spacing.md,
      },
    },
    button: {
      size: {
        sm: {
          fontSize: foundation.fontSize.sm,
          minHeight: '36px',
          paddingInline: '12px',
          radius: foundation.radius.md,
        },
        md: {
          fontSize: foundation.fontSize.md,
          minHeight: '44px',
          paddingInline: '16px',
          radius: foundation.radius.md,
        },
      },
      variant: {
        primary: {
          background: semantic.action.primary,
          borderColor: semantic.action.primary,
          textColor: semantic.text.inverse,
        },
        secondary: {
          background: semantic.surface.card,
          borderColor: semantic.border.default,
          textColor: semantic.text.primary,
        },
        warning: {
          background: semantic.state.warningLight,
          borderColor: semantic.state.warning,
          textColor: semantic.state.warning,
        },
      },
    },
    input: {
      background: semantic.surface.card,
      borderColor: semantic.border.default,
      radius: foundation.radius.md,
      textColor: semantic.text.primary,
      fontSize: foundation.fontSize.md,
      minHeight: '44px',
      paddingBlock: '10px',
      paddingInline: '14px',
    },
    tag: {
      radius: foundation.radius.md,
      fontSize: foundation.fontSize.sm,
      paddingBlock: '2px',
      paddingInline: '10px',
      variant: {
        neutral: {
          background: semantic.surface.muted,
          borderColor: semantic.border.default,
          textColor: semantic.text.secondary,
        },
        info: {
          background: semantic.action.primaryLight,
          borderColor: semantic.action.primary,
          textColor: semantic.action.primary,
        },
        success: {
          background: semantic.state.successLight,
          borderColor: semantic.state.success,
          textColor: semantic.state.success,
        },
        warning: {
          background: semantic.state.warningLight,
          borderColor: semantic.state.warning,
          textColor: semantic.state.warning,
        },
      },
    },
    field: {
      gap: '10px',
      hintMarginTop: foundation.spacing.xs,
    },
    emptyState: {
      background: semantic.action.primaryLight,
      borderColor: semantic.border.default,
      radius: foundation.radius.lg,
      gap: foundation.spacing.sm,
      padding: foundation.spacing.md,
      titleFontSize: foundation.fontSize.xxl,
      actionMarginTop: foundation.spacing.xs,
    },
    pageHeader: {
      gap: foundation.spacing.sm,
      titleGap: foundation.spacing.xs,
      actionGap: foundation.spacing.xs,
      marginBottom: foundation.spacing.sm,
      titleFontSize: foundation.fontSize.hero,
      descriptionFontSize: foundation.fontSize.md,
      descriptionColor: semantic.text.secondary,
    },
    pageSection: {
      background: semantic.surface.card,
      borderColor: semantic.border.subtle,
      radius: foundation.radius.lg,
      marginBottom: foundation.spacing.sm,
      padding: foundation.spacing.md,
      titleColor: semantic.text.primary,
      titleFontSize: foundation.fontSize.xl,
      titleFontWeight: '600',
      descriptionColor: semantic.text.primary,
      descriptionFontSize: foundation.fontSize.md,
      descriptionMarginTop: foundation.spacing.xs,
      contentMarginTop: foundation.spacing.sm,
    },
    statusCard: {
      background: semantic.surface.muted,
      borderColor: semantic.border.subtle,
      radius: foundation.radius.md,
      marginBottom: foundation.spacing.xs,
      padding: foundation.spacing.sm,
      labelColor: semantic.text.secondary,
      labelFontSize: foundation.fontSize.sm,
      valueFontSize: foundation.fontSize.lg,
      valueMarginTop: foundation.spacing.xs,
    },
    toggleSwitch: {
      gap: foundation.spacing.sm,
      trackWidth: '52px',
      trackHeight: '30px',
      trackRadius: foundation.radius.full,
      trackPadding: '3px',
      trackBackground: semantic.border.default,
      trackBackgroundActive: semantic.action.primary,
      trackBackgroundDisabled: semantic.border.subtle,
      thumbSize: '24px',
      thumbRadius: foundation.radius.full,
      thumbBackground: semantic.surface.card,
      thumbShadow: foundation.shadow.sm,
      descriptionMarginTop: foundation.spacing.xs,
      opacityDisabled: '0.6',
    },
  } as const;

  const patterns = {
    page: {
      contentMaxWidth: sharedPageLayoutBlueprint.pageContentMaxWidth,
      shellMainGutter: sharedPageLayoutBlueprint.shellMainGutter,
    },
    dashboard: {
      desktopColumns: sharedPageLayoutBlueprint.dashboard.desktopColumns,
      mobileColumns: sharedPageLayoutBlueprint.dashboard.mobileColumns,
      mobileBreakpoint: sharedPageLayoutBlueprint.dashboard.mobileBreakpoint,
      allowMouseResize: true,
      allowDragSort: true,
    },
    settings: {
      navWidth: sharedPageLayoutBlueprint.settings.navWidth,
      contentPadding: sharedPageLayoutBlueprint.settings.contentPadding,
      mobileBreakpoint: sharedPageLayoutBlueprint.settings.mobileBreakpoint,
    },
    assistant: {
      panelWidth: sharedPageLayoutBlueprint.assistant.panelWidth,
      mobilePanelWidth: sharedPageLayoutBlueprint.assistant.mobilePanelWidth,
      headerBarHeight: sharedPageLayoutBlueprint.assistant.headerBarHeight,
      mobileBreakpoint: sharedPageLayoutBlueprint.assistant.mobileBreakpoint,
    },
  } as const;

  return {
    foundation,
    semantic,
    component,
    patterns,
  };
}

export function resolveSharedThemeContract(theme: SharedThemeValueSource) {
  return createSharedThemeContract(theme);
}
