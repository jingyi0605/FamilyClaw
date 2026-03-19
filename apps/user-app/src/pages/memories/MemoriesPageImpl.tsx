import { useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { GuideAnchor, USER_GUIDE_ANCHOR_IDS, useAuthContext, useHouseholdContext, useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, EmptyState, PageHeader } from '../family/base';
import { api } from './api';
import { useMemoriesText } from './copy';
import { ScheduledTasksTab } from './ScheduledTasksTab';
import type { Member, MemoryCard, MemoryCardRevision, MemoryStatus, MemoryType, MemoryVisibility } from './types';

type MemoryFilterType = 'all' | 'fact' | 'event' | 'preference' | 'relation';
type MainTab = 'memories' | 'scheduledTasks';
type RevisionSnapshot = Record<string, unknown>;
type RevisionFieldKey = 'title' | 'content' | 'visibility' | 'status';

const LOADING_ICON = '\u23F3';
const MEMORY_FALLBACK_ICON = '\uD83D\uDCDD';
const CLOSE_ICON = '\u00D7';
const DIFF_ARROW_ICON = '\u2192';

const typeMap: Record<
  MemoryFilterType,
  { labelKey: 'memory.all' | 'memory.facts' | 'memory.events' | 'memory.preferences' | 'memory.relations'; icon: string }
> = {
  all: { labelKey: 'memory.all', icon: '\uD83D\uDCCB' },
  fact: { labelKey: 'memory.facts', icon: '\uD83D\uDCD6' },
  event: { labelKey: 'memory.events', icon: '\uD83D\uDCC5' },
  preference: { labelKey: 'memory.preferences', icon: '\u2764\uFE0F' },
  relation: { labelKey: 'memory.relations', icon: '\uD83D\uDD17' },
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

function formatRelativeTime(value: string, locale: string | undefined) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return getPageMessage(locale, 'memory.time.minutesAgo', { count: diffMinutes });
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return getPageMessage(locale, 'memory.time.hoursAgo', { count: diffHours });
  }

  return getPageMessage(locale, 'memory.time.daysAgo', { count: Math.round(diffHours / 24) });
}

function formatVisibility(visibility: MemoryVisibility, locale: string | undefined) {
  switch (visibility) {
    case 'public':
      return getPageMessage(locale, 'memory.visibility.public');
    case 'family':
      return getPageMessage(locale, 'memory.visibility.family');
    case 'private':
      return getPageMessage(locale, 'memory.visibility.private');
    case 'sensitive':
      return getPageMessage(locale, 'memory.visibility.sensitive');
  }
}

function formatStatus(status: MemoryStatus, locale: string | undefined) {
  switch (status) {
    case 'active':
      return getPageMessage(locale, 'memory.status.active');
    case 'pending_review':
      return getPageMessage(locale, 'memory.status.pendingReview');
    case 'invalidated':
      return getPageMessage(locale, 'memory.status.invalidated');
    case 'deleted':
      return getPageMessage(locale, 'memory.status.deleted');
  }
}

function formatRevisionAction(action: string, locale: string | undefined) {
  switch (action) {
    case 'create':
      return getPageMessage(locale, 'memory.revision.action.create');
    case 'correct':
      return getPageMessage(locale, 'memory.revision.action.correct');
    case 'invalidate':
      return getPageMessage(locale, 'memory.revision.action.invalidate');
    case 'delete':
      return getPageMessage(locale, 'memory.revision.action.delete');
    default:
      return action;
  }
}

function formatMetaItem(label: string, value: string, locale: string | undefined) {
  return getPageMessage(locale, 'memory.metaItem', { label, value });
}

function summarizeSource(card: MemoryCard, locale: string | undefined) {
  if (card.source_event_id) {
    return getPageMessage(locale, 'memory.source.eventGenerated');
  }
  if (card.created_by.includes('admin')) {
    return getPageMessage(locale, 'memory.source.adminConsole');
  }
  return getPageMessage(locale, 'memory.source.systemGenerated');
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
    return getPageMessage(locale, 'memory.owner.public');
  }

  if (card.visibility === 'family') {
    return getPageMessage(locale, 'memory.owner.family');
  }

  return getPageMessage(locale, 'memory.owner.unbound');
}

