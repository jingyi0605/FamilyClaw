import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, ScrollView, Text, Textarea, View } from '@tarojs/components';
import { useDidShow } from '@tarojs/taro';
import {
  AgentSummary,
  ConversationActionRecord,
  ConversationMessage,
  ConversationProposalItem,
  ConversationSession,
  ConversationSessionDetail,
} from '@familyclaw/user-core';
import { createBrowserRealtimeClient, newRealtimeRequestId, type BrowserRealtimeClient } from '@familyclaw/user-platform';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  OptionPills,
  PrimaryButton,
  SecondaryButton,
  SectionNote,
} from '../../components/AppUi';
import { MainShellPage } from '../../components/MainShellPage';
import { coreApiClient, needsBlockingSetup, useAppRuntime } from '../../runtime';

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '刚刚';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.floor((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }

  return `${Math.floor(diffHours / 24)} 天前`;
}

function formatConnectionState(state: 'connecting' | 'connected' | 'closed') {
  switch (state) {
    case 'connecting':
      return '实时连接中';
    case 'connected':
      return '实时已连通';
    default:
      return '实时未连通';
  }
}

function formatAgentType(agentType: AgentSummary['agent_type']) {
  switch (agentType) {
    case 'butler':
      return '家庭管家';
    case 'nutritionist':
      return '营养顾问';
    case 'fitness_coach':
      return '健康教练';
    case 'study_coach':
      return '学习教练';
    default:
      return '自定义助手';
  }
}

function formatMessageStatus(status: ConversationMessage['status']) {
  switch (status) {
    case 'pending':
      return '等待响应';
    case 'streaming':
      return '正在生成';
    case 'failed':
      return '本轮失败';
    default:
      return '已完成';
  }
}

function buildPendingMessages(
  current: ConversationSessionDetail,
  requestId: string,
  question: string,
  selectedAgentId: string | null,
) {
  const createdAt = new Date().toISOString();
  const baseSeq = current.messages.length;
  return [
    ...current.messages,
    {
      id: `user:${requestId}`,
      session_id: current.id,
      request_id: requestId,
      seq: baseSeq + 1,
      role: 'user',
      message_type: 'text',
      content: question,
      status: 'completed',
      effective_agent_id: selectedAgentId,
      ai_provider_code: null,
      ai_trace_id: null,
      degraded: false,
      error_code: null,
      facts: [],
      suggestions: [],
      created_at: createdAt,
      updated_at: createdAt,
    } satisfies ConversationMessage,
    {
      id: `assistant:${requestId}`,
      session_id: current.id,
      request_id: requestId,
      seq: baseSeq + 2,
      role: 'assistant',
      message_type: 'text',
      content: '',
      status: 'pending',
      effective_agent_id: selectedAgentId,
      ai_provider_code: null,
      ai_trace_id: null,
      degraded: false,
      error_code: null,
      facts: [],
      suggestions: [],
      created_at: createdAt,
      updated_at: createdAt,
    } satisfies ConversationMessage,
  ];
}

function upsertSession(sessions: ConversationSession[], next: ConversationSession) {
  return [next, ...sessions.filter(item => item.id !== next.id)];
}

