import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, Text, Textarea, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  AgentDetail,
  AgentSummary,
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderField,
  AiProviderProfile,
  ButlerBootstrapSession,
  HouseholdSetupStepCode,
  Member,
  assignSetupProviderFormValue,
  buildCreateSetupProviderPayload,
  buildSetupProviderFormState,
  buildSetupRoutePayload,
  buildUpdateSetupProviderPayload,
  listBuiltinLocaleDefinitions,
  parseTagList,
  pickSetupProviderProfile,
  readSetupProviderFormValue,
  resolveSetupRoutableCapabilities,
  SETUP_ROUTE_CAPABILITIES,
  stringifyTagList,
  toSetupProviderFormState,
} from '@familyclaw/user-core';
import {
  createBrowserRealtimeClient,
  newRealtimeRequestId,
  type BootstrapRealtimeEvent,
  type BootstrapRealtimeSessionSnapshot,
  type BrowserRealtimeClient,
} from '@familyclaw/user-platform';
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
} from '../../components/AppUi';
import { AuthShellPage } from '../../components/AuthShellPage';
import { APP_ROUTES, coreApiClient, isSetupComplete, resolveBootstrapRoute, useAppRuntime } from '../../runtime';

const STEP_ORDER: HouseholdSetupStepCode[] = [
  'family_profile',
  'first_member',
  'provider_setup',
  'first_butler_agent',
];

const STEP_LABELS: Record<HouseholdSetupStepCode, string> = {
  family_profile: '创建家庭',
  first_member: '创建首位成员',
  provider_setup: '配置 AI',
  first_butler_agent: '创建首位管家',
  finish: '完成',
};

const HIDDEN_PROVIDER_FIELDS = new Set(['provider_code', 'latency_budget_ms']);

const localeOptions = listBuiltinLocaleDefinitions().map(item => ({
  value: item.id,
  label: item.nativeLabel,
}));

const memberRoleOptions: Array<{ value: Member['role']; label: string }> = [
  { value: 'admin', label: '管理员' },
  { value: 'adult', label: '成人' },
  { value: 'elder', label: '长辈' },
];

const booleanFieldOptions = [
  { value: 'true', label: '是' },
  { value: 'false', label: '否' },
] as const;

type TranscriptMessage = {
  id: string;
  requestId?: string | null;
  role: 'assistant' | 'user';
  content: string;
};

function getAgeGroupFromRole(role: Member['role']): Member['age_group'] {
  if (role === 'elder') {
    return 'elder';
  }

  return 'adult';
}

function getCurrentStepIndex(step: HouseholdSetupStepCode | undefined) {
  const resolved = step ?? 'family_profile';
  const matchedIndex = STEP_ORDER.indexOf(resolved);
  return matchedIndex >= 0 ? matchedIndex : STEP_ORDER.length;
}

function pickPrimaryButler(items: AgentSummary[]) {
  return (
    items.find(item => item.agent_type === 'butler' && item.status === 'active' && item.is_primary)
    ?? items.find(item => item.agent_type === 'butler' && item.status === 'active')
    ?? null
  );
}

function toTranscriptMessages(session: ButlerBootstrapSession): TranscriptMessage[] {
  const source = session.messages.length > 0
    ? session.messages
    : [{ role: 'assistant' as const, content: session.assistant_message }];
  return source.map(message => ({
    id: message.id ?? `${message.request_id ?? 'message'}:${message.seq ?? Date.now()}`,
    requestId: message.request_id ?? null,
    role: message.role,
    content: message.content,
  }));
}

function normalizeMessageContent(content: string) {
  return content.replace(/\r\n/g, '\n').replace(/\n{2,}/g, '\n').trim();
}

function getButlerEmoji(name: string) {
  const normalized = name.toLowerCase();
  if (normalized.includes('暖') || normalized.includes('温')) return '☀️';
  if (normalized.includes('月') || normalized.includes('夜')) return '🌙';
  if (normalized.includes('星') || normalized.includes('闪')) return '⭐';
  if (normalized.includes('云') || normalized.includes('雾')) return '☁️';
  if (normalized.includes('风') || normalized.includes('飞')) return '🍃';
  if (normalized.includes('猫') || normalized.includes('喵')) return '😺';
  if (normalized.includes('狗') || normalized.includes('汪')) return '🐕';
  if (normalized.includes('熊')) return '🐻';
  return '🤖';
}

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}

function buildFieldLabel(field: AiProviderField) {
  return field.required ? `${field.label} *` : field.label;
}

