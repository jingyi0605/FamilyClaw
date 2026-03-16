import { useEffect, useMemo, useState } from 'react';
import { useAuthContext, useHouseholdContext, useI18n } from '../../runtime';
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
  getValue: (snapshot: RevisionSnapshot | null) => unknown;
}> = [
  {
    key: 'title',
    getValue: snapshot => snapshot?.title,
  },
  {
    key: 'content',
    getValue: snapshot => snapshot?.summary ?? snapshot?.content,
  },
  {
    key: 'visibility',
    getValue: snapshot => snapshot?.visibility,
  },
  {
    key: 'status',
    getValue: snapshot => snapshot?.status,
  },
];

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) return values.enUS;
  if (locale?.toLowerCase().startsWith('zh-tw')) return values.zhTW;
  return values.zhCN;
}

function formatRelativeTime(value: string, locale: string | undefined) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return pickLocaleText(locale, { zhCN: `${diffMinutes} 分钟前`, zhTW: `${diffMinutes} 分鐘前`, enUS: `${diffMinutes} minutes ago` });
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return pickLocaleText(locale, { zhCN: `${diffHours} 小时前`, zhTW: `${diffHours} 小時前`, enUS: `${diffHours} hours ago` });
  }

  return pickLocaleText(locale, { zhCN: `${Math.round(diffHours / 24)} 天前`, zhTW: `${Math.round(diffHours / 24)} 天前`, enUS: `${Math.round(diffHours / 24)} days ago` });
}

function formatVisibility(visibility: MemoryVisibility, locale: string | undefined) {
  switch (visibility) {
    case 'public':
      return pickLocaleText(locale, { zhCN: '公开可见', zhTW: '公開可見', enUS: 'Public' });
    case 'family':
      return pickLocaleText(locale, { zhCN: '全家可见', zhTW: '全家可見', enUS: 'Family visible' });
    case 'private':
      return pickLocaleText(locale, { zhCN: '私密', zhTW: '私密', enUS: 'Private' });
    case 'sensitive':
      return pickLocaleText(locale, { zhCN: '敏感', zhTW: '敏感', enUS: 'Sensitive' });
  }
}

function formatStatus(status: MemoryStatus, locale: string | undefined) {
  switch (status) {
    case 'active':
      return pickLocaleText(locale, { zhCN: '有效', zhTW: '有效', enUS: 'Active' });
    case 'pending_review':
      return pickLocaleText(locale, { zhCN: '待确认', zhTW: '待確認', enUS: 'Pending review' });
    case 'invalidated':
      return pickLocaleText(locale, { zhCN: '已失效', zhTW: '已失效', enUS: 'Invalidated' });
    case 'deleted':
      return pickLocaleText(locale, { zhCN: '已删除', zhTW: '已刪除', enUS: 'Deleted' });
  }
}

function formatRevisionAction(action: string, locale: string | undefined) {
  switch (action) {
    case 'create':
      return pickLocaleText(locale, { zhCN: '创建', zhTW: '建立', enUS: 'Created' });
    case 'correct':
      return pickLocaleText(locale, { zhCN: '更正', zhTW: '更正', enUS: 'Corrected' });
    case 'invalidate':
      return pickLocaleText(locale, { zhCN: '标记失效', zhTW: '標記失效', enUS: 'Invalidated' });
    case 'delete':
      return pickLocaleText(locale, { zhCN: '删除', zhTW: '刪除', enUS: 'Deleted' });
    default:
      return action;
  }
}

