import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, Textarea, View } from '@tarojs/components';
import { useDidShow } from '@tarojs/taro';
import {
  MemoryCard,
  MemoryCardRevision,
  MemoryStatus,
  MemoryType,
  MemoryVisibility,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  OptionPills,
  PrimaryButton,
  SecondaryButton,
  SectionNote,
  TextInput,
} from '../../components/AppUi';
import { MainShellPage } from '../../components/MainShellPage';
import { coreApiClient, useAppRuntime } from '../../runtime';

type MemoryFilterType = 'all' | 'fact' | 'event' | 'preference' | 'relation';

const MEMORY_FILTER_OPTIONS: Array<{
  value: MemoryFilterType;
  label: string;
  icon: string;
}> = [
  { value: 'all', label: '全部', icon: '📋' },
  { value: 'fact', label: '事实', icon: '📌' },
  { value: 'event', label: '事件', icon: '📅' },
  { value: 'preference', label: '偏好', icon: '💡' },
  { value: 'relation', label: '关系', icon: '🔗' },
];

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

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '暂无';
  }

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
    default:
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
    default:
      return '已删除';
  }
}

function getFilterLabel(filterType: MemoryFilterType) {
  return MEMORY_FILTER_OPTIONS.find(option => option.value === filterType)?.label ?? '全部';
}

function summarizeSource(memory: MemoryCard) {
  if (memory.source_event_id) {
    return '事件生成';
  }

  if (memory.created_by.toLowerCase().includes('admin')) {
    return '管理端录入';
  }

  return '系统生成';
}

function mapFilterToMemoryType(filterType: MemoryFilterType): Exclude<MemoryType, 'growth'> | undefined {
  if (filterType === 'all') {
    return undefined;
  }

  return filterType as Exclude<MemoryType, 'growth'>;
}

function getMemoryPermissionHint(memory: MemoryCard) {
  if (memory.status === 'deleted') {
    return '这条记忆已经删除，只保留查看记录，不能继续修改。';
  }

  if (memory.visibility === 'sensitive') {
    return '这条记忆属于敏感内容，修改前先确认是否真的需要保留。';
  }

  if (memory.visibility === 'private') {
    return '这条记忆是私密范围，建议只在确认归属和内容准确时再改。';
  }

  return '你可以在这里纠正文案、标记失效或删除，系统会保留修订历史。';
}

function getDetailContent(memory: MemoryCard) {
  if (memory.summary.trim()) {
    return memory.summary;
  }

  if (memory.content) {
    return JSON.stringify(memory.content, null, 2);
  }

  return '暂无详情内容';
}

function canDeleteMemory(actorRoleCandidates: Array<string | null | undefined>) {
  return actorRoleCandidates.some(value => typeof value === 'string' && value.toLowerCase().includes('admin'));
}

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

    return value.map(item => {
      if (item && typeof item === 'object') {
        const memberId = 'member_id' in item ? String(item.member_id) : '';
        const relationRole = 'relation_role' in item ? String(item.relation_role) : '';
        return [memberId, relationRole].filter(Boolean).join(' · ');
      }

      return String(item);
    }).join('、');
  }

  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .slice(0, 4)
      .map(([key, nestedValue]) => `${key}: ${formatRevisionValue(nestedValue)}`)
      .join('；');
  }

  return String(value);
}

