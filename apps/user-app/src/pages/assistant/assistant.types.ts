import type { ThemeId } from '@familyclaw/user-core';

export type AssistantLocale = 'zh-CN' | 'en-US';
export type AssistantThemeId = ThemeId;

export type FamilyQaFactReference = {
  type: string;
  label: string;
  source: string;
  occurred_at: string | null;
  visibility: string;
  inferred: boolean;
  extra: Record<string, unknown>;
};

export type FamilyQaSuggestionsResponse = {
  household_id: string;
  effective_agent_id: string | null;
  effective_agent_type: string | null;
  effective_agent_name: string | null;
  items: Array<{
    question: string;
    answer_type: string;
    reason: string;
  }>;
};

export type ConversationSessionMode = 'family_chat' | 'agent_bootstrap' | 'agent_config';
export type ConversationSessionStatus = 'active' | 'archived' | 'failed';
export type ConversationMessageRole = 'user' | 'assistant' | 'system';
export type ConversationMessageType = 'text' | 'error' | 'memory_candidate_notice';
export type ConversationMessageStatus = 'pending' | 'streaming' | 'completed' | 'failed';
export type ConversationActionCategory = 'memory' | 'config' | 'action';
export type ConversationActionPolicyMode = 'ask' | 'notify' | 'auto';
export type ConversationActionStatus =
  | 'pending_confirmation'
  | 'completed'
  | 'failed'
  | 'dismissed'
  | 'undone'
  | 'undo_failed';
export type ConversationProposalPolicyCategory = 'ask' | 'notify' | 'auto' | 'ignore';
export type ConversationProposalStatus =
  | 'pending_policy'
  | 'pending_confirmation'
  | 'completed'
  | 'dismissed'
  | 'ignored'
  | 'failed';

export type ConversationMessage = {
  id: string;
  session_id: string;
  request_id: string | null;
  seq: number;
  role: ConversationMessageRole;
  message_type: ConversationMessageType;
  content: string;
  status: ConversationMessageStatus;
  effective_agent_id: string | null;
  ai_provider_code: string | null;
  ai_trace_id: string | null;
  degraded: boolean;
  error_code: string | null;
  facts: FamilyQaFactReference[];
  suggestions: string[];
  created_at: string;
  updated_at: string;
};

export type ConversationActionRecord = {
  id: string;
  session_id: string;
  request_id: string | null;
  trigger_message_id: string | null;
  source_message_id: string | null;
  intent: string;
  action_category: ConversationActionCategory;
  action_name: string;
  policy_mode: ConversationActionPolicyMode;
  status: ConversationActionStatus;
  title: string;
  summary: string | null;
  target_ref: string | null;
  plan_payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
  undo_payload: Record<string, unknown>;
  created_at: string;
  executed_at: string | null;
  undone_at: string | null;
  updated_at: string;
};

export type ConversationProposalItem = {
  id: string;
  batch_id: string;
  proposal_kind: string;
  policy_category: ConversationProposalPolicyCategory;
  status: ConversationProposalStatus;
  title: string;
  summary: string | null;
  evidence_message_ids: string[];
  evidence_roles: string[];
  dedupe_key: string | null;
  confidence: number;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ScheduledTaskConversationProposalPayload = {
  draft_id: string;
  intent_summary: string;
  missing_fields: string[];
  missing_field_labels: string[];
  draft_payload: Record<string, unknown>;
  can_confirm: boolean;
  owner_summary: string | null;
  schedule_summary: string | null;
  target_summary: string | null;
  confirm_block_reason: string | null;
};

export type ConversationProposalBatch = {
  id: string;
  session_id: string;
  request_id: string | null;
  source_message_ids: string[];
  source_roles: string[];
  lane: Record<string, unknown>;
  status: ConversationProposalStatus | string;
  created_at: string;
  updated_at: string;
  items: ConversationProposalItem[];
};

export type ConversationSession = {
  id: string;
  household_id: string;
  requester_member_id: string | null;
  session_mode: ConversationSessionMode;
  active_agent_id: string | null;
  active_agent_name: string | null;
  active_agent_type: string | null;
  title: string;
  status: ConversationSessionStatus;
  last_message_at: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  latest_message_preview: string | null;
};

export type ConversationSessionDetail = ConversationSession & {
  messages: ConversationMessage[];
  memory_candidates: Array<Record<string, unknown>>;
  action_records: ConversationActionRecord[];
  proposal_batches: ConversationProposalBatch[];
};

export type ConversationSessionListResponse = {
  household_id: string;
  requester_member_id: string | null;
  items: ConversationSession[];
};

export type ConversationActionExecutionResponse = {
  action: ConversationActionRecord;
};

export type ConversationProposalExecutionResponse = {
  item: ConversationProposalItem;
  affected_target_id: string | null;
};

export type AgentAutonomousActionPolicy = {
  memory: 'ask' | 'notify' | 'auto';
  config: 'ask' | 'notify' | 'auto';
  action: 'ask' | 'notify' | 'auto';
};

export type AgentType = 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
export type AgentStatus = 'draft' | 'active' | 'inactive';

export type AgentSummary = {
  id: string;
  household_id: string;
  code: string;
  agent_type: AgentType;
  display_name: string;
  status: AgentStatus;
  is_primary: boolean;
  sort_order: number;
  summary: string | null;
  conversation_enabled: boolean;
  default_entry: boolean;
  updated_at: string;
};

export type AgentListResponse = {
  household_id: string;
  items: AgentSummary[];
};
