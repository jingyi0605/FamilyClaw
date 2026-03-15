import { ApiError, createRequestClient, type PaginatedResponse } from '@familyclaw/user-core';
import { coreApiClient } from '../../runtime';
import type {
  MemoryCard,
  MemoryCardRevision,
  MemoryType,
  ScheduledTaskDefinition,
  ScheduledTaskDefinitionCreate,
  ScheduledTaskDefinitionUpdate,
  ScheduledTaskRun,
} from './types';

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

export { ApiError };

export const api = {
  ...coreApiClient,
  listMemoryCards(params: { householdId: string; memoryType?: MemoryType; pageSize?: number }) {
    const query = new URLSearchParams({
      household_id: params.householdId,
      page_size: String(params.pageSize ?? 100),
    });
    if (params.memoryType) {
      query.set('memory_type', params.memoryType);
    }
    return request<PaginatedResponse<MemoryCard>>(`/memories/cards?${query.toString()}`);
  },
  listMemoryCardRevisions(memoryId: string) {
    return request<{ items: MemoryCardRevision[] }>(`/memories/cards/${encodeURIComponent(memoryId)}/revisions`);
  },
  correctMemoryCard(memoryId: string, payload: {
    action: 'correct' | 'invalidate' | 'delete';
    title?: string | null;
    summary?: string | null;
    content?: Record<string, unknown> | null;
    visibility?: MemoryCard['visibility'] | null;
    status?: MemoryCard['status'] | null;
    importance?: number | null;
    confidence?: number | null;
    reason?: string | null;
  }) {
    return request<MemoryCard>(`/memories/cards/${encodeURIComponent(memoryId)}/corrections`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listScheduledTasks(params: {
    household_id: string;
    owner_scope?: 'household' | 'member';
    owner_member_id?: string;
    enabled?: boolean;
    trigger_type?: 'schedule' | 'heartbeat';
    target_type?: 'plugin_job' | 'agent_reminder' | 'system_notice';
    status?: 'active' | 'paused' | 'error' | 'invalid_dependency';
  }) {
    const query = new URLSearchParams({ household_id: params.household_id });
    if (params.owner_scope) query.set('owner_scope', params.owner_scope);
    if (params.owner_member_id) query.set('owner_member_id', params.owner_member_id);
    if (params.enabled !== undefined) query.set('enabled', String(params.enabled));
    if (params.trigger_type) query.set('trigger_type', params.trigger_type);
    if (params.target_type) query.set('target_type', params.target_type);
    if (params.status) query.set('status', params.status);
    return request<ScheduledTaskDefinition[]>(`/scheduled-tasks?${query.toString()}`);
  },
  createScheduledTask(payload: ScheduledTaskDefinitionCreate) {
    return request<ScheduledTaskDefinition>('/scheduled-tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateScheduledTask(taskId: string, payload: ScheduledTaskDefinitionUpdate) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  enableScheduledTask(taskId: string) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}/enable`, {
      method: 'POST',
    });
  },
  disableScheduledTask(taskId: string) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}/disable`, {
      method: 'POST',
    });
  },
  listScheduledTaskRuns(params: {
    household_id: string;
    task_definition_id?: string;
    owner_scope?: 'household' | 'member';
    owner_member_id?: string;
    status?: 'queued' | 'dispatching' | 'succeeded' | 'failed' | 'skipped' | 'suppressed';
    created_from?: string;
    created_to?: string;
    limit?: number;
  }) {
    const query = new URLSearchParams({ household_id: params.household_id });
    if (params.task_definition_id) query.set('task_definition_id', params.task_definition_id);
    if (params.owner_scope) query.set('owner_scope', params.owner_scope);
    if (params.owner_member_id) query.set('owner_member_id', params.owner_member_id);
    if (params.status) query.set('status', params.status);
    if (params.created_from) query.set('created_from', params.created_from);
    if (params.created_to) query.set('created_to', params.created_to);
    if (params.limit) query.set('limit', String(params.limit));
    return request<ScheduledTaskRun[]>(`/scheduled-task-runs?${query.toString()}`);
  },
  deleteScheduledTask(taskId: string) {
    return request<void>(`/scheduled-tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    });
  },
};
