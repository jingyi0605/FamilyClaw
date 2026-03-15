import type { AssistantLocale } from './assistant.types';

type AssistantCopyKey =
  | 'nav.assistant'
  | 'settings.ai'
  | 'assistant.newChat'
  | 'assistant.inputPlaceholder'
  | 'assistant.send'
  | 'assistant.context'
  | 'assistant.currentFamily'
  | 'assistant.currentAgent'
  | 'assistant.recentMemories'
  | 'assistant.quickActions'
  | 'assistant.askFollow'
  | 'assistant.noSessions'
  | 'assistant.noSessionsHint'
  | 'assistant.welcome'
  | 'assistant.welcomeHint'
  | 'assistant.noAgents'
  | 'assistant.noAgentsHint';

const zhCN: Record<AssistantCopyKey, string> = {
  'nav.assistant': '对话',
  'settings.ai': 'AI 配置',
  'assistant.newChat': '新对话',
  'assistant.inputPlaceholder': '输入你的问题...',
  'assistant.send': '发送',
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
};

const enUS: Record<AssistantCopyKey, string> = {
  'nav.assistant': 'Conversation',
  'settings.ai': 'AI Settings',
  'assistant.newChat': 'New Chat',
  'assistant.inputPlaceholder': 'Ask me anything...',
  'assistant.send': 'Send',
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
};

export function normalizeAssistantLocale(localeId: string | null | undefined): AssistantLocale {
  return typeof localeId === 'string' && localeId.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
}

export function createAssistantTranslator(localeId: AssistantLocale) {
  const messages = localeId === 'en-US' ? enUS : zhCN;
  return function translate(key: AssistantCopyKey) {
    return messages[key];
  };
}
