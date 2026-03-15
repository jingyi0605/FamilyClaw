import { useEffect, useMemo, useState } from 'react';
import { useAuthContext, useHouseholdContext } from '../../runtime';
import { Card, EmptyState, PageHeader } from '../family/base';
import { api } from './api';
import { useMemoriesText } from './copy';
import { ScheduledTasksTab } from './ScheduledTasksTab';
import type { Member, MemoryCard, MemoryCardRevision, MemoryStatus, MemoryType, MemoryVisibility } from './types';

type MemoryFilterType = 'all' | 'fact' | 'event' | 'preference' | 'relation';
type MainTab = 'memories' | 'scheduledTasks';
type RevisionSnapshot = Record<string, unknown>;
type RevisionFieldKey = 'title' | 'content' | 'visibility' | 'status';

const typeMap: Record<
  MemoryFilterType,
  { labelKey: 'memory.all' | 'memory.facts' | 'memory.events' | 'memory.preferences' | 'memory.relations'; icon: string }
> = {
  all: { labelKey: 'memory.all', icon: '📋' },
  fact: { labelKey: 'memory.facts', icon: '📌' },
  event: { labelKey: 'memory.events', icon: '📅' },
  preference: { labelKey: 'memory.preferences', icon: '💡' },
  relation: { labelKey: 'memory.relations', icon: '🔗' },
};

const REVISION_VISIBLE_FIELDS: Array<{
  key: RevisionFieldKey;
  label: string;
  getValue: (snapshot: RevisionSnapshot | null) => unknown;
}> = [
  {
    key: 'title',
    label: '标题',
    getValue: snapshot => snapshot?.title,
  },
  {
    key: 'content',
    label: '内容',
    getValue: snapshot => snapshot?.summary ?? snapshot?.content,
  },
  {
    key: 'visibility',
    label: '可见范围',
    getValue: snapshot => snapshot?.visibility,
  },
  {
    key: 'status',
    label: '状态',
    getValue: snapshot => snapshot?.status,
  },
];

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }

  return `${Math.round(diffHours / 24)} 天前`;
}

function formatVisibility(visibility: MemoryVisibility) {
  switch (visibility) {
    case 'public':
      return '公开可见';
    case 'family':
      return '全家可见';
    case 'private':
      return '私密';
    case 'sensitive':
      return '敏感';
  }
}

function formatStatus(status: MemoryStatus) {
  switch (status) {
    case 'active':
      return '有效';
    case 'pending_review':
      return '待确认';
    case 'invalidated':
      return '已失效';
    case 'deleted':
      return '已删除';
  }
}

function formatRevisionAction(action: string) {
  switch (action) {
    case 'create':
      return '创建';
    case 'correct':
      return '更正';
    case 'invalidate':
      return '标记失效';
    case 'delete':
      return '删除';
    default:
      return action;
  }
}

function summarizeSource(card: MemoryCard) {
  if (card.source_event_id) {
    return '事件生成';
  }
  if (card.created_by.includes('admin')) {
    return '管理台录入';
  }
  return '系统生成';
}

function getMemberDisplayName(member: Member) {
  if (typeof member.name === 'string' && member.name.trim() !== '') {
    return member.name.trim();
  }

  if (typeof member.nickname === 'string' && member.nickname.trim() !== '') {
    return member.nickname.trim();
  }

  return member.id;
}

function getMemoryOwnerLabel(card: MemoryCard, members: Member[]) {
  if (card.subject_member_id) {
    const owner = members.find(member => member.id === card.subject_member_id);
    return owner ? getMemberDisplayName(owner) : card.subject_member_id;
  }

  if (card.visibility === 'public') {
    return '家庭公开记忆';
  }

  if (card.visibility === 'family') {
    return '全家共享记忆';
  }

  return '未绑定成员';
}

