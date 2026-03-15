import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, Textarea, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  AgentDetail,
  AgentSummary,
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderField,
  AiProviderProfile,
  Member,
  assignSetupProviderFormValue,
  buildCreateSetupProviderPayload,
  buildSetupProviderFormState,
  buildSetupRoutePayload,
  buildUpdateSetupProviderPayload,
  parseTagList,
  stringifyTagList,
  toSetupProviderFormState,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  FormField,
  OptionPills,
  PrimaryButton,
  SecondaryButton,
  SectionNote,
  TextInput,
} from '../../../components/AppUi';
import { MainShellPage } from '../../../components/MainShellPage';
import { APP_ROUTES, coreApiClient, useAppRuntime } from '../../../runtime';

const AI_CAPABILITY_OPTIONS = [
  { value: 'qa_generation', label: '家庭问答生成' },
  { value: 'qa_structured_answer', label: '结构化问答' },
  { value: 'reminder_copywriting', label: '提醒文案' },
  { value: 'scene_explanation', label: '场景解释' },
  { value: 'embedding', label: '向量检索' },
  { value: 'rerank', label: '结果重排' },
  { value: 'stt', label: '语音转文字' },
  { value: 'tts', label: '文字转语音' },
  { value: 'vision', label: '视觉理解' },
] as const;

const HIDDEN_PROVIDER_FIELDS = new Set(['provider_code', 'latency_budget_ms']);

const AGENT_TYPE_OPTIONS: Array<{ value: AgentSummary['agent_type']; label: string }> = [
  { value: 'butler', label: '主管家' },
  { value: 'nutritionist', label: '营养师' },
  { value: 'fitness_coach', label: '健身教练' },
  { value: 'study_coach', label: '学习教练' },
  { value: 'custom', label: '自定义角色' },
];

const AGENT_STATUS_OPTIONS: Array<{ value: AgentDetail['status']; label: string }> = [
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' },
  { value: 'draft', label: '草稿' },
];

const ACTION_POLICY_OPTIONS = [
  { value: 'ask', label: '先问我' },
  { value: 'notify', label: '先做后通知' },
  { value: 'auto', label: '自动执行' },
] as const;

const BOOLEAN_OPTIONS = [
  { value: 'true', label: '开启' },
  { value: 'false', label: '关闭' },
] as const;

type ProviderFormState = ReturnType<typeof buildSetupProviderFormState>;

type AgentCreateForm = {
  displayName: string;
  agentType: AgentSummary['agent_type'];
  selfIdentity: string;
  roleSummary: string;
  introMessage: string;
  speakingStyle: string;
  personalityTraits: string;
  serviceFocus: string;
};

function buildAgentCreateForm(): AgentCreateForm {
  return {
    displayName: '小爪管家',
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: '负责家庭问答、日常提醒和基础陪伴服务。',
    introMessage: '你好，我是你的家庭管家。',
    speakingStyle: '温和、直接、靠谱',
    personalityTraits: '细心, 稳定, 有边界感',
    serviceFocus: '家庭问答, 日常提醒, 成员关怀',
  };
}

function formatCapabilityLabel(capability: string) {
  return AI_CAPABILITY_OPTIONS.find(item => item.value === capability)?.label ?? capability;
}

function formatAgentType(agentType: AgentSummary['agent_type']) {
  return AGENT_TYPE_OPTIONS.find(item => item.value === agentType)?.label ?? agentType;
}

function formatAgentStatus(status: AgentSummary['status']) {
  return AGENT_STATUS_OPTIONS.find(item => item.value === status)?.label ?? status;
}

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

function pickPrimaryButler(agents: AgentSummary[]) {
  return (
    agents.find(item => item.agent_type === 'butler' && item.status === 'active' && item.is_primary)
    ?? agents.find(item => item.agent_type === 'butler' && item.status === 'active')
    ?? null
  );
}

function mapSetupRequirementLabel(step: string) {
  switch (step) {
    case 'family_profile':
      return '家庭资料';
    case 'first_member':
      return '首位成员';
    case 'provider_setup':
      return 'AI 供应商';
    case 'first_butler_agent':
      return '首位管家';
    default:
      return step;
  }
}

function readProviderFieldValue(form: ProviderFormState, field: AiProviderField) {
  if (field.key === 'display_name') return form.displayName;
  if (field.key === 'provider_code') return form.providerCode;
  if (field.key === 'base_url') return form.baseUrl;
  if (field.key === 'secret_ref') return form.secretRef;
  if (field.key === 'model_name') return form.modelName;
  if (field.key === 'privacy_level') return form.privacyLevel;
  if (field.key === 'latency_budget_ms') return form.latencyBudgetMs;
  return form.dynamicFields[field.key] ?? '';
}

