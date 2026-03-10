/* ============================================================
 * 国际化 - 英文语言包
 * ============================================================ */
import type { LocaleMessages } from './zh-CN';

const enUS: LocaleMessages = {
  /* 导航 */
  'nav.home': 'Home',
  'nav.family': 'Family',
  'nav.assistant': 'Assistant',
  'nav.memories': 'Memories',
  'nav.settings': 'Settings',

  /* 首页 */
  'home.welcome': 'Welcome back',
  'home.greeting': 'How can I help you today?',
  'home.familySummary': 'Family Summary',
  'home.roomStatus': 'Room Status',
  'home.memberStatus': 'Member Status',
  'home.recentEvents': 'Recent Events',
  'home.quickActions': 'Quick Actions',
  'home.membersAtHome': 'At Home',
  'home.activeRooms': 'Active Rooms',
  'home.devicesOnline': 'Devices Online',
  'home.alerts': 'Pending',
  'home.noEvents': 'No new events',
  'home.noEventsHint': 'New family events will appear here',

  /* 家庭 */
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

  /* 房间 */
  'room.devices': 'devices',
  'room.active': 'Active',
  'room.idle': 'Idle',
  'room.sensitive': 'Private Area',

  /* 成员 */
  'member.atHome': 'At Home',
  'member.away': 'Away',
  'member.resting': 'Resting',
  'member.edit': 'Edit',
  'member.preferences': 'Preferences',

  /* 关系 */
  'relationship.caregiving': 'Caregiving',
  'relationship.guardianship': 'Guardianship',
  'relationship.visibility': 'Visibility',

  /* 助手 */
  'assistant.newChat': 'New Chat',
  'assistant.search': 'Search chats...',
  'assistant.inputPlaceholder': 'Ask me anything...',
  'assistant.send': 'Send',
  'assistant.context': 'Context',
  'assistant.currentFamily': 'Current Family',
  'assistant.recentMemories': 'Related Memories',
  'assistant.quickActions': 'Quick Actions',
  'assistant.askFollow': 'Follow up',
  'assistant.toReminder': 'Create Reminder',
  'assistant.toMemory': 'Save to Memory',
  'assistant.noSessions': 'No conversations yet',
  'assistant.noSessionsHint': 'Click "New Chat" to start talking',
  'assistant.welcome': 'Hi! I\'m your family assistant',
  'assistant.welcomeHint': 'Ask me anything about your family, or let me help you with tasks',

  /* 记忆 */
  'memory.search': 'Search memories...',
  'memory.facts': 'Facts',
  'memory.events': 'Events',
  'memory.preferences': 'Preferences',
  'memory.relations': 'Relations',
  'memory.all': 'All',
  'memory.source': 'Source',
  'memory.visibility': 'Visibility',
  'memory.status': 'Status',
  'memory.updatedAt': 'Updated',
  'memory.edit': 'Edit',
  'memory.correct': 'Correct',
  'memory.invalidate': 'Invalidate',
  'memory.merge': 'Merge',
  'memory.delete': 'Delete',
  'memory.noResults': 'No memories yet',
  'memory.noResultsHint': 'Memories will accumulate over time',
  'memory.detail': 'Memory Detail',

  /* 设置 */
  'settings.title': 'Settings',
  'settings.appearance': 'Appearance',
  'settings.appearanceDesc': 'Switch between light, dark, or elder-friendly mode',
  'settings.ai': 'AI Settings',
  'settings.aiDesc': 'Adjust assistant tone, memory usage, and privacy controls',
  'settings.language': 'Language & Region',
  'settings.languageDesc': 'Change interface language and date/time format',
  'settings.notifications': 'Notifications',
  'settings.notificationsDesc': 'Manage notification methods and do-not-disturb',
  'settings.accessibility': 'Elder-friendly Mode',
  'settings.accessibilityDesc': 'Larger fonts, higher contrast, and simpler layout',
  'settings.integrations': 'Devices & Integrations',
  'settings.integrationsDesc': 'Manage smart home devices and Home Assistant connection',

  /* 设置 - 外观 */
  'settings.appearance.theme': 'Theme',
  'settings.appearance.themeLight': 'Light',
  'settings.appearance.themeDark': 'Dark',
  'settings.appearance.themeElder': 'Elder-friendly',
  'settings.appearance.current': 'Current Theme',

  /* 设置 - AI */
  'settings.ai.assistantName': 'Assistant Name',
  'settings.ai.replyTone': 'Reply Tone',
  'settings.ai.replyLength': 'Reply Length',
  'settings.ai.outputLanguage': 'Output Language',
  'settings.ai.useMemory': 'Use Family Memories',
  'settings.ai.useMemoryDesc': 'Allow the assistant to reference family memories',
  'settings.ai.suggestReminder': 'Suggest Reminders',
  'settings.ai.suggestReminderDesc': 'Allow the assistant to suggest creating reminders',
  'settings.ai.suggestScene': 'Suggest Scenes',
  'settings.ai.suggestSceneDesc': 'Allow the assistant to recommend scene actions',
  'settings.ai.privacyLevel': 'Privacy Level',
  'settings.ai.advancedNote': 'For advanced model and provider settings, visit the Admin Console',

  /* 设置 - 语言 */
  'settings.language.interfaceLang': 'Interface Language',
  'settings.language.dateFormat': 'Date Format',
  'settings.language.timeFormat': 'Time Format',
  'settings.language.timezone': 'Timezone',

  /* 设置 - 通知 */
  'settings.notifications.method': 'Notification Method',
  'settings.notifications.dnd': 'Do Not Disturb',
  'settings.notifications.scope': 'Notification Scope',

  /* 设置 - 长辈友好 */
  'settings.accessibility.enable': 'Enable Elder-friendly Mode',
  'settings.accessibility.enableDesc': 'Uses larger fonts, higher contrast, and more spacious layout',
  'settings.accessibility.largeFont': 'Large Font',
  'settings.accessibility.highContrast': 'High Contrast',
  'settings.accessibility.reducedDensity': 'Reduced Density',

  /* 设置 - 设备与集成 */
  'settings.integrations.devices': 'Device List',
  'settings.integrations.haStatus': 'Home Assistant Status',
  'settings.integrations.lastSync': 'Last Sync',
  'settings.integrations.syncNow': 'Sync Now',

  /* 家庭上下文 */
  'household.switch': 'Switch Family',
  'household.current': 'Current Family',
  'household.none': 'No Family Selected',

  /* 通用 */
  'common.save': 'Save',
  'common.cancel': 'Cancel',
  'common.edit': 'Edit',
  'common.delete': 'Delete',
  'common.confirm': 'Confirm',
  'common.loading': 'Loading...',
  'common.retry': 'Retry',
  'common.back': 'Back',
  'common.more': 'More',
  'common.viewAll': 'View All',
  'common.comingSoon': 'Coming Soon',
};

export default enUS;
