import { ApiError, createRequestClient } from '@familyclaw/user-core';
import type {
  AgentListResponse,
  ConversationActionExecutionResponse,
  ConversationProposalExecutionResponse,
  ConversationSessionDetail,
  ConversationSessionListResponse,
  FamilyQaSuggestionsResponse,
} from './assistant.types';

const request = createRequestClient({
  baseUrl: '/api/v1',
  timeoutMs: 8000,
  credentials: 'include',
});

export { ApiError };

export const assistantApi = {
  listAgents(householdId: string) {
    return request<AgentListResponse>(`/ai-config/${encodeURIComponent(householdId)}`);
  },
  getFamilyQaSuggestions(householdId: string, requesterMemberId?: string, agentId?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (requesterMemberId) {
      params.set('requester_member_id', requesterMemberId);
    }
    if (agentId) {
      params.set('agent_id', agentId);
    }
    return request<FamilyQaSuggestionsResponse>(`/family-qa/suggestions?${params.toString()}`);
  },
  createConversationSession(payload: {
    household_id: string;
    requester_member_id?: string;
    active_agent_id?: string;
    session_mode?: 'family_chat' | 'agent_bootstrap' | 'agent_config';
    title?: string;
  }) {
    return request<ConversationSessionDetail>('/conversations/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listConversationSessions(params: {
    household_id: string;
    requester_member_id?: string;
    limit?: number;
  }) {
    const query = new URLSearchParams({
      household_id: params.household_id,
      limit: String(params.limit ?? 50),
    });
    if (params.requester_member_id) {
      query.set('requester_member_id', params.requester_member_id);
    }
    return request<ConversationSessionListResponse>(`/conversations/sessions?${query.toString()}`, undefined, 20000);
  },
  getConversationSession(sessionId: string) {
    return request<ConversationSessionDetail>(
      `/conversations/sessions/${encodeURIComponent(sessionId)}`,
      undefined,
      20000,
    );
  },
  deleteConversationSession(sessionId: string) {
    return request<void>(`/conversations/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    });
  },
  confirmConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/confirm`,
      { method: 'POST' },
    );
  },
  dismissConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/dismiss`,
      { method: 'POST' },
    );
  },
  undoConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/undo`,
      { method: 'POST' },
    );
  },
  confirmConversationProposal(proposalItemId: string) {
    return request<ConversationProposalExecutionResponse>(
      `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/confirm`,
      { method: 'POST' },
    );
  },
  dismissConversationProposal(proposalItemId: string) {
    return request<ConversationProposalExecutionResponse>(
      `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/dismiss`,
      { method: 'POST' },
    );
  },
};
