import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Menu, MessageSquarePlus, History, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/base';
import { useI18n } from '../i18n';
import { api } from '../lib/api';
import { createConversationRealtimeClient, newRealtimeRequestId, type ConversationRealtimeClient } from '../lib/conversationRealtime';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel, isConversationAgent, pickDefaultConversationAgent } from '../lib/agents';
import type {
  AgentSummary,
  ConversationActionRecord,
  ConversationMessage,
  ConversationProposalItem,
  ConversationSession,
  ConversationSessionDetail,
  ScheduledTaskConversationProposalPayload,
} from '../lib/types';
import { useHouseholdContext } from '../state/household';

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '刚刚';
  const diffMinutes = Math.max(1, Math.floor((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return date.toLocaleDateString('zh-CN');
}

function upsertSession(sessions: ConversationSession[], next: ConversationSession) {
  return [next, ...sessions.filter(item => item.id !== next.id)];
}

function buildPendingMessages(
  current: ConversationSessionDetail,
  requestId: string,
  question: string,
  userMessageId: string,
  assistantMessageId: string,
  selectedAgentId: string | null,
) {
  const createdAt = new Date().toISOString();
  const base = current.messages.length;
  return [
    ...current.messages,
    {
      id: userMessageId,
      session_id: current.id,
      request_id: requestId,
      seq: base + 1,
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
      id: assistantMessageId,
      session_id: current.id,
      request_id: requestId,
      seq: base + 2,
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

function getActionIcon(action: ConversationActionRecord) {
  if (action.action_name === 'reminder.create') return '⏰';
  if (action.action_category === 'config') return '⚙️';
  return '🧠';
}

function getActionStatusText(action: ConversationActionRecord) {
  if (action.status === 'pending_confirmation') return '等待你确认';
  if (action.status === 'completed') return '已执行';
  if (action.status === 'dismissed') return '已忽略';
  if (action.status === 'undone') return '已撤回';
  if (action.status === 'undo_failed') return '撤回失败';
  return '执行失败';
}

function buildActionResultText(action: ConversationActionRecord) {
  if (action.status === 'completed' && action.action_name === 'memory.write') return '已写入正式记忆';
  if (action.status === 'completed' && action.action_name === 'config.apply') return '已应用配置建议';
  if (action.status === 'completed' && action.action_name === 'reminder.create') return '已创建提醒';
  if (action.status === 'undone') return '这次操作已经撤回';
  if (action.status === 'dismissed') return '这次操作已忽略';
  const error = action.result_payload?.error;
  return typeof error === 'string' && error ? error : getActionStatusText(action);
}

function getProposalIcon(item: ConversationProposalItem) {
  if (item.proposal_kind === 'scheduled_task_create') return '🗓️';
  if (item.proposal_kind === 'scheduled_task_update') return '🛠️';
  if (item.proposal_kind === 'scheduled_task_pause') return '⏸️';
  if (item.proposal_kind === 'scheduled_task_resume') return '▶️';
  if (item.proposal_kind === 'scheduled_task_delete') return '🗑️';
  if (item.proposal_kind === 'reminder_create') return '🔔';
  if (item.proposal_kind === 'config_apply') return '⚙️';
  return '🧠';
}

function getProposalStatusText(item: ConversationProposalItem) {
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_create') return '计划任务已经创建';
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_update') return '计划任务已经更新';
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_pause') return '计划任务已经暂停';
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_resume') return '计划任务已经恢复';
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_delete') return '计划任务已经删除';
  if (item.status === 'pending_confirmation') return '等待你确认';
  if (item.status === 'completed' && item.proposal_kind === 'config_apply') return '配置已经应用';
  if (item.status === 'completed' && item.proposal_kind === 'memory_write') return '记忆已经写入';
  if (item.status === 'completed' && item.proposal_kind === 'reminder_create') return '提醒已经创建';
  if (item.status === 'dismissed') return '这条建议已忽略';
  if (item.status === 'ignored') return '这条建议已忽略';
  if (item.status === 'failed') return '执行失败';
  return '建议已生成';
}

function getProposalPrimaryActionText(item: ConversationProposalItem) {
  if (item.proposal_kind === 'scheduled_task_create') return '确认创建';
  if (item.proposal_kind === 'scheduled_task_update') return '确认更新';
  if (item.proposal_kind === 'scheduled_task_pause') return '确认暂停';
  if (item.proposal_kind === 'scheduled_task_resume') return '确认恢复';
  if (item.proposal_kind === 'scheduled_task_delete') return '确认删除';
  return '确认应用';
}

function getProposalDismissText(item: ConversationProposalItem) {
  if (item.proposal_kind === 'scheduled_task_create') return '先不创建';
  if (item.proposal_kind.startsWith('scheduled_task_')) return '先不处理';
  return '先不改';
}

function getProposalMetaText(item: ConversationProposalItem) {
  if (item.proposal_kind.startsWith('scheduled_task_')) {
    return item.status === 'pending_confirmation' ? 'AI 已经整理出一条计划任务，等你确认后才会正式创建。' : getProposalStatusText(item);
  }
  return item.status === 'pending_confirmation' ? 'AI 整理出一条可执行建议，当前设置是先问你。' : getProposalStatusText(item);
}

function parseScheduledTaskProposalPayload(item: ConversationProposalItem): ScheduledTaskConversationProposalPayload | null {
  if (item.proposal_kind !== 'scheduled_task_create') return null;
  const payload = item.payload;
  if (!payload || typeof payload !== 'object') return null;
  return {
    draft_id: typeof payload.draft_id === 'string' ? payload.draft_id : '',
    intent_summary: typeof payload.intent_summary === 'string' ? payload.intent_summary : item.summary ?? item.title,
    missing_fields: Array.isArray(payload.missing_fields) ? payload.missing_fields.filter(value => typeof value === 'string') : [],
    missing_field_labels: Array.isArray(payload.missing_field_labels) ? payload.missing_field_labels.filter(value => typeof value === 'string') : [],
    draft_payload: payload.draft_payload && typeof payload.draft_payload === 'object' ? payload.draft_payload as Record<string, unknown> : {},
    can_confirm: Boolean(payload.can_confirm),
    owner_summary: typeof payload.owner_summary === 'string' ? payload.owner_summary : null,
    schedule_summary: typeof payload.schedule_summary === 'string' ? payload.schedule_summary : null,
    target_summary: typeof payload.target_summary === 'string' ? payload.target_summary : null,
    confirm_block_reason: typeof payload.confirm_block_reason === 'string' ? payload.confirm_block_reason : null,
  };
}

export function ConversationPageV2() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { currentHousehold, currentHouseholdId } = useHouseholdContext();
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [activeSessionDetail, setActiveSessionDetail] = useState<ConversationSessionDetail | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [realtimeReady, setRealtimeReady] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [actionBusyId, setActionBusyId] = useState('');
  const [expandedAutoMessageId, setExpandedAutoMessageId] = useState('');
  const realtimeClientRef = useRef<ConversationRealtimeClient | null>(null);
  const pendingSyncTimerRef = useRef<number | null>(null);
  const sendingRef = useRef(false);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const conversationAgents = useMemo(() => agents.filter(isConversationAgent), [agents]);
  const defaultAgent = useMemo(() => pickDefaultConversationAgent(agents), [agents]);
  const selectedAgent = useMemo(
    () => agents.find(item => item.id === selectedAgentId) ?? defaultAgent,
    [agents, defaultAgent, selectedAgentId],
  );
  const recentFacts = useMemo(
    () => (activeSessionDetail?.messages ?? []).filter(item => item.role === 'assistant').flatMap(item => item.facts).slice(0, 3),
    [activeSessionDetail],
  );
  const actionRecords = useMemo(() => activeSessionDetail?.action_records ?? [], [activeSessionDetail]);
  const proposalBatches = useMemo(() => activeSessionDetail?.proposal_batches ?? [], [activeSessionDetail]);
  const actionsByMessageId = useMemo(() => {
    const grouped = new Map<string, ConversationActionRecord[]>();
    for (const item of actionRecords) {
      if (!item.source_message_id) continue;
      const current = grouped.get(item.source_message_id) ?? [];
      current.push(item);
      grouped.set(item.source_message_id, current);
    }
    return grouped;
  }, [actionRecords]);
  const proposalsByRequestId = useMemo(() => {
    const grouped = new Map<string, ConversationProposalItem[]>();
    for (const batch of proposalBatches) {
      if (!batch.request_id) continue;
      const current = grouped.get(batch.request_id) ?? [];
      current.push(...batch.items);
      grouped.set(batch.request_id, current);
    }
    return grouped;
  }, [proposalBatches]);
  const latestScheduledProposalIds = useMemo(() => {
    const latest = new Map<string, string>();
    for (const batch of proposalBatches) {
      for (const item of batch.items) {
        const payload = parseScheduledTaskProposalPayload(item);
        if (!payload?.draft_id) continue;
        latest.set(payload.draft_id, item.id);
      }
    }
    return latest;
  }, [proposalBatches]);
  const pendingActionCount = useMemo(
    () => (
      actionRecords.filter(item => item.status === 'pending_confirmation').length
      + proposalBatches.flatMap(batch => batch.items).filter(item => item.status === 'pending_confirmation').length
    ),
    [actionRecords, proposalBatches],
  );
  const recentActionRecords = useMemo(() => actionRecords.slice(-5).reverse(), [actionRecords]);

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [activeSessionDetail?.messages, activeSessionDetail?.action_records]);

  useEffect(() => {
    if (!currentHouseholdId) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const [agentResult, sessionResult] = await Promise.all([
          api.listAgents(currentHouseholdId),
          api.listConversationSessions({ household_id: currentHouseholdId, limit: 50 }),
        ]);
        if (cancelled) return;
        setAgents(agentResult.items);
        setSessions(sessionResult.items);
        setActiveSessionId(current => current || sessionResult.items[0]?.id || '');
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载对话失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!activeSessionId) {
      setActiveSessionDetail(null);
      return;
    }
    let cancelled = false;
    void api.getConversationSession(activeSessionId)
      .then(detail => {
        if (cancelled) return;
        setActiveSessionDetail(detail);
        setSessions(current => upsertSession(current, detail));
      })
      .catch(detailError => {
        if (!cancelled) setError(detailError instanceof Error ? detailError.message : '加载会话详情失败');
      });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  async function syncActiveSessionDetail(sessionId?: string) {
    const targetSessionId = sessionId ?? activeSessionId;
    if (!targetSessionId) return;
    try {
      const detail = await api.getConversationSession(targetSessionId);
      setActiveSessionDetail(detail);
      setSessions(current => upsertSession(current, detail));
      const latestMessage = [...detail.messages].reverse().find(item => item.role === 'assistant');
      setSuggestions(latestMessage?.suggestions ?? []);
    } catch {
      return;
    }
  }

  function resetPendingSyncTimer() {
    if (pendingSyncTimerRef.current !== null) {
      window.clearTimeout(pendingSyncTimerRef.current);
      pendingSyncTimerRef.current = null;
    }
  }

  useEffect(() => {
    if (!currentHouseholdId || !activeSessionId) {
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setRealtimeReady(false);
      return;
    }

    realtimeClientRef.current?.close();
    realtimeClientRef.current = createConversationRealtimeClient({
      householdId: currentHouseholdId,
      sessionId: activeSessionId,
      onOpen: () => {
        setRealtimeReady(true);
        resetPendingSyncTimer();
      },
      onClose: () => {
        setRealtimeReady(false);
        if (sendingRef.current) {
          void syncActiveSessionDetail(activeSessionId);
          setSending(false);
          setError('实时连接已断开，已尝试同步最新会话。');
        }
      },
      onError: () => {
        setRealtimeReady(false);
        if (sendingRef.current) {
          void syncActiveSessionDetail(activeSessionId);
          setSending(false);
        }
        setError('实时连接异常，请稍后重试。');
      },
      onEvent: event => {
        if (event.type === 'session.snapshot') {
          const nextSession = (event.payload as { snapshot: ConversationSessionDetail }).snapshot;
          setActiveSessionDetail(nextSession);
          setSessions(current => upsertSession(current, nextSession));
          const latestMessage = [...nextSession.messages].reverse().find(item => item.role === 'assistant');
          setSuggestions(latestMessage?.suggestions ?? []);
          if (nextSession.messages.some(message => message.status === 'completed' || message.status === 'failed')) {
            resetPendingSyncTimer();
          }
          return;
        }
        if (event.type === 'agent.chunk') {
          const chunkText = 'text' in event.payload ? event.payload.text : '';
          setActiveSessionDetail(current => {
            if (!current) return current;
            const requestId = event.request_id ?? null;
            return {
              ...current,
              messages: current.messages.map(message => (
                message.request_id === requestId && message.role === 'assistant'
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
          resetPendingSyncTimer();
          setActiveSessionDetail(current => {
            if (!current) return current;
            const requestId = event.request_id ?? null;
            return {
              ...current,
              messages: current.messages.map(message => (
                message.request_id === requestId && message.role === 'assistant'
                  ? {
                    ...message,
                    status: message.status === 'failed' ? 'failed' : 'completed',
                    updated_at: new Date().toISOString(),
                  }
                  : message
              )),
            };
          });
          void syncActiveSessionDetail(activeSessionId);
          setSending(false);
          return;
        }
        if (event.type === 'agent.error') {
          resetPendingSyncTimer();
          const payload = event.payload as { detail: string };
          setError(payload.detail);
          setSending(false);
        }
      },
    });

    return () => {
      resetPendingSyncTimer();
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setRealtimeReady(false);
    };
  }, [activeSessionId, currentHouseholdId]);

  useEffect(() => {
    const nextAgentId = activeSessionDetail?.active_agent_id ?? defaultAgent?.id ?? '';
    if (nextAgentId && nextAgentId !== selectedAgentId) {
      setSelectedAgentId(nextAgentId);
    }
  }, [activeSessionDetail?.active_agent_id, defaultAgent?.id, selectedAgentId]);

  useEffect(() => {
    if (!currentHouseholdId) return;
    void api.getFamilyQaSuggestions(currentHouseholdId, undefined, selectedAgentId || undefined)
      .then(result => setSuggestions(result.items.map(item => item.question)))
      .catch(() => undefined);
  }, [currentHouseholdId, selectedAgentId]);

  async function refreshSessions(preferredSessionId?: string) {
    if (!currentHouseholdId) return;
    const result = await api.listConversationSessions({ household_id: currentHouseholdId, limit: 50 });
    setSessions(result.items);
    if (preferredSessionId) {
      setActiveSessionId(preferredSessionId);
    }
  }

  async function ensureSession() {
    if (activeSessionDetail) return activeSessionDetail;
    if (!currentHouseholdId) throw new Error('当前家庭不存在');
    const created = await api.createConversationSession({
      household_id: currentHouseholdId,
      active_agent_id: selectedAgent?.id ?? undefined,
    });
    setSessions(current => upsertSession(current, created));
    setActiveSessionId(created.id);
    setActiveSessionDetail(created);
    return created;
  }

  async function handleNewChat() {
    setStatus('');
    setError('');
    if (!currentHouseholdId) return;
    const created = await api.createConversationSession({
      household_id: currentHouseholdId,
      active_agent_id: selectedAgent?.id ?? undefined,
    });
    setSessions(current => upsertSession(current, created));
    setActiveSessionId(created.id);
    setActiveSessionDetail(created);
  }

  async function handleAgentSwitch(agentId: string) {
    setSelectedAgentId(agentId);
    if (!activeSessionDetail || activeSessionDetail.messages.length === 0) return;
    const nextAgent = conversationAgents.find(item => item.id === agentId);
    if (!nextAgent) return;
    setStatus(`已切换到 ${nextAgent.display_name}，新对话会按这个角色继续。`);
    await handleNewChat();
  }

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim();
    if (!question) return;
    setSending(true);
    setError('');
    setStatus('');
    setInputValue('');
    try {
      const session = await ensureSession();
      if (!realtimeClientRef.current || !realtimeReady) {
        throw new Error('实时连接还没建立完成');
      }
      const requestId = newRealtimeRequestId();
      setActiveSessionDetail(current => (
        current && current.id === session.id
          ? {
            ...current,
            messages: buildPendingMessages(
              current,
              requestId,
              question,
              `user:${requestId}`,
              `assistant:${requestId}`,
              selectedAgent?.id ?? current.active_agent_id ?? null,
            ),
          }
          : current
      ));
      realtimeClientRef.current.sendUserMessage(requestId, question);
      resetPendingSyncTimer();
      pendingSyncTimerRef.current = window.setTimeout(() => {
        void syncActiveSessionDetail(session.id);
        setSending(false);
      }, 20000);
      void refreshSessions(session.id).catch(() => undefined);
    } catch (submitError) {
      resetPendingSyncTimer();
      setError(submitError instanceof Error ? submitError.message : '提问失败');
      setSending(false);
    } finally {
      if (!realtimeReady) {
        setSending(false);
      }
    }
  }

  async function handleConversationAction(
    actionId: string,
    actionType: 'confirm' | 'dismiss' | 'undo',
    successText: string,
  ) {
    try {
      setActionBusyId(actionId);
      if (actionType === 'confirm') {
        await api.confirmConversationAction(actionId);
      } else if (actionType === 'dismiss') {
        await api.dismissConversationAction(actionId);
      } else {
        await api.undoConversationAction(actionId);
      }
      await syncActiveSessionDetail();
      setStatus(successText);
      setError('');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '处理动作失败');
    } finally {
      setActionBusyId('');
    }
  }

  async function handleConversationProposal(
    proposalItemId: string,
    actionType: 'confirm' | 'dismiss',
    successText: string,
  ) {
    try {
      setActionBusyId(proposalItemId);
      if (actionType === 'confirm') {
        await api.confirmConversationProposal(proposalItemId);
      } else {
        await api.dismissConversationProposal(proposalItemId);
      }
      await syncActiveSessionDetail();
      setStatus(successText);
      setError('');
    } catch (proposalError) {
      setError(proposalError instanceof Error ? proposalError.message : '处理建议失败');
    } finally {
      setActionBusyId('');
    }
  }

  function renderAskActionCard(action: ConversationActionRecord) {
    return (
      <div key={action.id} className="message__action-card message__action-card--ask">
        <div className="message__action-header">
          <span className="message__action-icon">{getActionIcon(action)}</span>
          <strong>{action.title}</strong>
        </div>
        {action.summary && <p className="message__action-text">{action.summary}</p>}
        <div className="message__action-meta">AI 识别到可执行动作，当前设置是先问你。</div>
        <div className="message__actions">
          <button
            className="msg-action-btn"
            disabled={actionBusyId === action.id}
            onClick={() => void handleConversationAction(action.id, 'confirm', '已按你的确认执行这条动作。')}
          >
            允许执行
          </button>
          <button
            className="msg-action-btn"
            disabled={actionBusyId === action.id}
            onClick={() => void handleConversationAction(action.id, 'dismiss', '已忽略这条动作。')}
          >
            先不做
          </button>
        </div>
      </div>
    );
  }

  function renderNotifyActionCard(action: ConversationActionRecord) {
    const canUndo = action.status === 'completed' && Object.keys(action.undo_payload ?? {}).length > 0;
    return (
      <div key={action.id} className="message__action-card message__action-card--notify">
        <div className="message__action-header">
          <span className="message__action-icon">{getActionIcon(action)}</span>
          <strong>{action.title}</strong>
        </div>
        {action.summary && <p className="message__action-text">{action.summary}</p>}
        <div className="message__action-meta">{buildActionResultText(action)}</div>
        {canUndo && (
          <div className="message__actions">
            <button
              className="msg-action-btn"
              disabled={actionBusyId === action.id}
              onClick={() => void handleConversationAction(action.id, 'undo', '已撤回刚才这条动作。')}
            >
              撤回
            </button>
          </div>
        )}
      </div>
    );
  }

  function renderAskProposalCard(item: ConversationProposalItem) {
    const scheduledPayload = parseScheduledTaskProposalPayload(item);
    if (scheduledPayload && latestScheduledProposalIds.get(scheduledPayload.draft_id) !== item.id) {
      return null;
    }
    return (
      <div key={item.id} className={`message__action-card message__action-card--ask ${item.proposal_kind === 'scheduled_task_create' ? 'message__proposal-card--scheduled' : ''}`}>
        <div className="message__action-header">
          <span className="message__action-icon">{getProposalIcon(item)}</span>
          <strong>{item.title}</strong>
        </div>
        {item.summary && <p className="message__action-text">{item.summary}</p>}
        {scheduledPayload ? (
          <div className="message__proposal-body">
            <div className="message__proposal-summary">{scheduledPayload.intent_summary}</div>
            <div className="message__proposal-chips">
              {scheduledPayload.schedule_summary ? <span className="message__proposal-chip">{scheduledPayload.schedule_summary}</span> : null}
              {scheduledPayload.owner_summary ? <span className="message__proposal-chip">{scheduledPayload.owner_summary}</span> : null}
              {scheduledPayload.target_summary ? <span className="message__proposal-chip">{scheduledPayload.target_summary}</span> : null}
            </div>
            {scheduledPayload.missing_field_labels.length > 0 ? (
              <div className="message__proposal-warning">
                还缺：{scheduledPayload.missing_field_labels.join('、')}
              </div>
            ) : null}
            {!scheduledPayload.can_confirm && scheduledPayload.confirm_block_reason ? (
              <div className="message__proposal-hint">{scheduledPayload.confirm_block_reason}</div>
            ) : null}
          </div>
        ) : null}
        <div className="message__action-meta">{getProposalMetaText(item)}</div>
        <div className="message__actions">
          <button
            className="msg-action-btn"
            disabled={actionBusyId === item.id || Boolean(scheduledPayload && !scheduledPayload.can_confirm)}
            onClick={() => void handleConversationProposal(item.id, 'confirm', item.proposal_kind === 'scheduled_task_create' ? '已按你的确认创建这条计划任务。' : '已按你的确认应用这条建议。')}
          >
            {getProposalPrimaryActionText(item)}
          </button>
          <button
            className="msg-action-btn"
            disabled={actionBusyId === item.id}
            onClick={() => void handleConversationProposal(item.id, 'dismiss', item.proposal_kind === 'scheduled_task_create' ? '已忽略这条计划任务提案。' : '已忽略这条建议。')}
          >
            {getProposalDismissText(item)}
          </button>
        </div>
      </div>
    );
  }

  function renderCompletedProposalCard(item: ConversationProposalItem) {
    const toneClass = item.policy_category === 'auto' ? 'message__action-card--auto' : 'message__action-card--notify';
    const scheduledPayload = parseScheduledTaskProposalPayload(item);
    if (scheduledPayload && latestScheduledProposalIds.get(scheduledPayload.draft_id) !== item.id) {
      return null;
    }
    return (
      <div key={item.id} className={`message__action-card ${toneClass} ${item.proposal_kind === 'scheduled_task_create' ? 'message__proposal-card--scheduled' : ''}`}>
        <div className="message__action-header">
          <span className="message__action-icon">{getProposalIcon(item)}</span>
          <strong>{item.title}</strong>
        </div>
        {item.summary && <p className="message__action-text">{item.summary}</p>}
        {scheduledPayload ? (
          <div className="message__proposal-body">
            <div className="message__proposal-summary">{scheduledPayload.intent_summary}</div>
            <div className="message__proposal-chips">
              {scheduledPayload.schedule_summary ? <span className="message__proposal-chip">{scheduledPayload.schedule_summary}</span> : null}
              {scheduledPayload.owner_summary ? <span className="message__proposal-chip">{scheduledPayload.owner_summary}</span> : null}
              {scheduledPayload.target_summary ? <span className="message__proposal-chip">{scheduledPayload.target_summary}</span> : null}
            </div>
          </div>
        ) : null}
        <div className="message__action-meta">{getProposalMetaText(item)}</div>
      </div>
    );
  }

  function renderAutoActionGroup(messageId: string, actions: ConversationActionRecord[]) {
    const expanded = expandedAutoMessageId === messageId;
    return (
      <div className="message__action-card message__action-card--auto">
        <div className="message__action-icons">
          {actions.map(action => (
            <button
              key={action.id}
              type="button"
              className="message__action-icon-btn"
              onClick={() => setExpandedAutoMessageId(current => current === messageId ? '' : messageId)}
              title={action.title}
            >
              <span>{getActionIcon(action)}</span>
            </button>
          ))}
          <span className="message__action-meta">已自动执行 {actions.length} 条动作</span>
        </div>
        {expanded && (
          <div className="message__action-details">
            {actions.map(action => (
              <div key={action.id} className="message__action-detail-row">
                <div className="message__action-header">
                  <span className="message__action-icon">{getActionIcon(action)}</span>
                  <strong>{action.title}</strong>
                </div>
                {action.summary && <p className="message__action-text">{action.summary}</p>}
                <div className="message__action-meta">{buildActionResultText(action)}</div>
                {action.status === 'completed' && Object.keys(action.undo_payload ?? {}).length > 0 && (
                  <div className="message__actions">
                    <button
                      className="msg-action-btn"
                      disabled={actionBusyId === action.id}
                      onClick={() => void handleConversationAction(action.id, 'undo', '已撤回自动执行的动作。')}
                    >
                      撤回
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderMessageActions(message: ConversationMessage) {
    if (message.role !== 'assistant' || message.status === 'pending') return null;
    const messageActions = actionsByMessageId.get(message.id) ?? [];
    const messageProposals = message.request_id ? (proposalsByRequestId.get(message.request_id) ?? []) : [];
    const askActions = messageActions.filter(item => item.policy_mode === 'ask' && item.status === 'pending_confirmation');
    const notifyActions = messageActions.filter(item => item.policy_mode === 'notify');
    const autoActions = messageActions.filter(item => item.policy_mode === 'auto');
    const askProposals = messageProposals.filter(item => item.policy_category === 'ask' && item.status === 'pending_confirmation');
    const completedProposals = messageProposals.filter(item => item.status !== 'pending_confirmation');
    if (messageActions.length === 0 && messageProposals.length === 0) return null;
    return (
      <div className="message__action-cards">
        {askActions.map(renderAskActionCard)}
        {notifyActions.map(renderNotifyActionCard)}
        {autoActions.length > 0 && renderAutoActionGroup(message.id, autoActions)}
        {askProposals.map(renderAskProposalCard)}
        {completedProposals.map(renderCompletedProposalCard)}
      </div>
    );
  }

  if (!currentHouseholdId) {
    return (
      <div className="page page--assistant">
        <EmptyState icon="💬" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} />
      </div>
    );
  }

  if (!loading && conversationAgents.length === 0) {
    return (
      <div className="page page--assistant">
        <EmptyState
          icon="🤖"
          title={t('assistant.noAgents')}
          description={t('assistant.noAgentsHint')}
          action={
            <button className="btn btn--outline" type="button" onClick={() => navigate('/settings/ai')}>
              {t('settings.ai')}
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="page page--assistant">
      {/* 上下文弹出面板 */}
      {contextPanelOpen && <div className="assistant-panel-overlay" onClick={() => setContextPanelOpen(false)} />}
      <div className={`assistant-panel assistant-panel--right ${contextPanelOpen ? 'is-open' : ''}`}>
        <div className="assistant-panel__header">
          <h3>会话详情</h3>
          <button className="btn btn--icon btn--ghost p-sm" onClick={() => setContextPanelOpen(false)}>
            ✕
          </button>
        </div>
        <div className="assistant-panel__content">
          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.context')}</h4>
            <div className="context-item">
              <span className="context-item__label">{t('assistant.currentFamily')}</span>
              <span className="context-item__value">{currentHousehold?.name ?? '-'}</span>
            </div>
            <div className="context-item">
              <span className="context-item__label">{t('assistant.currentAgent')}</span>
              <span className="context-item__value">{selectedAgent ? `${selectedAgent.display_name} · ${getAgentStatusLabel(selectedAgent.status)}` : '-'}</span>
            </div>
            <div className="context-item">
              <span className="context-item__label">待确认动作</span>
              <span className="context-item__value">{pendingActionCount} 条</span>
            </div>
          </div>

          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.recentMemories')}</h4>
            <div className="context-memory-list">
              {recentFacts.length > 0 ? (
                recentFacts.map(item => (
                  <div key={`${item.type}-${item.label}`} className="context-memory-item">
                    <span>🧠</span> {item.label}
                  </div>
                ))
              ) : (
                suggestions.slice(0, 3).map(question => (
                  <div key={question} className="context-memory-item">
                    <span>💡</span> {question}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="context-section">
            <h4 className="context-section__title">最近动作</h4>
            <div className="context-memory-list">
              {recentActionRecords.length > 0 ? (
                recentActionRecords.map(action => (
                  <div key={action.id} className="context-memory-item context-memory-item--block">
                    <div><span>{getActionIcon(action)}</span> {action.title}</div>
                    <div className="context-memory-item__sub">{buildActionResultText(action)}</div>
                  </div>
                ))
              ) : (
                <div className="context-memory-item">
                  <span>🪶</span> 当前还没有 AI 动作
                </div>
              )}
            </div>
          </div>

          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.quickActions')}</h4>
            <div className="context-actions">
              {suggestions.slice(0, 3).map(question => (
                <button key={question} className="context-action-btn" onClick={() => { setContextPanelOpen(false); void submitQuestion(question); }}>
                  {question}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 主聊天区域 */}
      <div className="assistant-main">
        {/* PC 顶部工具栏 */}
        <div className="assistant-toolbar">
          <div className="assistant-toolbar__history-wrapper">
            <button className="assistant-toolbar__btn" onClick={() => setIsSidebarOpen(prev => !prev)} title="历史会话">
              <History size={18} />
              <span>历史</span>
            </button>
          </div>
          <div className="assistant-toolbar__title">{activeSessionDetail?.title || t('nav.assistant')}</div>
          {/* 右侧按钮组 */}
          <div className="assistant-toolbar__actions">
            <button className="assistant-toolbar__btn" onClick={() => void handleNewChat()} title="新对话">
              <MessageSquarePlus size={18} />
              <span>新建</span>
            </button>
            <button className="assistant-toolbar__btn" onClick={() => setContextPanelOpen(true)} title="会话详情">
              <Info size={18} />
              <span>详情</span>
            </button>
          </div>
        </div>

        {/* 移动端顶部栏 */}
        <div className="assistant-mobile-header">
          <button className="btn btn--icon btn--ghost p-sm assistant-menu-btn" onClick={() => setIsSidebarOpen(prev => !prev)}>
            <Menu size={24} />
          </button>
          <div className="assistant-mobile-title">{activeSessionDetail?.title || t('nav.assistant')}</div>
          <button className="btn btn--icon btn--ghost p-sm" onClick={() => void handleNewChat()} title="新对话">
            <MessageSquarePlus size={20} />
          </button>
          <button className="btn btn--icon btn--ghost p-sm" onClick={() => setContextPanelOpen(true)}>
            <Info size={20} />
          </button>
        </div>

        {/* 统一的会话历史气泡框 - PC/移动端共用 */}
        {isSidebarOpen && (
          <>
            <div className="assistant-popover-overlay" onClick={() => setIsSidebarOpen(false)} />
            <div className="assistant-popover">
              <div className="assistant-popover__header">
                <span>历史会话</span>
                <button className="btn btn--icon btn--ghost p-xs" onClick={() => void handleNewChat()} title="新对话">
                  <MessageSquarePlus size={16} />
                </button>
              </div>
              <div className="assistant-popover__content">
                {loading ? (
                  <div className="context-memory-item">
                    <span>⏳</span> 正在加载会话
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="context-memory-item">
                    <span>📝</span> 暂无历史会话
                  </div>
                ) : (
                  sessions.map(session => (
                    <div
                      key={session.id}
                      className={`session-item session-item--compact ${activeSessionId === session.id ? 'session-item--active' : ''}`}
                      onClick={() => {
                        setActiveSessionId(session.id);
                        setIsSidebarOpen(false);
                      }}
                    >
                      <div className="session-item__content">
                        <span className="session-item__title">{session.title}</span>
                        <span className="session-item__preview">{session.latest_message_preview ?? '等待你的第一条消息'}</span>
                      </div>
                      <span className="session-item__time">{formatRelativeTime(session.last_message_at)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        )}

        <div className="conversation-agent-banner">
          <div className="conversation-agent-banner__main">
            <div className="conversation-agent-banner__avatar">
              {selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : <Bot size={18} />}
            </div>
            <div className="conversation-agent-banner__text">
              <div className="conversation-agent-banner__title-row">
                <h2>{selectedAgent?.display_name ?? 'AI 助手'}</h2>
                {selectedAgent && <span className="ai-pill ai-pill--outline">{getAgentTypeLabel(selectedAgent.agent_type)}</span>}
              </div>
              <p>{selectedAgent?.summary ?? 'AI 管家，协助家庭日常事务。'}</p>
            </div>
          </div>
          <div className="conversation-agent-switcher">
            {conversationAgents.map(agent => (
              <button
                key={agent.id}
                type="button"
                className={`conversation-agent-switcher__item ${selectedAgentId === agent.id ? 'conversation-agent-switcher__item--active' : ''}`}
                onClick={() => void handleAgentSwitch(agent.id)}
              >
                <span>{getAgentTypeEmoji(agent.agent_type)}</span>
                <span>{agent.display_name}</span>
              </button>
            ))}
          </div>
        </div>

        {activeSessionId ? (
          <>
            <div ref={messagesContainerRef} className="assistant-main__messages">
              {(activeSessionDetail?.messages ?? []).length > 0 ? (
                activeSessionDetail!.messages.map(message => (
                  <div key={message.id} className={`message message--${message.role}`}>
                    <div className={`message__avatar ${message.role === 'assistant' ? 'message__avatar--assistant' : 'message__avatar--user'}`}>
                      {message.role === 'assistant' ? (
                        <span>{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : '🤖'}</span>
                      ) : (
                        <span>你</span>
                      )}
                    </div>
                    <div className="message__content-wrapper">
                      <div className="message__bubble">
                        <p className="message__content">{message.content || (message.status === 'pending' ? '正在准备回复...' : '')}</p>
                        {message.degraded && <span className="message__memory-tag">⚠️ 当前回答已降级</span>}
                        {message.status === 'streaming' && <span className="message__memory-tag">⏳ 正在生成</span>}
                        {message.status === 'failed' && <span className="message__memory-tag">❌ 本轮失败</span>}
                      </div>
                      {renderMessageActions(message)}
                      {message.role === 'assistant' && message.status !== 'pending' && (
                        <div className="message__actions">
                          <button className="msg-action-btn" onClick={() => void submitQuestion(`继续追问：${message.content.slice(0, 40)}`)}>
                            {t('assistant.askFollow')}
                          </button>
                          <button className="msg-action-btn" onClick={() => navigate('/family')}>去家庭页</button>
                          <button className="msg-action-btn" onClick={() => navigate('/settings/ai')}>去 AI 配置</button>
                          <button className="msg-action-btn" onClick={() => navigate('/memories')}>去记忆页</button>
                          {message.suggestions.slice(0, 2).map(suggestion => (
                            <button key={suggestion} className="msg-action-btn" onClick={() => void submitQuestion(suggestion)}>
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState icon="💬" title={t('assistant.welcome')} description={t('assistant.welcomeHint')} />
              )}
            </div>

            <div className="assistant-main__input">
              <form
                className="chat-composer"
                onSubmit={event => {
                  event.preventDefault();
                  void submitQuestion(inputValue);
                }}
              >
                <textarea
                  value={inputValue}
                  onChange={event => setInputValue(event.target.value)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' && !event.shiftKey && !sending) {
                      event.preventDefault();
                      void submitQuestion(inputValue);
                    }
                  }}
                  placeholder={t('assistant.inputPlaceholder')}
                  className="chat-composer__input form-input"
                  rows={2}
                />
                <div className="chat-composer__footer">
                  <span className="chat-composer__hint">Enter 发送，Shift + Enter 换行</span>
                  <button type="submit" className="btn btn--primary" disabled={sending || !inputValue.trim() || !realtimeReady}>
                    {sending ? '发送中...' : t('assistant.send')}
                  </button>
                </div>
              </form>
            </div>

            {(error || status) && (
              <div className="text-text-secondary" style={{ marginTop: '0.75rem' }}>
                {error || status}
              </div>
            )}
          </>
        ) : (
          <EmptyState
            icon="💬"
            title={t('assistant.noSessions')}
            description={t('assistant.noSessionsHint')}
            action={<button className="btn btn--primary" onClick={() => void handleNewChat()}>{t('assistant.newChat')}</button>}
          />
        )}
      </div>
    </div>
  );
}
