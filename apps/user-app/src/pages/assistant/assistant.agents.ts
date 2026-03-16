import type { AgentStatus, AgentSummary, AgentType } from './assistant.types';

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

function pickLocaleText(locale: string | undefined, values: {
  zhCN: string;
  zhTW: string;
  enUS: string;
}) {
  if (locale?.toLowerCase().startsWith('en')) {
    return values.enUS;
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return values.zhTW;
  }
  return values.zhCN;
}

export function getAgentTypeLabel(agentType: AgentType, locale?: string | TranslateFn): string {
  const translate = typeof locale === 'function' ? locale as TranslateFn : null;
  const localeId = typeof locale === 'string' ? locale : undefined;
  if (translate) {
    switch (agentType) {
      case 'butler':
        return translate('assistant.agentType.butler');
      case 'nutritionist':
        return translate('assistant.agentType.nutritionist');
      case 'fitness_coach':
        return translate('assistant.agentType.fitnessCoach');
      case 'study_coach':
        return translate('assistant.agentType.studyCoach');
      case 'custom':
        return translate('assistant.agentType.custom');
      default:
        return translate('assistant.agentType.default');
    }
  }
  switch (agentType) {
    case 'butler':
      return pickLocaleText(localeId, { zhCN: '家庭管家', zhTW: '家庭管家', enUS: 'Butler' });
    case 'nutritionist':
      return pickLocaleText(localeId, { zhCN: '营养师', zhTW: '營養師', enUS: 'Nutritionist' });
    case 'fitness_coach':
      return pickLocaleText(localeId, { zhCN: '健身教练', zhTW: '健身教練', enUS: 'Fitness Coach' });
    case 'study_coach':
      return pickLocaleText(localeId, { zhCN: '学习教练', zhTW: '學習教練', enUS: 'Study Coach' });
    case 'custom':
      return pickLocaleText(localeId, { zhCN: '自定义角色', zhTW: '自訂角色', enUS: 'Custom Role' });
    default:
      return 'Agent';
  }
}

export function getAgentTypeEmoji(agentType: AgentType): string {
  switch (agentType) {
    case 'butler':
      return '管';
    case 'nutritionist':
      return '营';
    case 'fitness_coach':
      return '健';
    case 'study_coach':
      return '学';
    case 'custom':
      return '定';
    default:
      return 'AI';
  }
}

export function getAgentStatusLabel(status: AgentStatus, locale?: string | TranslateFn): string {
  const translate = typeof locale === 'function' ? locale as TranslateFn : null;
  const localeId = typeof locale === 'string' ? locale : undefined;
  if (translate) {
    switch (status) {
      case 'active':
        return translate('assistant.agentStatus.active');
      case 'inactive':
        return translate('assistant.agentStatus.inactive');
      case 'draft':
        return translate('assistant.agentStatus.draft');
      default:
        return translate('assistant.agentStatus.unknown');
    }
  }
  switch (status) {
    case 'active':
      return pickLocaleText(localeId, { zhCN: '已启用', zhTW: '已啟用', enUS: 'Active' });
    case 'inactive':
      return pickLocaleText(localeId, { zhCN: '已停用', zhTW: '已停用', enUS: 'Disabled' });
    case 'draft':
      return pickLocaleText(localeId, { zhCN: '草稿', zhTW: '草稿', enUS: 'Draft' });
    default:
      return pickLocaleText(localeId, { zhCN: '未知', zhTW: '未知', enUS: 'Unknown' });
  }
}

export function isConversationAgent(agent: AgentSummary): boolean {
  return agent.status === 'active' && agent.conversation_enabled;
}

export function pickDefaultConversationAgent(agents: AgentSummary[]): AgentSummary | null {
  const candidates = agents.filter(isConversationAgent).sort((left, right) => left.sort_order - right.sort_order);
  return candidates.find(agent => agent.default_entry) ?? candidates.find(agent => agent.is_primary) ?? candidates[0] ?? null;
}
