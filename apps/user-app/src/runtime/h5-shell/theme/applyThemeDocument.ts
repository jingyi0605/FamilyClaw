import {
  mapThemeContractToCssVariables,
  resolveSharedThemeContract,
  type SharedThemeValueSource,
} from '@familyclaw/user-ui';

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
  const variables = mapThemeContractToCssVariables(
    resolveSharedThemeContract(resolveThemeTokens(payload) as SharedThemeValueSource),
  );
  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  const themeId = typeof payload.id === 'string' ? payload.id : 'unknown';
  root.setAttribute('data-theme', themeId);
  if (typeof payload.plugin_id === 'string') {
    root.setAttribute('data-theme-plugin', payload.plugin_id);
  }
}
