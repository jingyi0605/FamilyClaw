import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  DEFAULT_LOCALE_ID,
  LOCALE_STORAGE_KEY,
  buildLocaleDefinitions,
  formatLocaleOptionLabel,
  resolveSupportedLocale,
  type LocaleDefinition,
  type PluginLocale,
} from '@familyclaw/user-core';

const SHELL_MESSAGES = {
  'zh-CN': {
    'auth.loading': '正在检查登录状态...',
    'login.welcome': '欢迎来到智能家庭空间',
    'login.subtitle': '一个温暖、智能、关怀的家庭助手，让每一天都充满可能',
    'login.feature1': '智能对话助手',
    'login.feature2': '家庭记忆中心',
    'login.feature3': '隐私安全保障',
    'login.title': '登录',
    'login.formSubtitle': '使用您的家庭账号进入',
    'login.username': '用户名',
    'login.usernamePlaceholder': '请输入用户名',
    'login.password': '密码',
    'login.passwordPlaceholder': '请输入密码',
    'login.loggingIn': '登录中...',
    'login.submit': '进入家庭空间',
    'login.footer': '让科技温暖每个家庭',
  },
  'en-US': {
    'auth.loading': 'Checking your session...',
    'login.welcome': 'Welcome to Your Smart Home',
    'login.subtitle': 'A warm, intelligent family assistant that makes every day possible',
    'login.feature1': 'Smart Conversation',
    'login.feature2': 'Family Memories',
    'login.feature3': 'Privacy & Security',
    'login.title': 'Sign In',
    'login.formSubtitle': 'Enter with your family account',
    'login.username': 'Username',
    'login.usernamePlaceholder': 'Enter your username',
    'login.password': 'Password',
    'login.passwordPlaceholder': 'Enter your password',
    'login.loggingIn': 'Signing in...',
    'login.submit': 'Enter Family Space',
    'login.footer': 'Technology that warms every family',
  },
} as const;

export type ShellMessageKey = keyof typeof SHELL_MESSAGES['zh-CN'];

type I18nContextValue = {
  locale: string;
  locales: LocaleDefinition[];
  setLocale: (id: string) => void;
  t: (key: ShellMessageKey) => string;
  replacePluginLocales: (items: PluginLocale[]) => void;
  formatLocaleLabel: (definition: Pick<LocaleDefinition, 'id' | 'nativeLabel'>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function getStoredLocale(localeDefinitions: LocaleDefinition[]) {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE_ID;
  }

  try {
    return resolveSupportedLocale(
      window.localStorage.getItem(LOCALE_STORAGE_KEY),
      localeDefinitions,
      DEFAULT_LOCALE_ID,
    );
  } catch {
    return DEFAULT_LOCALE_ID;
  }
}

export function I18nProvider(props: { children: ReactNode }) {
  const [pluginLocales, setPluginLocales] = useState<PluginLocale[]>([]);
  const locales = useMemo(() => buildLocaleDefinitions(pluginLocales), [pluginLocales]);
  const [locale, setLocaleState] = useState(() => getStoredLocale(buildLocaleDefinitions([])));

  useEffect(() => {
    setLocaleState(current => resolveSupportedLocale(current, locales, DEFAULT_LOCALE_ID));
  }, [locales]);

  const setLocale = useCallback((id: string) => {
    const nextLocale = resolveSupportedLocale(id, locales, DEFAULT_LOCALE_ID);
    setLocaleState(nextLocale);

    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale);
    } catch {
      // 忽略本地持久化失败，不阻塞语言切换
    }
  }, [locales]);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const replacePluginLocales = useCallback((items: PluginLocale[]) => {
    setPluginLocales(items);
  }, []);

  const t = useCallback((key: ShellMessageKey) => {
    const localeDefinition = locales.find(item => item.id === locale);
    const pluginMessage = localeDefinition?.messages?.[key];
    if (typeof pluginMessage === 'string' && pluginMessage.trim()) {
      return pluginMessage;
    }

    const builtinLocale = locale.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
    return SHELL_MESSAGES[builtinLocale][key] ?? SHELL_MESSAGES['zh-CN'][key] ?? key;
  }, [locale, locales]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      locales,
      setLocale,
      t,
      replacePluginLocales,
      formatLocaleLabel: definition => formatLocaleOptionLabel(definition),
    }),
    [locale, locales, replacePluginLocales, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{props.children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n 必须在 I18nProvider 内使用');
  }
  return context;
}
