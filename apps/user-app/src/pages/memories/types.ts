import type { Member } from '@familyclaw/user-core';

export type { Member };

export type MemoryType = 'fact' | 'event' | 'preference' | 'relation' | 'growth';
export type MemoryStatus = 'active' | 'pending_review' | 'invalidated' | 'deleted';
export type MemoryVisibility = 'public' | 'family' | 'private' | 'sensitive';

export type MemoryCard = {
  id: string;
  household_id: string;
  memory_type: MemoryType;
  title: string;
  summary: string;
  normalized_text: string | null;
  content: Record<string, unknown> | null;
  status: MemoryStatus;
  visibility: MemoryVisibility;
  importance: number;
  confidence: number;
  subject_member_id: string | null;
  source_event_id: string | null;
  dedupe_key: string | null;
  effective_at: string | null;
  last_observed_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  invalidated_at: string | null;
  related_members: Array<{
    memory_id: string;
    member_id: string;
    relation_role: string;
  }>;
};

export type MemoryCardRevision = {
  id: string;
  memory_id: string;
  revision_no: number;
  action: string;
  before_json: string | null;
  after_json: string | null;
  reason: string | null;
  actor_type: string;
  actor_id: string | null;
  created_at: string;
};

export type OwnerScope = 'household' | 'member';
export type TriggerType = 'schedule' | 'heartbeat';
export type ScheduleType = 'daily' | 'interval' | 'cron' | 'once';
export type TargetType = 'plugin_job' | 'agent_reminder' | 'system_notice';
export type RuleType = 'none' | 'context_insight' | 'presence' | 'device_summary';
export type TaskStatus = 'active' | 'paused' | 'error' | 'invalid_dependency';
export type RunStatus = 'queued' | 'dispatching' | 'succeeded' | 'failed' | 'skipped' | 'suppressed';
export type TriggerSource = 'schedule' | 'heartbeat' | 'manual_retry';

export type ScheduledTaskDefinition = {
  id: string;
  household_id: string;
  owner_scope: OwnerScope;
  owner_member_id: string | null;
  created_by_account_id: string;
  last_modified_by_account_id: string;
  code: string;
  name: string;
  description: string | null;
  trigger_type: TriggerType;
  schedule_type: ScheduleType | null;
  schedule_expr: string | null;
  heartbeat_interval_seconds: number | null;
  timezone: string;
  target_type: TargetType;
  target_ref_id: string | null;
  rule_type: RuleType;
  rule_config: Record<string, unknown>;
  payload_template: Record<string, unknown>;
  cooldown_seconds: number;
  quiet_hours_policy: 'allow' | 'suppress' | 'delay';
  enabled: boolean;
  status: TaskStatus;
  last_run_at: string | null;
  last_result: string | null;
  consecutive_failures: number;
  next_run_at: string | null;
  next_heartbeat_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ScheduledTaskDefinitionCreate = {
  household_id: string;
  owner_scope: OwnerScope;
  owner_member_id?: string | null;
  code: string;
  name: string;
  description?: string | null;
  trigger_type: TriggerType;
  schedule_type?: ScheduleType | null;
  schedule_expr?: string | null;
  heartbeat_interval_seconds?: number | null;
  timezone?: string | null;
  target_type: TargetType;
  target_ref_id?: string | null;
  rule_type?: RuleType;
  rule_config?: Record<string, unknown>;
  payload_template?: Record<string, unknown>;
  cooldown_seconds?: number;
  quiet_hours_policy?: 'allow' | 'suppress' | 'delay';
  enabled?: boolean;
};

export type ScheduledTaskDefinitionUpdate = {
  owner_scope?: OwnerScope;
  owner_member_id?: string | null;
  name?: string;
  description?: string | null;
  schedule_type?: ScheduleType | null;
  schedule_expr?: string | null;
  heartbeat_interval_seconds?: number | null;
  timezone?: string | null;
  target_type?: TargetType | null;
  target_ref_id?: string | null;
  rule_type?: RuleType | null;
  rule_config?: Record<string, unknown> | null;
  payload_template?: Record<string, unknown> | null;
  cooldown_seconds?: number | null;
  quiet_hours_policy?: 'allow' | 'suppress' | 'delay' | null;
  enabled?: boolean | null;
  status?: TaskStatus | null;
};

export type ScheduledTaskRun = {
  id: string;
  task_definition_id: string;
  household_id: string;
  owner_scope: OwnerScope;
  owner_member_id: string | null;
  trigger_source: TriggerSource;
  scheduled_for: string | null;
  status: RunStatus;
  idempotency_key: string;
  evaluation_snapshot: Record<string, unknown>;
  dispatch_payload: Record<string, unknown>;
  target_type: TargetType;
  target_ref_id: string | null;
  target_run_id: string | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};
