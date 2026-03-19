export type StorageAdapter = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

export type ThemeId = string;
export type ThemePluginId = string;
export type ThemeSelectionStatus = 'ready' | 'missing';

export interface ThemeSelection {
  pluginId: ThemePluginId;
  themeId: ThemeId;
  status: ThemeSelectionStatus;
}

export interface ThemeOption {
  pluginId: ThemePluginId;
  id: ThemeId;
  label: string;
  description: string;
  available: boolean;
}

export const THEME_STORAGE_KEY = 'familyclaw-theme';
export const THEME_SELECTION_STORAGE_KEY = 'familyclaw-theme-selection';
export const DEFAULT_THEME_ID: ThemeId = 'chun-he-jing-ming';
export const DEFAULT_THEME_PLUGIN_ID: ThemePluginId = 'builtin.theme.chun-he-jing-ming';

// 默认值只负责首次启动时指向内置 theme-pack 插件，不承载任何宿主静态主题 token。
const INITIAL_THEME_SELECTION: ThemeSelection = {
  pluginId: DEFAULT_THEME_PLUGIN_ID,
  themeId: DEFAULT_THEME_ID,
  status: 'ready',
};

export function listThemeOptions(): ThemeOption[] {
  return [];
}

export function resolveThemeId(
  themeId: string | null | undefined,
  fallback: ThemeId = DEFAULT_THEME_ID,
): ThemeId {
  const normalized = (themeId ?? '').trim();
  return normalized || fallback;
}

export function resolveThemePluginId(
  pluginId: string | null | undefined,
  fallback: ThemePluginId = DEFAULT_THEME_PLUGIN_ID,
): ThemePluginId {
  const normalized = (pluginId ?? '').trim();
  return normalized || fallback;
}

export function normalizeThemeSelection(
  selection: Partial<ThemeSelection> | null | undefined,
  fallback: ThemeSelection = INITIAL_THEME_SELECTION,
): ThemeSelection {
  return {
    pluginId: resolveThemePluginId(selection?.pluginId, fallback.pluginId),
    themeId: resolveThemeId(selection?.themeId, fallback.themeId),
    status: selection?.status === 'missing' ? 'missing' : 'ready',
  };
}

export function parseThemeSelection(
  raw: string | null | undefined,
  fallback: ThemeSelection = INITIAL_THEME_SELECTION,
): ThemeSelection {
  const normalizedRaw = (raw ?? '').trim();
  if (!normalizedRaw) {
    return normalizeThemeSelection(undefined, fallback);
  }

  try {
    const payload = JSON.parse(normalizedRaw) as Partial<ThemeSelection>;
    return normalizeThemeSelection(payload, fallback);
  } catch {
    return {
      pluginId: fallback.pluginId,
      themeId: resolveThemeId(normalizedRaw, fallback.themeId),
      status: 'ready',
    };
  }
}

export function serializeThemeSelection(selection: Partial<ThemeSelection> | null | undefined): string {
  return JSON.stringify(normalizeThemeSelection(selection));
}

export function isElderFriendlyTheme(themeId: string | null | undefined): boolean {
  return resolveThemeId(themeId, '') === 'ming-cha-qiu-hao';
}

export async function getStoredThemeSelection(
  storage: StorageAdapter,
  storageKey = THEME_SELECTION_STORAGE_KEY,
  fallback: ThemeSelection = INITIAL_THEME_SELECTION,
) {
  const rawSelection = await storage.getItem(storageKey);
  if (rawSelection && rawSelection.trim()) {
    return parseThemeSelection(rawSelection, fallback);
  }

  const legacyThemeId = await storage.getItem(THEME_STORAGE_KEY);
  return {
    pluginId: fallback.pluginId,
    themeId: resolveThemeId(legacyThemeId, fallback.themeId),
    status: 'ready',
  };
}

export async function persistThemeSelection(
  storage: StorageAdapter,
  selection: Partial<ThemeSelection> | null | undefined,
  storageKey = THEME_SELECTION_STORAGE_KEY,
) {
  const normalizedSelection = normalizeThemeSelection(selection);
  await storage.setItem(storageKey, JSON.stringify(normalizedSelection));
  await storage.setItem(THEME_STORAGE_KEY, normalizedSelection.themeId);
  return normalizedSelection;
}

export async function getStoredThemeId(
  storage: StorageAdapter,
  storageKey = THEME_STORAGE_KEY,
  fallback: ThemeId = DEFAULT_THEME_ID,
) {
  if (storageKey === THEME_STORAGE_KEY) {
    const selection = await getStoredThemeSelection(storage);
    return resolveThemeId(selection.themeId, fallback);
  }

  const stored = await storage.getItem(storageKey);
  return resolveThemeId(stored, fallback);
}

export async function persistThemeId(
  storage: StorageAdapter,
  themeId: string | null | undefined,
  storageKey = THEME_STORAGE_KEY,
  fallback: ThemeId = DEFAULT_THEME_ID,
) {
  const nextThemeId = resolveThemeId(themeId, fallback);
  if (storageKey === THEME_STORAGE_KEY) {
    await persistThemeSelection(storage, {
      pluginId: DEFAULT_THEME_PLUGIN_ID,
      themeId: nextThemeId,
      status: 'ready',
    });
  } else {
    await storage.setItem(storageKey, nextThemeId);
  }

  return nextThemeId;
}