function collectRevisionChanges(revision: MemoryCardRevision) {
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

export default function MemoriesPage() {
  const { bootstrap } = useAppRuntime();
  const [activeType, setActiveType] = useState<MemoryFilterType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [memories, setMemories] = useState<MemoryCard[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [editingDraft, setEditingDraft] = useState({ title: '', summary: '' });
  const [revisions, setRevisions] = useState<MemoryCardRevision[]>([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [revisionError, setRevisionError] = useState('');
  const [expandedRevisionId, setExpandedRevisionId] = useState('');
  const activeHouseholdIdRef = useRef('');
  const listRequestIdRef = useRef(0);
  const revisionRequestIdRef = useRef(0);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';
  const allowDelete = canDeleteMemory([
    bootstrap?.actor?.member_role,
    bootstrap?.actor?.role,
    bootstrap?.actor?.account_type,
  ]);

  const filteredMemories = useMemo(() => memories.filter(memory => {
    if (!searchQuery.trim()) {
      return true;
    }

    const keyword = searchQuery.trim().toLowerCase();
    return [
      memory.title,
      memory.summary,
      memory.normalized_text ?? '',
      JSON.stringify(memory.content ?? {}),
    ].some(value => value.toLowerCase().includes(keyword));
  }), [memories, searchQuery]);

  const selectedMemory = useMemo(
    () => filteredMemories.find(memory => memory.id === selectedId) ?? memories.find(memory => memory.id === selectedId) ?? null,
    [filteredMemories, memories, selectedId],
  );

  const canEditSelectedMemory = selectedMemory ? selectedMemory.status !== 'deleted' : false;

  const loadMemories = useCallback(async (preferredSelectedId?: string | null) => {
    const householdId = currentHouseholdId;
    const requestId = ++listRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      activeHouseholdIdRef.current = householdId;
      setSearchQuery('');
      setStatus('');
      setError('');
      setSelectedId('');
      setRevisions([]);
      setExpandedRevisionId('');
      setRevisionError('');
    }

    if (!householdId) {
      setMemories([]);
      setSelectedId('');
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    try {
      const result = await coreApiClient.listMemoryCards({
        household_id: householdId,
        memory_type: mapFilterToMemoryType(activeType),
        page_size: 100,
      });

      if (requestId !== listRequestIdRef.current) {
        return;
      }

      setMemories(result.items);
      setSelectedId(current => {
        if (preferredSelectedId === null) {
          return result.items[0]?.id ?? '';
        }

        if (preferredSelectedId && result.items.some(item => item.id === preferredSelectedId)) {
          return preferredSelectedId;
        }

        if (current && result.items.some(item => item.id === current)) {
          return current;
        }

        return result.items[0]?.id ?? '';
      });
    } catch (loadError) {
      if (requestId === listRequestIdRef.current) {
        setError(loadError instanceof Error ? loadError.message : '记忆列表加载失败');
        setMemories([]);
        setSelectedId('');
      }
    } finally {
      if (requestId === listRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [activeType, currentHouseholdId]);

  const loadRevisions = useCallback(async (memoryId: string) => {
    const requestId = ++revisionRequestIdRef.current;
    setRevisionsLoading(true);
    setRevisionError('');

    try {
      const result = await coreApiClient.listMemoryCardRevisions(memoryId);
      if (requestId !== revisionRequestIdRef.current) {
        return;
      }

      setRevisions(result.items);
      setExpandedRevisionId(result.items[0]?.id ?? '');
    } catch {
      if (requestId === revisionRequestIdRef.current) {
        setRevisions([]);
        setExpandedRevisionId('');
        setRevisionError('当前身份暂时不能查看修订历史，或者这条记忆没有公开修订记录。');
      }
    } finally {
      if (requestId === revisionRequestIdRef.current) {
        setRevisionsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadMemories();
  }, [loadMemories]);

  useDidShow(() => {
    if (currentHouseholdId) {
      void loadMemories(selectedId || undefined);
    }
  });

  useEffect(() => {
    if (!selectedMemory) {
      setEditingDraft({ title: '', summary: '' });
      setRevisions([]);
      setExpandedRevisionId('');
      setRevisionError('');
      return;
    }

    setEditingDraft({
      title: selectedMemory.title,
      summary: selectedMemory.summary,
    });
    void loadRevisions(selectedMemory.id);
  }, [loadRevisions, selectedMemory?.id]);

  async function handleCorrect() {
    if (!selectedMemory) {
      return;
    }

    setActionBusy('correct');
    setStatus('');
    setError('');

    try {
      const updated = await coreApiClient.correctMemoryCard(selectedMemory.id, {
        action: 'correct',
        title: editingDraft.title.trim(),
        summary: editingDraft.summary.trim(),
        reason: '用户在 user-app 记忆页手动纠错',
      });
      await loadMemories(updated.id);
      await loadRevisions(updated.id);
      setStatus('记忆已更新。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '记忆纠错失败');
    } finally {
      setActionBusy('');
    }
  }

  async function handleInvalidate() {
    if (!selectedMemory) {
      return;
    }

    setActionBusy('invalidate');
    setStatus('');
    setError('');

    try {
      const updated = await coreApiClient.correctMemoryCard(selectedMemory.id, {
        action: 'invalidate',
        reason: '用户在 user-app 记忆页标记失效',
      });
      await loadMemories(updated.id);
      await loadRevisions(updated.id);
      setStatus('记忆已标记失效。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '标记失效失败');
    } finally {
      setActionBusy('');
    }
  }

  async function handleDelete() {
    if (!selectedMemory || !allowDelete) {
      return;
    }

    setActionBusy('delete');
    setStatus('');
    setError('');

    try {
      await coreApiClient.correctMemoryCard(selectedMemory.id, {
        action: 'delete',
        reason: '用户在 user-app 记忆页删除记忆',
      });
      await loadMemories(null);
      setStatus('记忆已删除。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '删除失败');
    } finally {
      setActionBusy('');
    }
  }

  return (
    <MainShellPage
      currentNav="memories"
      title="记忆主链已进入新应用"
      description="这页直接消费共享记忆模型和 API，不再把 user-web 的页面壳整坨抄回来。"
    >
      <PageSection title="当前记忆状态" description="先把家庭上下文、列表加载和可执行动作放在一层看清楚。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="当前分类" value={getFilterLabel(activeType)} tone="success" />
        <StatusCard label="列表数量" value={`${filteredMemories.length} / ${memories.length}`} tone="info" />
        <StatusCard label="删除权限" value={allowDelete ? '允许' : '仅管理员可删'} tone={allowDelete ? 'success' : 'warning'} />
        {pageLoading ? <SectionNote>正在读取当前家庭的记忆列表...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
      </PageSection>

      <PageSection title="搜索与分类" description="先把搜索、分类和家庭切换后的刷新一致性做实，不搞花哨导航。">
        <TextInput
          value={searchQuery}
          placeholder="按标题、摘要或结构化内容搜索"
          onInput={value => setSearchQuery(value)}
        />
        <View style={{ marginTop: '12px' }}>
          <OptionPills
            value={activeType}
            options={MEMORY_FILTER_OPTIONS.map(option => ({
              value: option.value,
              label: `${option.icon} ${option.label}`,
            }))}
            onChange={value => setActiveType(value)}
          />
        </View>
      </PageSection>

      <PageSection title="记忆列表" description="列表先做到真能加载、筛选、切换和反馈，不先追逐复杂抽屉。">
        {pageLoading ? (
          <EmptyStateCard title="正在加载记忆" description="共享记忆 API 正在拉取当前家庭的数据。" />
        ) : filteredMemories.length === 0 ? (
          <EmptyStateCard
            title="当前没有匹配的记忆"
            description={searchQuery.trim() ? '换个关键词试试，或者切到别的分类。' : '这个家庭当前还没有这类记忆。'}
          />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredMemories.map(memory => {
              const active = memory.id === selectedId;
              const filterOption = MEMORY_FILTER_OPTIONS.find(option => option.value === (memory.memory_type === 'growth' ? 'event' : memory.memory_type));

              return (
                <View
                  key={memory.id}
                  onClick={() => setSelectedId(memory.id)}
                  style={{
                    background: active ? '#eef5ff' : '#ffffff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <View style={{ alignItems: 'center', display: 'flex', flexDirection: 'row', justifyContent: 'space-between', gap: '12px' }}>
                    <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600', flex: 1 }}>
                      {filterOption?.icon ?? '📝'} {memory.title}
                    </Text>
                    <Text style={{ color: memory.status === 'active' ? userAppTokens.colorSuccess : userAppTokens.colorWarning, fontSize: '22px' }}>
                      {formatStatus(memory.status)}
                    </Text>
                  </View>
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', lineHeight: '1.6', marginTop: '8px' }}>
                    {memory.summary || '暂无摘要'}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', lineHeight: '1.6', marginTop: '8px' }}>
                    {summarizeSource(memory)} · {formatVisibility(memory.visibility)} · {formatRelativeTime(memory.updated_at)}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="记忆详情" description="详情里只保留真正会用到的查看、纠错、失效和删除动作。">
        {!selectedMemory ? (
          <EmptyStateCard title="还没选中记忆" description="从上面的列表点开一条，右边这些动作才有意义。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <View style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <Text style={{ color: userAppTokens.colorText, fontSize: '24px', fontWeight: '600' }}>标题</Text>
              <TextInput
                value={editingDraft.title}
                disabled={!canEditSelectedMemory || actionBusy !== ''}
                onInput={value => setEditingDraft(current => ({ ...current, title: value }))}
              />
            </View>

            <View style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <Text style={{ color: userAppTokens.colorText, fontSize: '24px', fontWeight: '600' }}>摘要</Text>
              <Textarea
                value={editingDraft.summary}
                disabled={!canEditSelectedMemory || actionBusy !== ''}
                autoHeight
                maxlength={2000}
                onInput={event => setEditingDraft(current => ({ ...current, summary: event.detail.value }))}
                style={{
                  background: '#ffffff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  color: userAppTokens.colorText,
                  fontSize: '24px',
                  minHeight: '150px',
                  padding: '16px',
                  width: '100%',
                }}
              />
            </View>

            <View
              style={{
                background: '#f9fbff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '24px' }}>详情内容：{getDetailContent(selectedMemory)}</Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>来源：{summarizeSource(selectedMemory)}</Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>可见范围：{formatVisibility(selectedMemory.visibility)}</Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>状态：{formatStatus(selectedMemory.status)}</Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>最近更新：{formatRelativeTime(selectedMemory.updated_at)}</Text>
              <SectionNote>{getMemoryPermissionHint(selectedMemory)}</SectionNote>
              <SectionNote tone={allowDelete ? 'muted' : 'warning'}>
                {allowDelete ? '当前身份允许删除记忆，但删除后只保留修订记录。' : '当前身份没有删除权限，如需删除请联系家庭管理员。'}
              </SectionNote>
            </View>

            <ActionRow>
              <PrimaryButton
                disabled={!canEditSelectedMemory || actionBusy !== '' || !editingDraft.title.trim() || !editingDraft.summary.trim()}
                onClick={() => void handleCorrect()}
              >
                {actionBusy === 'correct' ? '保存中...' : '保存纠错'}
              </PrimaryButton>
              <SecondaryButton
                disabled={!canEditSelectedMemory || actionBusy !== ''}
                onClick={() => void handleInvalidate()}
              >
                {actionBusy === 'invalidate' ? '处理中...' : '标记失效'}
              </SecondaryButton>
              {allowDelete ? (
                <Button
                  disabled={!canEditSelectedMemory || actionBusy !== ''}
                  onClick={() => void handleDelete()}
                  style={{
                    background: '#fff5f2',
                    border: `1px solid ${userAppTokens.colorWarning}`,
                    borderRadius: userAppTokens.radiusMd,
                    color: userAppTokens.colorWarning,
                    fontSize: '24px',
                  }}
                >
                  {actionBusy === 'delete' ? '处理中...' : '删除记忆'}
                </Button>
              ) : null}
            </ActionRow>
          </View>
        )}
      </PageSection>

      <PageSection title="修订历史" description="修订历史必须可读，不然所谓纠错就是瞎改。">
        {!selectedMemory ? (
          <EmptyStateCard title="还没有可看的修订历史" description="先选中一条记忆，这里才知道该展示谁的历史。" />
        ) : revisionsLoading ? (
          <EmptyStateCard title="正在加载修订历史" description="共享记忆修订 API 正在返回最近变更。" />
        ) : revisionError ? (
          <EmptyStateCard title="修订历史暂时不可用" description={revisionError} />
        ) : revisions.length === 0 ? (
          <EmptyStateCard title="当前还没有修订历史" description="这条记忆目前还没有公开可读的修订记录。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {revisions.slice(0, 5).map(revision => {
              const expanded = expandedRevisionId === revision.id;
              const changes = collectRevisionChanges(revision);

              return (
                <View
                  key={revision.id}
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <View style={{ alignItems: 'center', display: 'flex', flexDirection: 'row', justifyContent: 'space-between', gap: '12px' }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', fontWeight: '600' }}>
                        #{revision.revision_no} · {revision.action}
                      </Text>
                      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '4px' }}>
                        {revision.reason ?? '无原因'} · {formatRelativeTime(revision.created_at)}
                      </Text>
                    </View>
                    <Button
                      size="mini"
                      onClick={() => setExpandedRevisionId(current => current === revision.id ? '' : revision.id)}
                      style={{
                        background: userAppTokens.colorSurface,
                        border: `1px solid ${userAppTokens.colorBorder}`,
                        borderRadius: userAppTokens.radiusMd,
                        color: userAppTokens.colorText,
                      }}
                    >
                      {expanded ? '收起' : '展开'}
                    </Button>
                  </View>

                  {expanded ? (
                    <View style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
                      {changes.length > 0 ? changes.map(change => (
                        <View
                          key={`${revision.id}-${change.field}`}
                          style={{
                            background: '#f9fbff',
                            border: `1px solid ${userAppTokens.colorBorder}`,
                            borderRadius: userAppTokens.radiusMd,
                            padding: userAppTokens.spacingSm,
                          }}
                        >
                          <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', fontWeight: '600' }}>
                            {change.label}
                          </Text>
                          <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                            变更前：{change.beforeText}
                          </Text>
                          <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '20px', marginTop: '4px' }}>
                            变更后：{change.afterText}
                          </Text>
                        </View>
                      )) : (
                        <SectionNote>这次修订没有可展示的字段差异，主要改动可能在内部元数据。</SectionNote>
                      )}
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>
        )}
      </PageSection>
    </MainShellPage>
  );
}
