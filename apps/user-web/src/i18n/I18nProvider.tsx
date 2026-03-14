/* ============================================================
 * I18nProvider - 管理语言切换和文案查询
 * ============================================================ */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { MessageKey } from './zh-CN';
import { getLocaleDefinition, listLocaleDefinitions, replacePluginLocaleDefinitions, resolveSupportedLocale, type LocaleDefinition, type LocaleId } from './localeRegistry';

interface I18nContextValue {
  locale: LocaleId;
  setLocale: (id: LocaleId) => void;
  t: (key: MessageKey) => string;
  locales: LocaleDefinition[];
  replacePluginLocales: (definitions: LocaleDefinition[]) => void;
}

const STORAGE_KEY = 'familyclaw-locale';

function getStoredLocale(): LocaleId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return resolveSupportedLocale(stored);
  } catch { /* noop */ }
  return 'zh-CN';
}

function resolveMessage(localeId: LocaleId, key: MessageKey, visited: Set<string>): string | undefined {
  if (visited.has(localeId)) return undefined;
  visited.add(localeId);

  const definition = getLocaleDefinition(localeId);
  if (!definition) return undefined;

  const currentMessage = definition.messages[key];
  if (currentMessage) return currentMessage;
  if (!definition.fallback) return undefined;
  return resolveMessage(definition.fallback, key, visited);
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleId>(getStoredLocale);
  const [registryVersion, setRegistryVersion] = useState(0);
  const locales = useMemo(() => listLocaleDefinitions(), [registryVersion]);

  const setLocale = useCallback((id: LocaleId) => {
    const nextLocale = resolveSupportedLocale(id);
    setLocaleState(nextLocale);
    try { localStorage.setItem(STORAGE_KEY, nextLocale); } catch { /* noop */ }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const replacePluginLocales = useCallback((definitions: LocaleDefinition[]) => {
    replacePluginLocaleDefinitions(definitions);
    setRegistryVersion(current => current + 1);
    setLocaleState(current => {
      const nextLocale = resolveSupportedLocale(current);
      try { localStorage.setItem(STORAGE_KEY, nextLocale); } catch { /* noop */ }
      return nextLocale;
    });
  }, []);

  const t = useCallback(
    (key: MessageKey): string => {
      return resolveMessage(locale, key, new Set()) ?? key;
    },
    [locale],
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, locales, replacePluginLocales }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n 必须在 I18nProvider 内使用');
  return ctx;
}