function getMemoryPermissionHint(card: MemoryCard) {
  if (card.status === 'deleted') {
    return '这条记忆已经删除，只保留查看记录，不能继续修改。';
  }
  if (card.visibility === 'sensitive') {
    return '这条记忆属于敏感内容，修改前请先确认是否真的需要保留或更正。';
  }
  if (card.visibility === 'private') {
    return '这条记忆是私密范围，建议只在确认归属和内容准确时再修改。';
  }
  return '你可以在这里更正文案或标记失效，系统会保留修订历史。';
}

function parseRevisionSnapshot(value: string | null) {
  if (!value) {
    return null;
  }

  try {
    const parsed = JSON.parse(value) as RevisionSnapshot;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function formatRevisionValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '空';
  }

  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '空';
    }

    return value
      .map(item => {
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>;
          const memberId = typeof record.member_id === 'string' ? record.member_id : '';
          const relationRole = typeof record.relation_role === 'string' ? record.relation_role : '';
          return [memberId, relationRole].filter(Boolean).join(' / ');
        }
        return String(item);
      })
      .join('，');
  }

  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, nestedValue]) => `${key}: ${formatRevisionValue(nestedValue)}`)
      .join('，');
  }

  return String(value);
}

function formatRevisionFieldValue(field: RevisionFieldKey, value: unknown) {
  if (field === 'visibility' && typeof value === 'string') {
    return ['public', 'family', 'private', 'sensitive'].includes(value)
      ? formatVisibility(value as MemoryVisibility)
      : value;
  }

  if (field === 'status' && typeof value === 'string') {
    return ['active', 'pending_review', 'invalidated', 'deleted'].includes(value)
      ? formatStatus(value as MemoryStatus)
      : value;
  }

  return formatRevisionValue(value);
}

function collectRevisionChanges(revision: MemoryCardRevision) {
  const before = parseRevisionSnapshot(revision.before_json);
  const after = parseRevisionSnapshot(revision.after_json);

  return REVISION_VISIBLE_FIELDS.flatMap(field => {
    const beforeValue = field.getValue(before);
    const afterValue = field.getValue(after);
    const beforeText = formatRevisionFieldValue(field.key, beforeValue);
    const afterText = formatRevisionFieldValue(field.key, afterValue);

    if (revision.action !== 'create' && beforeText === afterText) {
      return [];
    }

    if (revision.action === 'delete' && after === null && beforeValue === undefined) {
      return [];
    }

    return [{
      field: field.key,
      label: field.label,
      beforeText,
      afterText,
    }];
  });
}