export default function SetupPage() {
  const { bootstrap, loading, refresh } = useAppRuntime();

  const [householdForm, setHouseholdForm] = useState({
    name: '',
    timezone: 'Asia/Shanghai',
    locale: 'zh-CN',
  });
  const [memberForm, setMemberForm] = useState({
    name: '',
    nickname: '',
    role: 'admin' as Member['role'],
    username: '',
    password: '',
    confirmPassword: '',
  });

  const [generalStatus, setGeneralStatus] = useState('');
  const [generalError, setGeneralError] = useState('');
  const [householdSubmitting, setHouseholdSubmitting] = useState(false);
  const [memberSubmitting, setMemberSubmitting] = useState(false);

  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [providerForm, setProviderForm] = useState(buildSetupProviderFormState());
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerSaving, setProviderSaving] = useState(false);
  const [providerStatus, setProviderStatus] = useState('');
  const [providerError, setProviderError] = useState('');
  const [editingProviderId, setEditingProviderId] = useState('');
  const [configuredProvider, setConfiguredProvider] = useState<AiProviderProfile | null>(null);
  const [configuredRoutes, setConfiguredRoutes] = useState<AiCapabilityRoute[]>([]);

  const [existingButler, setExistingButler] = useState<AgentSummary | null>(null);
  const [createdButler, setCreatedButler] = useState<AgentDetail | null>(null);
  const [butlerSession, setButlerSession] = useState<ButlerBootstrapSession | null>(null);
  const [butlerMessages, setButlerMessages] = useState<TranscriptMessage[]>([]);
  const [butlerInput, setButlerInput] = useState('');
  const [butlerLoading, setButlerLoading] = useState(false);
  const [butlerSending, setButlerSending] = useState(false);
  const [butlerConfirming, setButlerConfirming] = useState(false);
  const [butlerRestarting, setButlerRestarting] = useState(false);
  const [butlerRealtimeReady, setButlerRealtimeReady] = useState(false);
  const [butlerStatus, setButlerStatus] = useState('');
  const [butlerError, setButlerError] = useState('');
  const [butlerRealtimeVersion, setButlerRealtimeVersion] = useState(0);

  const setupLoadRequestIdRef = useRef(0);
  const butlerLoadRequestIdRef = useRef(0);
  const realtimeClientRef = useRef<BrowserRealtimeClient | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const suppressRealtimeCloseFeedbackRef = useRef(false);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentStep = bootstrap?.setupStatus?.current_step ?? 'family_profile';
  const currentStepIndex = getCurrentStepIndex(currentStep);
  const currentAdapter = useMemo(
    () => adapters.find(item => item.adapter_code === providerForm.adapterCode) ?? null,
    [adapters, providerForm.adapterCode],
  );
  const setupRouteBindings = useMemo(
    () => configuredRoutes.filter(route => SETUP_ROUTE_CAPABILITIES.includes(route.capability as (typeof SETUP_ROUTE_CAPABILITIES)[number])),
    [configuredRoutes],
  );
  const routableCapabilities = useMemo(
    () => resolveSetupRoutableCapabilities(providerForm.supportedCapabilities),
    [providerForm.supportedCapabilities],
  );
  const canCreateFirstHousehold = useMemo(() => {
    const actor = bootstrap?.actor;
    return actor?.account_type === 'system'
      || (actor?.account_type === 'bootstrap' && actor.must_change_password);
  }, [bootstrap?.actor]);

  useEffect(() => {
    if (loading || !bootstrap) {
      return;
    }

    if (!bootstrap.actor?.authenticated) {
      void Taro.reLaunch({ url: APP_ROUTES.login });
      return;
    }

    if (isSetupComplete(bootstrap.setupStatus) && bootstrap.currentHousehold) {
      void Taro.reLaunch({ url: resolveBootstrapRoute(bootstrap) });
    }
  }, [bootstrap, loading]);

  useEffect(() => {
    setHouseholdForm({
      name: bootstrap?.currentHousehold?.name ?? '',
      timezone: bootstrap?.currentHousehold?.timezone ?? 'Asia/Shanghai',
      locale: bootstrap?.currentHousehold?.locale ?? 'zh-CN',
    });
  }, [
    bootstrap?.currentHousehold?.id,
    bootstrap?.currentHousehold?.locale,
    bootstrap?.currentHousehold?.name,
    bootstrap?.currentHousehold?.timezone,
  ]);

  const loadSetupWorkspace = useCallback(async (householdId: string) => {
    const requestId = ++setupLoadRequestIdRef.current;
    if (!householdId) {
      setAdapters([]);
      setProviderForm(buildSetupProviderFormState());
      setConfiguredProvider(null);
      setConfiguredRoutes([]);
      setEditingProviderId('');
      setExistingButler(null);
      setCreatedButler(null);
      return;
    }

    setProviderLoading(true);
    setProviderError('');

    try {
      const [adapterRows, providerRows, routeRows, agentRows] = await Promise.all([
        coreApiClient.listAiProviderAdapters(),
        coreApiClient.listHouseholdAiProviders(householdId),
        coreApiClient.listHouseholdAiRoutes(householdId),
        coreApiClient.listAgents(householdId),
      ]);

      if (requestId !== setupLoadRequestIdRef.current) {
        return;
      }

      const setupProvider = pickSetupProviderProfile(providerRows, routeRows);
      const setupAdapter = setupProvider
        ? adapterRows.find(item => item.adapter_code === String(setupProvider.extra_config?.adapter_code ?? '')) ?? adapterRows[0] ?? null
        : adapterRows[0] ?? null;

      setAdapters(adapterRows);
      setConfiguredProvider(setupProvider);
      setConfiguredRoutes(routeRows);
      setEditingProviderId(setupProvider?.id ?? '');
      setProviderForm(
        setupProvider
          ? toSetupProviderFormState(setupProvider, setupAdapter)
          : buildSetupProviderFormState(setupAdapter),
      );
      setExistingButler(pickPrimaryButler(agentRows.items));
    } catch (error) {
      if (requestId === setupLoadRequestIdRef.current) {
        setProviderError(toErrorMessage(error, '读取 AI 配置状态失败'));
      }
    } finally {
      if (requestId === setupLoadRequestIdRef.current) {
        setProviderLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadSetupWorkspace(currentHouseholdId);
  }, [currentHouseholdId, loadSetupWorkspace]);

  const syncLatestButlerSession = useCallback(async (householdId: string, expectedSessionId?: string | null) => {
    if (!householdId) {
      return;
    }

    try {
      const nextSession = await coreApiClient.getLatestButlerBootstrapSession(householdId);
      if (!nextSession) {
        return;
      }
      if (expectedSessionId && nextSession.session_id !== expectedSessionId && butlerSession?.session_id === expectedSessionId) {
        return;
      }
      setButlerSession(nextSession);
      setButlerMessages(toTranscriptMessages(nextSession));
      setButlerSending(Boolean(nextSession.current_request_id));
      setButlerStatus(nextSession.current_request_id ? '已恢复当前引导会话。' : '已同步最新引导状态。');
    } catch {
      // 不覆盖更明确的业务错误。
    }
  }, [butlerSession?.session_id]);

  const loadOrStartButlerSession = useCallback(async (householdId: string) => {
    const requestId = ++butlerLoadRequestIdRef.current;
    if (!householdId) {
      setButlerSession(null);
      setButlerMessages([]);
      return;
    }

    setButlerLoading(true);
    setButlerError('');
    setButlerStatus('');

    try {
      const existingSession = await coreApiClient.getLatestButlerBootstrapSession(householdId);
      const nextSession = existingSession ?? await coreApiClient.createButlerBootstrapSession(householdId);
      if (requestId !== butlerLoadRequestIdRef.current) {
        return;
      }
      setButlerSession(nextSession);
      setButlerMessages(toTranscriptMessages(nextSession));
      setButlerSending(Boolean(nextSession.current_request_id));
    } catch (error) {
      if (requestId === butlerLoadRequestIdRef.current) {
        setButlerError(toErrorMessage(error, '启动首位管家引导失败'));
        setButlerSession(null);
        setButlerMessages([]);
      }
    } finally {
      if (requestId === butlerLoadRequestIdRef.current) {
        setButlerLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!currentHouseholdId || currentStep !== 'first_butler_agent' || existingButler) {
      setButlerSession(null);
      setButlerMessages([]);
      setButlerInput('');
      setButlerRealtimeReady(false);
      setButlerSending(false);
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      return;
    }

    void loadOrStartButlerSession(currentHouseholdId);
  }, [currentHouseholdId, currentStep, existingButler, loadOrStartButlerSession]);

  useEffect(() => {
    if (!currentHouseholdId || !butlerSession?.session_id || existingButler) {
      suppressRealtimeCloseFeedbackRef.current = true;
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setButlerRealtimeReady(false);
      return;
    }

    suppressRealtimeCloseFeedbackRef.current = true;
    realtimeClientRef.current?.close();
    setButlerRealtimeReady(false);

    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    try {
      realtimeClientRef.current = createBrowserRealtimeClient({
        householdId: currentHouseholdId,
        sessionId: butlerSession.session_id,
        channel: 'agent-bootstrap',
        onOpen: () => {
          reconnectAttemptsRef.current = 0;
          suppressRealtimeCloseFeedbackRef.current = false;
          setButlerRealtimeReady(true);
          setButlerStatus('管家引导实时连接已建立。');
        },
        onClose: () => {
          setButlerRealtimeReady(false);
          if (suppressRealtimeCloseFeedbackRef.current) {
            suppressRealtimeCloseFeedbackRef.current = false;
            return;
          }

          const delayMs = Math.min(1000 * (reconnectAttemptsRef.current + 1), 5000);
          reconnectAttemptsRef.current += 1;
          setButlerStatus(`实时连接已断开，${Math.ceil(delayMs / 1000)} 秒后尝试恢复。`);
          reconnectTimerRef.current = setTimeout(() => {
            reconnectTimerRef.current = null;
            void syncLatestButlerSession(currentHouseholdId, butlerSession.session_id);
            setButlerRealtimeVersion(current => current + 1);
          }, delayMs);
        },
        onError: () => {
          setButlerRealtimeReady(false);
          setButlerError('管家引导实时连接异常，请稍后重试。');
        },
        onEvent: (event: BootstrapRealtimeEvent) => {
          if (event.type === 'session.ready') {
            return;
          }

          if (event.type === 'session.snapshot') {
            const snapshot = (event.payload as { snapshot: BootstrapRealtimeSessionSnapshot }).snapshot;
            setButlerSession(snapshot);
            setButlerMessages(toTranscriptMessages(snapshot));
            setButlerSending(Boolean(snapshot.current_request_id));
            return;
          }

          if (event.type === 'user.message.accepted') {
            setButlerSending(true);
            setButlerSession(current => current ? { ...current, current_request_id: event.request_id ?? null } : current);
            return;
          }

          if (event.type === 'agent.chunk') {
            const payload = event.payload as { text: string };
            setButlerMessages(current => {
              const targetId = `assistant:${event.request_id}`;
              const existingMessage = current.find(message => message.id === targetId);
              if (existingMessage) {
                return current.map(message => (
                  message.id === targetId
                    ? { ...message, content: message.content + payload.text }
                    : message
                ));
              }
              return [...current, {
                id: targetId,
                requestId: event.request_id,
                role: 'assistant',
                content: payload.text,
              }];
            });
            return;
          }

          if (event.type === 'agent.state_patch') {
            setButlerSession(current => {
              if (!current) {
                return current;
              }
              return {
                ...current,
                draft: {
                  ...current.draft,
                  ...event.payload,
                },
              };
            });
            return;
          }

          if (event.type === 'agent.done') {
            setButlerSending(false);
            void syncLatestButlerSession(currentHouseholdId, butlerSession.session_id);
            return;
          }

          if (event.type === 'agent.error') {
            const payload = event.payload as { detail?: string };
            setButlerSending(false);
            setButlerError(typeof payload.detail === 'string' ? payload.detail : '管家引导响应失败');
            void syncLatestButlerSession(currentHouseholdId, butlerSession.session_id);
          }
        },
      });
    } catch (error) {
      setButlerError(toErrorMessage(error, '当前平台还没建立好管家引导实时连接'));
      setButlerRealtimeReady(false);
    }

    return () => {
      suppressRealtimeCloseFeedbackRef.current = true;
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setButlerRealtimeReady(false);
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [butlerRealtimeVersion, butlerSession?.session_id, currentHouseholdId, existingButler, syncLatestButlerSession]);

  useDidShow(() => {
    if (loading || !bootstrap?.actor?.authenticated) {
      return;
    }

    void refresh();
  });

  async function refreshAfterStep(successMessage: string) {
    setGeneralStatus(successMessage);
    const nextBootstrap = await refresh();
    if (currentHouseholdId) {
      await loadSetupWorkspace(currentHouseholdId);
    }

    if (isSetupComplete(nextBootstrap?.setupStatus ?? null) && nextBootstrap?.currentHousehold) {
      await Taro.reLaunch({ url: APP_ROUTES.home });
    }
  }

  async function handleHouseholdSubmit() {
    if (!householdForm.name.trim()) {
      setGeneralError('请先填写家庭名称。');
      return;
    }

    setHouseholdSubmitting(true);
    setGeneralError('');
    setGeneralStatus('');

    try {
      if (bootstrap?.currentHousehold?.id) {
        await coreApiClient.updateHousehold(bootstrap.currentHousehold.id, {
          name: householdForm.name.trim(),
          timezone: householdForm.timezone.trim(),
          locale: householdForm.locale,
        });
      } else {
        if (!canCreateFirstHousehold) {
          throw new Error('当前账号没有创建家庭的权限。');
        }
        await coreApiClient.createHousehold({
          name: householdForm.name.trim(),
          timezone: householdForm.timezone.trim(),
          locale: householdForm.locale,
        });
      }

      await refreshAfterStep('家庭资料已保存。');
    } catch (error) {
      setGeneralError(toErrorMessage(error, '保存家庭资料失败'));
    } finally {
      setHouseholdSubmitting(false);
    }
  }

  async function handleMemberSubmit() {
    if (!currentHouseholdId) {
      setGeneralError('请先完成家庭创建。');
      return;
    }

    if (!memberForm.name.trim() || !memberForm.username.trim()) {
      setGeneralError('请先填写成员姓名和登录账号。');
      return;
    }

    if (!memberForm.password || memberForm.password !== memberForm.confirmPassword) {
      setGeneralError('请确认两次输入的密码一致。');
      return;
    }

    setMemberSubmitting(true);
    setGeneralError('');
    setGeneralStatus('');

    try {
      const member = await coreApiClient.createMember({
        household_id: currentHouseholdId,
        name: memberForm.name.trim(),
        nickname: memberForm.nickname.trim() || null,
        role: memberForm.role,
        age_group: getAgeGroupFromRole(memberForm.role),
      });

      await coreApiClient.completeBootstrapAccount({
        household_id: currentHouseholdId,
        member_id: member.id,
        username: memberForm.username.trim(),
        password: memberForm.password,
      });

      await refreshAfterStep('首位成员和正式账号已创建。');
    } catch (error) {
      setGeneralError(toErrorMessage(error, '创建首位成员失败'));
    } finally {
      setMemberSubmitting(false);
    }
  }

  async function handleProviderSubmit() {
    if (!currentHouseholdId) {
      setProviderError('当前没有可用的家庭上下文。');
      return;
    }

    if (!currentAdapter) {
      setProviderError('请先选择 AI 供应商。');
      return;
    }

    const targetCapabilities = resolveSetupRoutableCapabilities(providerForm.supportedCapabilities);
    if (targetCapabilities.length === 0) {
      setProviderError('当前供应商没有覆盖家庭问答主链所需能力。');
      return;
    }

    setProviderSaving(true);
    setProviderError('');
    setProviderStatus(editingProviderId ? '正在保存 AI 供应商...' : '正在创建 AI 供应商...');

    try {
      const providerId = editingProviderId || (
        await coreApiClient.createHouseholdAiProvider(
          currentHouseholdId,
          buildCreateSetupProviderPayload(providerForm, currentAdapter),
        )
      ).id;

      if (editingProviderId) {
        await coreApiClient.updateHouseholdAiProvider(
          currentHouseholdId,
          editingProviderId,
          buildUpdateSetupProviderPayload(providerForm, currentAdapter),
        );
      } else {
        setEditingProviderId(providerId);
      }

      setProviderStatus('正在绑定最小可用路由...');
      const routes = await coreApiClient.listHouseholdAiRoutes(currentHouseholdId);
      await Promise.all(
        targetCapabilities.map(capability => coreApiClient.upsertHouseholdAiRoute(
          currentHouseholdId,
          capability,
          buildSetupRoutePayload(
            currentHouseholdId,
            capability,
            routes.find(route => route.capability === capability),
            providerId,
            true,
          ),
        )),
      );

      await refreshAfterStep('AI 供应商和最小问答路由已保存。');
      setProviderStatus(`已将 ${currentAdapter.display_name} 绑定到 setup 主链。`);
    } catch (error) {
      setProviderError(toErrorMessage(error, '保存 AI 配置失败'));
    } finally {
      setProviderSaving(false);
    }
  }

  function updateButlerDraft(nextDraft: ButlerBootstrapSession['draft']) {
    setButlerSession(current => current ? { ...current, draft: nextDraft } : current);
  }

  async function handleButlerRestart() {
    if (!currentHouseholdId) {
      setButlerError('当前没有可用的家庭上下文。');
      return;
    }

    setButlerRestarting(true);
    setButlerError('');
    setButlerStatus('');

    try {
      const nextSession = await coreApiClient.restartButlerBootstrapSession(currentHouseholdId);
      setButlerSession(nextSession);
      setButlerMessages(toTranscriptMessages(nextSession));
      setButlerInput('');
      setButlerStatus('已重新开始管家引导。');
      setButlerRealtimeVersion(current => current + 1);
    } catch (error) {
      setButlerError(toErrorMessage(error, '重新开始管家引导失败'));
    } finally {
      setButlerRestarting(false);
    }
  }

  async function handleButlerSend() {
    if (!butlerSession || !butlerInput.trim()) {
      return;
    }

    if (!realtimeClientRef.current || !butlerRealtimeReady) {
      setButlerError('实时连接还没建立好，稍后再发。');
      return;
    }

    const requestId = newRealtimeRequestId();
    const userMessage = butlerInput.trim();

    setButlerSending(true);
    setButlerError('');
    setButlerStatus('');
    setButlerInput('');
    setButlerMessages(current => [
      ...current,
      { id: `user:${requestId}`, requestId, role: 'user', content: userMessage },
      { id: `assistant:${requestId}`, requestId, role: 'assistant', content: '' },
    ]);

    try {
      realtimeClientRef.current.sendUserMessage(requestId, userMessage);
    } catch (error) {
      setButlerSending(false);
      setButlerMessages(current => current.filter(message => message.requestId !== requestId));
      setButlerError(toErrorMessage(error, '发送引导消息失败'));
    }
  }

  async function handleButlerConfirm() {
    if (!currentHouseholdId || !butlerSession) {
      return;
    }

    setButlerConfirming(true);
    setButlerError('');
    setButlerStatus('');

    try {
      const created = await coreApiClient.confirmButlerBootstrapSession(
        currentHouseholdId,
        butlerSession.session_id,
        {
          draft: butlerSession.draft,
          created_by: 'user-app-setup',
        },
      );
      setCreatedButler(created);
      setExistingButler(created);
      setButlerStatus(`首位管家 ${created.display_name} 已创建。`);
      await refreshAfterStep('首位管家已完成初始化。');
    } catch (error) {
      setButlerError(toErrorMessage(error, '确认创建首位管家失败'));
    } finally {
      setButlerConfirming(false);
    }
  }

  if (!currentHouseholdId && !canCreateFirstHousehold && !loading) {
    return (
      <AuthShellPage title="初始化向导" description="当前账号没有家庭上下文，而且也不能创建首个家庭，这不是前端该硬糊过去的状态。">
        <EmptyStateCard title="未找到可用家庭上下文" description="请先确认当前账号是不是正确的 bootstrap / system 账号。" />
      </AuthShellPage>
    );
  }

  return (
    <AuthShellPage title="Setup 主链继续收口" description="这一页现在不再只停在前两步，AI 配置和首位管家初始化已经接进新应用主线。">
      <PageSection title="当前进度" description="先把 setup 状态摆平，再谈别的。家庭切换后，这里的状态会跟着当前家庭一起刷新。">
        <StatusCard label="当前步骤" value={STEP_LABELS[currentStep] ?? currentStep} tone={isSetupComplete(bootstrap?.setupStatus ?? null) ? 'success' : 'warning'} />
        <StatusCard label="当前家庭" value={bootstrap?.currentHousehold?.name ?? '尚未创建'} tone="info" />
        <StatusCard label="AI 供应商" value={configuredProvider?.display_name ?? '尚未配置'} tone={configuredProvider ? 'success' : 'warning'} />
        <StatusCard label="首位管家" value={existingButler?.display_name ?? createdButler?.display_name ?? '尚未创建'} tone={existingButler || createdButler ? 'success' : 'warning'} />
        <ScrollView scrollX>
          <View style={{ display: 'flex', flexDirection: 'row', gap: '12px', marginTop: '12px' }}>
            {STEP_ORDER.map((step, index) => {
              const done = index < currentStepIndex || bootstrap?.setupStatus?.completed_steps.includes(step);
              const active = step === currentStep;
              return (
                <View
                  key={step}
                  style={{
                    background: active ? userAppTokens.colorPrimary : done ? '#eef8f3' : '#f9fbff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : done ? userAppTokens.colorSuccess : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusMd,
                    minWidth: '176px',
                    padding: '12px 16px',
                  }}
                >
                  <Text style={{ color: active ? '#ffffff' : userAppTokens.colorText, display: 'block', fontSize: '22px', fontWeight: '600' }}>
                    {index + 1}. {STEP_LABELS[step]}
                  </Text>
                  <Text style={{ color: active ? 'rgba(255,255,255,0.86)' : userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                    {done ? '已完成' : active ? '当前步骤' : '待处理'}
                  </Text>
                </View>
              );
            })}
          </View>
        </ScrollView>
        {generalStatus ? <SectionNote tone="success">{generalStatus}</SectionNote> : null}
        {generalError ? <SectionNote tone="warning">{generalError}</SectionNote> : null}
      </PageSection>

      {(!bootstrap?.currentHousehold || currentStep === 'family_profile') ? (
        <PageSection title="第一步：创建家庭" description="先把家庭壳立住。这里先收口名称、时区和语言，不把旧页面那套地区大表单整坨搬过来。">
          <FormField label="家庭名称">
            <TextInput
              value={householdForm.name}
              placeholder="例如：观澜园 / 张家大院"
              onInput={value => setHouseholdForm(current => ({ ...current, name: value }))}
            />
          </FormField>
          <FormField label="时区">
            <TextInput
              value={householdForm.timezone}
              placeholder="Asia/Shanghai"
              onInput={value => setHouseholdForm(current => ({ ...current, timezone: value }))}
            />
          </FormField>
          <FormField label="默认语言">
            <OptionPills
              value={householdForm.locale}
              options={localeOptions}
              onChange={value => setHouseholdForm(current => ({ ...current, locale: value }))}
            />
          </FormField>
          <ActionRow>
            <PrimaryButton disabled={householdSubmitting} onClick={() => void handleHouseholdSubmit()}>
              {householdSubmitting ? '保存中...' : '保存家庭并继续'}
            </PrimaryButton>
          </ActionRow>
        </PageSection>
      ) : null}

      {currentHouseholdId && currentStep === 'first_member' ? (
        <PageSection title="第二步：创建首位成员" description="先把正式成员和登录账号建出来，后面所有 AI 配置和管家初始化都得挂在这个家庭上下文上。">
          <FormField label="成员姓名">
            <TextInput
              value={memberForm.name}
              placeholder="请输入姓名"
              onInput={value => setMemberForm(current => ({ ...current, name: value }))}
            />
          </FormField>
          <FormField label="昵称">
            <TextInput
              value={memberForm.nickname}
              placeholder="可选"
              onInput={value => setMemberForm(current => ({ ...current, nickname: value }))}
            />
          </FormField>
          <FormField label="角色">
            <OptionPills
              value={memberForm.role}
              options={memberRoleOptions}
              onChange={value => setMemberForm(current => ({ ...current, role: value }))}
            />
          </FormField>
          <FormField label="登录账号">
            <TextInput
              value={memberForm.username}
              placeholder="请输入登录账号"
              onInput={value => setMemberForm(current => ({ ...current, username: value }))}
            />
          </FormField>
          <FormField label="登录密码">
            <TextInput
              value={memberForm.password}
              password
              placeholder="请输入密码"
              onInput={value => setMemberForm(current => ({ ...current, password: value }))}
            />
          </FormField>
          <FormField label="确认密码">
            <TextInput
              value={memberForm.confirmPassword}
              password
              placeholder="再次输入密码"
              onInput={value => setMemberForm(current => ({ ...current, confirmPassword: value }))}
            />
          </FormField>
          <ActionRow>
            <PrimaryButton disabled={memberSubmitting} onClick={() => void handleMemberSubmit()}>
              {memberSubmitting ? '创建中...' : '创建账号并进入 AI 配置'}
            </PrimaryButton>
          </ActionRow>
        </PageSection>
      ) : null}

      {currentHouseholdId ? (
        <PageSection title="第三步：配置 AI 供应商" description="这里不做大而全的控制台，只收一条最小可用主链：选 provider、填模型凭据、把问答主路由绑上。">
          <StatusCard
            label="当前绑定"
            value={configuredProvider ? `${configuredProvider.display_name} / ${setupRouteBindings.length} 条 setup 路由` : '尚未绑定'}
            tone={configuredProvider ? 'success' : 'warning'}
          />
          {providerLoading ? <SectionNote>正在读取当前家庭的 AI 配置...</SectionNote> : null}
          {configuredProvider ? (
            <SectionNote>
              当前已接入 {configuredProvider.display_name}，最小主链能力：{setupRouteBindings.length > 0 ? setupRouteBindings.map(item => item.capability).join('、') : '还没绑好'}。
            </SectionNote>
          ) : (
            <SectionNote>
              这一步只要求把家庭问答主链跑起来，不顺手扩成完整 AI 管理后台。
            </SectionNote>
          )}
          <FormField label="供应商平台">
            <OptionPills
              value={providerForm.adapterCode}
              disabled={providerSaving || Boolean(editingProviderId)}
              options={adapters.map(adapter => ({
                value: adapter.adapter_code,
                label: adapter.display_name,
              }))}
              onChange={value => {
                const nextAdapter = adapters.find(item => item.adapter_code === value) ?? null;
                setProviderForm(buildSetupProviderFormState(nextAdapter));
                setProviderStatus('');
                setProviderError('');
              }}
            />
          </FormField>
          {currentAdapter ? (
            <>
              <SectionNote>{currentAdapter.description}</SectionNote>
              {currentAdapter.field_schema.filter(field => !HIDDEN_PROVIDER_FIELDS.has(field.key)).map(field => {
                const value = readSetupProviderFormValue(providerForm, field.key);
                return (
                  <FormField key={field.key} label={buildFieldLabel(field)} hint={field.help_text ?? undefined}>
                    {field.field_type === 'select' ? (
                      <OptionPills
                        value={value}
                        disabled={providerSaving}
                        options={field.options.map(option => ({
                          value: option.value,
                          label: option.label,
                        }))}
                        onChange={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    ) : field.field_type === 'boolean' ? (
                      <OptionPills
                        value={value || String(field.default_value ?? false)}
                        disabled={providerSaving}
                        options={booleanFieldOptions.map(option => ({
                          value: option.value,
                          label: option.label,
                        }))}
                        onChange={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    ) : (
                      <TextInput
                        value={value}
                        password={field.field_type === 'secret'}
                        disabled={providerSaving}
                        placeholder={field.placeholder ?? undefined}
                        onInput={nextValue => setProviderForm(current => assignSetupProviderFormValue(current, field.key, nextValue))}
                      />
                    )}
                  </FormField>
                );
              })}
              <SectionNote>
                当前会绑定的最小能力：{routableCapabilities.length > 0 ? routableCapabilities.join('、') : '无'}。只保住 setup 主链，不乱配语音、视觉这些旁枝。
              </SectionNote>
            </>
          ) : (
            <EmptyStateCard title="还没选 AI 供应商" description="先选一个可用 adapter，后面的模型地址、密钥和路由才有意义。" />
          )}
          {providerStatus ? <SectionNote tone="success">{providerStatus}</SectionNote> : null}
          {providerError ? <SectionNote tone="warning">{providerError}</SectionNote> : null}
          <ActionRow>
            <PrimaryButton
              disabled={providerSaving || !currentAdapter || !providerForm.displayName.trim() || !providerForm.modelName.trim()}
              onClick={() => void handleProviderSubmit()}
            >
              {providerSaving ? '保存中...' : editingProviderId ? '保存并更新主链' : '创建并绑定主链'}
            </PrimaryButton>
            <SecondaryButton disabled={providerLoading || providerSaving} onClick={() => void loadSetupWorkspace(currentHouseholdId)}>
              刷新 AI 状态
            </SecondaryButton>
          </ActionRow>
        </PageSection>
      ) : null}

      {currentHouseholdId && currentStep === 'first_butler_agent' ? (
        <PageSection title="第四步：创建首位管家" description="这里接的是最小闭环：恢复或创建引导会话，实时聊天收集设定，确认后生成首位管家。">
          <StatusCard label="实时连接" value={butlerRealtimeReady ? '已连通' : '未连通'} tone={butlerRealtimeReady ? 'success' : 'warning'} />
          {existingButler ? (
            <View
              style={{
                background: '#eef8f3',
                border: `1px solid ${userAppTokens.colorSuccess}`,
                borderRadius: userAppTokens.radiusLg,
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '30px', fontWeight: '600' }}>
                当前家庭已经有首位管家
              </Text>
              <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', lineHeight: '1.6', marginTop: '8px' }}>
                {existingButler.display_name} 已经存在。现在最可能的问题不是“再建一个”，而是后端 setup 状态还没刷新到位。
              </Text>
              <ActionRow>
                <SecondaryButton onClick={() => void refreshAfterStep('已手动刷新 setup 状态。')}>
                  重新同步 setup 状态
                </SecondaryButton>
              </ActionRow>
            </View>
          ) : butlerLoading ? (
            <EmptyStateCard title="正在准备管家引导" description="先恢复已有 session，没有就创建新的，不在前端自己瞎造状态。" />
          ) : !butlerSession ? (
            <EmptyStateCard title="当前还没拿到管家引导会话" description="一般是 AI provider 还没配好，或者后端还没把当前家庭推进到这一步。" />
          ) : (
            <>
              <View
                style={{
                  background: '#f9fbff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  maxHeight: '720px',
                  overflow: 'auto',
                  padding: userAppTokens.spacingMd,
                }}
              >
                {butlerMessages.map(message => (
                  <View
                    key={message.id}
                    style={{
                      alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                      background: message.role === 'user' ? userAppTokens.colorPrimary : '#ffffff',
                      border: `1px solid ${message.role === 'user' ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusLg,
                      maxWidth: '88%',
                      padding: userAppTokens.spacingSm,
                    }}
                  >
                    <Text style={{ color: message.role === 'user' ? '#ffffff' : userAppTokens.colorText, display: 'block', fontSize: '24px', fontWeight: '600' }}>
                      {message.role === 'assistant' ? `${getButlerEmoji(butlerSession.draft.display_name || 'AI 管家')} ${butlerSession.draft.display_name || 'AI 管家'}` : '你'}
                    </Text>
                    <Text style={{ color: message.role === 'user' ? 'rgba(255,255,255,0.92)' : userAppTokens.colorText, display: 'block', fontSize: '24px', lineHeight: '1.6', marginTop: '8px', whiteSpace: 'pre-wrap' }}>
                      {normalizeMessageContent(message.content || (message.role === 'assistant' && butlerSending ? '正在输入...' : ''))}
                    </Text>
                  </View>
                ))}
              </View>

              {butlerSession.status === 'collecting' ? (
                <>
                  <Textarea
                    value={butlerInput}
                    maxlength={1000}
                    autoHeight
                    placeholder="直接说你希望这个家庭管家怎么称呼、怎么说话、有什么性格。"
                    onInput={event => setButlerInput(event.detail.value)}
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
                  <ActionRow>
                    <PrimaryButton disabled={butlerSending || !butlerInput.trim() || !butlerRealtimeReady} onClick={() => void handleButlerSend()}>
                      {butlerSending ? '发送中...' : '发送引导消息'}
                    </PrimaryButton>
                    <SecondaryButton disabled={butlerSending || butlerConfirming || butlerRestarting} onClick={() => void handleButlerRestart()}>
                      {butlerRestarting ? '重启中...' : '重新开始'}
                    </SecondaryButton>
                  </ActionRow>
                  <SectionNote>
                    当前{butlerRealtimeReady ? '优先走实时引导链路。' : '实时链路未就绪，先别硬发。'}
                  </SectionNote>
                </>
              ) : null}

              {butlerSession.status === 'reviewing' ? (
                <>
                  <FormField label="管家名称">
                    <TextInput
                      value={butlerSession.draft.display_name}
                      onInput={value => updateButlerDraft({ ...butlerSession.draft, display_name: value })}
                    />
                  </FormField>
                  <FormField label="说话风格">
                    <TextInput
                      value={butlerSession.draft.speaking_style}
                      onInput={value => updateButlerDraft({ ...butlerSession.draft, speaking_style: value })}
                    />
                  </FormField>
                  <FormField label="性格标签" hint="用逗号分开。至少留两个，不然这个设定还是空心的。">
                    <TextInput
                      value={stringifyTagList(butlerSession.draft.personality_traits)}
                      onInput={value => updateButlerDraft({
                        ...butlerSession.draft,
                        personality_traits: parseTagList(value),
                      })}
                    />
                  </FormField>
                  <ActionRow>
                    <PrimaryButton
                      disabled={
                        butlerConfirming
                        || !butlerSession.draft.display_name.trim()
                        || !butlerSession.draft.speaking_style.trim()
                        || butlerSession.draft.personality_traits.length < 2
                      }
                      onClick={() => void handleButlerConfirm()}
                    >
                      {butlerConfirming ? '创建中...' : `确认创建 ${butlerSession.draft.display_name || '首位管家'}`}
                    </PrimaryButton>
                    <SecondaryButton disabled={butlerConfirming || butlerRestarting} onClick={() => void handleButlerRestart()}>
                      重新生成
                    </SecondaryButton>
                  </ActionRow>
                </>
              ) : null}

              {createdButler ? (
                <View
                  style={{
                    background: '#eef8f3',
                    border: `1px solid ${userAppTokens.colorSuccess}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '30px', fontWeight: '600' }}>
                    {getButlerEmoji(createdButler.display_name)} {createdButler.display_name} 已加入家庭
                  </Text>
                </View>
              ) : null}

              {butlerStatus ? <SectionNote tone="success">{butlerStatus}</SectionNote> : null}
              {butlerError ? <SectionNote tone="warning">{butlerError}</SectionNote> : null}
            </>
          )}
        </PageSection>
      ) : null}

      {!bootstrap ? (
        <EmptyStateCard title="正在读取 setup 状态" description="启动摘要还没回来，先别急着判断页面有没有问题。" />
      ) : null}

      {!bootstrap?.actor?.authenticated && !loading ? (
        <EmptyStateCard
          title="当前还没登录"
          description="初始化向导需要先拿到账号态。"
          actionLabel="返回登录"
          onAction={() => void Taro.reLaunch({ url: APP_ROUTES.login })}
        />
      ) : null}

      {!bootstrap?.currentHousehold && currentStep !== 'family_profile' ? (
        <PageSection title="状态异常" description="如果 setup 步骤已经往后走，但当前家庭上下文为空，这就是数据不一致，不是前端该瞎猜。">
          <SectionNote tone="warning">
            先刷新一次；如果还这样，就该回头查后端 setup 状态和当前账号绑定。
          </SectionNote>
          <ActionRow>
            <SecondaryButton onClick={() => void refresh()}>
              重新读取 setup 状态
            </SecondaryButton>
          </ActionRow>
        </PageSection>
      ) : null}
    </AuthShellPage>
  );
}