function getMemoryPermissionHint(card: MemoryCard, locale: string | undefined) {
  if (card.status === 'deleted') {
    return getPageMessage(locale, 'memory.permission.deleted');
  }
  if (card.visibility === 'sensitive') {
    return getPageMessage(locale, 'memory.permission.sensitive');
  }
  if (card.visibility === 'private') {
    return getPageMessage(locale, 'memory.permission.private');
  }
  return getPageMessage(locale, 'memory.permission.default');
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
    return getPageMessage(locale, 'memory.emptyValue');
  }

  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  if (typeof value === 'boolean') {
    return value ? getPageMessage(locale, 'memory.boolean.yes') : getPageMessage(locale, 'memory.boolean.no');
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return getPageMessage(locale, 'memory.emptyValue');
    }

    return value
      .map(item => {
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>;
          const memberId = typeof record.member_id === 'string' ? record.member_id : '';
          const relationRole = typeof record.relation_role === 'string' ? record.relation_role : '';

          if (memberId && relationRole) {
            return getPageMessage(locale, 'memory.value.memberRelation', { memberId, relationRole });
          }
          if (memberId || relationRole) {
            return memberId || relationRole;
          }
          return getPageMessage(locale, 'memory.emptyValue');
        }
        return String(item);
      })
      .join(getPageMessage(locale, 'memory.separator'));
  }

  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, nestedValue]) => getPageMessage(locale, 'memory.value.objectEntry', {
        key,
        value: formatRevisionValue(nestedValue, locale),
      }))
      .join(getPageMessage(locale, 'memory.separator'));
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
      return getPageMessage(locale, 'memory.field.title');
    case 'content':
      return getPageMessage(locale, 'memory.field.content');
    case 'visibility':
      return getPageMessage(locale, 'memory.field.visibility');
    case 'status':
      return getPageMessage(locale, 'memory.field.status');
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

function formatRevisionSummary(revision: MemoryCardRevision, locale: string | undefined) {
  return getPageMessage(locale, 'memory.revision.summary', {
    revisionNo: revision.revision_no,
    action: formatRevisionAction(revision.action, locale),
  });
}

