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
import { PAGE_MESSAGES } from './pageMessages';

const SHELL_MESSAGES = {
  'zh-CN': {
    'common.close': '关闭',
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
    'nav.home': '首页',
    'nav.assistant': '对话',
    'nav.family': '家庭',
    'nav.memories': '记忆',
    'nav.settings': '设置',
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
    'assistant.noSessionsHint': '点击“新对话”开始和助手聊天',
    'assistant.welcome': '开始一段新对话',
    'assistant.welcomeHint': '你可以直接提问，也可以先切换到更适合当前问题的 Agent',
    'assistant.noAgents': '还没有可对话的 Agent',
    'assistant.noAgentsHint': '先在 AI 配置里启用至少一个可对话的 Agent。',
      'family.overview': '家庭概览',
      'family.rooms': '房间',
      'family.devices': '设备',
      'family.members': '成员',
      'family.relationships': '关系',
    'family.name': '家庭名称',
    'family.timezone': '时区',
    'family.language': '默认语言',
    'family.mode': '家庭模式',
    'family.privacy': '隐私模式',
    'family.services': '已开启的服务',
    'room.devices': '设备',
    'room.active': '活跃',
    'room.idle': '空闲',
    'room.sensitive': '隐私区域',
    'member.atHome': '在家',
    'member.away': '外出',
    'member.resting': '休息中',
    'member.edit': '编辑',
    'member.preferences': '偏好',
    'common.save': '保存',
    'common.create': '创建',
    'common.cancel': '取消',
    'common.edit': '编辑',
    'common.currentHousehold': '当前家庭',
    'common.userMenu': '用户菜单',
    'common.notLoggedIn': '未登录',
    'common.logout': '退出登录',
    'common.expand': '展开',
    'common.collapse': '收起',
    'common.saving': '正在保存...',
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
    'settings.title': '设置',
    'settings.ai': 'AI 配置',
    'settings.nav.appearance.label': '外观主题',
    'settings.nav.appearance.desc': '切换主题并预览当前风格',
    'settings.nav.ai.label': 'AI 配置',
    'settings.nav.ai.desc': '管理提供商、管家和 Agent',
    'settings.nav.language.label': '语言与地区',
    'settings.nav.language.desc': '调整界面语言和时区',
    'settings.nav.notifications.label': '通知偏好',
    'settings.nav.notifications.desc': '设置提醒方式和免打扰时段',
    'settings.nav.accessibility.label': '长辈友好',
    'settings.nav.accessibility.desc': '切换更大字号和更高对比',
    'settings.nav.integrations.label': '设备与集成',
          'settings.nav.integrations.desc': '管理设备与插件同步',
    'settings.nav.channelAccess.label': '通讯平台接入',
    'settings.nav.channelAccess.desc': '接入 Telegram、Discord 等外部平台',
    'settings.nav.plugins.label': '插件管理',
    'settings.nav.plugins.desc': '查看和管理已安装插件',
    'settings.nav.accounts.label': '账号管理',
    'settings.nav.accounts.desc': '管理家庭账号与登录凭证',
    // 仪表盘/首页标签页
    'dashboard.title': '仪表盘',
    'dashboard.tab.home': '主页',
    'dashboard.tab.add': '添加标签页',
    // 聊天页面标签页
    'assistant.tab.personal': '个人聊天',
    'assistant.tab.public': '公共聊天',
    'assistant.tab.moments': '家人圈',
    'assistant.tab.comingSoonTitle': '功能开发中',
    'assistant.tab.comingSoonDesc': '该功能正在紧张开发中，敬请期待！',
    'settings.appearance.title': '主题模式',
    'settings.appearance.loading': '正在读取当前家庭可用的主题...',
    'settings.appearance.noAvailableThemes': '当前家庭没有启用可选主题，界面已暂时回退到默认主题。',
    'settings.appearance.themeDisabledNotice': '你之前选择的主题“{theme}”已在当前家庭停用，系统已自动切换到可用主题。',
    'settings.appearance.disabledReason': '停用原因：{reason}',
    'settings.language.title': '语言与地区',
    'settings.language.interface': '界面语言',
    'settings.language.timezone': '时区',
    'settings.language.localeSaved': '界面语言已更新。',
    'settings.language.timezoneSaved': '时区已更新。',
    'settings.language.saveFailed': '保存语言设置失败',
    'settings.language.noHousehold': '请先选择家庭。',
    'settings.notifications.title': '通知偏好',
    'settings.notifications.channel': '通知方式',
    'settings.notifications.channelBrowserAndInApp': '浏览器通知 + 站内消息',
    'settings.notifications.channelInAppOnly': '仅站内消息',
    'settings.notifications.channelOff': '全部关闭',
    'settings.notifications.channelHint': '目前默认会通过浏览器通知和站内消息提醒你，后续会支持更多选择。',
    'settings.notifications.quietHours': '免打扰',
    'settings.notifications.quietHoursDesc': '开启后，系统会在 {start}-{end} 之间尽量不打扰你',
    'settings.notifications.scope': '通知范围',
    'settings.notifications.scopeAll': '全部通知',
    'settings.notifications.scopeUrgent': '仅紧急通知',
    'settings.notifications.scopeMine': '仅与我相关',
    'settings.notifications.info': '你现在可以设置免打扰时段。通知方式和提醒范围会在后续版本里继续补充。',
    'settings.notifications.scopeHint': '通知范围后续会开放自定义，现在先按默认方式提醒。',
    'settings.notifications.loading': '正在保存...',
    'settings.accessibility.title': '长辈友好',
    'settings.accessibility.elderMode': '启用长辈友好模式',
    'settings.accessibility.elderModeDesc': '切换到更大字号和更高对比度',
    'settings.accessibility.elderModeUnavailable': '当前家庭没有启用长辈模式主题，所以这里暂时不能打开。',
    'settings.accessibility.elderModeDisabledReason': '当前家庭没有启用长辈模式主题。停用原因：{reason}',
    'settings.accessibility.previewTitle': '预览效果',
    'settings.accessibility.previewEnabled': '长辈友好模式已开启，界面会使用更大的字号和更高的对比度。',
    'settings.accessibility.previewDisabled': '当前是标准模式。开启后会更适合年长用户阅读和操作。',
    'settings.guide.replayLabel': '重新查看应用导览',
    'settings.guide.replayDesc': '如果你想再快速回顾首页、家庭、对话、记忆和设置这几块入口，可以从这里重新走一遍。',
    'settings.guide.replayAction': '重新查看导览',
    'settings.status.saved': '设置已保存。',
    'settings.error.loadFailed': '加载设置失败',
    'settings.error.saveFailed': '保存设置失败',
    'userGuide.badge': '新手导览',
    'userGuide.progress': '第 {current} / {total} 步',
    'userGuide.actions.previous': '上一步',
    'userGuide.actions.next': '下一步',
    'userGuide.actions.finish': '完成导览',
    'userGuide.actions.skip': '暂时跳过',
    'userGuide.status.locating': '正在等待当前页面稳定下来...',
    'userGuide.status.completing': '正在保存你的导览状态...',
    'userGuide.error.loadFailed': '加载导览状态失败',
    'userGuide.error.saveFailed': '保存导览状态失败',
    'userGuide.error.navigateFailed': '导览跳转失败，请稍后再试',
    'userGuide.home.title': '先看首页，今天发生了什么一眼就能知道',
    'userGuide.home.content': '这里会汇总家庭状态、快捷入口和当天最值得先处理的卡片，第一次进入应用先从这里熟悉最省事。',
    'userGuide.family.title': '家庭页负责把人、房间和关系放在一起看',
    'userGuide.family.content': '之后你可以在这里继续管理成员、房间、设备和关系结构。第一轮导览先帮你知道入口在哪，不会把所有细节一次灌给你。',
    'userGuide.assistant.title': '对话入口在这里，后面会继续补完整能力',
    'userGuide.assistant.content': '现在这页还是过渡版本，但它会是你之后和家庭助手互动的主入口，所以先记住它的位置。',
    'userGuide.memories.title': '记忆页用来回看家庭事实、事件和偏好',
    'userGuide.memories.content': '当你想确认某条家庭记忆是否存在、想纠正内容，或者想知道系统记住了什么，就从这里进入最直接。',
    'userGuide.settings.title': '设置页里可以重新打开这套导览',
    'userGuide.settings.content': '主题、语言、通知等体验设置都在这里。以后如果你想再快速回顾应用入口，也可以直接从这个按钮重新开始。',
    'locale.source.builtin': '内置',
    'locale.source.official': '官方',
    'locale.source.thirdParty': '第三方',
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
    'nav.home': 'Home',
    'nav.assistant': 'Chat',
    'nav.family': 'Family',
    'nav.memories': 'Memories',
    'nav.settings': 'Settings',
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
      'family.overview': 'Overview',
      'family.rooms': 'Rooms',
      'family.devices': 'Devices',
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
    'common.create': 'Create',
    'common.cancel': 'Cancel',
    'common.close': 'Close',
    'common.edit': 'Edit',
    'common.currentHousehold': 'Current Household',
    'common.userMenu': 'User Menu',
    'common.notLoggedIn': 'Not signed in',
    'common.logout': 'Sign Out',
    'common.expand': 'Expand',
    'common.collapse': 'Collapse',
    'common.saving': 'Saving...',
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
    'settings.title': 'Settings',
    'settings.ai': 'AI Settings',
    'settings.nav.appearance.label': 'Appearance',
    'settings.nav.appearance.desc': 'Switch themes and preview the current style',
    'settings.nav.ai.label': 'AI Settings',
    'settings.nav.ai.desc': 'Manage providers, butlers, and agents',
    'settings.nav.language.label': 'Language & Region',
    'settings.nav.language.desc': 'Adjust the interface language and timezone',
    'settings.nav.notifications.label': 'Notifications',
    'settings.nav.notifications.desc': 'Choose reminders and quiet hours',
    'settings.nav.accessibility.label': 'Accessibility',
    'settings.nav.accessibility.desc': 'Use larger text and higher contrast',
    'settings.nav.integrations.label': 'Devices & Integrations',
          'settings.nav.integrations.desc': 'Manage device and plugin sync',
    'settings.nav.channelAccess.label': 'Channel Access',
    'settings.nav.channelAccess.desc': 'Connect Telegram, Discord, and other external platforms',
    'settings.nav.plugins.label': 'Plugins',
    'settings.nav.plugins.desc': 'Review and manage installed plugins',
    'settings.nav.accounts.label': 'Account Management',
    'settings.nav.accounts.desc': 'Manage family accounts and credentials',
    // Dashboard/Home tabs
    'dashboard.title': 'Dashboard',
    'dashboard.tab.home': 'Home',
    'dashboard.tab.add': 'Add Tab',
    // Assistant tabs
    'assistant.tab.personal': 'Personal Chat',
    'assistant.tab.public': 'Public Chat',
    'assistant.tab.moments': 'Moments',
    'assistant.tab.comingSoonTitle': 'Coming Soon',
    'assistant.tab.comingSoonDesc': 'This feature is under development. Stay tuned!',
    'settings.appearance.title': 'Theme Mode',
    'settings.appearance.loading': 'Loading the themes available to this household...',
    'settings.appearance.noAvailableThemes': 'No selectable themes are enabled for this household. The interface has fallen back to the default theme for now.',
    'settings.appearance.themeDisabledNotice': 'Your previously selected theme "{theme}" has been disabled for this household, so the system switched to an available theme automatically.',
    'settings.appearance.disabledReason': 'Reason: {reason}',
    'settings.language.title': 'Language & Region',
    'settings.language.interface': 'Interface Language',
    'settings.language.timezone': 'Timezone',
    'settings.language.localeSaved': 'Interface language updated.',
    'settings.language.timezoneSaved': 'Timezone updated.',
    'settings.language.saveFailed': 'Failed to save language settings',
    'settings.language.noHousehold': 'Please select a household first.',
    'settings.notifications.title': 'Notifications',
    'settings.notifications.channel': 'Delivery Method',
    'settings.notifications.channelBrowserAndInApp': 'Browser notifications + in-app inbox',
    'settings.notifications.channelInAppOnly': 'In-app inbox only',
    'settings.notifications.channelOff': 'Turn everything off',
    'settings.notifications.channelHint': 'For now, reminders are sent through browser notifications and in-app messages by default. More options will come later.',
    'settings.notifications.quietHours': 'Quiet Hours',
    'settings.notifications.quietHoursDesc': 'When enabled, the system tries not to disturb you between {start} and {end}',
    'settings.notifications.scope': 'Notification Scope',
    'settings.notifications.scopeAll': 'All notifications',
    'settings.notifications.scopeUrgent': 'Urgent only',
    'settings.notifications.scopeMine': 'Only items related to me',
    'settings.notifications.info': 'You can set quiet hours now. Delivery methods and reminder scope will be expanded in a later update.',
    'settings.notifications.scopeHint': 'Custom reminder scope will be available later. For now, the default reminder range is used.',
    'settings.notifications.loading': 'Saving...',
    'settings.accessibility.title': 'Accessibility',
    'settings.accessibility.elderMode': 'Enable senior-friendly mode',
    'settings.accessibility.elderModeDesc': 'Switch to larger text and stronger contrast',
    'settings.accessibility.elderModeUnavailable': 'The senior-friendly theme is not enabled for this household right now, so this toggle is temporarily unavailable.',
    'settings.accessibility.elderModeDisabledReason': 'The senior-friendly theme is not enabled for this household. Reason: {reason}',
    'settings.accessibility.previewTitle': 'Preview',
    'settings.accessibility.previewEnabled': 'Senior-friendly mode is on. The interface now uses larger text and stronger contrast.',
    'settings.accessibility.previewDisabled': 'The standard mode is active. Turning this on makes reading and interaction easier for older users.',
    'settings.guide.replayLabel': 'Replay the app tour',
    'settings.guide.replayDesc': 'If you want another quick walkthrough of Home, Family, Chat, Memories, and Settings, you can relaunch it here.',
    'settings.guide.replayAction': 'Replay guide',
    'settings.status.saved': 'Settings saved.',
    'settings.error.loadFailed': 'Failed to load settings',
    'settings.error.saveFailed': 'Failed to save settings',
    'userGuide.badge': 'App tour',
    'userGuide.progress': 'Step {current} / {total}',
    'userGuide.actions.previous': 'Back',
    'userGuide.actions.next': 'Next',
    'userGuide.actions.finish': 'Finish',
    'userGuide.actions.skip': 'Skip for now',
    'userGuide.status.locating': 'Waiting for this page to settle...',
    'userGuide.status.completing': 'Saving your guide progress...',
    'userGuide.error.loadFailed': 'Failed to load guide status',
    'userGuide.error.saveFailed': 'Failed to save guide status',
    'userGuide.error.navigateFailed': 'Guide navigation failed. Please try again later.',
    'userGuide.home.title': 'Start from Home so today’s household view is obvious',
    'userGuide.home.content': 'This page gathers family status, quick actions, and the most important cards for today. It is the fastest place to build your first mental model of the app.',
    'userGuide.family.title': 'Family keeps people, rooms, devices, and relationships together',
    'userGuide.family.content': 'You will come back here to manage members, rooms, devices, and family structure. The first tour only shows the entrance so the app stays easy to absorb.',
    'userGuide.assistant.title': 'Chat lives here, even though this page is still evolving',
    'userGuide.assistant.content': 'This screen is still a transition version, but it will become the main place to talk with your household assistant, so it is worth remembering now.',
    'userGuide.memories.title': 'Memories is where family facts, events, and preferences are reviewed',
    'userGuide.memories.content': 'Use this page when you want to confirm what the system remembers, check a fact, or correct a memory that no longer feels right.',
    'userGuide.settings.title': 'Settings also gives you a way to replay this tour later',
    'userGuide.settings.content': 'Theme, language, notifications, and other experience controls live here. If you ever want a fast refresher of the main app entrances, this is the button to use.',
    'locale.source.builtin': 'Built-in',
    'locale.source.official': 'Official',
    'locale.source.thirdParty': 'Third-party',
  },
} as const;

