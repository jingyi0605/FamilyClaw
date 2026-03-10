/* ============================================================
 * 国际化 - 中文语言包
 * ============================================================ */
const zhCN = {
  /* 导航 */
  'nav.home': '首页',
  'nav.family': '家庭',
  'nav.assistant': '助手',
  'nav.memories': '记忆',
  'nav.settings': '设置',

  /* 首页 */
  'home.welcome': '欢迎回来',
  'home.greeting': '今天有什么可以帮到你的？',
  'home.familySummary': '家庭摘要',
  'home.roomStatus': '房间状态',
  'home.memberStatus': '成员状态',
  'home.recentEvents': '最近事件',
  'home.quickActions': '快捷操作',
  'home.membersAtHome': '在家',
  'home.activeRooms': '活跃房间',
  'home.devicesOnline': '设备在线',
  'home.alerts': '待处理',
  'home.noEvents': '暂时没有新事件',
  'home.noEventsHint': '当有新的家庭事件发生时，会显示在这里',

  /* 家庭 */
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

  /* 房间 */
  'room.devices': '个设备',
  'room.active': '活跃',
  'room.idle': '空闲',
  'room.sensitive': '隐私区域',

  /* 成员 */
  'member.atHome': '在家',
  'member.away': '外出',
  'member.resting': '休息中',
  'member.edit': '编辑',
  'member.preferences': '偏好',

  /* 关系 */
  'relationship.caregiving': '照护关系',
  'relationship.guardianship': '监护关系',
  'relationship.visibility': '可见范围',

  /* 助手 */
  'assistant.newChat': '新对话',
  'assistant.search': '搜索会话...',
  'assistant.inputPlaceholder': '输入你的问题...',
  'assistant.send': '发送',
  'assistant.context': '当前上下文',
  'assistant.currentFamily': '当前家庭',
  'assistant.recentMemories': '相关记忆',
  'assistant.quickActions': '快捷操作',
  'assistant.askFollow': '继续追问',
  'assistant.toReminder': '转为提醒',
  'assistant.toMemory': '写入记忆',
  'assistant.noSessions': '还没有对话',
  'assistant.noSessionsHint': '点击"新对话"开始和助手聊天',
  'assistant.welcome': '你好！我是你的家庭助手',
  'assistant.welcomeHint': '你可以问我任何关于家庭的问题，或者让我帮你执行操作',

  /* 记忆 */
  'memory.search': '搜索记忆...',
  'memory.facts': '事实',
  'memory.events': '事件',
  'memory.preferences': '偏好',
  'memory.relations': '关系',
  'memory.all': '全部',
  'memory.source': '来源',
  'memory.visibility': '可见范围',
  'memory.status': '状态',
  'memory.updatedAt': '更新时间',
  'memory.edit': '编辑',
  'memory.correct': '纠错',
  'memory.invalidate': '标记失效',
  'memory.merge': '合并',
  'memory.delete': '删除',
  'memory.noResults': '暂无记忆',
  'memory.noResultsHint': '家庭记忆会随着使用逐渐积累',
  'memory.detail': '记忆详情',

  /* 设置 */
  'settings.title': '设置',
  'settings.appearance': '外观主题',
  'settings.appearanceDesc': '切换浅色、深色或长辈友好模式',
  'settings.ai': 'AI 配置',
  'settings.aiDesc': '调整助手的回复风格、记忆引用和隐私控制',
  'settings.language': '语言与地区',
  'settings.languageDesc': '切换界面语言和日期时间格式',
  'settings.notifications': '通知偏好',
  'settings.notificationsDesc': '管理提醒方式、免打扰和通知范围',
  'settings.accessibility': '长辈友好模式',
  'settings.accessibilityDesc': '更大字号、更高对比度、更简洁的界面',
  'settings.integrations': '设备与集成',
  'settings.integrationsDesc': '管理智能家居设备和 Home Assistant 连接',

  /* 设置 - 外观 */
  'settings.appearance.theme': '主题模式',
  'settings.appearance.themeLight': '浅色',
  'settings.appearance.themeDark': '深色',
  'settings.appearance.themeElder': '长辈友好',
  'settings.appearance.current': '当前主题',

  /* 设置 - AI */
  'settings.ai.assistantName': '助手称呼',
  'settings.ai.replyTone': '回复语气',
  'settings.ai.replyLength': '回复长度',
  'settings.ai.outputLanguage': '输出语言',
  'settings.ai.useMemory': '引用家庭记忆',
  'settings.ai.useMemoryDesc': '允许助手在回答时参考家庭记忆中的信息',
  'settings.ai.suggestReminder': '主动建议提醒',
  'settings.ai.suggestReminderDesc': '允许助手根据对话内容主动建议创建提醒',
  'settings.ai.suggestScene': '推荐场景动作',
  'settings.ai.suggestSceneDesc': '允许助手根据情况推荐可执行的场景',
  'settings.ai.privacyLevel': '隐私级别',
  'settings.ai.advancedNote': '如需调整底层模型配置、供应商路由等高级设置，请前往管理控制台',

  /* 设置 - 语言 */
  'settings.language.interfaceLang': '界面语言',
  'settings.language.dateFormat': '日期格式',
  'settings.language.timeFormat': '时间格式',
  'settings.language.timezone': '时区',

  /* 设置 - 通知 */
  'settings.notifications.method': '通知方式',
  'settings.notifications.dnd': '免打扰',
  'settings.notifications.scope': '通知范围',

  /* 设置 - 长辈友好 */
  'settings.accessibility.enable': '启用长辈友好模式',
  'settings.accessibility.enableDesc': '启用后界面会使用更大的字号、更高的对比度和更宽松的排版',
  'settings.accessibility.largeFont': '放大字号',
  'settings.accessibility.highContrast': '高对比度',
  'settings.accessibility.reducedDensity': '降低信息密度',

  /* 设置 - 设备与集成 */
  'settings.integrations.devices': '设备列表',
  'settings.integrations.haStatus': 'Home Assistant 连接状态',
  'settings.integrations.lastSync': '上次同步',
  'settings.integrations.syncNow': '立即同步',

  /* 家庭上下文 */
  'household.switch': '切换家庭',
  'household.current': '当前家庭',
  'household.none': '未选择家庭',

  /* 通用 */
  'common.save': '保存',
  'common.cancel': '取消',
  'common.edit': '编辑',
  'common.delete': '删除',
  'common.confirm': '确认',
  'common.loading': '加载中...',
  'common.retry': '重试',
  'common.back': '返回',
  'common.more': '更多',
  'common.viewAll': '查看全部',
  'common.comingSoon': '即将推出',
};

export type MessageKey = keyof typeof zhCN;
export type LocaleMessages = Record<MessageKey, string>;
export default zhCN as LocaleMessages;