function formatRevisionMeta(revision: MemoryCardRevision, locale: string | undefined) {
  return getPageMessage(locale, 'memory.revision.meta', {
    reason: revision.reason ?? getPageMessage(locale, 'memory.revision.noReason'),
    time: formatRelativeTime(revision.created_at, locale),
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
    void Taro.setNavigationBarTitle({ title: t('nav.memories') }).catch(() => undefined);
  }, [t, locale]);

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
          setError(loadError instanceof Error ? loadError.message : getPageMessage(locale, 'memory.loadFailed'));
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
          setRevisionError(getPageMessage(locale, 'memory.revision.loadDenied'));
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
        reason: getPageMessage(locale, 'memory.reason.correct'),
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus(getPageMessage(locale, 'memory.action.updated'));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : getPageMessage(locale, 'memory.action.updateFailed'));
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
        reason: getPageMessage(locale, 'memory.reason.invalidate'),
      });
      await refreshCurrentList();
      setSelectedId(updated.id);
      setActionStatus(getPageMessage(locale, 'memory.action.invalidated'));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : getPageMessage(locale, 'memory.action.invalidateFailed'));
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
        reason: getPageMessage(locale, 'memory.reason.delete'),
      });
      await refreshCurrentList();
      setSelectedId(null);
      setActionStatus(getPageMessage(locale, 'memory.action.deleted'));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : getPageMessage(locale, 'memory.action.deleteFailed'));
    }
  }

  return (
    <div className="page page--memories">
      <PageHeader
        title={t('nav.memories')}
        description={error ? getPageMessage(locale, 'memory.partialLoadFailed') : actionStatus || undefined}
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

            <GuideAnchor anchorId={USER_GUIDE_ANCHOR_IDS.memoriesOverview}>
              <div className="memory-list">
                {loading ? (
                  <EmptyState
                    icon={LOADING_ICON}
                    title={t('common.loading')}
                    description={getPageMessage(locale, 'memory.loadingRealData')}
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
                          {typeMap[(memory.memory_type === 'growth' ? 'event' : memory.memory_type) as MemoryFilterType]?.icon ?? MEMORY_FALLBACK_ICON}
                        </span>
                        <h3 className="memory-item-card__title">{memory.title}</h3>
                        <span className={`badge badge--${memory.status === 'active' ? 'success' : 'warning'}`}>
                          {formatStatus(memory.status, locale)}
                        </span>
                      </div>
                      <p className="memory-item-card__content">{memory.summary}</p>
                      <div className="memory-item-card__meta">
                        <span>{formatMetaItem(t('memory.source'), summarizeSource(memory, locale), locale)}</span>
                        <span>{formatMetaItem(t('memory.updatedAt'), formatRelativeTime(memory.updated_at, locale), locale)}</span>
                      </div>
                    </Card>
                  ))
                ) : (
                  <EmptyState
                    icon={MEMORY_FALLBACK_ICON}
                    title={t('memory.noResults')}
                    description={error || t('memory.noResultsHint')}
                  />
                )}
              </div>
            </GuideAnchor>

            <div className={`memory-detail ${selectedMemory ? 'memory-detail--open' : ''}`}>
              {selectedMemory ? (
                <>
                  <div className="memory-detail__header">
                    <h2>{t('memory.detail')}</h2>
                    <button className="close-btn" type="button" onClick={() => setSelectedId(null)}>
                      {CLOSE_ICON}
                    </button>
                  </div>
                  <div className="memory-detail__body">
                    <div className="detail-field">
                      <label>{getPageMessage(locale, 'memory.field.title')}</label>
                      <input
                        className="form-input"
                        value={editingDraft.title}
                        disabled={!canEditSelectedMemory}
                        onChange={event => setEditingDraft(current => ({ ...current, title: event.target.value }))}
                      />
                    </div>
                    <div className="detail-field">
                      <label>{getPageMessage(locale, 'memory.field.content')}</label>
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
                      <label>{getPageMessage(locale, 'memory.field.owner')}</label>
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
                      <label>{getPageMessage(locale, 'memory.field.actionNotes')}</label>
                      <p>{getMemoryPermissionHint(selectedMemory, locale)}</p>
                      <p>
                        {canDeleteMemory
                          ? getPageMessage(locale, 'memory.deleteAllowedHint')
                          : getPageMessage(locale, 'memory.deleteForbiddenHint')}
                      </p>
                    </div>
                    <div className="detail-field">
                      <label>{t('memory.updatedAt')}</label>
                      <p>{formatRelativeTime(selectedMemory.updated_at, locale)}</p>
                    </div>
                    <div className="detail-field">
                      <label>{getPageMessage(locale, 'memory.field.revisionHistory')}</label>
                      {revisionsLoading ? (
                        <p>{getPageMessage(locale, 'memory.revision.loading')}</p>
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
                                    <strong>{formatRevisionSummary(revision, locale)}</strong>
                                    <span>{formatRevisionMeta(revision, locale)}</span>
                                  </div>
                                  <button
                                    className="btn btn--outline btn--sm"
                                    type="button"
                                    onClick={() => setExpandedRevisionId(current => (current === revision.id ? null : revision.id))}
                                  >
                                    {isExpanded ? getPageMessage(locale, 'memory.revision.collapse') : getPageMessage(locale, 'memory.revision.expand')}
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
                                              <span className="memory-revision-diff__caption">{getPageMessage(locale, 'memory.revision.before')}</span>
                                              <p>{change.beforeText}</p>
                                            </div>
                                            <span className="memory-revision-diff__arrow">{DIFF_ARROW_ICON}</span>
                                            <div className="memory-revision-diff__card memory-revision-diff__card--after">
                                              <span className="memory-revision-diff__caption">{getPageMessage(locale, 'memory.revision.after')}</span>
                                              <p>{change.afterText}</p>
                                            </div>
                                          </div>
                                        </div>
                                      ))
                                    ) : (
                                      <div className="memory-revision-diff__empty">
                                        {getPageMessage(locale, 'memory.revision.noVisibleDiff')}
                                      </div>
                                    )}
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p>{getPageMessage(locale, 'memory.revision.empty')}</p>
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
                  <p>{getPageMessage(locale, 'memory.emptyDetailHint')}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