export default function AssistantPage() {
  const { bootstrap, loading } = useAppRuntime();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [activeSessionDetail, setActiveSessionDetail] = useState<ConversationSessionDetail | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [pageLoading, setPageLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [actionBusyId, setActionBusyId] = useState('');
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'closed'>('closed');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const loadRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const activeHouseholdIdRef = useRef('');
  const realtimeClientRef = useRef<BrowserRealtimeClient | null>(null);
  const pendingSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRealtimeRequestIdRef = useRef('');
  const suppressRealtimeCloseFeedbackRef = useRef(false);
  const sendingRef = useRef(false);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';

  const availableAgents = useMemo(
    () => agents.filter(agent => agent.conversation_enabled && agent.status === 'active'),
    [agents],
  );
  const selectedAgent = useMemo(
    () => availableAgents.find(agent => agent.id === selectedAgentId) ?? availableAgents[0] ?? null,
    [availableAgents, selectedAgentId],
  );
  const latestAssistantMessage = useMemo(
    () => [...(activeSessionDetail?.messages ?? [])].reverse().find(message => message.role === 'assistant') ?? null,
    [activeSessionDetail?.messages],
  );
  const pendingActions = useMemo(
    () => activeSessionDetail?.action_records.filter(item => item.status === 'pending_confirmation') ?? [],
    [activeSessionDetail?.action_records],
  );
  const pendingProposals = useMemo(
    () => activeSessionDetail?.proposal_batches.flatMap(batch => batch.items).filter(item => item.status === 'pending_confirmation') ?? [],
    [activeSessionDetail?.proposal_batches],
  );
  const undoableActions = useMemo(
    () => (
      activeSessionDetail?.action_records.filter(item => item.status === 'completed' && Object.keys(item.undo_payload ?? {}).length > 0) ?? []
    ).slice(-3),
    [activeSessionDetail?.action_records],
  );

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  useEffect(() => {
    if (activeSessionDetail?.active_agent_id) {
      setSelectedAgentId(current => current === activeSessionDetail.active_agent_id ? current : activeSessionDetail.active_agent_id ?? '');
      return;
    }

    setSelectedAgentId(current => {
      if (current && availableAgents.some(agent => agent.id === current)) {
        return current;
      }

      return availableAgents.find(agent => agent.default_entry)?.id ?? availableAgents[0]?.id ?? '';
    });
  }, [activeSessionDetail?.active_agent_id, availableAgents]);

  const resetPendingSyncTimer = useCallback(() => {
    if (pendingSyncTimerRef.current !== null) {
      clearTimeout(pendingSyncTimerRef.current);
      pendingSyncTimerRef.current = null;
    }
  }, []);

  const clearPendingRealtimeRequest = useCallback(() => {
    pendingRealtimeRequestIdRef.current = '';
    resetPendingSyncTimer();
    setSending(false);
  }, [resetPendingSyncTimer]);

  const syncActiveSessionDetail = useCallback(async (sessionId?: string) => {
    const targetSessionId = sessionId ?? activeSessionId;
    if (!targetSessionId) {
      return;
    }

    try {
      const detail = await coreApiClient.getConversationSession(targetSessionId);
      setActiveSessionDetail(detail);
      setSessions(current => upsertSession(current, detail));
    } catch {
      // 同步失败时保留当前页面内容，避免闪回空态。
    }
  }, [activeSessionId]);

  const loadAssistantWorkspace = useCallback(async () => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      setAgents([]);
      setSessions([]);
      setActiveSessionId('');
      setActiveSessionDetail(null);
      setSelectedAgentId('');
      setStatus('');
      setError('');
      clearPendingRealtimeRequest();
      resetPendingSyncTimer();
    }

    activeHouseholdIdRef.current = householdId;

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    try {
      const [agentsResult, sessionsResult] = await Promise.all([
        coreApiClient.listAgents(householdId),
        coreApiClient.listConversationSessions({ household_id: householdId, limit: 50 }),
      ]);

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      const nextAgents = agentsResult.items
        .filter(agent => agent.conversation_enabled && agent.status === 'active')
        .sort((left, right) => left.sort_order - right.sort_order);
      const nextSessions = sessionsResult.items;
      const nextSessionId = nextSessions.some(item => item.id === activeSessionId)
        ? activeSessionId
        : nextSessions[0]?.id ?? '';

      setAgents(nextAgents);
      setSessions(nextSessions);
      setSelectedAgentId(current => current || nextAgents.find(agent => agent.default_entry)?.id || nextAgents[0]?.id || '');
      setActiveSessionId(nextSessionId);
    } catch (loadError) {
      if (requestId === loadRequestIdRef.current) {
        setError(loadError instanceof Error ? loadError.message : '助手页加载失败');
      }
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [activeSessionId, clearPendingRealtimeRequest, currentHouseholdId, resetPendingSyncTimer]);

  useEffect(() => {
    if (loading || !bootstrap?.actor?.authenticated || needsBlockingSetup(bootstrap.setupStatus)) {
      return;
    }

    void loadAssistantWorkspace();
  }, [bootstrap, loadAssistantWorkspace, loading]);

  useDidShow(() => {
    if (!loading && bootstrap?.actor?.authenticated && !needsBlockingSetup(bootstrap.setupStatus)) {
      void loadAssistantWorkspace();
    }
  });

  useEffect(() => {
    if (!activeSessionId) {
      setActiveSessionDetail(null);
      return;
    }

    const requestId = ++detailRequestIdRef.current;
    setError('');

    void coreApiClient.getConversationSession(activeSessionId)
      .then(detail => {
        if (requestId !== detailRequestIdRef.current) {
          return;
        }
        setActiveSessionDetail(detail);
        setSessions(current => upsertSession(current, detail));
      })
      .catch(detailError => {
        if (requestId === detailRequestIdRef.current) {
          setError(detailError instanceof Error ? detailError.message : '会话详情加载失败');
        }
      });
  }, [activeSessionId]);

  useEffect(() => {
    if (!currentHouseholdId || !activeSessionId) {
      clearPendingRealtimeRequest();
      suppressRealtimeCloseFeedbackRef.current = true;
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setConnectionState('closed');
      return;
    }

    clearPendingRealtimeRequest();
    suppressRealtimeCloseFeedbackRef.current = true;
    realtimeClientRef.current?.close();
    setConnectionState('connecting');

    realtimeClientRef.current = createBrowserRealtimeClient({
      householdId: currentHouseholdId,
      sessionId: activeSessionId,
      channel: 'conversation',
      onOpen: () => {
        suppressRealtimeCloseFeedbackRef.current = false;
        setConnectionState('connected');
      },
      onClose: () => {
        setConnectionState('closed');
        if (suppressRealtimeCloseFeedbackRef.current) {
          suppressRealtimeCloseFeedbackRef.current = false;
          return;
        }
        if (sendingRef.current) {
          void syncActiveSessionDetail(activeSessionId);
          clearPendingRealtimeRequest();
          setError('实时连接已断开，已回退到会话同步。');
        }
      },
      onError: () => {
        setConnectionState('closed');
        if (sendingRef.current) {
          void syncActiveSessionDetail(activeSessionId);
          clearPendingRealtimeRequest();
          setError('实时连接异常，已回退到会话同步。');
        }
      },
      onEvent: event => {
        if (event.type === 'session.snapshot') {
          const snapshot = (event.payload as { snapshot: ConversationSessionDetail }).snapshot;
          setActiveSessionDetail(snapshot);
          setSessions(current => upsertSession(current, snapshot));
          if (pendingRealtimeRequestIdRef.current) {
            const pendingMessage = snapshot.messages.find(message => (
              message.request_id === pendingRealtimeRequestIdRef.current && message.role === 'assistant'
            ));
            if (!pendingMessage || pendingMessage.status === 'completed' || pendingMessage.status === 'failed') {
              clearPendingRealtimeRequest();
            }
          }
          return;
        }

        if (event.type === 'agent.chunk') {
          const chunkPayload = event.payload as { text?: string };
          const chunkText = typeof chunkPayload.text === 'string' ? chunkPayload.text : '';
          setActiveSessionDetail(current => {
            if (!current) {
              return current;
            }

            return {
              ...current,
              messages: current.messages.map(message => (
                message.request_id === event.request_id && message.role === 'assistant'
                  ? {
                    ...message,
                    status: 'streaming',
                    content: message.content + chunkText,
                    updated_at: new Date().toISOString(),
                  }
                  : message
              )),
            };
          });
          return;
        }

        if (event.type === 'agent.done') {
          clearPendingRealtimeRequest();
          void syncActiveSessionDetail(activeSessionId);
          return;
        }

        if (event.type === 'agent.error') {
          clearPendingRealtimeRequest();
          const errorPayload = event.payload as { detail?: string };
          setError(typeof errorPayload.detail === 'string' ? errorPayload.detail : '助手响应失败');
          void syncActiveSessionDetail(activeSessionId);
        }
      },
    });

    return () => {
      clearPendingRealtimeRequest();
      suppressRealtimeCloseFeedbackRef.current = true;
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setConnectionState('closed');
    };
  }, [activeSessionId, clearPendingRealtimeRequest, currentHouseholdId, resetPendingSyncTimer, syncActiveSessionDetail]);

  async function refreshSessions(preferredSessionId?: string) {
    if (!currentHouseholdId) {
      return;
    }

    const result = await coreApiClient.listConversationSessions({
      household_id: currentHouseholdId,
      limit: 50,
    });
    setSessions(result.items);
    if (preferredSessionId) {
      setActiveSessionId(preferredSessionId);
    }
  }

  async function ensureSession() {
    if (activeSessionDetail) {
      return activeSessionDetail;
    }

    if (!currentHouseholdId) {
      throw new Error('当前没有可用的家庭上下文');
    }

    const created = await coreApiClient.createConversationSession({
      household_id: currentHouseholdId,
      active_agent_id: selectedAgent?.id ?? undefined,
    });
    setSessions(current => upsertSession(current, created));
    setActiveSessionId(created.id);
    setActiveSessionDetail(created);
    return created;
  }

  async function handleNewSession() {
    if (!currentHouseholdId) {
      return;
    }

    clearPendingRealtimeRequest();
    setStatus('');
    setError('');

    try {
      const created = await coreApiClient.createConversationSession({
        household_id: currentHouseholdId,
        active_agent_id: selectedAgent?.id ?? undefined,
      });
      setSessions(current => upsertSession(current, created));
      setActiveSessionId(created.id);
      setActiveSessionDetail(created);
      setStatus('已新建会话。');
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建会话失败');
    }
  }

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim();
    if (!question) {
      return;
    }

    setSending(true);
    setStatus('');
    setError('');
    setInputValue('');

    try {
      const session = await ensureSession();
      const fallbackToHttp = async (statusMessage: string) => {
        const result = await coreApiClient.createConversationTurn(session.id, {
          message: question,
          agent_id: selectedAgent?.id ?? undefined,
          channel: 'h5',
        });
        clearPendingRealtimeRequest();
        setActiveSessionDetail(result.session);
        setSessions(current => upsertSession(current, result.session));
        setStatus(statusMessage);
      };

      if (realtimeClientRef.current && connectionState === 'connected') {
        const requestId = newRealtimeRequestId();
        pendingRealtimeRequestIdRef.current = requestId;
        setActiveSessionDetail(current => (
          current && current.id === session.id
            ? {
              ...current,
              messages: buildPendingMessages(
                current,
                requestId,
                question,
                selectedAgent?.id ?? current.active_agent_id ?? null,
              ),
            }
            : current
        ));
        try {
          realtimeClientRef.current.sendUserMessage(requestId, question);
          resetPendingSyncTimer();
          pendingSyncTimerRef.current = setTimeout(() => {
            clearPendingRealtimeRequest();
            void syncActiveSessionDetail(session.id);
            setError('实时回复超时，已回退到会话同步。');
          }, 20000);
          void refreshSessions(session.id).catch(() => undefined);
          return;
        } catch {
          pendingRealtimeRequestIdRef.current = '';
          resetPendingSyncTimer();
          await fallbackToHttp('实时发送失败，已自动回退到 HTTP 链路。');
          return;
        }
      }

      await fallbackToHttp('已通过 HTTP 回退链路完成本轮对话。');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '发送失败');
    } finally {
      if (!pendingRealtimeRequestIdRef.current) {
        setSending(false);
      }
    }
  }

  async function handleAction(actionId: string, actionType: 'confirm' | 'dismiss' | 'undo') {
    setActionBusyId(actionId);
    setStatus('');
    setError('');

    try {
      if (actionType === 'confirm') {
        await coreApiClient.confirmConversationAction(actionId);
        setStatus('动作已确认执行。');
      } else if (actionType === 'dismiss') {
        await coreApiClient.dismissConversationAction(actionId);
        setStatus('动作已忽略。');
      } else {
        await coreApiClient.undoConversationAction(actionId);
        setStatus('动作已撤回。');
      }

      await syncActiveSessionDetail();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '动作处理失败');
    } finally {
      setActionBusyId('');
    }
  }

  async function handleProposal(proposalId: string, actionType: 'confirm' | 'dismiss') {
    setActionBusyId(proposalId);
    setStatus('');
    setError('');

    try {
      if (actionType === 'confirm') {
        await coreApiClient.confirmConversationProposal(proposalId);
        setStatus('建议已确认执行。');
      } else {
        await coreApiClient.dismissConversationProposal(proposalId);
        setStatus('建议已忽略。');
      }

      await syncActiveSessionDetail();
    } catch (proposalError) {
      setError(proposalError instanceof Error ? proposalError.message : '建议处理失败');
    } finally {
      setActionBusyId('');
    }
  }

  return (
    <MainShellPage currentNav="assistant" title="助手主链已迁入新应用" description="这页已经接入共享会话 API 和实时适配层，聊天不再靠 user-web 托底。">
      <PageSection title="当前会话状态" description="先把会话、实时连接和当前家庭上下文放在同一层看清楚。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="可用助手" value={availableAgents.length ? `${availableAgents.length} 个` : '暂无'} tone="success" />
        <StatusCard label="实时状态" value={formatConnectionState(connectionState)} tone={connectionState === 'connected' ? 'success' : 'warning'} />
        <StatusCard label="待确认事项" value={`${pendingActions.length + pendingProposals.length}`} tone="warning" />
        {pageLoading ? <SectionNote>正在加载助手工作台...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
      </PageSection>

      {availableAgents.length === 0 && !pageLoading ? (
        <EmptyStateCard title="当前还没有可用助手" description="先在 AI 配置里准备一个可对话助手，这里才会真正跑起来。" />
      ) : (
        <>
          <PageSection title="选择助手" description="优先保留真正可用的助手切换，不照搬旧页面那套厚壳。">
            <OptionPills
              value={selectedAgent?.id ?? ''}
              disabled={sending}
              options={availableAgents.map(agent => ({
                value: agent.id,
                label: `${agent.display_name} · ${formatAgentType(agent.agent_type)}`,
              }))}
              onChange={value => setSelectedAgentId(value)}
            />
            {selectedAgent ? (
              <SectionNote>
                {selectedAgent.summary ?? `${selectedAgent.display_name} 已准备好接管当前家庭的对话。`}
              </SectionNote>
            ) : null}
          </PageSection>

          <PageSection title="会话历史" description="会话列表先做到真能切换和新建，不搞复杂抽屉。">
            <ActionRow>
              <PrimaryButton disabled={!currentHouseholdId || sending} onClick={() => void handleNewSession()}>
                新建会话
              </PrimaryButton>
              <SecondaryButton disabled={!activeSessionId || sending} onClick={() => void syncActiveSessionDetail()}>
                同步当前会话
              </SecondaryButton>
            </ActionRow>
            {sessions.length === 0 && !pageLoading ? (
              <EmptyStateCard title="还没有历史会话" description="先发起第一条消息，助手链路就会把会话建起来。" />
            ) : (
              <ScrollView scrollX>
                <View style={{ display: 'flex', flexDirection: 'row', gap: '12px', marginTop: '12px' }}>
                  {sessions.map(session => (
                    <Button
                      key={session.id}
                      size="mini"
                      disabled={sending}
                      onClick={() => setActiveSessionId(session.id)}
                      style={{
                        background: session.id === activeSessionId ? userAppTokens.colorPrimary : '#f9fbff',
                        border: `1px solid ${session.id === activeSessionId ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                        borderRadius: userAppTokens.radiusMd,
                        color: session.id === activeSessionId ? '#ffffff' : userAppTokens.colorText,
                        minWidth: '220px',
                      }}
                    >
                      {session.title || '未命名会话'}
                    </Button>
                  ))}
                </View>
              </ScrollView>
            )}
          </PageSection>

          <PageSection title="对话记录" description="实时可用时走流式消息，不可用时自动退回 HTTP 回答。">
            {!activeSessionDetail ? (
              <EmptyStateCard title="当前还没有打开的会话" description="先新建会话，或者从上面的历史里选一个。" />
            ) : (
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
                {activeSessionDetail.messages.length === 0 ? (
                  <EmptyStateCard title="这轮会话还没有消息" description="直接问问题，看看助手链路会不会真响应。" />
                ) : (
                  activeSessionDetail.messages.map(message => (
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
                      <Text style={{ color: message.role === 'user' ? '#ffffff' : userAppTokens.colorText, display: 'block', fontSize: '26px', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
                        {message.content || (message.status === 'pending' ? '正在等待助手响应...' : '')}
                      </Text>
                      <Text style={{ color: message.role === 'user' ? 'rgba(255,255,255,0.82)' : userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '8px' }}>
                        {message.role === 'user' ? '你' : selectedAgent?.display_name ?? '助手'} · {formatMessageStatus(message.status)} · {formatRelativeTime(message.updated_at)}
                      </Text>
                      {message.degraded ? <SectionNote tone="warning">当前回答已降级。</SectionNote> : null}
                    </View>
                  ))
                )}
              </View>
            )}
          </PageSection>

          {(pendingActions.length > 0 || pendingProposals.length > 0 || undoableActions.length > 0) ? (
            <PageSection title="待确认与可撤回动作" description="助手不只是聊天，执行链路也得能在新应用里收口。">
              <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {pendingActions.map((action: ConversationActionRecord) => (
                  <View
                    key={action.id}
                    style={{
                      background: '#fff8ec',
                      border: `1px solid ${userAppTokens.colorWarning}`,
                      borderRadius: userAppTokens.radiusLg,
                      padding: userAppTokens.spacingMd,
                    }}
                  >
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                      {action.title}
                    </Text>
                    {action.summary ? <SectionNote>{action.summary}</SectionNote> : null}
                    <ActionRow>
                      <PrimaryButton disabled={actionBusyId === action.id} onClick={() => void handleAction(action.id, 'confirm')}>
                        {actionBusyId === action.id ? '处理中...' : '确认执行'}
                      </PrimaryButton>
                      <SecondaryButton disabled={actionBusyId === action.id} onClick={() => void handleAction(action.id, 'dismiss')}>
                        暂不执行
                      </SecondaryButton>
                    </ActionRow>
                  </View>
                ))}

                {pendingProposals.map((proposal: ConversationProposalItem) => (
                  <View
                    key={proposal.id}
                    style={{
                      background: '#eef5ff',
                      border: `1px solid ${userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusLg,
                      padding: userAppTokens.spacingMd,
                    }}
                  >
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                      {proposal.title}
                    </Text>
                    {proposal.summary ? <SectionNote>{proposal.summary}</SectionNote> : null}
                    <ActionRow>
                      <PrimaryButton disabled={actionBusyId === proposal.id} onClick={() => void handleProposal(proposal.id, 'confirm')}>
                        {actionBusyId === proposal.id ? '处理中...' : '确认应用'}
                      </PrimaryButton>
                      <SecondaryButton disabled={actionBusyId === proposal.id} onClick={() => void handleProposal(proposal.id, 'dismiss')}>
                        先忽略
                      </SecondaryButton>
                    </ActionRow>
                  </View>
                ))}

                {undoableActions.map((action: ConversationActionRecord) => (
                  <View
                    key={`${action.id}-undo`}
                    style={{
                      background: '#f9fbff',
                      border: `1px solid ${userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusLg,
                      padding: userAppTokens.spacingMd,
                    }}
                  >
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                      {action.title}
                    </Text>
                    <SectionNote>{action.summary ?? '这条动作已经执行，如有必要可以在这里撤回。'}</SectionNote>
                    <ActionRow>
                      <SecondaryButton disabled={actionBusyId === action.id} onClick={() => void handleAction(action.id, 'undo')}>
                        {actionBusyId === action.id ? '处理中...' : '撤回动作'}
                      </SecondaryButton>
                    </ActionRow>
                  </View>
                ))}
              </View>
            </PageSection>
          ) : null}

          <PageSection title="发送消息" description="输入框先保证真能发、真能回，不先追逐复杂花活。">
            <Textarea
              value={inputValue}
              maxlength={1000}
              autoHeight
              placeholder="直接问家庭状态、提醒安排、配置建议，看看助手会不会真响应。"
              onInput={event => setInputValue(event.detail.value)}
              style={{
                background: '#ffffff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                color: userAppTokens.colorText,
                fontSize: '26px',
                minHeight: '140px',
                padding: '16px',
                width: '100%',
              }}
            />
            {latestAssistantMessage?.suggestions?.length ? (
              <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '12px', marginTop: '12px' }}>
                {latestAssistantMessage.suggestions.slice(0, 4).map(suggestion => (
                  <Button
                    key={suggestion}
                    size="mini"
                    onClick={() => void submitQuestion(suggestion)}
                    style={{
                      background: userAppTokens.colorSurface,
                      border: `1px solid ${userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusMd,
                      color: userAppTokens.colorText,
                    }}
                  >
                    {suggestion}
                  </Button>
                ))}
              </View>
            ) : null}
            <ActionRow>
              <PrimaryButton disabled={sending || !inputValue.trim() || !currentHouseholdId} onClick={() => void submitQuestion(inputValue)}>
                {sending ? '发送中...' : '发送问题'}
              </PrimaryButton>
              <SecondaryButton disabled={sending || !activeSessionId} onClick={() => void syncActiveSessionDetail()}>
                刷新当前会话
              </SecondaryButton>
            </ActionRow>
            <SectionNote>
              {connectionState === 'connected'
                ? '当前优先走实时通道，能看到流式回复。'
                : '当前实时不可用，会自动退回 HTTP 回答，不会把页面卡死。'}
            </SectionNote>
          </PageSection>
        </>
      )}
    </MainShellPage>
  );
}
