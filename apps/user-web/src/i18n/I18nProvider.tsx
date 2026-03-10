/* ============================================================
 * I18nProvider - 管理语言切换和文案查询
 * ============================================================ */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import zhCN, { type LocaleMessages, type MessageKey } from './zh-CN';
import enUS from './en-US';

export type LocaleId = 'zh-CN' | 'en-US';

const locales: Record<LocaleId, LocaleMessages> = {
  'zh-CN': zhCN,
  'en-US': enUS,
};

interface I18nContextValue {
  locale: LocaleId;
  setLocale: (id: LocaleId) => void;
  t: (key: MessageKey) => string;
}

const STORAGE_KEY = 'familyclaw-locale';

function getStoredLocale(): LocaleId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored in locales) return stored as LocaleId;
  } catch { /* noop */ }
  return 'zh-CN';
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleId>(getStoredLocale);

  const setLocale = useCallback((id: LocaleId) => {
    setLocaleState(id);
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* noop */ }
    document.documentElement.lang = id;
  }, []);

  const t = useCallback(
    (key: MessageKey): string => {
      return locales[locale][key] ?? key;
    },
    [locale],
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n 必须在 I18nProvider 内使用');
  return ctx;
}
