import { PluginLocale } from '../domain/types';

export type LocaleId = string;

export type StorageAdapter = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

export interface LocaleDefinition {
  id: LocaleId;
  label: string;
  nativeLabel: string;
  flag?: string;
  fallback?: LocaleId | null;
  messages?: Record<string, string>;
  source: 'builtin' | 'plugin';
  sourceType?: 'builtin' | 'third_party';
  pluginId?: string;
  overriddenPluginIds?: string[];
}

export const LOCALE_STORAGE_KEY = 'familyclaw-locale';
export const DEFAULT_LOCALE_ID = 'zh-CN';

const BUILTIN_LOCALE_DEFINITIONS: LocaleDefinition[] = [
  {
    id: 'zh-CN',
    label: '简体中文',
    nativeLabel: '简体中文',
    flag: 'CN',
    source: 'builtin',
    sourceType: 'builtin',
  },
  {
    id: 'en-US',
    label: 'English',
    nativeLabel: 'English',
    flag: 'US',
    fallback: 'zh-CN',
    source: 'builtin',
    sourceType: 'builtin',
  },
];

function normalizeLocaleLookup(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase();
}

function sanitizeLocaleId(value: string | null | undefined): string {
  return (value ?? '').trim();
}

export function listBuiltinLocaleDefinitions(): LocaleDefinition[] {
  return BUILTIN_LOCALE_DEFINITIONS.map(definition => ({ ...definition }));
}

export function buildLocaleDefinitions(pluginLocales: readonly PluginLocale[] = []): LocaleDefinition[] {
  const registry = new Map<string, LocaleDefinition>();

  for (const definition of BUILTIN_LOCALE_DEFINITIONS) {
    registry.set(definition.id, { ...definition });
  }

  for (const pluginLocale of pluginLocales) {
    const id = sanitizeLocaleId(pluginLocale.locale_id);
    if (!id) {
      continue;
    }

    registry.set(id, {
      id,
      label: pluginLocale.label || id,
      nativeLabel: pluginLocale.native_label || pluginLocale.label || id,
      fallback: sanitizeLocaleId(pluginLocale.fallback) || undefined,
      messages: pluginLocale.messages,
      source: 'plugin',
      sourceType: pluginLocale.source_type,
      pluginId: pluginLocale.plugin_id,
      overriddenPluginIds: pluginLocale.overridden_plugin_ids,
    });
  }

  return Array.from(registry.values());
}

export function formatLocaleOptionLabel(definition: Pick<LocaleDefinition, 'id' | 'nativeLabel'>): string {
  return `${definition.nativeLabel} (${definition.id})`;
}

export function getLocaleSourceLabel(definition: Pick<LocaleDefinition, 'source' | 'sourceType'>): string {
  if (definition.source === 'builtin' || definition.sourceType === 'builtin') {
    return 'builtin';
  }
  return 'third_party';
}

export function getLocaleDefinition(
  definitions: readonly LocaleDefinition[],
  locale: string | null | undefined,
): LocaleDefinition | undefined {
  if (!locale) {
    return undefined;
  }

  const normalized = normalizeLocaleLookup(locale);
  return definitions.find(item => normalizeLocaleLookup(item.id) === normalized);
}

export function isRegisteredLocale(
  definitions: readonly LocaleDefinition[],
  locale: string | null | undefined,
): locale is LocaleId {
  return Boolean(getLocaleDefinition(definitions, locale));
}

export function resolveSupportedLocale(
  locale: string | null | undefined,
  definitions: readonly LocaleDefinition[] = BUILTIN_LOCALE_DEFINITIONS,
  fallback: LocaleId = DEFAULT_LOCALE_ID,
): LocaleId {
  const matched = getLocaleDefinition(definitions, locale);
  if (matched) {
    return matched.id;
  }

  const normalized = normalizeLocaleLookup(locale);
  if (!normalized) {
    return fallback;
  }

  if (
    (normalized.includes('hant')
      || normalized.startsWith('zh-tw')
      || normalized.startsWith('zh-hk')
      || normalized.startsWith('zh-mo'))
    && isRegisteredLocale(definitions, 'zh-TW')
  ) {
    return 'zh-TW';
  }

  if (normalized.startsWith('zh') && isRegisteredLocale(definitions, 'zh-CN')) {
    return 'zh-CN';
  }

  const languageCode = normalized.split(/[-_]/)[0];
  const languageMatched = definitions.find(item => normalizeLocaleLookup(item.id).split(/[-_]/)[0] === languageCode);
  return languageMatched?.id ?? fallback;
}

export async function getStoredLocaleId(
  storage: StorageAdapter,
  definitions: readonly LocaleDefinition[] = BUILTIN_LOCALE_DEFINITIONS,
  fallback: LocaleId = DEFAULT_LOCALE_ID,
  storageKey = LOCALE_STORAGE_KEY,
) {
  const stored = await storage.getItem(storageKey);
  return resolveSupportedLocale(stored, definitions, fallback);
}

export async function persistLocaleId(
  storage: StorageAdapter,
  locale: string | null | undefined,
  definitions: readonly LocaleDefinition[] = BUILTIN_LOCALE_DEFINITIONS,
  fallback: LocaleId = DEFAULT_LOCALE_ID,
  storageKey = LOCALE_STORAGE_KEY,
) {
  const nextLocale = resolveSupportedLocale(locale, definitions, fallback);
  await storage.setItem(storageKey, nextLocale);
  return nextLocale;
}
