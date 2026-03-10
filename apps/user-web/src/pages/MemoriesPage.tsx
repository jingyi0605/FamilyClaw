/* ============================================================
 * 记忆页 - 搜索 + 分类导航 + 列表 + 详情抽屉
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { useI18n, type MessageKey } from '../i18n';
import { PageHeader, Card, EmptyState } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import type { MemoryCard, MemoryStatus, MemoryType, MemoryVisibility } from '../lib/types';

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

function getDetailContent(card: MemoryCard) {
  if (card.summary) {
    return card.summary;
  }
  if (card.content) {
    return JSON.stringify(card.content, null, 2);
  }
  return '暂无详情内容';
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

  useEffect(() => {
    if (selectedMemory) {
      setEditingDraft({ title: selectedMemory.title, summary: selectedMemory.summary });
    }
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
                  <input className="form-input" value={editingDraft.title} onChange={event => setEditingDraft(current => ({ ...current, title: event.target.value }))} />
                </div>
                <div className="detail-field">
                  <label>内容</label>
                  <textarea className="form-input" value={editingDraft.summary} onChange={event => setEditingDraft(current => ({ ...current, summary: event.target.value }))} rows={5} />
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
                  <label>{t('memory.updatedAt')}</label>
                  <p>{formatRelativeTime(selectedMemory.updated_at)}</p>
                </div>
              </div>
              <div className="memory-detail__actions">
                <button className="btn btn--outline" onClick={() => setEditingDraft({ title: selectedMemory.title, summary: selectedMemory.summary })}>{t('memory.edit')}</button>
                <button className="btn btn--outline" onClick={() => void handleCorrect()}>{t('memory.correct')}</button>
                <button className="btn btn--outline btn--warning" onClick={() => void handleInvalidate()}>{t('memory.invalidate')}</button>
                <button className="btn btn--outline btn--danger" onClick={() => void handleDelete()}>{t('memory.delete')}</button>
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
