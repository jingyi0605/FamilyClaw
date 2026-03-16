import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../../assistant/assistant.agents';
import { Card } from '../../family/base';
import { parseTags, stringifyTags } from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type { AgentDetail, AgentSummary, Member } from '../settingsTypes';

type CreateFormState = {
  displayName: string;
  agentType: 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
  selfIdentity: string;
  roleSummary: string;
  introMessage: string;
  speakingStyle: string;
  personalityTraits: string;
  serviceFocus: string;
};

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) return values.enUS;
  if (locale?.toLowerCase().startsWith('zh-tw')) return values.zhTW;
  return values.zhCN;
}

function buildCreateForm(locale: string | undefined): CreateFormState {
  return {
    displayName: pickLocaleText(locale, { zhCN: '家庭管家', zhTW: '家庭管家', enUS: 'Household Butler' }),
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: pickLocaleText(locale, { zhCN: '负责家庭问答、提醒和日常陪伴。', zhTW: '負責家庭問答、提醒和日常陪伴。', enUS: 'Responsible for household Q&A, reminders, and everyday companionship.' }),
    introMessage: pickLocaleText(locale, { zhCN: '你好，我是你的家庭管家。', zhTW: '你好，我是你的家庭管家。', enUS: 'Hello, I am your household butler.' }),
    speakingStyle: pickLocaleText(locale, { zhCN: '温和、清晰、让人安心', zhTW: '溫和、清晰、讓人安心', enUS: 'Gentle, clear, and reassuring' }),
    personalityTraits: pickLocaleText(locale, { zhCN: '细心, 稳定, 可靠', zhTW: '細心, 穩定, 可靠', enUS: 'Thoughtful, steady, reliable' }),
    serviceFocus: pickLocaleText(locale, { zhCN: '家庭问答, 日常提醒, 成员关怀', zhTW: '家庭問答, 日常提醒, 成員關懷', enUS: 'Household Q&A, daily reminders, member care' }),
  };
}

