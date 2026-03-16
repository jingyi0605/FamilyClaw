import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuthContext, useHouseholdContext } from '../../runtime';
import { Card, EmptyState } from '../family/base';
import { api, ApiError } from './api';
import { useMemoriesText } from './copy';
import { ScheduledTaskForm } from './ScheduledTaskForm';
import type { Member, ScheduledTaskDefinition, ScheduledTaskRun, TaskStatus } from './types';

type ViewScope = 'my' | 'family';
type TaskFilterStatus = 'all' | 'enabled' | 'paused' | 'needsAttention';
type FormMode = 'create' | 'edit' | 'copy';
type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

function formatRelativeTime(value: string | null | undefined, t: TranslateFn): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return t('scheduledTasks.time.minutesAgo', { count: diffMinutes });
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return t('scheduledTasks.time.hoursAgo', { count: diffHours });
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return t('scheduledTasks.time.daysAgo', { count: diffDays });

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function formatNextTime(task: ScheduledTaskDefinition, t: TranslateFn): string {
  return task.trigger_type === 'schedule'
    ? (task.next_run_at ? formatRelativeTime(task.next_run_at, t) : '-')
    : (task.next_heartbeat_at ? formatRelativeTime(task.next_heartbeat_at, t) : '-');
}

function getStatusBadgeClass(status: TaskStatus): string {
  switch (status) {
    case 'active': return 'badge--success';
    case 'paused': return 'badge--warning';
    case 'error':
    case 'invalid_dependency':
      return 'badge--danger';
    default:
      return 'badge--default';
  }
}

