import type { AgentStatus, AgentSummary, AgentType } from './types';

export function getAgentTypeLabel(agentType: AgentType): string {
  switch (agentType) {
    case 'butler':
      return '家庭管家';
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

export function getAgentStatusLabel(status: AgentStatus): string {
  switch (status) {
    case 'active':
      return '已启用';
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
  const candidates = agents
    .filter(isConversationAgent)
    .sort((left, right) => left.sort_order - right.sort_order);

  return (
    candidates.find(agent => agent.default_entry) ??
    candidates.find(agent => agent.is_primary) ??
    candidates[0] ??
    null
  );
}