export function MemoriesPageImpl() {
  const t = useMemoriesText();
  const { actor } = useAuthContext();
  const { currentHouseholdId } = useHouseholdContext();
  const [mainTab, setMainTab] = useState<MainTab>('memories');
  const [activeType, setActiveType] = useState<MemoryFilterType>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [memories, setMemories] = useState<MemoryCard[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionStatus, setActionStatus] = useState('');
  const [editingDraft, setEditingDraft] = useState({ title: '', summary: '' });
  const [revisions, setRevisions] = useState<MemoryCardRevision[]>([]);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [expandedRevisionId, setExpandedRevisionId] = useState<string | null>(null);
  const [revisionError, setRevisionError] = useState('');
  const canDeleteMemory = actor?.member_role === 'admin';

  useEffect(() => {
    if (!currentHouseholdId) {
      setMembers([]);
      return;
    }

    let cancelled = false;

    const loadMembers = async () => {
      try {
        const result = await api.listMembers(currentHouseholdId);
        if (!cancelled) {
          setMembers(result.items);
        }
      } catch {
        if (!cancelled) {
          setMembers([]);
        }
      }
    };

    void loadMembers();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setMemories([]);
      setSelectedId(null);
      return;
    }

    let cancelled = false;

    const loadMemories = async () => {
      setLoading(true);
      setError('');

      try {
        const result = await api.listMemoryCards({
          householdId: currentHouseholdId,
          memoryType: activeType === 'all' ? undefined : activeType as Exclude<MemoryType, 'growth'>,
        });

        if (!cancelled) {
          setMemories(result.items);
          setSelectedId(current => (
            current && result.items.some(item => item.id === current)
              ? current
              : result.items[0]?.id ?? null
          ));
          setActionStatus('');
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载记忆失败');
          setMemories([]);
          setSelectedId(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadMemories();

    return () => {
      cancelled = true;
    };
  }, [activeType, currentHouseholdId]);

  const filtered = useMemo(
    () => memories.filter(memory => (
      searchQuery === ''
        || memory.title.includes(searchQuery)
        || memory.summary.includes(searchQuery)
    )),
    [memories, searchQuery],
  );

  const selectedMemory = filtered.find(memory => memory.id === selectedId)
    ?? memories.find(memory => memory.id === selectedId)
    ?? null;
  const canEditSelectedMemory = selectedMemory ? selectedMemory.status !== 'deleted' : false;

  useEffect(() => {
    if (selectedMemory) {
      setEditingDraft({
        title: selectedMemory.title,
        summary: selectedMemory.summary,
      });
    }
  }, [selectedMemory?.id]);

  useEffect(() => {
    if (!selectedMemory) {
      setRevisions([]);
      setExpandedRevisionId(null);
      setRevisionError('');
      return;
    }

    let cancelled = false;

    const loadRevisions = async () => {
      setRevisionsLoading(true);

      try {
        const result = await api.listMemoryCardRevisions(selectedMemory.id);
        if (!cancelled) {
          setRevisions(result.items);
          setExpandedRevisionId(null);
          setRevisionError('');
        }
      } catch {
        if (!cancelled) {
          setRevisions([]);
          setExpandedRevisionId(null);
          setRevisionError('当前身份暂时不能查看修订历史，或者这条记忆没有公开修订记录。');
        }
      } finally {
        if (!cancelled) {
          setRevisionsLoading(false);
        }
      }
    };

    void loadRevisions();

    return () => {
      cancelled = true;
    };
  }, [selectedMemory?.id]);

  async function refreshCurrentList() {
    if (!currentHouseholdId) {
      return;
    }

    const result = await api.listMemoryCards({
      householdId: currentHouseholdId,
      memoryType: activeType === 'all' ? undefined : activeType as Exclude<MemoryType, 'growth'>,
    });
    setMemories(result.items);
  }

  async function handleCorrect() {
    if (!selectedMemory) {
      return;
    }

    try {
      setError('');
      const updated = await api.correctMemoryCard(selectedMemory.id, {
        action: 'correct',
        title: editingDraft.title,
        summary: editingDraft.summary,
        reason: '用户在记忆页手动纠错',
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus('记忆已更新。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '纠错失败');
    }
  }

  async function handleInvalidate() {
    if (!selectedMemory) {
      return;
    }

    try {
      setError('');
      const updated = await api.correctMemoryCard(selectedMemory.id, {
        action: 'invalidate',
        reason: '用户在记忆页标记失效',
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus('记忆已标记失效。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '标记失效失败');
    }
  }

  async function handleDelete() {
    if (!selectedMemory) {
      return;
    }

    try {
      setError('');
      await api.correctMemoryCard(selectedMemory.id, {
        action: 'delete',
        reason: '用户在记忆页删除记忆',
      });
      await refreshCurrentList();
      setSelectedId(null);
      setActionStatus('记忆已删除。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '删除失败');
    }
  }

  return (
    <div className="page page--memories">
      <PageHeader
        title={t('nav.memories')}
        description={error ? '部分或全部记忆数据加载失败。' : actionStatus || undefined}
      />

      <div className="memory-main-tabs">
        <button
          className={`memory-main-tab ${mainTab === 'memories' ? 'memory-main-tab--active' : ''}`}
          type="button"
          onClick={() => setMainTab('memories')}
        >
          {t('memory.all')}
        </button>
        <button
          className={`memory-main-tab ${mainTab === 'scheduledTasks' ? 'memory-main-tab--active' : ''}`}
          type="button"
          onClick={() => setMainTab('scheduledTasks')}
        >
          {t('scheduledTasks.tab')}
        </button>
      </div>

      {mainTab === 'scheduledTasks' ? (
        <ScheduledTasksTab />
      ) : (
        <>
          <div className="memory-search">
            <input
              type="text"
              placeholder={t('memory.search')}
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              className="search-input search-input--lg"
            />
          </div>

          <div className="memory-layout">
            <nav className="memory-categories">
              {(Object.keys(typeMap) as MemoryFilterType[]).map(type => (
                <button
                  key={type}
                  className={`memory-cat-btn ${activeType === type ? 'memory-cat-btn--active' : ''}`}
                  type="button"
                  onClick={() => setActiveType(type)}
                >
                  <span>{typeMap[type].icon}</span>
                  <span>{t(typeMap[type].labelKey)}</span>
                </button>
              ))}
            </nav>

            <div className="memory-list">
              {loading ? (
                <EmptyState
                  icon="⏳"
                  title={t('common.loading')}
                  description="正在读取真实记忆数据"
                />
              ) : filtered.length > 0 ? (
                filtered.map(memory => (
                  <Card
                    key={memory.id}
                    className={`memory-item-card ${selectedId === memory.id ? 'memory-item-card--selected' : ''}`}
                    onClick={() => setSelectedId(memory.id)}
                  >
                    <div className="memory-item-card__top">
                      <span className="memory-item-card__icon">
                        {typeMap[(memory.memory_type === 'growth' ? 'event' : memory.memory_type) as MemoryFilterType]?.icon ?? '🧠'}
                      </span>
                      <h3 className="memory-item-card__title">{memory.title}</h3>
                      <span className={`badge badge--${memory.status === 'active' ? 'success' : 'warning'}`}>
                        {formatStatus(memory.status)}
                      </span>
                    </div>
                    <p className="memory-item-card__content">{memory.summary}</p>
                    <div className="memory-item-card__meta">
                      <span>{t('memory.source')}：{summarizeSource(memory)}</span>
                      <span>{t('memory.updatedAt')}：{formatRelativeTime(memory.updated_at)}</span>
                    </div>
                  </Card>
                ))
              ) : (
                <EmptyState
                  icon="🧠"
                  title={t('memory.noResults')}
                  description={error || t('memory.noResultsHint')}
                />
              )}
            </div>

            <div className={`memory-detail ${selectedMemory ? 'memory-detail--open' : ''}`}>
              {selectedMemory ? (
                <>
                  <div className="memory-detail__header">
                    <h2>{t('memory.detail')}</h2>
                    <button className="close-btn" type="button" onClick={() => setSelectedId(null)}>
                      ×
                    </button>
                  </div>
                  <div className="memory-detail__body">
                    <div className="detail-field">
                      <label>标题</label>
                      <input
                        className="form-input"
                        value={editingDraft.title}
                        disabled={!canEditSelectedMemory}
                        onChange={event => setEditingDraft(current => ({ ...current, title: event.target.value }))}
                      />
                    </div>
                    <div className="detail-field">
                      <label>内容</label>
                      <textarea
                        className="form-input"
                        value={editingDraft.summary}
                        disabled={!canEditSelectedMemory}
                        onChange={event => setEditingDraft(current => ({ ...current, summary: event.target.value }))}
                        rows={5}
                      />
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.source')}</label>
                      <p>{summarizeSource(selectedMemory)}</p>
                    </div>
                    <div className="detail-field">
                      <label>归属</label>
                      <p>{getMemoryOwnerLabel(selectedMemory, members)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.visibility')}</label>
                      <p>{formatVisibility(selectedMemory.visibility)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.status')}</label>
                      <p>{formatStatus(selectedMemory.status)}</p>
                    </div>
                    <div className="detail-field">
                      <label>当前操作说明</label>
                      <p>{getMemoryPermissionHint(selectedMemory)}</p>
                      <p>
                        {canDeleteMemory
                          ? '当前身份允许删除记忆，但删除后只保留修订记录。'
                          : '当前身份没有删除权限，如需删除请联系家庭管理员。'}
                      </p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.updatedAt')}</label>
                      <p>{formatRelativeTime(selectedMemory.updated_at)}</p>
                    </div>
                    <div className="detail-field">
                      <label>修订历史</label>
                      {revisionsLoading ? (
                        <p>正在加载修订历史...</p>
                      ) : revisionError ? (
                        <p>{revisionError}</p>
                      ) : revisions.length > 0 ? (
                        <div className="memory-revision-list">
                          {revisions.slice(0, 5).map(revision => {
                            const isExpanded = expandedRevisionId === revision.id;
                            const changes = collectRevisionChanges(revision);

                            return (
                              <div key={revision.id} className="memory-revision-item">
                                <div className="memory-revision-item__top">
                                  <div className="memory-revision-item__summary">
                                    <strong>#{revision.revision_no} · {formatRevisionAction(revision.action)}</strong>
                                    <span>{revision.reason ?? '未填写原因'} · {formatRelativeTime(revision.created_at)}</span>
                                  </div>
                                  <button
                                    className="btn btn--outline btn--sm"
                                    type="button"
                                    onClick={() => setExpandedRevisionId(current => (current === revision.id ? null : revision.id))}
                                  >
                                    {isExpanded ? '收起' : '展开'}
                                  </button>
                                </div>
                                {isExpanded ? (
                                  <div className="memory-revision-diff">
                                    {changes.length > 0 ? (
                                      changes.map(change => (
                                        <div key={`${revision.id}-${change.field}`} className="memory-revision-diff__row">
                                          <span className="memory-revision-diff__label">{change.label}</span>
                                          <div className="memory-revision-diff__values">
                                            <div className="memory-revision-diff__card memory-revision-diff__card--before">
                                              <span className="memory-revision-diff__caption">变更前</span>
                                              <p>{change.beforeText}</p>
                                            </div>
                                            <span className="memory-revision-diff__arrow">→</span>
                                            <div className="memory-revision-diff__card memory-revision-diff__card--after">
                                              <span className="memory-revision-diff__caption">变更后</span>
                                              <p>{change.afterText}</p>
                                            </div>
                                          </div>
                                        </div>
                                      ))
                                    ) : (
                                      <div className="memory-revision-diff__empty">
                                        这次修订没有标题、内容、可见范围或状态上的差异。
                                      </div>
                                    )}
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p>当前还没有修订历史。</p>
                      )}
                    </div>
                  </div>
                  <div className="memory-detail__actions">
                    <button
                      className="btn btn--outline"
                      type="button"
                      disabled={!canEditSelectedMemory}
                      onClick={() => setEditingDraft({ title: selectedMemory.title, summary: selectedMemory.summary })}
                    >
                      {t('memory.edit')}
                    </button>
                    <button
                      className="btn btn--outline"
                      type="button"
                      disabled={!canEditSelectedMemory}
                      onClick={() => void handleCorrect()}
                    >
                      {t('memory.correct')}
                    </button>
                    <button
                      className="btn btn--outline btn--warning"
                      type="button"
                      disabled={!canEditSelectedMemory}
                      onClick={() => void handleInvalidate()}
                    >
                      {t('memory.invalidate')}
                    </button>
                    {canDeleteMemory ? (
                      <button
                        className="btn btn--outline btn--danger"
                        type="button"
                        disabled={!canEditSelectedMemory}
                        onClick={() => void handleDelete()}
                      >
                        {t('memory.delete')}
                      </button>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="memory-detail__empty">
                  <p>点击左侧记忆条目查看详情</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
