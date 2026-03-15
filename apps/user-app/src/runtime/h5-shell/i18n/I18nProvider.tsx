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
    // 登录页
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
    // 导航
    'nav.assistant': '对话',
    'nav.family': '家庭',
    'nav.memories': '记忆',
    'nav.settings': '设置',
    // 助手页
    'assistant.newChat': '新对话',
    'assistant.inputPlaceholder': '输入你的问题...',
    'assistant.send': '发送',
    'assistant.sending': '发送中...',
    'assistant.context': '当前上下文',
    'assistant.currentFamily': '当前家庭',
    'assistant.currentAgent': '当前 Agent',
    'assistant.recentMemories': '相关记忆',
    'assistant.quickActions': '快捷操作',
    'assistant.askFollow': '继续追问',
    'assistant.noSessions': '还没有对话',
    'assistant.noSessionsHint': '点击"新对话"开始和助手聊天',
    'assistant.welcome': '开始一段新对话',
    'assistant.welcomeHint': '你可以直接提问，也可以先切换到更适合当前问题的 Agent',
    'assistant.noAgents': '还没有可对话的 Agent',
    'assistant.noAgentsHint': '先在 AI 配置里启用至少一个可对话的 Agent。',
    'settings.ai': 'AI 配置',
    // 家庭页
    'family.overview': '家庭概览',
    'family.rooms': '房间',
    'family.members': '成员',
    'family.relationships': '关系',
    'family.name': '家庭名称',
    'family.timezone': '时区',
    'family.language': '默认语言',
    'family.mode': '家庭模式',
    'family.privacy': '隐私模式',
    'family.services': '已开启的服务',
    'room.devices': '个设备',
    'room.active': '活跃',
    'room.idle': '空闲',
    'room.sensitive': '隐私区域',
    'member.atHome': '在家',
    'member.away': '外出',
    'member.resting': '休息中',
    'member.edit': '编辑',
    'member.preferences': '偏好',
    'common.save': '保存',
    'common.cancel': '取消',
    'common.edit': '编辑',
    // 首页
    'home.welcome': '欢迎回来',
    'home.greeting': '今天有什么可以帮到你的？',
    'home.roomStatus': '房间状态',
    'home.memberStatus': '成员状态',
    'home.recentEvents': '最近事件',
    'home.quickActions': '快捷操作',
    'home.membersAtHome': '在家',
    'home.activeRooms': '活跃房间',
    'home.devicesOnline': '设备在线',
    'home.alerts': '待处理',
    'home.noEventsHint': '当有新的家庭事件发生时，会显示在这里',
  },
  'en-US': {
    // Login
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
    // Navigation
    'nav.assistant': 'Chat',
    'nav.family': 'Family',
    'nav.memories': 'Memories',
    'nav.settings': 'Settings',
    // Assistant
    'assistant.newChat': 'New Chat',
    'assistant.inputPlaceholder': 'Ask me anything...',
    'assistant.send': 'Send',
    'assistant.sending': 'Sending...',
    'assistant.context': 'Context',
    'assistant.currentFamily': 'Current Family',
    'assistant.currentAgent': 'Current Agent',
    'assistant.recentMemories': 'Related Memories',
    'assistant.quickActions': 'Quick Actions',
    'assistant.askFollow': 'Follow up',
    'assistant.noSessions': 'No conversations yet',
    'assistant.noSessionsHint': 'Click "New Chat" to start talking',
    'assistant.welcome': 'Start a new conversation',
    'assistant.welcomeHint': 'Ask directly, or switch to the agent that fits this topic better first',
    'assistant.noAgents': 'No conversation agents available',
    'assistant.noAgentsHint': 'Enable at least one conversation-ready agent in AI Config first.',
    'settings.ai': 'AI Settings',
    // Family page
    'family.overview': 'Overview',
    'family.rooms': 'Rooms',
    'family.members': 'Members',
    'family.relationships': 'Relationships',
    'family.name': 'Family Name',
    'family.timezone': 'Timezone',
    'family.language': 'Default Language',
    'family.mode': 'Family Mode',
    'family.privacy': 'Privacy Mode',
    'family.services': 'Active Services',
    'room.devices': 'devices',
    'room.active': 'Active',
    'room.idle': 'Idle',
    'room.sensitive': 'Private Area',
    'member.atHome': 'Home',
    'member.away': 'Away',
    'member.resting': 'Resting',
    'member.edit': 'Edit',
    'member.preferences': 'Preferences',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.edit': 'Edit',
    // Home
    'home.welcome': 'Welcome back',
    'home.greeting': 'How can I help you today?',
    'home.roomStatus': 'Room Status',
    'home.memberStatus': 'Member Status',
    'home.recentEvents': 'Recent Events',
    'home.quickActions': 'Quick Actions',
    'home.membersAtHome': 'At Home',
    'home.activeRooms': 'Active Rooms',
    'home.devicesOnline': 'Online Devices',
    'home.alerts': 'Alerts',
    'home.noEventsHint': 'New family events will appear here',
  },
} as const;

export type ShellMessageKey = string;

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
    const builtinMessages = SHELL_MESSAGES[builtinLocale] as Record<string, string>;
    const fallbackMessages = SHELL_MESSAGES['zh-CN'] as Record<string, string>;
    return builtinMessages[key] ?? fallbackMessages[key] ?? key;
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
    throw new Error('useI18n 必须在 I18nProvider 内使用。');
  }
  return context;
}