export function AgentConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  onlyButler?: boolean;
  onChanged?: () => Promise<void> | void;
}) {
  const { locale } = useI18n();
  const { householdId, compact = false, onlyButler = false, onChanged } = props;
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState<CreateFormState>(buildCreateForm(locale));
  const [baseForm, setBaseForm] = useState({ displayName: '', status: 'active', sortOrder: '100' });
  const [soulForm, setSoulForm] = useState({
    selfIdentity: '',
    roleSummary: '',
    introMessage: '',
    speakingStyle: '',
    personalityTraits: '',
    serviceFocus: '',
  });
  const [runtimeForm, setRuntimeForm] = useState({
    conversationEnabled: true,
    defaultEntry: false,
    routingTags: '',
    memoryActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    configActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    operationActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
  });
  const [cognitionForm, setCognitionForm] = useState<Record<string, {
    displayAddress: string;
    closenessLevel: string;
    servicePriority: string;
    communicationStyle: string;
    promptNotes: string;
  }>>({});

  const visibleAgents = useMemo(
    () => agents.filter(item => !onlyButler || item.agent_type === 'butler'),
    [agents, onlyButler],
  );

  const createActionLabel = compact
    ? pickLocaleText(locale, { zhCN: '创建第一个 AI 管家', zhTW: '建立第一個 AI 管家', enUS: 'Create the first AI butler' })
    : (onlyButler
      ? pickLocaleText(locale, { zhCN: '添加 AI 管家', zhTW: '新增 AI 管家', enUS: 'Add AI butler' })
      : pickLocaleText(locale, { zhCN: '添加 AI 助手', zhTW: '新增 AI 助手', enUS: 'Add AI agent' }));
  const createDisabled = (
    saving
    || !createForm.displayName.trim()
    || !createForm.selfIdentity.trim()
    || !createForm.roleSummary.trim()
    || parseTags(createForm.personalityTraits).length === 0
    || parseTags(createForm.serviceFocus).length === 0
  );

  const actionOptions = [
    { value: 'ask', label: pickLocaleText(locale, { zhCN: '先询问我', zhTW: '先詢問我', enUS: 'Ask me first' }) },
    { value: 'notify', label: pickLocaleText(locale, { zhCN: '先处理再告诉我', zhTW: '先處理再告訴我', enUS: 'Handle first, then tell me' }) },
    { value: 'auto', label: pickLocaleText(locale, { zhCN: '自动处理', zhTW: '自動處理', enUS: 'Handle automatically' }) },
  ] as const;
  const copy = {
    loadFailed: pickLocaleText(locale, { zhCN: '加载 AI 助手失败', zhTW: '載入 AI 助手失敗', enUS: 'Failed to load AI agents' }),
    loadDetailFailed: pickLocaleText(locale, { zhCN: '加载助手详情失败', zhTW: '載入助手詳情失敗', enUS: 'Failed to load the agent details' }),
    createdStatus: (name: string) => pickLocaleText(locale, { zhCN: `已添加 AI 助手：${name}`, zhTW: `已新增 AI 助手：${name}`, enUS: `AI agent added: ${name}` }),
    createFailed: pickLocaleText(locale, { zhCN: '添加 AI 助手失败', zhTW: '新增 AI 助手失敗', enUS: 'Failed to add the AI agent' }),
    saveBaseSuccess: pickLocaleText(locale, { zhCN: '基本信息已保存', zhTW: '基本資訊已儲存', enUS: 'Basic information saved' }),
    saveBaseFailed: pickLocaleText(locale, { zhCN: '保存基本信息失败', zhTW: '儲存基本資訊失敗', enUS: 'Failed to save the basic information' }),
    saveSoulSuccess: pickLocaleText(locale, { zhCN: '角色设定已保存', zhTW: '角色設定已儲存', enUS: 'Role settings saved' }),
    saveSoulFailed: pickLocaleText(locale, { zhCN: '保存角色设定失败', zhTW: '儲存角色設定失敗', enUS: 'Failed to save the role settings' }),
    saveRuntimeSuccess: pickLocaleText(locale, { zhCN: '使用方式已保存', zhTW: '使用方式已儲存', enUS: 'Usage settings saved' }),
    saveRuntimeFailed: pickLocaleText(locale, { zhCN: '保存使用方式失败', zhTW: '儲存使用方式失敗', enUS: 'Failed to save usage settings' }),
    saveCognitionSuccess: pickLocaleText(locale, { zhCN: '与家人的互动方式已保存', zhTW: '與家人的互動方式已儲存', enUS: 'Household interaction settings saved' }),
    saveCognitionFailed: pickLocaleText(locale, { zhCN: '保存互动方式失败', zhTW: '儲存互動方式失敗', enUS: 'Failed to save the interaction settings' }),
    panelTitleCompact: pickLocaleText(locale, { zhCN: '创建第一个 AI 管家', zhTW: '建立第一個 AI 管家', enUS: 'Create the first AI butler' }),
    panelTitleButler: pickLocaleText(locale, { zhCN: 'AI 管家', zhTW: 'AI 管家', enUS: 'AI butler' }),
    panelTitleAgent: pickLocaleText(locale, { zhCN: 'AI 助手', zhTW: 'AI 助手', enUS: 'AI agents' }),
    panelDescriptionCompact: pickLocaleText(locale, {
      zhCN: '先创建一个 AI 管家，之后还可以继续完善名字、语气和服务内容。',
      zhTW: '先建立一個 AI 管家，之後還可以繼續完善名稱、語氣和服務內容。',
      enUS: 'Create an AI butler first. You can refine the name, tone, and service scope afterward.',
    }),
    panelDescriptionDefault: pickLocaleText(locale, {
      zhCN: '你可以在这里添加不同的 AI 助手，比如家庭管家、营养师或学习教练。',
      zhTW: '您可以在這裡新增不同的 AI 助手，例如家庭管家、營養師或學習教練。',
      enUS: 'Add different AI agents here, such as a household butler, nutritionist, or study coach.',
    }),
    loading: pickLocaleText(locale, { zhCN: '正在读取 AI 助手信息...', zhTW: '正在讀取 AI 助手資訊...', enUS: 'Loading AI agents...' }),
    conversationEnabled: pickLocaleText(locale, { zhCN: '可对话', zhTW: '可對話', enUS: 'Available for chat' }),
    conversationPaused: pickLocaleText(locale, { zhCN: '已暂停对话', zhTW: '已暫停對話', enUS: 'Conversation paused' }),
    summaryEmpty: pickLocaleText(locale, { zhCN: '还没有填写角色简介。', zhTW: '還沒有填寫角色簡介。', enUS: 'No role summary yet.' }),
    baseTitle: pickLocaleText(locale, { zhCN: '基本信息', zhTW: '基本資訊', enUS: 'Basic information' }),
    displayNameLabel: pickLocaleText(locale, { zhCN: '显示名称', zhTW: '顯示名稱', enUS: 'Display name' }),
    statusLabel: pickLocaleText(locale, { zhCN: '当前状态', zhTW: '目前狀態', enUS: 'Current status' }),
    sortOrderLabel: pickLocaleText(locale, { zhCN: '显示顺序', zhTW: '顯示順序', enUS: 'Display order' }),
    saveBaseButton: pickLocaleText(locale, { zhCN: '保存基本信息', zhTW: '儲存基本資訊', enUS: 'Save basic information' }),
    soulTitle: pickLocaleText(locale, { zhCN: '角色设定', zhTW: '角色設定', enUS: 'Role settings' }),
    selfIdentityLabel: pickLocaleText(locale, { zhCN: 'Ta 是谁', zhTW: 'Ta 是誰', enUS: 'Who is this agent?' }),
    roleSummaryLabel: pickLocaleText(locale, { zhCN: '角色简介', zhTW: '角色簡介', enUS: 'Role summary' }),
    introMessageLabel: pickLocaleText(locale, { zhCN: '开场问候', zhTW: '開場問候', enUS: 'Opening greeting' }),
    speakingStyleLabel: pickLocaleText(locale, { zhCN: '说话风格', zhTW: '說話風格', enUS: 'Speaking style' }),
    personalityTraitsLabel: pickLocaleText(locale, { zhCN: '性格特点', zhTW: '性格特點', enUS: 'Personality traits' }),
    serviceFocusLabel: pickLocaleText(locale, { zhCN: '擅长内容', zhTW: '擅長內容', enUS: 'Service focus' }),
    saveSoulButton: pickLocaleText(locale, { zhCN: '保存角色设定', zhTW: '儲存角色設定', enUS: 'Save role settings' }),
    runtimeTitle: pickLocaleText(locale, { zhCN: '使用方式', zhTW: '使用方式', enUS: 'Usage settings' }),
    conversationOption: pickLocaleText(locale, { zhCN: '允许和家人对话', zhTW: '允許和家人對話', enUS: 'Allow conversations with household members' }),
    defaultEntryOption: pickLocaleText(locale, { zhCN: '设为默认助手', zhTW: '設為預設助手', enUS: 'Set as the default agent' }),
    routingTagsLabel: pickLocaleText(locale, { zhCN: '适用标签', zhTW: '適用標籤', enUS: 'Routing tags' }),
    memoryActionLabel: pickLocaleText(locale, { zhCN: '涉及记忆内容时', zhTW: '涉及記憶內容時', enUS: 'When memory content is involved' }),
    configActionLabel: pickLocaleText(locale, { zhCN: '涉及设置调整时', zhTW: '涉及設定調整時', enUS: 'When settings changes are involved' }),
    operationActionLabel: pickLocaleText(locale, { zhCN: '涉及后续操作时', zhTW: '涉及後續操作時', enUS: 'When follow-up actions are involved' }),
    saveRuntimeButton: pickLocaleText(locale, { zhCN: '保存使用方式', zhTW: '儲存使用方式', enUS: 'Save usage settings' }),
    cognitionTitle: pickLocaleText(locale, { zhCN: '与家人的互动方式', zhTW: '與家人的互動方式', enUS: 'Household interaction settings' }),
    displayAddressLabel: pickLocaleText(locale, { zhCN: '怎么称呼 Ta', zhTW: '怎麼稱呼 Ta', enUS: 'How to address them' }),
    closenessLevelLabel: pickLocaleText(locale, { zhCN: '熟悉程度', zhTW: '熟悉程度', enUS: 'Closeness level' }),
    servicePriorityLabel: pickLocaleText(locale, { zhCN: '关注优先级', zhTW: '關注優先級', enUS: 'Service priority' }),
    communicationStyleLabel: pickLocaleText(locale, { zhCN: '沟通方式', zhTW: '溝通方式', enUS: 'Communication style' }),
    promptNotesLabel: pickLocaleText(locale, { zhCN: '补充备注', zhTW: '補充備註', enUS: 'Additional notes' }),
    saveCognitionButton: pickLocaleText(locale, { zhCN: '保存互动方式', zhTW: '儲存互動方式', enUS: 'Save interaction settings' }),
    emptyButlerTitle: pickLocaleText(locale, { zhCN: '还没有 AI 管家', zhTW: '還沒有 AI 管家', enUS: 'No AI butler yet' }),
    emptyAgentTitle: pickLocaleText(locale, { zhCN: '还没有 AI 助手', zhTW: '還沒有 AI 助手', enUS: 'No AI agents yet' }),
    emptyDescription: pickLocaleText(locale, { zhCN: '先添加一个 AI 助手，再继续完善它的资料。', zhTW: '先新增一個 AI 助手，再繼續完善它的資料。', enUS: 'Add an AI agent first, then continue refining its profile.' }),
    createModalDescription: pickLocaleText(locale, { zhCN: '先填写基础信息，创建后还可以继续完善。', zhTW: '先填寫基礎資訊，建立後還可以繼續完善。', enUS: 'Fill in the basics first. You can refine the details after creation.' }),
    agentTypeLabel: pickLocaleText(locale, { zhCN: '助手类型', zhTW: '助手類型', enUS: 'Agent type' }),
    personalityTraitsHint: pickLocaleText(locale, { zhCN: '多个特点请用逗号分隔。', zhTW: '多個特點請用逗號分隔。', enUS: 'Separate multiple traits with commas.' }),
    serviceFocusHint: pickLocaleText(locale, { zhCN: '多个内容请用逗号分隔。', zhTW: '多個內容請用逗號分隔。', enUS: 'Separate multiple items with commas.' }),
    cancel: pickLocaleText(locale, { zhCN: '取消', zhTW: '取消', enUS: 'Cancel' }),
    creating: pickLocaleText(locale, { zhCN: '添加中...', zhTW: '新增中...', enUS: 'Adding...' }),
  };
  const agentTypeOptions: Array<CreateFormState['agentType']> = ['butler', 'nutritionist', 'fitness_coach', 'study_coach', 'custom'];
  const statusOptions: Array<AgentDetail['status']> = ['active', 'inactive', 'draft'];

  function applyDetail(result: AgentDetail) {
    setDetail(result);
    setBaseForm({
      displayName: result.display_name,
      status: result.status,
      sortOrder: String(result.sort_order),
    });
    setSoulForm({
      selfIdentity: result.soul?.self_identity ?? '',
      roleSummary: result.soul?.role_summary ?? '',
      introMessage: result.soul?.intro_message ?? '',
      speakingStyle: result.soul?.speaking_style ?? '',
      personalityTraits: stringifyTags(result.soul?.personality_traits ?? []),
      serviceFocus: stringifyTags(result.soul?.service_focus ?? []),
    });
    setRuntimeForm({
      conversationEnabled: result.runtime_policy?.conversation_enabled ?? true,
      defaultEntry: result.runtime_policy?.default_entry ?? false,
      routingTags: stringifyTags(result.runtime_policy?.routing_tags ?? []),
      memoryActionLevel: result.runtime_policy?.autonomous_action_policy?.memory ?? 'ask',
      configActionLevel: result.runtime_policy?.autonomous_action_policy?.config ?? 'ask',
      operationActionLevel: result.runtime_policy?.autonomous_action_policy?.action ?? 'ask',
    });
    setCognitionForm(Object.fromEntries(result.member_cognitions.map(item => [
      item.member_id,
      {
        displayAddress: item.display_address ?? '',
        closenessLevel: String(item.closeness_level),
        servicePriority: String(item.service_priority),
        communicationStyle: item.communication_style ?? '',
        promptNotes: item.prompt_notes ?? '',
      },
    ])));
  }

  function resetCreateForm() {
    setCreateForm(buildCreateForm(locale));
  }

  function openCreateModal() {
    resetCreateForm();
    setError('');
    setStatus('');
    setCreateModalOpen(true);
  }

  function closeCreateModal() {
    if (saving) return;
    setCreateModalOpen(false);
    resetCreateForm();
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [agentRows, memberRows] = await Promise.all([
          settingsApi.listAgents(householdId),
          settingsApi.listMembers(householdId),
        ]);
        if (cancelled) return;
        const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setSelectedAgentId(current => (nextAgents.some(item => item.id === current) ? current : (nextAgents[0]?.id ?? '')));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [householdId, onlyButler]);

  useEffect(() => {
    if (!selectedAgentId) {
      setDetail(null);
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      setLoading(true);
      setError('');
      try {
        const result = await settingsApi.getAgentDetail(householdId, selectedAgentId);
        if (!cancelled) {
          applyDetail(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadDetailFailed);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [householdId, selectedAgentId]);

  async function reload(selectAgentId?: string) {
    const agentRows = await settingsApi.listAgents(householdId);
    const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
    const nextSelectedId = selectAgentId ?? (
      nextAgents.some(item => item.id === selectedAgentId) ? selectedAgentId : (nextAgents[0]?.id ?? '')
    );
    setAgents(nextAgents);
    setSelectedAgentId(nextSelectedId);
    if (nextSelectedId) {
      applyDetail(await settingsApi.getAgentDetail(householdId, nextSelectedId));
    } else {
      setDetail(null);
    }
    await onChanged?.();
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setStatus('');
    try {
      const created = await settingsApi.createAgent(householdId, {
        display_name: createForm.displayName.trim(),
        agent_type: (onlyButler ? 'butler' : createForm.agentType) as CreateFormState['agentType'],
        self_identity: createForm.selfIdentity.trim(),
        role_summary: createForm.roleSummary.trim(),
        intro_message: createForm.introMessage.trim() || null,
        speaking_style: createForm.speakingStyle.trim() || null,
        personality_traits: parseTags(createForm.personalityTraits),
        service_focus: parseTags(createForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-app',
      });
      await reload(created.id);
      setCreateModalOpen(false);
      resetCreateForm();
      setStatus(copy.createdStatus(created.display_name));
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveBase() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.updateAgent(householdId, detail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status as AgentDetail['status'],
        sort_order: Number(baseForm.sortOrder),
      });
      await reload(detail.id);
      setStatus(copy.saveBaseSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveBaseFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSoul() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentSoul(householdId, detail.id, {
        self_identity: soulForm.selfIdentity.trim(),
        role_summary: soulForm.roleSummary.trim(),
        intro_message: soulForm.introMessage.trim() || null,
        speaking_style: soulForm.speakingStyle.trim() || null,
        personality_traits: parseTags(soulForm.personalityTraits),
        service_focus: parseTags(soulForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-app',
      });
      await reload(detail.id);
      setStatus(copy.saveSoulSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveSoulFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRuntime() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentRuntimePolicy(householdId, detail.id, {
        conversation_enabled: runtimeForm.conversationEnabled,
        default_entry: runtimeForm.defaultEntry,
        routing_tags: parseTags(runtimeForm.routingTags),
        memory_scope: null,
        autonomous_action_policy: {
          memory: runtimeForm.memoryActionLevel,
          config: runtimeForm.configActionLevel,
          action: runtimeForm.operationActionLevel,
        },
      });
      await reload(detail.id);
      setStatus(copy.saveRuntimeSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveRuntimeFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveCognitions() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentMemberCognitions(householdId, detail.id, {
        items: members.map(member => {
          const item = cognitionForm[member.id] ?? {
            displayAddress: '',
            closenessLevel: '3',
            servicePriority: '3',
            communicationStyle: '',
            promptNotes: '',
          };
          return {
            member_id: member.id,
            display_address: item.displayAddress.trim() || null,
            closeness_level: Number(item.closenessLevel),
            service_priority: Number(item.servicePriority),
            communication_style: item.communicationStyle.trim() || null,
            prompt_notes: item.promptNotes.trim() || null,
            care_notes: null,
          };
        }),
      });
      await reload(detail.id);
      setStatus(copy.saveCognitionSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveCognitionFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      <Card className="ai-config-detail-card">
        <div className="agent-config-center__toolbar">
          <div className="agent-config-center__intro">
            <h3>{compact ? copy.panelTitleCompact : (onlyButler ? copy.panelTitleButler : copy.panelTitleAgent)}</h3>
            <p>
              {compact
                ? copy.panelDescriptionCompact
                : copy.panelDescriptionDefault}
            </p>
          </div>
          <button className="btn btn--primary" type="button" onClick={openCreateModal}>
            {createActionLabel}
          </button>
        </div>
        {status ? <div className="setup-form-status">{status}</div> : null}
      </Card>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">{copy.loading}</div> : null}

      {!loading && !compact ? (
        visibleAgents.length > 0 ? (
          <>
            <div className="ai-config-list">
              {visibleAgents.map(agent => (
                <button
                  key={agent.id}
                  type="button"
                  className={`card ai-config-card ${selectedAgentId === agent.id ? 'ai-config-card--selected' : ''}`}
                  onClick={() => setSelectedAgentId(agent.id)}
                >
                  <div className="ai-config-card__top">
                    <div className="ai-config-card__avatar">{getAgentTypeEmoji(agent.agent_type)}</div>
                    <div className="ai-config-card__text">
                      <div className="ai-config-card__title-row">
                        <h3>{agent.display_name}</h3>
                        <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                          {agent.conversation_enabled ? copy.conversationEnabled : copy.conversationPaused}
                        </span>
                      </div>
                      <p className="ai-config-card__meta">{getAgentTypeLabel(agent.agent_type, locale)} · {getAgentStatusLabel(agent.status, locale)}</p>
                      <p className="ai-config-card__summary">{agent.summary ?? copy.summaryEmpty}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {detail ? (
              <div className="ai-config-detail__grid">
                <Card className="ai-config-detail-card">
                  <h4>{copy.baseTitle}</h4>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.displayNameLabel}</label><input className="form-input" value={baseForm.displayName} onChange={(event) => setBaseForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.statusLabel}</label><select className="form-select" value={baseForm.status} onChange={(event) => setBaseForm(current => ({ ...current, status: event.target.value }))}>{statusOptions.map(option => <option key={option} value={option}>{getAgentStatusLabel(option, locale)}</option>)}</select></div>
                    <div className="form-group"><label>{copy.sortOrderLabel}</label><input className="form-input" type="number" value={baseForm.sortOrder} onChange={(event) => setBaseForm(current => ({ ...current, sortOrder: event.target.value }))} /></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveBase()} disabled={saving}>{copy.saveBaseButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.soulTitle}</h4>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.selfIdentityLabel}</label><textarea className="form-input setup-textarea" value={soulForm.selfIdentity} onChange={(event) => setSoulForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.roleSummaryLabel}</label><textarea className="form-input setup-textarea" value={soulForm.roleSummary} onChange={(event) => setSoulForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.introMessageLabel}</label><input className="form-input" value={soulForm.introMessage} onChange={(event) => setSoulForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.speakingStyleLabel}</label><input className="form-input" value={soulForm.speakingStyle} onChange={(event) => setSoulForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.personalityTraitsLabel}</label><input className="form-input" value={soulForm.personalityTraits} onChange={(event) => setSoulForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.serviceFocusLabel}</label><input className="form-input" value={soulForm.serviceFocus} onChange={(event) => setSoulForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveSoul()} disabled={saving}>{copy.saveSoulButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.runtimeTitle}</h4>
                  <div className="setup-choice-group">
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.conversationEnabled} onChange={(event) => setRuntimeForm(current => ({ ...current, conversationEnabled: event.target.checked }))} /><span>{copy.conversationOption}</span></label>
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.defaultEntry} onChange={(event) => setRuntimeForm(current => ({ ...current, defaultEntry: event.target.checked }))} /><span>{copy.defaultEntryOption}</span></label>
                  </div>
                  <div className="form-group"><label>{copy.routingTagsLabel}</label><input className="form-input" value={runtimeForm.routingTags} onChange={(event) => setRuntimeForm(current => ({ ...current, routingTags: event.target.value }))} /></div>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.memoryActionLabel}</label><select className="form-select" value={runtimeForm.memoryActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>{copy.configActionLabel}</label><select className="form-select" value={runtimeForm.configActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>{copy.operationActionLabel}</label><select className="form-select" value={runtimeForm.operationActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>{copy.saveRuntimeButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.cognitionTitle}</h4>
                  <div className="ai-cognition-list">
                    {members.map(member => {
                      const cognition = cognitionForm[member.id] ?? { displayAddress: '', closenessLevel: '3', servicePriority: '3', communicationStyle: '', promptNotes: '' };
                      return (
                        <div key={member.id} className="ai-cognition-item">
                          <div className="ai-cognition-item__top"><strong>{member.name}</strong><span className="ai-config-muted">{member.role}</span></div>
                          <div className="setup-form-grid">
                            <div className="form-group"><label>{copy.displayAddressLabel}</label><input className="form-input" value={cognition.displayAddress} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.closenessLevelLabel}</label><input className="form-input" type="number" min="1" max="5" value={cognition.closenessLevel} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, closenessLevel: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.servicePriorityLabel}</label><input className="form-input" type="number" min="1" max="5" value={cognition.servicePriority} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, servicePriority: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.communicationStyleLabel}</label><input className="form-input" value={cognition.communicationStyle} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.promptNotesLabel}</label><textarea className="form-input setup-textarea" value={cognition.promptNotes} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))} /></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>{copy.saveCognitionButton}</button></div>
                </Card>
              </div>
            ) : null}
          </>
        ) : (
          <Card className="ai-config-detail-card agent-config-empty">
            <h4>{onlyButler ? copy.emptyButlerTitle : copy.emptyAgentTitle}</h4>
            <p className="ai-config-muted">{copy.emptyDescription}</p>
          </Card>
        )
      ) : null}

      {createModalOpen ? (
        <div className="member-modal-overlay" onClick={saving ? undefined : closeCreateModal}>
          <div className="member-modal agent-create-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{createActionLabel}</h3>
                <p>{copy.createModalDescription}</p>
              </div>
            </div>
            <form className="settings-form agent-create-form" onSubmit={handleCreate}>
              <div className="setup-form-grid">
                {!onlyButler ? (
                  <div className="form-group">
                    <label htmlFor={`agent-type-${householdId}`}>{copy.agentTypeLabel}</label>
                    <select id={`agent-type-${householdId}`} className="form-select" value={createForm.agentType} onChange={(event) => setCreateForm(current => ({ ...current, agentType: event.target.value as CreateFormState['agentType'] }))}>
                      {agentTypeOptions.map(option => <option key={option} value={option}>{getAgentTypeLabel(option, locale)}</option>)}
                    </select>
                  </div>
                ) : null}
                <div className="form-group"><label>{copy.displayNameLabel}</label><input className="form-input" value={createForm.displayName} onChange={(event) => setCreateForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                <div className="form-group"><label>{copy.selfIdentityLabel}</label><textarea className="form-input setup-textarea" value={createForm.selfIdentity} onChange={(event) => setCreateForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                <div className="form-group"><label>{copy.roleSummaryLabel}</label><textarea className="form-input setup-textarea" value={createForm.roleSummary} onChange={(event) => setCreateForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                <div className="form-group"><label>{copy.introMessageLabel}</label><input className="form-input" value={createForm.introMessage} onChange={(event) => setCreateForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                <div className="form-group"><label>{copy.speakingStyleLabel}</label><input className="form-input" value={createForm.speakingStyle} onChange={(event) => setCreateForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                <div className="form-group"><label>{copy.personalityTraitsLabel}</label><input className="form-input" value={createForm.personalityTraits} onChange={(event) => setCreateForm(current => ({ ...current, personalityTraits: event.target.value }))} /><div className="form-help">{copy.personalityTraitsHint}</div></div>
                <div className="form-group"><label>{copy.serviceFocusLabel}</label><input className="form-input" value={createForm.serviceFocus} onChange={(event) => setCreateForm(current => ({ ...current, serviceFocus: event.target.value }))} /><div className="form-help">{copy.serviceFocusHint}</div></div>
              </div>
              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={saving}>{copy.cancel}</button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={createDisabled}>{saving ? copy.creating : createActionLabel}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
