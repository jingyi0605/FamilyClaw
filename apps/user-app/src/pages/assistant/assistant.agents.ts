import type { AgentStatus, AgentSummary, AgentType } from './assistant.types';

export function getAgentTypeLabel(agentType: AgentType): string {
  switch (agentType) {
    case 'butler':
      return '主管家';
    case 'nutritionist':
      return '营养师';
    case 'fitness_coach':
      return '健身教练';
    case 'study_coach':
      return '学习教练';
    case 'custom':
      return '自定义角色';
    default:
      return 'Agent';
  }
}

export function getAgentTypeEmoji(agentType: AgentType): string {
  switch (agentType) {
    case 'butler':
      return '🧑';
    case 'nutritionist':
      return '🥗';
    case 'fitness_coach':
      return '🏋️';
    case 'study_coach':
      return '📚';
    case 'custom':
      return '✨';
    default:
      return '🤖';
  }
}

export function getAgentStatusLabel(status: AgentStatus): string {
  switch (status) {
    case 'active':
      return '启用中';
    case 'inactive':
      return '已停用';
    case 'draft':
      return '草稿';
    default:
      return '未知';
  }
}

export function isConversationAgent(agent: AgentSummary): boolean {
  return agent.status === 'active' && agent.conversation_enabled;
}

export function pickDefaultConversationAgent(agents: AgentSummary[]): AgentSummary | null {
  const candidates = agents.filter(isConversationAgent).sort((left, right) => left.sort_order - right.sort_order);
  return candidates.find(agent => agent.default_entry) ?? candidates.find(agent => agent.is_primary) ?? candidates[0] ?? null;
}