export default function SettingsAiPage() {
  const { bootstrap, refresh } = useAppRuntime();
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState('');
  const [editingProviderId, setEditingProviderId] = useState('');
  const [providerForm, setProviderForm] = useState<ProviderFormState>(buildSetupProviderFormState());
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [agentDetail, setAgentDetail] = useState<AgentDetail | null>(null);
  const [agentCreateForm, setAgentCreateForm] = useState<AgentCreateForm>(buildAgentCreateForm());
  const [baseForm, setBaseForm] = useState({ displayName: '', status: 'active' as AgentDetail['status'], sortOrder: '100' });
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
  const [pageLoading, setPageLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyKey, setBusyKey] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const activeHouseholdIdRef = useRef('');
  const workspaceRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';
  const currentSetupStatus = bootstrap?.setupStatus ?? null;
  const selectedProvider = useMemo(() => providers.find(item => item.id === selectedProviderId) ?? null, [providers, selectedProviderId]);
  const currentAdapter = useMemo(() => adapters.find(item => item.adapter_code === providerForm.adapterCode) ?? null, [adapters, providerForm.adapterCode]);
  const activeProviders = useMemo(() => providers.filter(item => item.enabled), [providers]);
  const primaryButler = useMemo(() => pickPrimaryButler(agents), [agents]);
  const missingRequirements = (currentSetupStatus?.missing_requirements ?? []).map(mapSetupRequirementLabel);
  const routeCount = routes.filter(item => item.enabled && item.primary_provider_profile_id).length;

  const applyAgentDetail = useCallback((detail: AgentDetail) => {
    setAgentDetail(detail);
    setBaseForm({
      displayName: detail.display_name,
      status: detail.status,
      sortOrder: String(detail.sort_order),
    });
    setSoulForm({
      selfIdentity: detail.soul?.self_identity ?? '',
      roleSummary: detail.soul?.role_summary ?? '',
      introMessage: detail.soul?.intro_message ?? '',
      speakingStyle: detail.soul?.speaking_style ?? '',
      personalityTraits: stringifyTagList(detail.soul?.personality_traits ?? []),
      serviceFocus: stringifyTagList(detail.soul?.service_focus ?? []),
    });
    setRuntimeForm({
      conversationEnabled: detail.runtime_policy?.conversation_enabled ?? true,
      defaultEntry: detail.runtime_policy?.default_entry ?? false,
      routingTags: stringifyTagList(detail.runtime_policy?.routing_tags ?? []),
      memoryActionLevel: detail.runtime_policy?.autonomous_action_policy.memory ?? 'ask',
      configActionLevel: detail.runtime_policy?.autonomous_action_policy.config ?? 'ask',
      operationActionLevel: detail.runtime_policy?.autonomous_action_policy.action ?? 'ask',
    });
    setCognitionForm(Object.fromEntries(detail.member_cognitions.map(item => [
      item.member_id,
      {
        displayAddress: item.display_address ?? '',
        closenessLevel: String(item.closeness_level),
        servicePriority: String(item.service_priority),
        communicationStyle: item.communication_style ?? '',
        promptNotes: item.prompt_notes ?? '',
      },
    ])));
  }, []);

  const loadWorkspace = useCallback(async (preferredProviderId?: string | null, preferredAgentId?: string | null) => {
    const householdId = currentHouseholdId;
    const requestId = ++workspaceRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      activeHouseholdIdRef.current = householdId;
      setAdapters([]);
      setProviders([]);
      setRoutes([]);
      setAgents([]);
      setMembers([]);
      setSelectedProviderId('');
      setEditingProviderId('');
      setProviderForm(buildSetupProviderFormState());
      setSelectedAgentId('');
      setAgentDetail(null);
      setStatus('');
      setError('');
    }

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    try {
      const [adapterRows, providerRows, routeRows, agentRows, memberRows] = await Promise.all([
        coreApiClient.listAiProviderAdapters(),
        coreApiClient.listHouseholdAiProviders(householdId),
        coreApiClient.listHouseholdAiRoutes(householdId),
        coreApiClient.listAgents(householdId),
        coreApiClient.listMembers(householdId),
      ]);

      if (requestId !== workspaceRequestIdRef.current) {
        return;
      }

      setAdapters(adapterRows);
      setProviders(providerRows);
      setRoutes(routeRows);
      setAgents(agentRows.items);
      setMembers(memberRows.items);

      setSelectedProviderId(current => {
        if (preferredProviderId && providerRows.some(item => item.id === preferredProviderId)) {
          return preferredProviderId;
        }
        if (current && providerRows.some(item => item.id === current)) {
          return current;
        }
        return providerRows[0]?.id ?? '';
      });

      setSelectedAgentId(current => {
        if (preferredAgentId && agentRows.items.some(item => item.id === preferredAgentId)) {
          return preferredAgentId;
        }
        if (current && agentRows.items.some(item => item.id === current)) {
          return current;
        }
        return agentRows.items[0]?.id ?? '';
      });

      setProviderForm(current => {
        if (editingProviderId) {
          const editingProvider = providerRows.find(item => item.id === editingProviderId);
          if (editingProvider) {
            const adapter = adapterRows.find(item => item.adapter_code === String(editingProvider.extra_config?.adapter_code ?? '')) ?? adapterRows[0] ?? null;
            return toSetupProviderFormState(editingProvider, adapter);
          }
        }

        if (current.adapterCode) {
          return current;
        }

        return buildSetupProviderFormState(adapterRows[0] ?? null);
      });

      if (editingProviderId && !providerRows.some(item => item.id === editingProviderId)) {
        setEditingProviderId('');
        setProviderForm(buildSetupProviderFormState(adapterRows[0] ?? null));
      }
    } catch (loadError) {
      if (requestId === workspaceRequestIdRef.current) {
        setError(loadError instanceof Error ? loadError.message : 'AI 设置页加载失败');
      }
    } finally {
      if (requestId === workspaceRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [currentHouseholdId, editingProviderId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useDidShow(() => {
    if (currentHouseholdId) {
      void loadWorkspace(selectedProviderId || undefined, selectedAgentId || undefined);
    }
  });

  useEffect(() => {
    if (!currentHouseholdId || !selectedAgentId) {
      setAgentDetail(null);
      return;
    }

    const requestId = ++detailRequestIdRef.current;
    setDetailLoading(true);

    void coreApiClient.getAgentDetail(currentHouseholdId, selectedAgentId)
      .then(result => {
        if (requestId !== detailRequestIdRef.current) {
          return;
        }
        applyAgentDetail(result);
      })
      .catch(detailError => {
        if (requestId === detailRequestIdRef.current) {
          setError(detailError instanceof Error ? detailError.message : 'Agent 详情加载失败');
          setAgentDetail(null);
        }
      })
      .finally(() => {
        if (requestId === detailRequestIdRef.current) {
          setDetailLoading(false);
        }
      });
  }, [applyAgentDetail, currentHouseholdId, selectedAgentId]);

  async function reloadWorkspace(successMessage?: string, preferredProviderId?: string | null, preferredAgentId?: string | null) {
    await Promise.all([
      loadWorkspace(preferredProviderId, preferredAgentId),
      refresh(),
    ]);
    if (successMessage) {
      setStatus(successMessage);
    }
  }

  function resetProviderForm(adapter?: AiProviderAdapter | null) {
    setEditingProviderId('');
    setProviderForm(buildSetupProviderFormState(adapter));
  }

  function startEditProvider(provider: AiProviderProfile) {
    const adapter = adapters.find(item => item.adapter_code === String(provider.extra_config?.adapter_code ?? '')) ?? adapters[0] ?? null;
    setEditingProviderId(provider.id);
    setSelectedProviderId(provider.id);
    setProviderForm(toSetupProviderFormState(provider, adapter));
    setStatus('');
    setError('');
  }

  async function handleSaveProvider() {
    if (!currentHouseholdId || !currentAdapter) {
      setError('当前没有可用的家庭或供应商适配器');
      return;
    }

    setBusyKey('provider-save');
    setStatus('');
    setError('');

    try {
      if (editingProviderId) {
        const updated = await coreApiClient.updateHouseholdAiProvider(
          currentHouseholdId,
          editingProviderId,
          buildUpdateSetupProviderPayload(providerForm, currentAdapter),
        );
        await reloadWorkspace('AI 供应商配置已保存。', updated.id, selectedAgentId || undefined);
      } else {
        const created = await coreApiClient.createHouseholdAiProvider(
          currentHouseholdId,
          buildCreateSetupProviderPayload(providerForm, currentAdapter),
        );
        setEditingProviderId(created.id);
        await reloadWorkspace('AI 供应商已创建。', created.id, selectedAgentId || undefined);
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 AI 供应商失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleDeleteProvider() {
    if (!currentHouseholdId || !selectedProvider) {
      return;
    }

    const result = await Taro.showModal({
      title: '删除 AI 供应商',
      content: `确定删除“${selectedProvider.display_name}”吗？已经绑定到能力路由的设置会一起失效。`,
    });

    if (!result.confirm) {
      return;
    }

    setBusyKey('provider-delete');
    setStatus('');
    setError('');

    try {
      await coreApiClient.deleteHouseholdAiProvider(currentHouseholdId, selectedProvider.id);
      setEditingProviderId('');
      setProviderForm(buildSetupProviderFormState(adapters[0] ?? null));
      await reloadWorkspace('AI 供应商已删除。', null, selectedAgentId || undefined);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '删除 AI 供应商失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleBindRoute(capability: string, providerId: string) {
    if (!currentHouseholdId) {
      return;
    }

    setBusyKey(`route-${capability}`);
    setStatus('');
    setError('');

    try {
      const currentRoute = routes.find(item => item.capability === capability);
      await coreApiClient.upsertHouseholdAiRoute(
        currentHouseholdId,
        capability,
        buildSetupRoutePayload(currentHouseholdId, capability, currentRoute, providerId || null, Boolean(providerId)),
      );
      await reloadWorkspace(`${formatCapabilityLabel(capability)} 路由已更新。`, selectedProviderId || undefined, selectedAgentId || undefined);
    } catch (routeError) {
      setError(routeError instanceof Error ? routeError.message : '保存能力路由失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleToggleRoute(capability: string) {
    if (!currentHouseholdId) {
      return;
    }

    const route = routes.find(item => item.capability === capability);
    if (!route?.primary_provider_profile_id) {
      return;
    }

    setBusyKey(`route-toggle-${capability}`);
    setStatus('');
    setError('');

    try {
      await coreApiClient.upsertHouseholdAiRoute(
        currentHouseholdId,
        capability,
        buildSetupRoutePayload(currentHouseholdId, capability, route, route.primary_provider_profile_id, !route.enabled),
      );
      await reloadWorkspace(
        route.enabled ? `${formatCapabilityLabel(capability)} 路由已停用。` : `${formatCapabilityLabel(capability)} 路由已启用。`,
        selectedProviderId || undefined,
        selectedAgentId || undefined,
      );
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '切换能力路由失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleCreateAgent() {
    if (!currentHouseholdId) {
      setError('当前没有可用的家庭上下文');
      return;
    }

    const personalityTraits = parseTagList(agentCreateForm.personalityTraits);
    const serviceFocus = parseTagList(agentCreateForm.serviceFocus);
    if (!agentCreateForm.displayName.trim() || !agentCreateForm.selfIdentity.trim() || !agentCreateForm.roleSummary.trim()) {
      setError('显示名称、自我身份和角色摘要都必须填写');
      return;
    }
    if (personalityTraits.length === 0 || serviceFocus.length === 0) {
      setError('人格特征和服务重点至少各填一个');
      return;
    }

    setBusyKey('agent-create');
    setStatus('');
    setError('');

    try {
      const created = await coreApiClient.createAgent(currentHouseholdId, {
        display_name: agentCreateForm.displayName.trim(),
        agent_type: agentCreateForm.agentType,
        self_identity: agentCreateForm.selfIdentity.trim(),
        role_summary: agentCreateForm.roleSummary.trim(),
        intro_message: agentCreateForm.introMessage.trim() || null,
        speaking_style: agentCreateForm.speakingStyle.trim() || null,
        personality_traits: personalityTraits,
        service_focus: serviceFocus,
        created_by: 'user-app-settings-ai',
      });
      setAgentCreateForm(buildAgentCreateForm());
      await reloadWorkspace('Agent 已创建。', selectedProviderId || undefined, created.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建 Agent 失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSaveAgentBase() {
    if (!currentHouseholdId || !agentDetail) {
      return;
    }

    setBusyKey('agent-base');
    setStatus('');
    setError('');

    try {
      await coreApiClient.updateAgent(currentHouseholdId, agentDetail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status,
        sort_order: Number(baseForm.sortOrder),
      });
      await reloadWorkspace('Agent 基础资料已保存。', selectedProviderId || undefined, agentDetail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 Agent 基础资料失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSaveAgentSoul() {
    if (!currentHouseholdId || !agentDetail) {
      return;
    }

    setBusyKey('agent-soul');
    setStatus('');
    setError('');

    try {
      await coreApiClient.upsertAgentSoul(currentHouseholdId, agentDetail.id, {
        self_identity: soulForm.selfIdentity.trim(),
        role_summary: soulForm.roleSummary.trim(),
        intro_message: soulForm.introMessage.trim() || null,
        speaking_style: soulForm.speakingStyle.trim() || null,
        personality_traits: parseTagList(soulForm.personalityTraits),
        service_focus: parseTagList(soulForm.serviceFocus),
        created_by: 'user-app-settings-ai',
      });
      await reloadWorkspace('Agent 人格资料已保存。', selectedProviderId || undefined, agentDetail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 Agent 人格资料失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSaveAgentRuntime() {
    if (!currentHouseholdId || !agentDetail) {
      return;
    }

    setBusyKey('agent-runtime');
    setStatus('');
    setError('');

    try {
      await coreApiClient.upsertAgentRuntimePolicy(currentHouseholdId, agentDetail.id, {
        conversation_enabled: runtimeForm.conversationEnabled,
        default_entry: runtimeForm.defaultEntry,
        routing_tags: parseTagList(runtimeForm.routingTags),
        memory_scope: null,
        autonomous_action_policy: {
          memory: runtimeForm.memoryActionLevel,
          config: runtimeForm.configActionLevel,
          action: runtimeForm.operationActionLevel,
        },
      });
      await reloadWorkspace('Agent 运行时策略已保存。', selectedProviderId || undefined, agentDetail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 Agent 运行时策略失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSaveAgentCognitions() {
    if (!currentHouseholdId || !agentDetail) {
      return;
    }

    setBusyKey('agent-cognitions');
    setStatus('');
    setError('');

    try {
      await coreApiClient.upsertAgentMemberCognitions(currentHouseholdId, agentDetail.id, {
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
            care_notes: null,
            prompt_notes: item.promptNotes.trim() || null,
          };
        }),
      });
      await reloadWorkspace('成员认知已保存。', selectedProviderId || undefined, agentDetail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员认知失败');
    } finally {
      setBusyKey('');
    }
  }

  return (
    <MainShellPage
      currentNav="settings"
      title="AI 设置已经进入正式长期入口"
      description="这里是 user-app 的正式 AI 设置中心，不再拿 setup 充当长期设置页。供应商、能力路由、首位管家补建和 Agent 配置都在这里收口。"
    >
      <PageSection title="AI 设置总览" description="骨架已建立，下面开始接正式配置和操作。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="供应商数量" value={`${providers.length}`} tone={providers.length > 0 ? 'success' : 'warning'} />
        <StatusCard label="启用路由" value={`${routeCount}`} tone={routeCount > 0 ? 'success' : 'warning'} />
        <StatusCard label="Agent 数量" value={`${agents.length}`} tone={agents.length > 0 ? 'info' : 'warning'} />
        <StatusCard label="首位管家" value={primaryButler ? primaryButler.display_name : '还没补建'} tone={primaryButler ? 'success' : 'warning'} />
        {pageLoading ? <SectionNote>正在读取当前家庭的 AI 设置...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
        {missingRequirements.length > 0 ? (
          <SectionNote tone="warning">当前还有初始化缺口：{missingRequirements.join('、')}。</SectionNote>
        ) : null}
      </PageSection>

      <PageSection title="初始化缺口" description="长期设置入口已经独立出来，但 setup 剩下的坑不会自己消失。">
        {missingRequirements.length === 0 ? (
          <SectionNote tone="success">当前家庭没有未完成的 AI 初始化缺口，长期设置链路可以独立维护。</SectionNote>
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <SectionNote tone="warning">
              当前还缺：{missingRequirements.join('、')}。这不是摆设，后面真会反咬对话和路由。
            </SectionNote>
            <ActionRow>
              <SecondaryButton onClick={() => void reloadWorkspace('已刷新 AI 初始化状态。', selectedProviderId || undefined, selectedAgentId || undefined)}>
                刷新初始化状态
              </SecondaryButton>
              <SecondaryButton onClick={() => void Taro.navigateTo({ url: APP_ROUTES.setup })}>
                继续初始化向导
              </SecondaryButton>
            </ActionRow>
          </View>
        )}
      </PageSection>

      <PageSection title="AI 供应商管理" description="先把 provider 和 capability route 做成正式入口。真正在跑的主链看这里，不看花哨说明文案。">
        <ActionRow>
          <PrimaryButton onClick={() => resetProviderForm(adapters[0] ?? null)}>
            新增供应商
          </PrimaryButton>
          <SecondaryButton disabled={!selectedProvider} onClick={() => selectedProvider && startEditProvider(selectedProvider)}>
            编辑当前供应商
          </SecondaryButton>
          <Button
            disabled={!selectedProvider || Boolean(busyKey)}
            onClick={() => void handleDeleteProvider()}
            style={{
              background: '#fff5f2',
              border: `1px solid ${userAppTokens.colorWarning}`,
              borderRadius: userAppTokens.radiusMd,
              color: userAppTokens.colorWarning,
              fontSize: '24px',
            }}
          >
            {busyKey === 'provider-delete' ? '删除中...' : '删除当前供应商'}
          </Button>
        </ActionRow>

        {providers.length === 0 ? (
          <EmptyStateCard title="当前还没有 AI 供应商" description="先配一个正式供应商，不要再让 setup 兜底长期设置。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
            {providers.map(provider => {
              const active = provider.id === selectedProviderId;
              const modelName = typeof provider.extra_config?.model_name === 'string' ? provider.extra_config.model_name : provider.api_version ?? '未配置模型';
              return (
                <View
                  key={provider.id}
                  onClick={() => setSelectedProviderId(provider.id)}
                  style={{
                    background: active ? '#eef5ff' : '#ffffff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '28px', fontWeight: '600' }}>
                    {provider.display_name}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                    {provider.provider_code} · {modelName}
                  </Text>
                  <Text style={{ color: provider.enabled ? userAppTokens.colorSuccess : userAppTokens.colorWarning, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    {provider.enabled ? '已启用' : '已停用'}
                  </Text>
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    能力：{provider.supported_capabilities.length > 0 ? provider.supported_capabilities.map(formatCapabilityLabel).join('、') : '未声明'}
                  </Text>
                </View>
              );
            })}
          </View>
        )}

        <View
          style={{
            background: '#f9fbff',
            border: `1px solid ${userAppTokens.colorBorder}`,
            borderRadius: userAppTokens.radiusLg,
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            marginTop: '16px',
            padding: userAppTokens.spacingMd,
          }}
        >
          <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
            {editingProviderId ? '编辑供应商配置' : '新增供应商配置'}
          </Text>
          <FormField label="供应商类型">
            <OptionPills
              value={providerForm.adapterCode}
              disabled={Boolean(editingProviderId)}
              options={adapters.map(adapter => ({ value: adapter.adapter_code, label: adapter.display_name }))}
              onChange={value => {
                const adapter = adapters.find(item => item.adapter_code === value) ?? null;
                setProviderForm(buildSetupProviderFormState(adapter));
                setEditingProviderId('');
              }}
            />
          </FormField>
          {currentAdapter ? (
            <>
              <SectionNote>{currentAdapter.description}</SectionNote>
              {currentAdapter.field_schema.filter(field => !HIDDEN_PROVIDER_FIELDS.has(field.key)).map(field => {
                const value = readProviderFieldValue(providerForm, field);
                return (
                  <FormField key={field.key} label={field.required ? `${field.label} *` : field.label} hint={field.help_text ?? undefined}>
                    {field.field_type === 'select' ? (
                      <OptionPills
                        value={value}
                        options={field.options.map(option => ({ value: option.value, label: option.label }))}
                        onChange={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    ) : field.field_type === 'boolean' ? (
                      <OptionPills
                        value={value || String(field.default_value ?? false)}
                        options={BOOLEAN_OPTIONS.map(option => ({ value: option.value, label: option.label }))}
                        onChange={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    ) : (
                      <TextInput
                        value={value}
                        password={field.field_type === 'secret'}
                        placeholder={field.placeholder ?? undefined}
                        onInput={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    )}
                  </FormField>
                );
              })}
              <FormField label="支持能力">
                <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '10px' }}>
                  {AI_CAPABILITY_OPTIONS.map(option => {
                    const active = providerForm.supportedCapabilities.includes(option.value);
                    return (
                      <Button
                        key={option.value}
                        size="mini"
                        onClick={() => {
                          setProviderForm(current => ({
                            ...current,
                            supportedCapabilities: active
                              ? current.supportedCapabilities.filter(item => item !== option.value)
                              : [...current.supportedCapabilities, option.value],
                          }));
                        }}
                        style={{
                          background: active ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
                          border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                          borderRadius: userAppTokens.radiusMd,
                          color: active ? '#ffffff' : userAppTokens.colorText,
                          fontSize: '22px',
                        }}
                      >
                        {option.label}
                      </Button>
                    );
                  })}
                </View>
              </FormField>
              <FormField label="是否启用">
                <OptionPills
                  value={providerForm.enabled ? 'true' : 'false'}
                  options={BOOLEAN_OPTIONS.map(option => ({ value: option.value, label: option.label }))}
                  onChange={value => setProviderForm(current => ({ ...current, enabled: value === 'true' }))}
                />
              </FormField>
              <ActionRow>
                <PrimaryButton
                  disabled={busyKey === 'provider-save' || !providerForm.displayName.trim() || !providerForm.modelName.trim() || !currentAdapter}
                  onClick={() => void handleSaveProvider()}
                >
                  {busyKey === 'provider-save' ? '保存中...' : editingProviderId ? '保存供应商' : '创建供应商'}
                </PrimaryButton>
                <SecondaryButton onClick={() => resetProviderForm(adapters[0] ?? null)}>
                  重置表单
                </SecondaryButton>
              </ActionRow>
            </>
          ) : (
            <EmptyStateCard title="还没选供应商类型" description="先选一个 adapter，后面的字段才有意义。" />
          )}
        </View>
      </PageSection>

      <PageSection title="能力路由绑定" description="供应商只是资源池，真正决定对话主链的是这里。">
        {AI_CAPABILITY_OPTIONS.map(option => {
          const route = routes.find(item => item.capability === option.value);
          const candidates = activeProviders.filter(provider => provider.supported_capabilities.includes(option.value));
          return (
            <View
              key={option.value}
              style={{
                background: '#ffffff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                marginBottom: '12px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '26px', fontWeight: '600' }}>
                {option.label}
              </Text>
              <Text style={{ color: route?.enabled ? userAppTokens.colorSuccess : userAppTokens.colorWarning, fontSize: '22px' }}>
                当前状态：{route?.enabled ? '已启用' : '未启用'}
              </Text>
              {candidates.length === 0 ? (
                <SectionNote tone="warning">当前没有已启用且声明了这项能力的供应商。</SectionNote>
              ) : (
                <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '10px' }}>
                  {candidates.map(provider => {
                    const active = route?.primary_provider_profile_id === provider.id;
                    return (
                      <Button
                        key={provider.id}
                        size="mini"
                        disabled={Boolean(busyKey)}
                        onClick={() => void handleBindRoute(option.value, provider.id)}
                        style={{
                          background: active ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
                          border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                          borderRadius: userAppTokens.radiusMd,
                          color: active ? '#ffffff' : userAppTokens.colorText,
                          fontSize: '22px',
                        }}
                      >
                        {provider.display_name}
                      </Button>
                    );
                  })}
                  {route?.primary_provider_profile_id ? (
                    <Button
                      size="mini"
                      disabled={Boolean(busyKey)}
                      onClick={() => void handleBindRoute(option.value, '')}
                      style={{
                        background: '#fff5f2',
                        border: `1px solid ${userAppTokens.colorWarning}`,
                        borderRadius: userAppTokens.radiusMd,
                        color: userAppTokens.colorWarning,
                        fontSize: '22px',
                      }}
                    >
                      解除绑定
                    </Button>
                  ) : null}
                </View>
              )}
              <ActionRow>
                <SecondaryButton disabled={!route?.primary_provider_profile_id || Boolean(busyKey)} onClick={() => void handleToggleRoute(option.value)}>
                  {busyKey === `route-toggle-${option.value}` ? '处理中...' : route?.enabled ? '停用路由' : '启用路由'}
                </SecondaryButton>
              </ActionRow>
            </View>
          );
        })}
      </PageSection>

      <PageSection title="首位管家补建与 Agent 新建" description="正式设置入口里也能补建首位管家，不再只会把人赶回 setup。">
        {!primaryButler ? (
          <SectionNote tone="warning">当前还没有激活中的主管家。你可以直接在下面创建，也可以继续 setup 引导。</SectionNote>
        ) : (
          <SectionNote tone="success">当前主管家是 {primaryButler.display_name}，最近更新时间 {formatRelativeTime(primaryButler.updated_at)}。</SectionNote>
        )}
        <FormField label="Agent 类型">
          <OptionPills
            value={agentCreateForm.agentType}
            options={AGENT_TYPE_OPTIONS.map(option => ({ value: option.value, label: option.label }))}
            onChange={value => setAgentCreateForm(current => ({ ...current, agentType: value }))}
          />
        </FormField>
        <FormField label="显示名称">
          <TextInput value={agentCreateForm.displayName} onInput={value => setAgentCreateForm(current => ({ ...current, displayName: value }))} />
        </FormField>
        <FormField label="自我身份">
          <Textarea
            value={agentCreateForm.selfIdentity}
            autoHeight
            maxlength={800}
            onInput={event => setAgentCreateForm(current => ({ ...current, selfIdentity: event.detail.value }))}
            style={{
              background: '#ffffff',
              border: `1px solid ${userAppTokens.colorBorder}`,
              borderRadius: userAppTokens.radiusLg,
              color: userAppTokens.colorText,
              fontSize: '24px',
              minHeight: '140px',
              padding: '16px',
              width: '100%',
            }}
          />
        </FormField>
        <FormField label="角色摘要">
          <Textarea
            value={agentCreateForm.roleSummary}
            autoHeight
            maxlength={800}
            onInput={event => setAgentCreateForm(current => ({ ...current, roleSummary: event.detail.value }))}
            style={{
              background: '#ffffff',
              border: `1px solid ${userAppTokens.colorBorder}`,
              borderRadius: userAppTokens.radiusLg,
              color: userAppTokens.colorText,
              fontSize: '24px',
              minHeight: '140px',
              padding: '16px',
              width: '100%',
            }}
          />
        </FormField>
        <FormField label="开场白">
          <TextInput value={agentCreateForm.introMessage} onInput={value => setAgentCreateForm(current => ({ ...current, introMessage: value }))} />
        </FormField>
        <FormField label="说话风格">
          <TextInput value={agentCreateForm.speakingStyle} onInput={value => setAgentCreateForm(current => ({ ...current, speakingStyle: value }))} />
        </FormField>
        <FormField label="人格特征" hint="用逗号分开。没有这个，Agent 就还是空壳。">
          <TextInput value={agentCreateForm.personalityTraits} onInput={value => setAgentCreateForm(current => ({ ...current, personalityTraits: value }))} />
        </FormField>
        <FormField label="服务重点" hint="也用逗号分开，先说清楚它究竟负责什么。">
          <TextInput value={agentCreateForm.serviceFocus} onInput={value => setAgentCreateForm(current => ({ ...current, serviceFocus: value }))} />
        </FormField>
        <ActionRow>
          <PrimaryButton disabled={busyKey === 'agent-create'} onClick={() => void handleCreateAgent()}>
            {busyKey === 'agent-create' ? '创建中...' : primaryButler ? '创建 Agent' : '补建首位管家'}
          </PrimaryButton>
          <SecondaryButton onClick={() => setAgentCreateForm(buildAgentCreateForm())}>
            重置 Agent 表单
          </SecondaryButton>
        </ActionRow>
      </PageSection>

      <PageSection title="Agent 列表" description="这里是正式的 Agent 配置中心，不再躲在旧 web 页面里。">
        {agents.length === 0 ? (
          <EmptyStateCard title="当前还没有 Agent" description="先在上面创建一个，不然下面的配置中心就是空壳。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {agents.map(agent => {
              const active = agent.id === selectedAgentId;
              return (
                <View
                  key={agent.id}
                  onClick={() => setSelectedAgentId(agent.id)}
                  style={{
                    background: active ? '#eef5ff' : '#ffffff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '28px', fontWeight: '600' }}>
                    {agent.display_name}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                    {formatAgentType(agent.agent_type)} · {formatAgentStatus(agent.status)} · 排序 {agent.sort_order}
                  </Text>
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    {agent.summary ?? '还没有角色摘要'}
                  </Text>
                  <Text style={{ color: agent.conversation_enabled ? userAppTokens.colorSuccess : userAppTokens.colorWarning, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    {agent.conversation_enabled ? '允许进入对话' : '当前已静默'}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="Agent 基础资料" description="先把最容易破坏用户体验的基础字段收住。">
        {!agentDetail ? (
          <EmptyStateCard title="还没选中 Agent" description="先从上面选一个 Agent，这里才有可编辑的正式配置。" />
        ) : detailLoading ? (
          <EmptyStateCard title="正在加载 Agent 详情" description="共享 AI API 正在返回当前 Agent 的详细配置。" />
        ) : (
          <>
            <FormField label="显示名称">
              <TextInput value={baseForm.displayName} onInput={value => setBaseForm(current => ({ ...current, displayName: value }))} />
            </FormField>
            <FormField label="状态">
              <OptionPills
                value={baseForm.status}
                options={AGENT_STATUS_OPTIONS.map(option => ({ value: option.value, label: option.label }))}
                onChange={value => setBaseForm(current => ({ ...current, status: value }))}
              />
            </FormField>
            <FormField label="排序">
              <TextInput value={baseForm.sortOrder} onInput={value => setBaseForm(current => ({ ...current, sortOrder: value }))} />
            </FormField>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'agent-base'} onClick={() => void handleSaveAgentBase()}>
                {busyKey === 'agent-base' ? '保存中...' : '保存基础资料'}
              </PrimaryButton>
            </ActionRow>
          </>
        )}
      </PageSection>

      <PageSection title="Agent 人格资料" description="人格设定不是 decoration，它会直接影响用户听到的东西。">
        {!agentDetail ? (
          <EmptyStateCard title="当前没有人格资料可编辑" description="先选中一个 Agent，再改它的人格与边界。" />
        ) : (
          <>
            <FormField label="自我身份">
              <Textarea
                value={soulForm.selfIdentity}
                autoHeight
                maxlength={800}
                onInput={event => setSoulForm(current => ({ ...current, selfIdentity: event.detail.value }))}
                style={{
                  background: '#ffffff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  color: userAppTokens.colorText,
                  fontSize: '24px',
                  minHeight: '140px',
                  padding: '16px',
                  width: '100%',
                }}
              />
            </FormField>
            <FormField label="角色摘要">
              <Textarea
                value={soulForm.roleSummary}
                autoHeight
                maxlength={800}
                onInput={event => setSoulForm(current => ({ ...current, roleSummary: event.detail.value }))}
                style={{
                  background: '#ffffff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  color: userAppTokens.colorText,
                  fontSize: '24px',
                  minHeight: '140px',
                  padding: '16px',
                  width: '100%',
                }}
              />
            </FormField>
            <FormField label="开场白">
              <TextInput value={soulForm.introMessage} onInput={value => setSoulForm(current => ({ ...current, introMessage: value }))} />
            </FormField>
            <FormField label="说话风格">
              <TextInput value={soulForm.speakingStyle} onInput={value => setSoulForm(current => ({ ...current, speakingStyle: value }))} />
            </FormField>
            <FormField label="人格特征">
              <TextInput value={soulForm.personalityTraits} onInput={value => setSoulForm(current => ({ ...current, personalityTraits: value }))} />
            </FormField>
            <FormField label="服务重点">
              <TextInput value={soulForm.serviceFocus} onInput={value => setSoulForm(current => ({ ...current, serviceFocus: value }))} />
            </FormField>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'agent-soul'} onClick={() => void handleSaveAgentSoul()}>
                {busyKey === 'agent-soul' ? '保存中...' : '保存人格资料'}
              </PrimaryButton>
            </ActionRow>
          </>
        )}
      </PageSection>

      <PageSection title="Agent 运行时策略" description="能不能对话、默认进哪个 Agent、动作策略怎么走，都在这层。">
        {!agentDetail ? (
          <EmptyStateCard title="当前没有运行时策略可编辑" description="先选中一个 Agent，再改它的运行时行为。" />
        ) : (
          <>
            <FormField label="允许进入对话">
              <OptionPills value={runtimeForm.conversationEnabled ? 'true' : 'false'} options={BOOLEAN_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setRuntimeForm(current => ({ ...current, conversationEnabled: value === 'true' }))} />
            </FormField>
            <FormField label="设为默认入口">
              <OptionPills value={runtimeForm.defaultEntry ? 'true' : 'false'} options={BOOLEAN_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setRuntimeForm(current => ({ ...current, defaultEntry: value === 'true' }))} />
            </FormField>
            <FormField label="路由标签">
              <TextInput value={runtimeForm.routingTags} onInput={value => setRuntimeForm(current => ({ ...current, routingTags: value }))} />
            </FormField>
            <FormField label="记忆动作策略">
              <OptionPills value={runtimeForm.memoryActionLevel} options={ACTION_POLICY_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setRuntimeForm(current => ({ ...current, memoryActionLevel: value }))} />
            </FormField>
            <FormField label="配置动作策略">
              <OptionPills value={runtimeForm.configActionLevel} options={ACTION_POLICY_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setRuntimeForm(current => ({ ...current, configActionLevel: value }))} />
            </FormField>
            <FormField label="提醒与操作策略">
              <OptionPills value={runtimeForm.operationActionLevel} options={ACTION_POLICY_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setRuntimeForm(current => ({ ...current, operationActionLevel: value }))} />
            </FormField>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'agent-runtime'} onClick={() => void handleSaveAgentRuntime()}>
                {busyKey === 'agent-runtime' ? '保存中...' : '保存运行时策略'}
              </PrimaryButton>
            </ActionRow>
          </>
        )}
      </PageSection>

      <PageSection title="成员认知" description="Agent 怎么称呼成员、优先照顾谁，这些不能靠猜。">
        {!agentDetail ? (
          <EmptyStateCard title="当前没有成员认知可编辑" description="先选中一个 Agent，再补它对家庭成员的理解。" />
        ) : members.length === 0 ? (
          <EmptyStateCard title="当前家庭还没有成员" description="没有成员就谈不上成员认知，先回家庭页补上下文。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {members.map(member => {
              const cognition = cognitionForm[member.id] ?? {
                displayAddress: '',
                closenessLevel: '3',
                servicePriority: '3',
                communicationStyle: '',
                promptNotes: '',
              };
              return (
                <View
                  key={member.id}
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                    {member.name}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '4px' }}>
                    角色：{member.role}
                  </Text>
                  <View style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
                    <FormField label="称呼">
                      <TextInput value={cognition.displayAddress} onInput={value => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: value } }))} />
                    </FormField>
                    <FormField label="亲密度">
                      <TextInput value={cognition.closenessLevel} onInput={value => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, closenessLevel: value } }))} />
                    </FormField>
                    <FormField label="服务优先级">
                      <TextInput value={cognition.servicePriority} onInput={value => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, servicePriority: value } }))} />
                    </FormField>
                    <FormField label="沟通风格">
                      <TextInput value={cognition.communicationStyle} onInput={value => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: value } }))} />
                    </FormField>
                    <FormField label="提示备注">
                      <Textarea
                        value={cognition.promptNotes}
                        autoHeight
                        maxlength={500}
                        onInput={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.detail.value } }))}
                        style={{
                          background: '#ffffff',
                          border: `1px solid ${userAppTokens.colorBorder}`,
                          borderRadius: userAppTokens.radiusLg,
                          color: userAppTokens.colorText,
                          fontSize: '24px',
                          minHeight: '120px',
                          padding: '16px',
                          width: '100%',
                        }}
                      />
                    </FormField>
                  </View>
                </View>
              );
            })}
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'agent-cognitions'} onClick={() => void handleSaveAgentCognitions()}>
                {busyKey === 'agent-cognitions' ? '保存中...' : '保存成员认知'}
              </PrimaryButton>
            </ActionRow>
          </View>
        )}
      </PageSection>
    </MainShellPage>
  );
}