function DeleteConfirmDialog(props: {
  isOpen: boolean;
  taskName: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  t: TranslateFn;
}) {
  if (!props.isOpen) {
    return null;
  }

  return (
    <div className="dialog-overlay" onClick={props.onCancel}>
      <div className="dialog-content" onClick={event => event.stopPropagation()}>
        <h3 className="dialog-title">{props.t('scheduledTasks.delete.title')}</h3>
        <p className="dialog-message">{props.t('scheduledTasks.delete.message', { name: props.taskName })}</p>
        <div className="dialog-actions">
          <button className="btn btn--outline" type="button" onClick={props.onCancel} disabled={props.loading}>{props.t('common.cancel')}</button>
          <button className="btn btn--danger" type="button" onClick={props.onConfirm} disabled={props.loading}>
            {props.loading ? props.t('common.loading') : props.t('scheduledTasks.delete.confirm')}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ScheduledTasksTab() {
  const t = useMemoriesText();
  const { currentHouseholdId } = useHouseholdContext();
  const { actor } = useAuthContext();
  const [viewScope, setViewScope] = useState<ViewScope>('my');
  const [filterStatus, setFilterStatus] = useState<TaskFilterStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [tasks, setTasks] = useState<ScheduledTaskDefinition[]>([]);
  const [runs, setRuns] = useState<ScheduledTaskRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [formTask, setFormTask] = useState<ScheduledTaskDefinition | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTask, setDeleteTask] = useState<ScheduledTaskDefinition | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [adminViewMemberId, setAdminViewMemberId] = useState<string | null>(null);
  const isAdmin = actor?.member_role === 'admin';

  useEffect(() => {
    if (!isAdmin || !currentHouseholdId) {
      return;
    }

    let cancelled = false;
    const loadMembers = async () => {
      setMembersLoading(true);
      try {
        const result = await api.listMembers(currentHouseholdId);
        if (!cancelled) {
          setMembers(result.items);
        }
      } catch {
        if (!cancelled) {
          setMembers([]);
        }
      } finally {
        if (!cancelled) {
          setMembersLoading(false);
        }
      }
    };

    void loadMembers();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, isAdmin]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setTasks([]);
      setSelectedTaskId(null);
      return;
    }

    let cancelled = false;
    const loadTasks = async () => {
      setLoading(true);
      setError('');
      try {
        const params: Parameters<typeof api.listScheduledTasks>[0] = {
          household_id: currentHouseholdId,
          owner_scope: viewScope === 'my' ? 'member' : 'household',
        };

        if (viewScope === 'my') {
          if (adminViewMemberId) {
            params.owner_member_id = adminViewMemberId;
          } else if (actor?.member_id) {
            params.owner_member_id = actor.member_id;
          }
        }

        if (filterStatus === 'enabled') params.enabled = true;
        else if (filterStatus === 'paused') params.enabled = false;
        else if (filterStatus === 'needsAttention') params.status = 'error';

        const result = await api.listScheduledTasks(params);
        if (!cancelled) {
          setTasks(result);
          setSelectedTaskId(current => current && result.some(item => item.id === current) ? current : result[0]?.id ?? null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : t('scheduledTasks.error.loadFailed'));
          setTasks([]);
          setSelectedTaskId(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadTasks();
    return () => {
      cancelled = true;
    };
  }, [actor?.member_id, adminViewMemberId, currentHouseholdId, filterStatus, t, viewScope]);

  useEffect(() => {
    if (!currentHouseholdId || !selectedTaskId) {
      setRuns([]);
      return;
    }

    let cancelled = false;
    const loadRuns = async () => {
      try {
        const result = await api.listScheduledTaskRuns({
          household_id: currentHouseholdId,
          task_definition_id: selectedTaskId,
          limit: 10,
        });
        if (!cancelled) {
          setRuns(result);
        }
      } catch {
        if (!cancelled) {
          setRuns([]);
        }
      }
    };

    void loadRuns();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, selectedTaskId]);

  const filteredTasks = useMemo(() => {
    if (!searchQuery) return tasks;
    const query = searchQuery.toLowerCase();
    return tasks.filter(task => task.name.toLowerCase().includes(query) || (task.description?.toLowerCase().includes(query) ?? false));
  }, [searchQuery, tasks]);

  const selectedTask = filteredTasks.find(task => task.id === selectedTaskId) ?? null;

  const stats = useMemo(() => ({
    myCount: tasks.filter(task => task.owner_scope === 'member').length,
    familyCount: tasks.filter(task => task.owner_scope === 'household').length,
    enabledCount: tasks.filter(task => task.enabled).length,
    needsAttentionCount: tasks.filter(task => task.status === 'error' || task.status === 'invalid_dependency').length,
  }), [tasks]);

  const viewingMemberName = useMemo(() => {
    if (!adminViewMemberId || members.length === 0) {
      return null;
    }
    return members.find(member => member.id === adminViewMemberId)?.name ?? null;
  }, [adminViewMemberId, members]);

  const handleToggleEnabled = useCallback(async (task: ScheduledTaskDefinition) => {
    if (actionPending) {
      return;
    }

    setActionPending(true);
    try {
      const updated = task.enabled ? await api.disableScheduledTask(task.id) : await api.enableScheduledTask(task.id);
      setTasks(current => current.map(item => item.id === updated.id ? updated : item));
    } catch (toggleError) {
      setError(toggleError instanceof ApiError ? toggleError.message : t('scheduledTasks.error.saveFailed'));
    } finally {
      setActionPending(false);
    }
  }, [actionPending, t]);

  const handleFormSuccess = useCallback((task: ScheduledTaskDefinition) => {
    if (formMode === 'edit') {
      setTasks(current => current.map(item => item.id === task.id ? task : item));
      return;
    }

    setTasks(current => [task, ...current]);
    setSelectedTaskId(task.id);
  }, [formMode]);

  return (
    <div className="scheduled-tasks-tab">
      <div className="scheduled-tasks-summary">
        <div className="scheduled-tasks-stat"><span className="scheduled-tasks-stat__value">{stats.myCount}</span><span className="scheduled-tasks-stat__label">{t('scheduledTasks.owner.member')}</span></div>
        <div className="scheduled-tasks-stat"><span className="scheduled-tasks-stat__value">{stats.familyCount}</span><span className="scheduled-tasks-stat__label">{t('scheduledTasks.owner.household')}</span></div>
        <div className="scheduled-tasks-stat"><span className="scheduled-tasks-stat__value">{stats.enabledCount}</span><span className="scheduled-tasks-stat__label">{t('scheduledTasks.filter.enabled')}</span></div>
        {stats.needsAttentionCount > 0 ? <div className="scheduled-tasks-stat scheduled-tasks-stat--warning"><span className="scheduled-tasks-stat__value">{stats.needsAttentionCount}</span><span className="scheduled-tasks-stat__label">{t('scheduledTasks.filter.needsAttention')}</span></div> : null}
      </div>

      <div className="scheduled-tasks-view-tabs">
        <button className={`scheduled-tasks-view-tab ${viewScope === 'my' ? 'scheduled-tasks-view-tab--active' : ''}`} type="button" onClick={() => setViewScope('my')}>{t('scheduledTasks.myTasks')}</button>
        <button className={`scheduled-tasks-view-tab ${viewScope === 'family' ? 'scheduled-tasks-view-tab--active' : ''}`} type="button" onClick={() => setViewScope('family')}>{t('scheduledTasks.familyTasks')}</button>
      </div>

      <div className="scheduled-tasks-toolbar">
        <input type="text" placeholder={t('scheduledTasks.search')} value={searchQuery} onChange={event => setSearchQuery(event.target.value)} className="search-input" />
        <div className="scheduled-tasks-filters">
          <button className={`filter-btn ${filterStatus === 'all' ? 'filter-btn--active' : ''}`} type="button" onClick={() => setFilterStatus('all')}>{t('scheduledTasks.filter.all')}</button>
          <button className={`filter-btn ${filterStatus === 'enabled' ? 'filter-btn--active' : ''}`} type="button" onClick={() => setFilterStatus('enabled')}>{t('scheduledTasks.filter.enabled')}</button>
          <button className={`filter-btn ${filterStatus === 'paused' ? 'filter-btn--active' : ''}`} type="button" onClick={() => setFilterStatus('paused')}>{t('scheduledTasks.filter.paused')}</button>
        </div>
        {isAdmin && viewScope === 'my' ? (
          <select className="form-select" value={adminViewMemberId ?? ''} onChange={event => setAdminViewMemberId(event.target.value || null)} disabled={membersLoading} title={viewingMemberName ? t('scheduledTasks.adminView.viewingMember', { name: viewingMemberName }) : t('scheduledTasks.adminView.viewOwnTasks')}>
            <option value="">{t('scheduledTasks.myTasks')}</option>
            {members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
          </select>
        ) : null}
        <button className="btn btn--primary btn--sm" type="button" onClick={() => { setFormMode('create'); setFormTask(null); setFormOpen(true); }}>{t('scheduledTasks.newTask')}</button>
      </div>

      <div className="scheduled-tasks-layout">
        <div className="scheduled-tasks-list">
          {loading ? <EmptyState icon="⏳" title={t('common.loading')} description={t('scheduledTasks.loading')} /> : error ? <EmptyState icon="⚠️" title={t('scheduledTasks.error.loadFailed')} description={error} /> : filteredTasks.length > 0 ? filteredTasks.map(task => (
            <Card key={task.id} className={`scheduled-task-card ${selectedTaskId === task.id ? 'scheduled-task-card--selected' : ''}`} onClick={() => setSelectedTaskId(task.id)}>
              <div className="scheduled-task-card__header">
                <h3 className="scheduled-task-card__name">{task.name}</h3>
                <span className={`badge ${getStatusBadgeClass(task.status)}`}>{task.status === 'active' ? t('scheduledTasks.status.enabled') : task.status === 'paused' ? t('scheduledTasks.status.paused') : task.status === 'error' ? t('scheduledTasks.status.error') : t('scheduledTasks.status.invalid')}</span>
              </div>
              <p className="scheduled-task-card__desc">{task.description || task.name}</p>
              <div className="scheduled-task-card__meta">
                <span className="scheduled-task-card__item">{task.trigger_type === 'schedule' ? t('scheduledTasks.trigger.schedule') : t('scheduledTasks.trigger.heartbeat')}</span>
                <span className="scheduled-task-card__item">{t('scheduledTasks.list.nextTime')}：{formatNextTime(task, t)}</span>
              </div>
            </Card>
          )) : <EmptyState icon="📋" title={viewScope === 'my' ? t('scheduledTasks.emptyMyTasks') : t('scheduledTasks.emptyFamilyTasks')} description={viewScope === 'my' ? t('scheduledTasks.emptyMyTasksHint') : t('scheduledTasks.emptyFamilyTasksHint')} action={<button className="btn btn--primary" type="button" onClick={() => { setFormMode('create'); setFormTask(null); setFormOpen(true); }}>{t('scheduledTasks.newTask')}</button>} />}
        </div>

        <div className={`scheduled-tasks-detail ${selectedTask ? 'scheduled-tasks-detail--open' : ''}`}>
          {selectedTask ? (
            <>
              <div className="scheduled-tasks-detail__header">
                <h2>{selectedTask.name}</h2>
                <button className="close-btn" type="button" onClick={() => setSelectedTaskId(null)}>✕</button>
              </div>
              <div className="scheduled-tasks-detail__body">
                <div className="detail-field"><label>{t('scheduledTasks.detail.description')}</label><p>{selectedTask.description || t('scheduledTasks.detail.noDescription')}</p></div>
                <div className="detail-field"><label>{t('scheduledTasks.detail.triggerType')}</label><p>{selectedTask.trigger_type === 'schedule' ? t('scheduledTasks.trigger.schedule') : t('scheduledTasks.trigger.heartbeat')}</p></div>
                <div className="detail-field"><label>{t('scheduledTasks.detail.status')}</label><p><span className={`badge ${getStatusBadgeClass(selectedTask.status)}`}>{selectedTask.status === 'active' ? t('scheduledTasks.status.enabled') : selectedTask.status === 'paused' ? t('scheduledTasks.status.paused') : selectedTask.status === 'error' ? t('scheduledTasks.status.error') : t('scheduledTasks.status.invalid')}</span></p></div>
                <div className="detail-field"><label>{t('scheduledTasks.detail.owner')}</label><p>{selectedTask.owner_scope === 'household' ? t('scheduledTasks.owner.household') : t('scheduledTasks.owner.member')}</p></div>
                <div className="detail-field"><label>{selectedTask.trigger_type === 'schedule' ? t('scheduledTasks.detail.nextRun') : t('scheduledTasks.detail.nextCheck')}</label><p>{formatNextTime(selectedTask, t)}</p></div>
                {selectedTask.last_run_at ? <div className="detail-field"><label>{t('scheduledTasks.detail.lastRun')}</label><p>{formatRelativeTime(selectedTask.last_run_at, t)}</p></div> : null}
                {selectedTask.last_result ? <div className="detail-field"><label>{t('scheduledTasks.detail.lastResult')}</label><p>{selectedTask.last_result === 'succeeded' ? t('scheduledTasks.result.succeeded') : selectedTask.last_result === 'suppressed' ? t('scheduledTasks.result.suppressed') : selectedTask.last_result === 'failed' ? t('scheduledTasks.result.failed') : selectedTask.last_result === 'skipped' ? t('scheduledTasks.result.skipped') : selectedTask.last_result === 'queued' ? t('scheduledTasks.result.queued') : selectedTask.last_result === 'dispatching' ? t('scheduledTasks.result.dispatching') : selectedTask.last_result}</p></div> : null}
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.runHistory')}</label>
                  {runs.length > 0 ? <div className="scheduled-tasks-runs">{runs.slice(0, 5).map(run => <div key={run.id} className="scheduled-tasks-run-item"><div className="scheduled-tasks-run-item__time">{formatRelativeTime(run.created_at, t)}</div><div className={`scheduled-tasks-run-item__status scheduled-tasks-run-item__status--${run.status}`}>{run.status === 'succeeded' ? t('scheduledTasks.result.succeeded') : run.status === 'suppressed' ? t('scheduledTasks.result.suppressed') : run.status === 'failed' ? t('scheduledTasks.result.failed') : run.status === 'skipped' ? t('scheduledTasks.result.skipped') : run.status === 'queued' ? t('scheduledTasks.result.queued') : run.status === 'dispatching' ? t('scheduledTasks.result.dispatching') : run.status}</div></div>)}</div> : <p>{t('scheduledTasks.runHistory.noRecords')}</p>}
                </div>
              </div>
              <div className="scheduled-tasks-detail__actions">
                <button className={`btn ${selectedTask.enabled ? 'btn--outline btn--warning' : 'btn--primary'}`} type="button" disabled={actionPending} onClick={() => void handleToggleEnabled(selectedTask)}>{selectedTask.enabled ? t('scheduledTasks.action.pause') : t('scheduledTasks.action.resume')}</button>
                <button className="btn btn--outline" type="button" onClick={() => { setFormMode('edit'); setFormTask(selectedTask); setFormOpen(true); }} disabled={actionPending}>{t('scheduledTasks.action.edit')}</button>
                <button className="btn btn--outline" type="button" onClick={() => { setFormMode('copy'); setFormTask(selectedTask); setFormOpen(true); }} disabled={actionPending}>{t('scheduledTasks.action.copy')}</button>
                <button className="btn btn--outline btn--danger" type="button" onClick={() => { setDeleteTask(selectedTask); setDeleteOpen(true); }} disabled={actionPending}>{t('scheduledTasks.action.delete')}</button>
              </div>
            </>
          ) : <div className="scheduled-tasks-detail__empty"><p>{t('scheduledTasks.detail.clickToView')}</p></div>}
        </div>
      </div>

      <ScheduledTaskForm mode={formMode} task={formTask} isOpen={formOpen} onClose={() => setFormOpen(false)} onSuccess={handleFormSuccess} />
      <DeleteConfirmDialog isOpen={deleteOpen} taskName={deleteTask?.name ?? ''} onConfirm={() => void handleConfirmDelete()} onCancel={() => { setDeleteOpen(false); setDeleteTask(null); }} loading={deleteLoading} t={t} />
    </div>
  );

  async function handleConfirmDelete() {
    if (!deleteTask) {
      return;
    }

    setDeleteLoading(true);
    try {
      await api.deleteScheduledTask(deleteTask.id);
      setTasks(current => current.filter(task => task.id !== deleteTask.id));
      if (selectedTaskId === deleteTask.id) {
        setSelectedTaskId(null);
      }
      setDeleteOpen(false);
      setDeleteTask(null);
    } catch (deleteError) {
      setError(deleteError instanceof ApiError ? deleteError.message : t('scheduledTasks.error.saveFailed'));
    } finally {
      setDeleteLoading(false);
    }
  }
}