function summarizeSource(card: MemoryCard, locale: string | undefined) {
  if (card.source_event_id) {
    return pickLocaleText(locale, { zhCN: '事件生成', zhTW: '事件生成', enUS: 'Event generated' });
  }
  if (card.created_by.includes('admin')) {
    return pickLocaleText(locale, { zhCN: '管理台录入', zhTW: '管理台錄入', enUS: 'Entered from admin console' });
  }
  return pickLocaleText(locale, { zhCN: '系统生成', zhTW: '系統生成', enUS: 'System generated' });
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

function getMemoryOwnerLabel(card: MemoryCard, members: Member[], locale: string | undefined) {
  if (card.subject_member_id) {
    const owner = members.find(member => member.id === card.subject_member_id);
    return owner ? getMemberDisplayName(owner) : card.subject_member_id;
  }

  if (card.visibility === 'public') {
    return pickLocaleText(locale, { zhCN: '家庭公开记忆', zhTW: '家庭公開記憶', enUS: 'Public household memory' });
  }

  if (card.visibility === 'family') {
    return pickLocaleText(locale, { zhCN: '全家共享记忆', zhTW: '全家共享記憶', enUS: 'Family shared memory' });
  }

  return pickLocaleText(locale, { zhCN: '未绑定成员', zhTW: '未綁定成員', enUS: 'No bound member' });
}

function getMemoryPermissionHint(card: MemoryCard, locale: string | undefined) {
  if (card.status === 'deleted') {
    return pickLocaleText(locale, { zhCN: '这条记忆已经删除，只保留查看记录，不能继续修改。', zhTW: '這條記憶已刪除，只保留查看記錄，不能繼續修改。', enUS: 'This memory has been deleted. Only its history is kept, and it can no longer be edited.' });
  }
  if (card.visibility === 'sensitive') {
    return pickLocaleText(locale, { zhCN: '这条记忆属于敏感内容，修改前请先确认是否真的需要保留或更正。', zhTW: '這條記憶屬於敏感內容，修改前請先確認是否真的需要保留或更正。', enUS: 'This memory is sensitive. Confirm whether it truly needs to be kept or corrected before editing.' });
  }
  if (card.visibility === 'private') {
    return pickLocaleText(locale, { zhCN: '这条记忆是私密范围，建议只在确认归属和内容准确时再修改。', zhTW: '這條記憶是私密範圍，建議只在確認歸屬和內容準確時再修改。', enUS: 'This memory is private. Edit it only after confirming ownership and accuracy.' });
  }
  return pickLocaleText(locale, { zhCN: '你可以在这里更正文案或标记失效，系统会保留修订历史。', zhTW: '您可以在這裡更正文案或標記失效，系統會保留修訂歷史。', enUS: 'You can correct the content or invalidate it here. The system will keep the revision history.' });
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

function formatRevisionValue(value: unknown, locale: string | undefined): string {
  if (value === null || value === undefined || value === '') {
    return pickLocaleText(locale, { zhCN: '空', zhTW: '空', enUS: 'Empty' });
  }

  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  if (typeof value === 'boolean') {
    return value ? pickLocaleText(locale, { zhCN: '是', zhTW: '是', enUS: 'Yes' }) : pickLocaleText(locale, { zhCN: '否', zhTW: '否', enUS: 'No' });
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return pickLocaleText(locale, { zhCN: '空', zhTW: '空', enUS: 'Empty' });
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
      .join(pickLocaleText(locale, { zhCN: '，', zhTW: '，', enUS: ', ' }));
  }

  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, nestedValue]) => `${key}: ${formatRevisionValue(nestedValue, locale)}`)
      .join(pickLocaleText(locale, { zhCN: '，', zhTW: '，', enUS: ', ' }));
  }

  return String(value);
}

function formatRevisionFieldValue(field: RevisionFieldKey, value: unknown, locale: string | undefined) {
  if (field === 'visibility' && typeof value === 'string') {
    return ['public', 'family', 'private', 'sensitive'].includes(value)
      ? formatVisibility(value as MemoryVisibility, locale)
      : value;
  }

  if (field === 'status' && typeof value === 'string') {
    return ['active', 'pending_review', 'invalidated', 'deleted'].includes(value)
      ? formatStatus(value as MemoryStatus, locale)
      : value;
  }

  return formatRevisionValue(value, locale);
}

function formatRevisionFieldLabel(field: RevisionFieldKey, locale: string | undefined) {
  switch (field) {
    case 'title':
      return pickLocaleText(locale, { zhCN: '标题', zhTW: '標題', enUS: 'Title' });
    case 'content':
      return pickLocaleText(locale, { zhCN: '内容', zhTW: '內容', enUS: 'Content' });
    case 'visibility':
      return pickLocaleText(locale, { zhCN: '可见范围', zhTW: '可見範圍', enUS: 'Visibility' });
    case 'status':
      return pickLocaleText(locale, { zhCN: '状态', zhTW: '狀態', enUS: 'Status' });
  }
}