const BUILTIN_MESSAGES = {
  'zh-CN': {
    ...SHELL_MESSAGES['zh-CN'],
    ...PAGE_MESSAGES['zh-CN'],
  },
  'en-US': {
    ...SHELL_MESSAGES['en-US'],
    ...PAGE_MESSAGES['en-US'],
  },
} as const;

export type ShellMessageKey = string;
type ShellMessageParams = Record<string, string | number>;

type I18nContextValue = {
  locale: string;
  locales: LocaleDefinition[];
  setLocale: (id: string) => void;
  t: (key: ShellMessageKey, params?: ShellMessageParams) => string;
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

function formatMessage(template: string, params?: ShellMessageParams) {
  if (!params) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (full, key: string) => {
    const value = params[key];
    return value === undefined ? full : String(value);
  });
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

  const t = useCallback((key: ShellMessageKey, params?: ShellMessageParams) => {
    const localeDefinition = locales.find(item => item.id === locale);
    const pluginMessage = localeDefinition?.messages?.[key];
    if (typeof pluginMessage === 'string' && pluginMessage.trim()) {
      return formatMessage(pluginMessage, params);
    }

    const builtinLocale = locale.toLowerCase().startsWith('en')
      ? 'en-US'
      : locale.toLowerCase().startsWith('zh-tw')
        ? 'en-US'
        : 'zh-CN';
    const builtinMessages = BUILTIN_MESSAGES[builtinLocale] as Record<string, string>;
    return formatMessage(builtinMessages[key] ?? key, params);
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
