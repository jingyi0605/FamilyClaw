/* ============================================================
 * 计划任务标签页 - 列表 + 筛选 + 详情抽屉 + 表单 + 删除确认
 * ============================================================ */
import { useEffect, useMemo, useState, useCallback } from 'react';
import { useI18n } from '../i18n';
import { Card, EmptyState } from './base';
import { useHouseholdContext } from '../state/household';
import { useAuthContext } from '../state/auth';
import { api, ApiError } from '../lib/api';
import type {
  ScheduledTaskDefinition,
  ScheduledTaskRun,
  Member,
  TaskStatus,
} from '../lib/types';
import { ScheduledTaskForm } from './ScheduledTaskForm';

type ViewScope = 'my' | 'family';
type TaskFilterStatus = 'all' | 'enabled' | 'paused' | 'needsAttention';
type FormMode = 'create' | 'edit' | 'copy';

/* ---- 工具函数 ---- */

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays} 天前`;

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function formatNextTime(task: ScheduledTaskDefinition): string {
  if (task.trigger_type === 'schedule') {
    return task.next_run_at ? formatRelativeTime(task.next_run_at) : '-';
  }
  return task.next_heartbeat_at ? formatRelativeTime(task.next_heartbeat_at) : '-';
}

function getStatusBadgeClass(status: TaskStatus): string {
  switch (status) {
    case 'active': return 'badge--success';
    case 'paused': return 'badge--warning';
    case 'error':
    case 'invalid_dependency':
      return 'badge--danger';
    default: return 'badge--default';
  }
}

/* ---- 删除确认对话框 ---- */

interface DeleteConfirmDialogProps {
  isOpen: boolean;
  taskName: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

function DeleteConfirmDialog({ isOpen, taskName, onConfirm, onCancel, loading }: DeleteConfirmDialogProps) {
  const { t } = useI18n();

  if (!isOpen) return null;

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-content" onClick={e => e.stopPropagation()}>
        <h3 className="dialog-title">{t('scheduledTasks.delete.title')}</h3>
        <p className="dialog-message">
          {t('scheduledTasks.delete.message').replace('{name}', taskName)}
        </p>
        <div className="dialog-actions">
          <button className="btn btn--outline" onClick={onCancel} disabled={loading}>
            {t('common.cancel')}
          </button>
          <button className="btn btn--danger" onClick={onConfirm} disabled={loading}>
            {loading ? t('common.loading') : t('scheduledTasks.delete.confirm')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---- 主组件 ---- */

export function ScheduledTasksTab() {
  const { t } = useI18n();
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

  // 表单状态
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [formTask, setFormTask] = useState<ScheduledTaskDefinition | null>(null);

  // 删除确认状态
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTask, setDeleteTask] = useState<ScheduledTaskDefinition | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 管理员代成员查看
  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [adminViewMemberId, setAdminViewMemberId] = useState<string | null>(null);

  const isAdmin = actor?.member_role === 'admin';

  // 加载成员列表（仅管理员需要）
  useEffect(() => {
    if (!isAdmin || !currentHouseholdId) return;

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
    return () => { cancelled = true; };
  }, [isAdmin, currentHouseholdId]);

  // 加载任务列表
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

        // 管理员代成员查看时，使用被代成员的 ID
        if (viewScope === 'my') {
          if (adminViewMemberId) {
            params.owner_member_id = adminViewMemberId;
          } else if (actor?.member_id) {
            params.owner_member_id = actor.member_id;
          }
        }

        if (filterStatus === 'enabled') {
          params.enabled = true;
        } else if (filterStatus === 'paused') {
          params.enabled = false;
        } else if (filterStatus === 'needsAttention') {
          params.status = 'error';
        }

        const result = await api.listScheduledTasks(params);
        if (!cancelled) {
          setTasks(result);
          setSelectedTaskId(current => {
            if (current && result.some(item => item.id === current)) {
              return current;
            }
            return result[0]?.id ?? null;
          });
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
  }, [currentHouseholdId, viewScope, filterStatus, actor?.member_id, adminViewMemberId, t]);

  // 加载运行记录
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

  // 筛选后的任务列表
  const filteredTasks = useMemo(() => {
    if (!searchQuery) return tasks;
    const query = searchQuery.toLowerCase();
    return tasks.filter(
      task =>
        task.name.toLowerCase().includes(query) ||
        (task.description?.toLowerCase().includes(query) ?? false)
    );
  }, [tasks, searchQuery]);

  const selectedTask = filteredTasks.find(task => task.id === selectedTaskId) ?? null;

  // 启停任务
  const handleToggleEnabled = useCallback(async (task: ScheduledTaskDefinition) => {
    if (actionPending) return;

    setActionPending(true);
    try {
      const updated = task.enabled
        ? await api.disableScheduledTask(task.id)
        : await api.enableScheduledTask(task.id);
      setTasks(current =>
        current.map(t => (t.id === updated.id ? updated : t))
      );
    } catch (toggleError) {
      setError(toggleError instanceof ApiError ? toggleError.message : t('scheduledTasks.error.saveFailed'));
    } finally {
      setActionPending(false);
    }
  }, [actionPending, t]);

  // 打开新建表单
  const handleOpenCreateForm = useCallback(() => {
    setFormMode('create');
    setFormTask(null);
    setFormOpen(true);
  }, []);

  // 打开编辑表单
  const handleOpenEditForm = useCallback((task: ScheduledTaskDefinition) => {
    setFormMode('edit');
    setFormTask(task);
    setFormOpen(true);
  }, []);

  // 打开复制表单
  const handleOpenCopyForm = useCallback((task: ScheduledTaskDefinition) => {
    setFormMode('copy');
    setFormTask(task);
    setFormOpen(true);
  }, []);

  // 表单提交成功
  const handleFormSuccess = useCallback((task: ScheduledTaskDefinition) => {
    if (formMode === 'edit') {
      setTasks(current =>
        current.map(t => (t.id === task.id ? task : t))
      );
    } else {
      setTasks(current => [task, ...current]);
      setSelectedTaskId(task.id);
    }
  }, [formMode]);

  // 打开删除确认
  const handleOpenDeleteConfirm = useCallback((task: ScheduledTaskDefinition) => {
    setDeleteTask(task);
    setDeleteOpen(true);
  }, []);

  // 确认删除
  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTask) return;

    setDeleteLoading(true);
    try {
      await api.deleteScheduledTask(deleteTask.id);
      setTasks(current => current.filter(t => t.id !== deleteTask.id));
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
  }, [deleteTask, selectedTaskId, t]);

  // 统计数据
  const stats = useMemo(() => {
    const myTasks = tasks.filter(t => t.owner_scope === 'member');
    const familyTasks = tasks.filter(t => t.owner_scope === 'household');
    const enabledCount = tasks.filter(t => t.enabled).length;
    const needsAttentionCount = tasks.filter(
      t => t.status === 'error' || t.status === 'invalid_dependency'
    ).length;

    return {
      myCount: myTasks.length,
      familyCount: familyTasks.length,
      enabledCount,
      needsAttentionCount,
    };
  }, [tasks]);

  // 当前查看的成员名称
  const viewingMemberName = useMemo(() => {
    if (!adminViewMemberId || !members.length) return null;
    return members.find(m => m.id === adminViewMemberId)?.name ?? null;
  }, [adminViewMemberId, members]);

  return (
    <div className="scheduled-tasks-tab">
      {/* 摘要条 */}
      <div className="scheduled-tasks-summary">
        <div className="scheduled-tasks-stat">
          <span className="scheduled-tasks-stat__value">{stats.myCount}</span>
          <span className="scheduled-tasks-stat__label">{t('scheduledTasks.owner.member')}</span>
        </div>
        <div className="scheduled-tasks-stat">
          <span className="scheduled-tasks-stat__value">{stats.familyCount}</span>
          <span className="scheduled-tasks-stat__label">{t('scheduledTasks.owner.household')}</span>
        </div>
        <div className="scheduled-tasks-stat">
          <span className="scheduled-tasks-stat__value">{stats.enabledCount}</span>
          <span className="scheduled-tasks-stat__label">{t('scheduledTasks.filter.enabled')}</span>
        </div>
        {stats.needsAttentionCount > 0 && (
          <div className="scheduled-tasks-stat scheduled-tasks-stat--warning">
            <span className="scheduled-tasks-stat__value">{stats.needsAttentionCount}</span>
            <span className="scheduled-tasks-stat__label">{t('scheduledTasks.filter.needsAttention')}</span>
          </div>
        )}
      </div>

      {/* 视图切换条 */}
      <div className="scheduled-tasks-view-tabs">
        <button
          className={`scheduled-tasks-view-tab ${viewScope === 'my' ? 'scheduled-tasks-view-tab--active' : ''}`}
          onClick={() => setViewScope('my')}
        >
          {t('scheduledTasks.myTasks')}
        </button>
        <button
          className={`scheduled-tasks-view-tab ${viewScope === 'family' ? 'scheduled-tasks-view-tab--active' : ''}`}
          onClick={() => setViewScope('family')}
        >
          {t('scheduledTasks.familyTasks')}
        </button>
      </div>

      {/* 筛选和搜索条 */}
      <div className="scheduled-tasks-toolbar">
        <input
          type="text"
          placeholder={t('scheduledTasks.search')}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <div className="scheduled-tasks-filters">
          <button
            className={`filter-btn ${filterStatus === 'all' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilterStatus('all')}
          >
            {t('scheduledTasks.filter.all')}
          </button>
          <button
            className={`filter-btn ${filterStatus === 'enabled' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilterStatus('enabled')}
          >
            {t('scheduledTasks.filter.enabled')}
          </button>
          <button
            className={`filter-btn ${filterStatus === 'paused' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilterStatus('paused')}
          >
            {t('scheduledTasks.filter.paused')}
          </button>
        </div>
        {/* 管理员代成员选择器 */}
        {isAdmin && viewScope === 'my' && (
          <select
            className="form-select form-select--sm"
            value={adminViewMemberId || ''}
            onChange={e => setAdminViewMemberId(e.target.value || null)}
            disabled={membersLoading}
            title={viewingMemberName ? `正在查看：${viewingMemberName}` : '查看自己的任务'}
          >
            <option value="">{t('scheduledTasks.myTasks')}</option>
            {members.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        )}
        <button className="btn btn--primary btn--sm" onClick={handleOpenCreateForm}>
          {t('scheduledTasks.newTask')}
        </button>
      </div>

      {/* 主布局 */}
      <div className="scheduled-tasks-layout">
        {/* 任务列表 */}
        <div className="scheduled-tasks-list">
          {loading ? (
            <EmptyState icon="⏳" title={t('common.loading')} description={t('scheduledTasks.loading')} />
          ) : error ? (
            <EmptyState icon="⚠️" title={t('scheduledTasks.error.loadFailed')} description={error} />
          ) : filteredTasks.length > 0 ? (
            filteredTasks.map(task => (
              <Card
                key={task.id}
                className={`scheduled-task-card ${selectedTaskId === task.id ? 'scheduled-task-card--selected' : ''}`}
                onClick={() => setSelectedTaskId(task.id)}
              >
                <div className="scheduled-task-card__header">
                  <h3 className="scheduled-task-card__name">{task.name}</h3>
                  <span className={`badge ${getStatusBadgeClass(task.status)}`}>
                    {task.status === 'active' ? t('scheduledTasks.status.enabled') :
                     task.status === 'paused' ? t('scheduledTasks.status.paused') :
                     task.status === 'error' ? t('scheduledTasks.status.error') :
                     t('scheduledTasks.status.invalid')}
                  </span>
                </div>
                <p className="scheduled-task-card__desc">
                  {task.description || task.name}
                </p>
                <div className="scheduled-task-card__meta">
                  <span className="scheduled-task-card__item">
                    {task.trigger_type === 'schedule' ? t('scheduledTasks.trigger.schedule') : t('scheduledTasks.trigger.heartbeat')}
                  </span>
                  <span className="scheduled-task-card__item">
                    {t('scheduledTasks.list.nextTime')}：{formatNextTime(task)}
                  </span>
                </div>
              </Card>
            ))
          ) : (
            <EmptyState
              icon="📋"
              title={viewScope === 'my' ? t('scheduledTasks.emptyMyTasks') : t('scheduledTasks.emptyFamilyTasks')}
              description={viewScope === 'my' ? t('scheduledTasks.emptyMyTasksHint') : t('scheduledTasks.emptyFamilyTasksHint')}
              action={
                <button className="btn btn--primary" onClick={handleOpenCreateForm}>
                  {t('scheduledTasks.newTask')}
                </button>
              }
            />
          )}
        </div>

        {/* 详情抽屉 */}
        <div className={`scheduled-tasks-detail ${selectedTask ? 'scheduled-tasks-detail--open' : ''}`}>
          {selectedTask ? (
            <>
              <div className="scheduled-tasks-detail__header">
                <h2>{selectedTask.name}</h2>
                <button className="close-btn" onClick={() => setSelectedTaskId(null)}>✕</button>
              </div>
              <div className="scheduled-tasks-detail__body">
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.description')}</label>
                  <p>{selectedTask.description || '暂无描述'}</p>
                </div>
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.triggerType')}</label>
                  <p>{selectedTask.trigger_type === 'schedule' ? t('scheduledTasks.trigger.schedule') : t('scheduledTasks.trigger.heartbeat')}</p>
                </div>
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.status')}</label>
                  <p>
                    <span className={`badge ${getStatusBadgeClass(selectedTask.status)}`}>
                      {selectedTask.status === 'active' ? t('scheduledTasks.status.enabled') :
                       selectedTask.status === 'paused' ? t('scheduledTasks.status.paused') :
                       selectedTask.status === 'error' ? t('scheduledTasks.status.error') :
                       t('scheduledTasks.status.invalid')}
                    </span>
                  </p>
                </div>
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.owner')}</label>
                  <p>{selectedTask.owner_scope === 'household' ? t('scheduledTasks.owner.household') : t('scheduledTasks.owner.member')}</p>
                </div>
                <div className="detail-field">
                  <label>{selectedTask.trigger_type === 'schedule' ? t('scheduledTasks.detail.nextRun') : t('scheduledTasks.detail.nextCheck')}</label>
                  <p>{formatNextTime(selectedTask)}</p>
                </div>
                {selectedTask.last_run_at && (
                  <div className="detail-field">
                    <label>{t('scheduledTasks.detail.lastRun')}</label>
                    <p>{formatRelativeTime(selectedTask.last_run_at)}</p>
                  </div>
                )}
                {selectedTask.last_result && (
                  <div className="detail-field">
                    <label>{t('scheduledTasks.detail.lastResult')}</label>
                    <p>{selectedTask.last_result === 'succeeded' ? t('scheduledTasks.result.succeeded') :
                        selectedTask.last_result === 'suppressed' ? t('scheduledTasks.result.suppressed') :
                        selectedTask.last_result === 'failed' ? t('scheduledTasks.result.failed') :
                        selectedTask.last_result === 'skipped' ? t('scheduledTasks.result.skipped') :
                        selectedTask.last_result === 'queued' ? t('scheduledTasks.result.queued') :
                        selectedTask.last_result === 'dispatching' ? t('scheduledTasks.result.dispatching') :
                        selectedTask.last_result}
                    </p>
                  </div>
                )}

                {/* 运行记录 */}
                <div className="detail-field">
                  <label>{t('scheduledTasks.detail.runHistory')}</label>
                  {runs.length > 0 ? (
                    <div className="scheduled-tasks-runs">
                      {runs.slice(0, 5).map(run => (
                        <div key={run.id} className="scheduled-tasks-run-item">
                          <div className="scheduled-tasks-run-item__time">
                            {formatRelativeTime(run.created_at)}
                          </div>
                          <div className={`scheduled-tasks-run-item__status scheduled-tasks-run-item__status--${run.status}`}>
                            {run.status === 'succeeded' ? t('scheduledTasks.result.succeeded') :
                             run.status === 'suppressed' ? t('scheduledTasks.result.suppressed') :
                             run.status === 'failed' ? t('scheduledTasks.result.failed') :
                             run.status === 'skipped' ? t('scheduledTasks.result.skipped') :
                             run.status === 'queued' ? t('scheduledTasks.result.queued') :
                             run.status === 'dispatching' ? t('scheduledTasks.result.dispatching') :
                             run.status}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-secondary">暂无运行记录</p>
                  )}
                </div>
              </div>
              <div className="scheduled-tasks-detail__actions">
                <button
                  className={`btn ${selectedTask.enabled ? 'btn--outline btn--warning' : 'btn--primary'}`}
                  disabled={actionPending}
                  onClick={() => void handleToggleEnabled(selectedTask)}
                >
                  {selectedTask.enabled ? t('scheduledTasks.action.pause') : t('scheduledTasks.action.resume')}
                </button>
                <button
                  className="btn btn--outline"
                  onClick={() => handleOpenEditForm(selectedTask)}
                  disabled={actionPending}
                >
                  {t('scheduledTasks.action.edit')}
                </button>
                <button
                  className="btn btn--outline"
                  onClick={() => handleOpenCopyForm(selectedTask)}
                  disabled={actionPending}
                >
                  {t('scheduledTasks.action.copy')}
                </button>
                <button
                  className="btn btn--outline btn--danger"
                  onClick={() => handleOpenDeleteConfirm(selectedTask)}
                  disabled={actionPending}
                >
                  {t('scheduledTasks.action.delete')}
                </button>
              </div>
            </>
          ) : (
            <div className="scheduled-tasks-detail__empty">
              <p>点击左侧任务查看详情</p>
            </div>
          )}
        </div>
      </div>

      {/* 表单抽屉 */}
      <ScheduledTaskForm
        mode={formMode}
        task={formTask}
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSuccess={handleFormSuccess}
      />

      {/* 删除确认对话框 */}
      <DeleteConfirmDialog
        isOpen={deleteOpen}
        taskName={deleteTask?.name ?? ''}
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => {
          setDeleteOpen(false);
          setDeleteTask(null);
        }}
        loading={deleteLoading}
      />
    </div>
  );
}

export default ScheduledTasksTab;