function collectRevisionChanges(revision: MemoryCardRevision, locale: string | undefined) {
  const before = parseRevisionSnapshot(revision.before_json);
  const after = parseRevisionSnapshot(revision.after_json);

  return REVISION_VISIBLE_FIELDS.flatMap(field => {
    const beforeValue = field.getValue(before);
    const afterValue = field.getValue(after);
    const beforeText = formatRevisionFieldValue(field.key, beforeValue, locale);
    const afterText = formatRevisionFieldValue(field.key, afterValue, locale);

    if (revision.action !== 'create' && beforeText === afterText) {
      return [];
    }

    if (revision.action === 'delete' && after === null && beforeValue === undefined) {
      return [];
    }

    return [{
      field: field.key,
      label: formatRevisionFieldLabel(field.key, locale),
      beforeText,
      afterText,
    }];
  });
}

export function MemoriesPageImpl() {
  const t = useMemoriesText();
  const { locale } = useI18n();
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
          setError(loadError instanceof Error ? loadError.message : pickLocaleText(locale, { zhCN: '加载记忆失败', zhTW: '載入記憶失敗', enUS: 'Failed to load memories' }));
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
          setRevisionError(pickLocaleText(locale, { zhCN: '当前身份暂时不能查看修订历史，或者这条记忆没有公开修订记录。', zhTW: '目前身份暫時不能查看修訂歷史，或者這條記憶沒有公開修訂記錄。', enUS: 'Your current role cannot view the revision history, or this memory does not expose any public revisions.' }));
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
        reason: pickLocaleText(locale, { zhCN: '用户在记忆页手动纠错', zhTW: '使用者在記憶頁手動更正', enUS: 'User corrected the memory manually from the memories page' }),
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus(pickLocaleText(locale, { zhCN: '记忆已更新。', zhTW: '記憶已更新。', enUS: 'Memory updated.' }));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : pickLocaleText(locale, { zhCN: '纠错失败', zhTW: '更正失敗', enUS: 'Correction failed' }));
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
        reason: pickLocaleText(locale, { zhCN: '用户在记忆页标记失效', zhTW: '使用者在記憶頁標記失效', enUS: 'User invalidated the memory from the memories page' }),
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus(pickLocaleText(locale, { zhCN: '记忆已标记失效。', zhTW: '記憶已標記失效。', enUS: 'Memory invalidated.' }));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : pickLocaleText(locale, { zhCN: '标记失效失败', zhTW: '標記失效失敗', enUS: 'Failed to invalidate the memory' }));
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
        reason: pickLocaleText(locale, { zhCN: '用户在记忆页删除记忆', zhTW: '使用者在記憶頁刪除記憶', enUS: 'User deleted the memory from the memories page' }),
      });
      await refreshCurrentList();
      setSelectedId(null);
      setActionStatus(pickLocaleText(locale, { zhCN: '记忆已删除。', zhTW: '記憶已刪除。', enUS: 'Memory deleted.' }));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : pickLocaleText(locale, { zhCN: '删除失败', zhTW: '刪除失敗', enUS: 'Delete failed' }));
    }
  }

  return (
    <div className="page page--memories">
      <PageHeader
        title={t('nav.memories')}
        description={error ? pickLocaleText(locale, { zhCN: '部分或全部记忆数据加载失败。', zhTW: '部分或全部記憶資料載入失敗。', enUS: 'Some or all memory data failed to load.' }) : actionStatus || undefined}
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
                  description={pickLocaleText(locale, { zhCN: '正在读取真实记忆数据', zhTW: '正在讀取真實記憶資料', enUS: 'Loading real memory data' })}
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
                        {formatStatus(memory.status, locale)}
                      </span>
                    </div>
                    <p className="memory-item-card__content">{memory.summary}</p>
                    <div className="memory-item-card__meta">
                      <span>{t('memory.source')}：{summarizeSource(memory, locale)}</span>
                      <span>{t('memory.updatedAt')}：{formatRelativeTime(memory.updated_at, locale)}</span>
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
                      <label>{pickLocaleText(locale, { zhCN: '标题', zhTW: '標題', enUS: 'Title' })}</label>
                      <input
                        className="form-input"
                        value={editingDraft.title}
                        disabled={!canEditSelectedMemory}
                        onChange={event => setEditingDraft(current => ({ ...current, title: event.target.value }))}
                      />
                    </div>
                    <div className="detail-field">
                      <label>{pickLocaleText(locale, { zhCN: '内容', zhTW: '內容', enUS: 'Content' })}</label>
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
                      <p>{summarizeSource(selectedMemory, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{pickLocaleText(locale, { zhCN: '归属', zhTW: '歸屬', enUS: 'Owner' })}</label>
                      <p>{getMemoryOwnerLabel(selectedMemory, members, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.visibility')}</label>
                      <p>{formatVisibility(selectedMemory.visibility, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.status')}</label>
                      <p>{formatStatus(selectedMemory.status, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{pickLocaleText(locale, { zhCN: '当前操作说明', zhTW: '目前操作說明', enUS: 'Current action notes' })}</label>
                      <p>{getMemoryPermissionHint(selectedMemory, locale)}</p>
                      <p>
                        {canDeleteMemory
                          ? pickLocaleText(locale, { zhCN: '当前身份允许删除记忆，但删除后只保留修订记录。', zhTW: '目前身份允許刪除記憶，但刪除後只保留修訂記錄。', enUS: 'Your current role can delete memories, but only the revision history will remain afterward.' })
                          : pickLocaleText(locale, { zhCN: '当前身份没有删除权限，如需删除请联系家庭管理员。', zhTW: '目前身份沒有刪除權限，如需刪除請聯繫家庭管理員。', enUS: 'Your current role cannot delete memories. Contact the household admin if deletion is needed.' })}
                      </p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.updatedAt')}</label>
                      <p>{formatRelativeTime(selectedMemory.updated_at, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{pickLocaleText(locale, { zhCN: '修订历史', zhTW: '修訂歷史', enUS: 'Revision history' })}</label>
                      {revisionsLoading ? (
                        <p>{pickLocaleText(locale, { zhCN: '正在加载修订历史...', zhTW: '正在載入修訂歷史...', enUS: 'Loading revision history...' })}</p>
                      ) : revisionError ? (
                        <p>{revisionError}</p>
                      ) : revisions.length > 0 ? (
                        <div className="memory-revision-list">
                          {revisions.slice(0, 5).map(revision => {
                            const isExpanded = expandedRevisionId === revision.id;
                            const changes = collectRevisionChanges(revision, locale);

                            return (
                              <div key={revision.id} className="memory-revision-item">
                                <div className="memory-revision-item__top">
                                  <div className="memory-revision-item__summary">
                                    <strong>#{revision.revision_no} · {formatRevisionAction(revision.action, locale)}</strong>
                                    <span>{revision.reason ?? pickLocaleText(locale, { zhCN: '未填写原因', zhTW: '未填寫原因', enUS: 'No reason provided' })} · {formatRelativeTime(revision.created_at, locale)}</span>
                                  </div>
                                  <button
                                    className="btn btn--outline btn--sm"
                                    type="button"
                                    onClick={() => setExpandedRevisionId(current => (current === revision.id ? null : revision.id))}
                                  >
                                    {isExpanded ? pickLocaleText(locale, { zhCN: '收起', zhTW: '收起', enUS: 'Collapse' }) : pickLocaleText(locale, { zhCN: '展开', zhTW: '展開', enUS: 'Expand' })}
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
                                              <span className="memory-revision-diff__caption">{pickLocaleText(locale, { zhCN: '变更前', zhTW: '變更前', enUS: 'Before' })}</span>
                                              <p>{change.beforeText}</p>
                                            </div>
                                            <span className="memory-revision-diff__arrow">→</span>
                                            <div className="memory-revision-diff__card memory-revision-diff__card--after">
                                              <span className="memory-revision-diff__caption">{pickLocaleText(locale, { zhCN: '变更后', zhTW: '變更後', enUS: 'After' })}</span>
                                              <p>{change.afterText}</p>
                                            </div>
                                          </div>
                                        </div>
                                      ))
                                    ) : (
                                      <div className="memory-revision-diff__empty">
                                        {pickLocaleText(locale, { zhCN: '这次修订没有标题、内容、可见范围或状态上的差异。', zhTW: '這次修訂在標題、內容、可見範圍或狀態上沒有差異。', enUS: 'This revision did not change the title, content, visibility, or status.' })}
                                      </div>
                                    )}
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p>{pickLocaleText(locale, { zhCN: '当前还没有修订历史。', zhTW: '目前還沒有修訂歷史。', enUS: 'There is no revision history yet.' })}</p>
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
                  <p>{pickLocaleText(locale, { zhCN: '点击左侧记忆条目查看详情', zhTW: '點擊左側記憶條目查看詳情', enUS: 'Click a memory item on the left to view details' })}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
