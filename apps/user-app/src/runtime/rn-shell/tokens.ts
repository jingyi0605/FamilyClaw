import {
  getRuntimeThemePlaceholder,
  normalizePluginThemeTokens,
  registerRuntimeTheme,
  resolveRuntimeTheme,
  type PluginThemeResourcePayload,
  type UserAppTheme,
} from '@familyclaw/user-ui';

export type RnThemeRuntimeStatus = 'ready' | 'missing';

export type RnThemeRuntimeState = {
  pluginId: string | null;
  themeId: string;
  status: RnThemeRuntimeStatus;
  reason: string | null;
};

function toPxNumber(value: string, fallback: number): number {
  const normalized = value.trim().toLowerCase();
  if (normalized.endsWith('px')) {
    const parsed = Number.parseFloat(normalized.slice(0, -2));
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function buildRnThemeTokens(theme: UserAppTheme) {
  const foundation = {
    spacing: {
      xs: toPxNumber(theme.spacingXs, 4),
      sm: toPxNumber(theme.spacingSm, 8),
      md: toPxNumber(theme.spacingMd, 16),
      lg: toPxNumber(theme.spacingLg, 24),
      xl: toPxNumber(theme.spacingXl, 32),
      xxl: toPxNumber(theme.spacingXxl, 48),
    },
    radius: {
      sm: toPxNumber(theme.radiusSm, 6),
      md: toPxNumber(theme.radiusMd, 10),
      lg: toPxNumber(theme.radiusLg, 14),
      xl: toPxNumber(theme.radiusXl, 20),
      full: 999,
    },
    fontSize: {
      xs: toPxNumber(theme.fontSizeXs, 12),
      sm: toPxNumber(theme.fontSizeSm, 13),
      md: toPxNumber(theme.fontSizeMd, 15),
      lg: toPxNumber(theme.fontSizeLg, 18),
      xl: toPxNumber(theme.fontSizeXl, 22),
      xxl: toPxNumber(theme.fontSizeXxl, 28),
      hero: toPxNumber(theme.fontSizeHero, 36),
    },
    lineHeight: {
      tight: 1.3,
      normal: 1.5,
      relaxed: 1.6,
    },
  } as const;

  const semantic = {
    surface: {
      page: theme.bgApp,
      shell: theme.bgSurface,
      card: theme.bgCard,
      cardHover: theme.bgCardHover,
      sidebar: theme.bgSidebar,
      muted: theme.bgInput,
    },
    text: {
      primary: theme.textPrimary,
      secondary: theme.textSecondary,
      tertiary: theme.textTertiary,
      inverse: theme.textInverse,
    },
    border: {
      default: theme.border,
      subtle: theme.borderLight,
      divider: theme.divider,
    },
    action: {
      primary: theme.brandPrimary,
      primaryHover: theme.brandPrimaryHover,
      primaryLight: theme.brandPrimaryLight,
      secondary: theme.brandSecondary,
    },
    state: {
      success: theme.success,
      successLight: theme.successLight,
      warning: theme.warning,
      warningLight: theme.warningLight,
      danger: theme.danger,
      dangerLight: theme.dangerLight,
      info: theme.info,
      infoLight: theme.infoLight,
    },
    nav: {
      background: theme.navBg,
      text: theme.navText,
      textActive: theme.navTextActive,
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

  return { foundation, semantic, component };
}

function replaceRecord(target: Record<string, any>, source: Record<string, any>): void {
  for (const key of Object.keys(target)) {
    if (!(key in source)) {
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete target[key];
    }
  }
  for (const [key, value] of Object.entries(source)) {
    if (
      value &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      key in target &&
      target[key] &&
      typeof target[key] === 'object' &&
      !Array.isArray(target[key])
    ) {
      replaceRecord(target[key] as Record<string, any>, value as Record<string, any>);
      continue;
    }
    target[key] = value;
  }
}

const initialTheme = getRuntimeThemePlaceholder();
const initialBundle = buildRnThemeTokens(initialTheme);
let currentRuntimeTheme = initialTheme;
let runtimeState: RnThemeRuntimeState = {
  pluginId: null,
  themeId: initialTheme.id,
  status: 'missing',
  reason: 'runtime_theme_placeholder',
};

export const rnFoundationTokens = initialBundle.foundation;
export const rnSemanticTokens = initialBundle.semantic;
export const rnComponentTokens = initialBundle.component;

export function applyRnTheme(theme: UserAppTheme): void {
  currentRuntimeTheme = theme;
  const next = buildRnThemeTokens(theme);
  replaceRecord(rnFoundationTokens, next.foundation);
  replaceRecord(rnSemanticTokens, next.semantic);
  replaceRecord(rnComponentTokens, next.component);
  runtimeState = {
    ...runtimeState,
    themeId: theme.id,
    status: 'ready',
    reason: null,
  };
}

export function applyRnThemeFromPluginResource(payload: PluginThemeResourcePayload): UserAppTheme {
  const normalized = normalizePluginThemeTokens(payload);
  registerRuntimeTheme(normalized);
  applyRnTheme(normalized);
  runtimeState = {
    ...runtimeState,
    pluginId: payload.plugin_id ?? null,
    themeId: normalized.id,
    status: 'ready',
    reason: null,
  };
  return normalized;
}

export function buildRnThemeTokenBundleFromPluginResource(payload: PluginThemeResourcePayload) {
  const normalized = normalizePluginThemeTokens(payload);
  return buildRnThemeTokens(normalized);
}

export function applyRnThemeById(themeId: string): RnThemeRuntimeState {
  const normalizedThemeId = themeId.trim();
  const theme = normalizedThemeId ? resolveRuntimeTheme(normalizedThemeId) : null;
  if (!theme) {
    runtimeState = {
      ...runtimeState,
      themeId: normalizedThemeId || runtimeState.themeId,
      status: 'missing',
      reason: 'theme_not_registered',
    };
    return { ...runtimeState };
  }
  applyRnTheme(theme);
  runtimeState = {
    ...runtimeState,
    themeId: theme.id,
    status: 'ready',
    reason: null,
  };
  return { ...runtimeState };
}

export function getCurrentRnThemeId(): string {
  return runtimeState.themeId;
}

export function getCurrentRnTheme(): UserAppTheme {
  return currentRuntimeTheme;
}

export function getRnThemeRuntimeState(): RnThemeRuntimeState {
  return { ...runtimeState };
}
