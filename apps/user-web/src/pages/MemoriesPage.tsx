/* ============================================================
 * 记忆页 - 搜索 + 分类导航 + 列表 + 详情抽屉
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { useI18n, type MessageKey } from '../i18n';
import { PageHeader, Card, EmptyState } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import type { MemoryCard, MemoryCardRevision, MemoryStatus, MemoryType, MemoryVisibility } from '../lib/types';

const ACTOR_ROLE = (import.meta.env.VITE_API_ACTOR_ROLE ?? 'admin').toLowerCase();
const CAN_DELETE_MEMORY = ACTOR_ROLE === 'admin';

type MemoryFilterType = 'all' | 'fact' | 'event' | 'preference' | 'relation';

const typeMap: Record<MemoryFilterType, { labelKey: MessageKey; icon: string }> = {
  all: { labelKey: 'memory.all', icon: '📋' },
  fact: { labelKey: 'memory.facts', icon: '📌' },
  event: { labelKey: 'memory.events', icon: '📅' },
  preference: { labelKey: 'memory.preferences', icon: '💡' },
  relation: { labelKey: 'memory.relations', icon: '🔗' },
};

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return `${Math.round(diffHours / 24)} 天前`;
}

function formatVisibility(visibility: MemoryVisibility) {
  switch (visibility) {
    case 'public': return '公开可见';
    case 'family': return '全家可见';
    case 'private': return '私密';
    case 'sensitive': return '敏感';
  }
}

function formatStatus(status: MemoryStatus) {
  switch (status) {
    case 'active': return '有效';
    case 'pending_review': return '待确认';
    case 'invalidated': return '已失效';
    case 'deleted': return '已删除';
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

function getDetailContent(card: MemoryCard) {
  if (card.summary) {
    return card.summary;
  }
  if (card.content) {
    return JSON.stringify(card.content, null, 2);
  }
  return '暂无详情内容';
}

const REVISION_FIELD_LABELS: Record<string, string> = {
  title: '标题',
  summary: '摘要',
  visibility: '可见范围',
  status: '状态',
  importance: '重要度',
  confidence: '置信度',
  subject_member_id: '主体成员',
  source_event_id: '来源事件',
  effective_at: '生效时间',
  last_observed_at: '最近观察时间',
  invalidated_at: '失效时间',
  content: '结构化内容',
  related_members: '关联成员',
};

const REVISION_VISIBLE_FIELDS = [
  'title',
  'summary',
  'visibility',
  'status',
  'importance',
  'confidence',
  'subject_member_id',
  'source_event_id',
  'effective_at',
  'last_observed_at',
  'invalidated_at',
  'content',
  'related_members',
] as const;

function parseRevisionSnapshot(value: string | null) {
  if (!value) {
    return null;
  }

  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
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
          const memberId = 'member_id' in item ? String(item.member_id) : '';
          const relationRole = 'relation_role' in item ? String(item.relation_role) : '';
          return [memberId, relationRole].filter(Boolean).join(' · ');
        }
        return String(item);
      })
      .join('、');
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, nestedValue]) => `${key}: ${formatRevisionValue(nestedValue)}`)
      .join('；');
  }
  return String(value);
}

function collectRevisionChanges(revision: MemoryCardRevision): Array<{
  field: string;
  label: string;
  beforeText: string;
  afterText: string;
}> {
  const before = parseRevisionSnapshot(revision.before_json);
  const after = parseRevisionSnapshot(revision.after_json);

  return REVISION_VISIBLE_FIELDS.flatMap(field => {
    const beforeValue = before?.[field];
    const afterValue = after?.[field];
    const beforeText = formatRevisionValue(beforeValue);
    const afterText = formatRevisionValue(afterValue);

    if (revision.action !== 'create' && beforeText === afterText) {
      return [];
    }

    if (revision.action === 'delete' && after === null && beforeValue === undefined) {
      return [];
    }

    return [{
      field,
      label: REVISION_FIELD_LABELS[field] ?? field,
      beforeText,
      afterText,
    }];
  });
}

export function MemoriesPage() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const [activeType, setActiveType] = useState<MemoryFilterType>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [memories, setMemories] = useState<MemoryCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionStatus, setActionStatus] = useState('');
  const [editingDraft, setEditingDraft] = useState({ title: '', summary: '' });
  const [revisions, setRevisions] = useState<MemoryCardRevision[]>([]);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [expandedRevisionId, setExpandedRevisionId] = useState<string | null>(null);
  const [revisionError, setRevisionError] = useState('');

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
          setSelectedId(current => current && result.items.some(item => item.id === current) ? current : result.items[0]?.id ?? null);
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

  const filtered = useMemo(() => memories.filter(m => (
    searchQuery === '' || m.title.includes(searchQuery) || m.summary.includes(searchQuery)
  )), [memories, searchQuery]);

  const selectedMemory = filtered.find(m => m.id === selectedId) ?? memories.find(m => m.id === selectedId) ?? null;
  const canEditSelectedMemory = selectedMemory ? selectedMemory.status !== 'deleted' : false;

  useEffect(() => {
    if (selectedMemory) {
      setEditingDraft({ title: selectedMemory.title, summary: selectedMemory.summary });
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
          setExpandedRevisionId(result.items[0]?.id ?? null);
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
      <PageHeader title={t('nav.memories')} description={error ? '部分或全部记忆数据加载失败。' : actionStatus || undefined} />

      <div className="memory-search">
        <input
          type="text"
          placeholder={t('memory.search')}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="search-input search-input--lg"
        />
      </div>

      <div className="memory-layout">
        <nav className="memory-categories">
          {(Object.keys(typeMap) as MemoryFilterType[]).map(type => (
            <button
              key={type}
              className={`memory-cat-btn ${activeType === type ? 'memory-cat-btn--active' : ''}`}
              onClick={() => setActiveType(type)}
            >
              <span>{typeMap[type].icon}</span>
              <span>{t(typeMap[type].labelKey)}</span>
            </button>
          ))}
        </nav>

        <div className="memory-list">
          {loading ? (
            <EmptyState icon="⏳" title={t('common.loading')} description="正在读取真实记忆数据" />
          ) : filtered.length > 0 ? filtered.map(m => (
            <Card
              key={m.id}
              className={`memory-item-card ${selectedId === m.id ? 'memory-item-card--selected' : ''}`}
              onClick={() => setSelectedId(m.id)}
            >
              <div className="memory-item-card__top">
                <span className="memory-item-card__icon">{typeMap[(m.memory_type === 'growth' ? 'event' : m.memory_type) as MemoryFilterType]?.icon ?? '📝'}</span>
                <h3 className="memory-item-card__title">{m.title}</h3>
                <span className={`badge badge--${m.status === 'active' ? 'success' : 'warning'}`}>{formatStatus(m.status)}</span>
              </div>
              <p className="memory-item-card__content">{m.summary}</p>
              <div className="memory-item-card__meta">
                <span>{t('memory.source')}：{summarizeSource(m)}</span>
                <span>{t('memory.updatedAt')}：{formatRelativeTime(m.updated_at)}</span>
              </div>
            </Card>
          )) : (
            <EmptyState icon="📝" title={t('memory.noResults')} description={error || t('memory.noResultsHint')} />
          )}
        </div>

        <div className={`memory-detail ${selectedMemory ? 'memory-detail--open' : ''}`}>
          {selectedMemory ? (
            <>
              <div className="memory-detail__header">
                <h2>{t('memory.detail')}</h2>
                <button className="close-btn" onClick={() => setSelectedId(null)}>✕</button>
              </div>
              <div className="memory-detail__body">
                <div className="detail-field">
                  <label>{t('memory.detail')}</label>
                  <input className="form-input" value={editingDraft.title} disabled={!canEditSelectedMemory} onChange={event => setEditingDraft(current => ({ ...current, title: event.target.value }))} />
                </div>
                <div className="detail-field">
                  <label>内容</label>
                  <textarea className="form-input" value={editingDraft.summary} disabled={!canEditSelectedMemory} onChange={event => setEditingDraft(current => ({ ...current, summary: event.target.value }))} rows={5} />
                </div>
                <div className="detail-field">
                  <label>{t('memory.source')}</label>
                  <p>{summarizeSource(selectedMemory)}</p>
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
                  <p>{CAN_DELETE_MEMORY ? '当前身份允许删除记忆，但删除后只保留修订记录。' : '当前身份没有删除权限，如需删除请联系家庭管理员。'}</p>
                </div>
                <div className="detail-field">
                  <label>{t('memory.updatedAt')}</label>
                  <p>{formatRelativeTime(selectedMemory.updated_at)}</p>
                </div>
                <div className="detail-field">
                  <label>修订历史</label>
                  {revisionsLoading ? <p>正在加载修订历史...</p> : revisionError ? <p>{revisionError}</p> : revisions.length > 0 ? (
                    <div className="memory-revision-list">
                      {revisions.slice(0, 5).map(revision => {
                        const isExpanded = expandedRevisionId === revision.id;
                        const changes = collectRevisionChanges(revision);

                        return (
                          <div key={revision.id} className="memory-revision-item">
                            <div className="memory-revision-item__top">
                              <div className="memory-revision-item__summary">
                                <strong>#{revision.revision_no} · {revision.action}</strong>
                                <span>{revision.reason ?? '无原因'} · {formatRelativeTime(revision.created_at)}</span>
                              </div>
                              <button className="btn btn--outline btn--sm" type="button" onClick={() => setExpandedRevisionId(current => current === revision.id ? null : revision.id)}>
                                {isExpanded ? '收起' : '展开'}
                              </button>
                            </div>
                            {isExpanded && (
                              <div className="memory-revision-diff">
                                {changes.length > 0 ? changes.map(change => (
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
                                )) : (
                                  <div className="memory-revision-diff__empty">
                                    这次修订没有可展示的字段差异，可能主要变更了内部元数据。
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : <p>当前还没有修订历史。</p>}
                </div>
              </div>
              <div className="memory-detail__actions">
                <button className="btn btn--outline" disabled={!canEditSelectedMemory} onClick={() => setEditingDraft({ title: selectedMemory.title, summary: selectedMemory.summary })}>{t('memory.edit')}</button>
                <button className="btn btn--outline" disabled={!canEditSelectedMemory} onClick={() => void handleCorrect()}>{t('memory.correct')}</button>
                <button className="btn btn--outline btn--warning" disabled={!canEditSelectedMemory} onClick={() => void handleInvalidate()}>{t('memory.invalidate')}</button>
                {CAN_DELETE_MEMORY ? (
                  <button className="btn btn--outline btn--danger" disabled={!canEditSelectedMemory} onClick={() => void handleDelete()}>{t('memory.delete')}</button>
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
    </div>
  );
}
