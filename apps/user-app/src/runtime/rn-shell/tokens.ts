import {
  getRuntimeThemePlaceholder,
  mapThemeContractToRnTokens,
  normalizePluginThemeTokens,
  registerRuntimeTheme,
  resolveSharedThemeContract,
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

function buildRnThemeTokens(theme: UserAppTheme) {
  return mapThemeContractToRnTokens(resolveSharedThemeContract(theme));
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
export const rnPagePatternTokens = initialBundle.patterns;

export function applyRnTheme(theme: UserAppTheme): void {
  currentRuntimeTheme = theme;
  const next = buildRnThemeTokens(theme);
  replaceRecord(rnFoundationTokens, next.foundation);
  replaceRecord(rnSemanticTokens, next.semantic);
  replaceRecord(rnComponentTokens, next.component);
  replaceRecord(rnPagePatternTokens, next.patterns);
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
