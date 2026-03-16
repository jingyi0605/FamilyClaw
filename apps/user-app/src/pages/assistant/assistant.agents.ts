import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type { AgentStatus, AgentSummary, AgentType } from './assistant.types';

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

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
      return getPageMessage(localeId, 'assistant.agentType.butler');
    case 'nutritionist':
      return getPageMessage(localeId, 'assistant.agentType.nutritionist');
    case 'fitness_coach':
      return getPageMessage(localeId, 'assistant.agentType.fitnessCoach');
    case 'study_coach':
      return getPageMessage(localeId, 'assistant.agentType.studyCoach');
    case 'custom':
      return getPageMessage(localeId, 'assistant.agentType.custom');
    default:
      return getPageMessage(localeId, 'assistant.agentType.default');
  }
}

export function getAgentTypeEmoji(agentType: AgentType): string {
  switch (agentType) {
    case 'butler':
      return '🏠';
    case 'nutritionist':
      return '🥗';
    case 'fitness_coach':
      return '💪';
    case 'study_coach':
      return '📘';
    case 'custom':
      return '✨';
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
      return getPageMessage(localeId, 'assistant.agentStatus.active');
    case 'inactive':
      return getPageMessage(localeId, 'assistant.agentStatus.inactive');
    case 'draft':
      return getPageMessage(localeId, 'assistant.agentStatus.draft');
    default:
      return getPageMessage(localeId, 'assistant.agentStatus.unknown');
  }
}

export function isConversationAgent(agent: AgentSummary): boolean {
  return agent.status === 'active' && agent.conversation_enabled;
}

export function pickDefaultConversationAgent(agents: AgentSummary[]): AgentSummary | null {
  const candidates = agents.filter(isConversationAgent).sort((left, right) => left.sort_order - right.sort_order);
  return candidates.find(agent => agent.default_entry) ?? candidates.find(agent => agent.is_primary) ?? candidates[0] ?? null;
}
