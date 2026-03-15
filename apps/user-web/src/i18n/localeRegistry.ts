import zhCN, { type LocaleMessages } from './zh-CN';
import enUS from './en-US';
import {
  DEFAULT_LOCALE_ID,
  formatLocaleOptionLabel as formatSharedLocaleOptionLabel,
  getLocaleSourceLabel as getSharedLocaleSourceLabel,
  resolveSupportedLocale as resolveSharedSupportedLocale,
  type LocaleId as SharedLocaleId,
} from '@familyclaw/user-core';

export type LocaleId = SharedLocaleId;

export interface LocaleDefinition {
  id: LocaleId;
  label: string;
  nativeLabel: string;
  flag?: string;
  fallback?: LocaleId | null;
  messages: LocaleMessages;
  source: 'builtin' | 'plugin';
  sourceType?: 'builtin' | 'official' | 'third_party';
  pluginId?: string;
  overriddenPluginIds?: string[];
}

export function formatLocaleOptionLabel(definition: Pick<LocaleDefinition, 'id' | 'nativeLabel'>): string {
  return formatSharedLocaleOptionLabel(definition);
}

export function getLocaleSourceLabel(definition: Pick<LocaleDefinition, 'source' | 'sourceType'>): string {
  return getSharedLocaleSourceLabel(definition);
}

const localeRegistry = new Map<LocaleId, LocaleDefinition>();

const builtinLocaleIds = new Set<LocaleId>();

function sanitizeLocaleId(value: string): string {
  return value.trim();
}

function normalizeLocaleLookup(value: string): string {
  return value.trim().toLowerCase();
}

export function registerLocaleDefinitions(definitions: LocaleDefinition[]) {
  for (const definition of definitions) {
    const id = sanitizeLocaleId(definition.id);
    if (!id) continue;

    localeRegistry.set(id, {
      ...definition,
      id,
      fallback: definition.fallback?.trim() || undefined,
    });

    if (definition.source === 'builtin') {
      builtinLocaleIds.add(id);
    }
  }
}

registerLocaleDefinitions([
  {
    id: 'zh-CN',
    label: '简体中文',
    nativeLabel: '简体中文',
    flag: '🇨🇳',
    messages: zhCN,
    source: 'builtin',
  },
  {
    id: 'en-US',
    label: 'English',
    nativeLabel: 'English',
    flag: '🇺🇸',
    fallback: 'zh-CN',
    messages: enUS,
    source: 'builtin',
  },
]);

export function replacePluginLocaleDefinitions(definitions: LocaleDefinition[]) {
  for (const [id, definition] of localeRegistry.entries()) {
    if (!builtinLocaleIds.has(id) && definition.source === 'plugin') {
      localeRegistry.delete(id);
    }
  }

  registerLocaleDefinitions(definitions.map(definition => ({ ...definition, source: 'plugin' })));
}

export function listLocaleDefinitions(): LocaleDefinition[] {
  return Array.from(localeRegistry.values());
}

export function getLocaleDefinition(locale: string | null | undefined): LocaleDefinition | undefined {
  if (!locale) return undefined;

  const direct = localeRegistry.get(locale.trim());
  if (direct) return direct;

  const lookup = normalizeLocaleLookup(locale);
  return listLocaleDefinitions().find(item => normalizeLocaleLookup(item.id) === lookup);
}

export function isRegisteredLocale(locale: string | null | undefined): locale is LocaleId {
  return getLocaleDefinition(locale) !== undefined;
}

export function resolveSupportedLocale(locale: string | null | undefined, fallback: LocaleId = DEFAULT_LOCALE_ID): LocaleId {
  return resolveSharedSupportedLocale(locale, listLocaleDefinitions(), fallback);
}

export function getLocaleLabel(locale: string | null | undefined): string {
  if (!locale) return '-';
  const definition = getLocaleDefinition(locale);
  if (!definition) return locale;
  return formatLocaleOptionLabel(definition);
}
