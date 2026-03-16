import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import { createBrowserRealtimeClient, newRealtimeRequestId, type BootstrapRealtimeEvent } from '@familyclaw/user-platform/web';
import { EmptyStateCard, PageHeader, userAppFoundationTokens } from '@familyclaw/user-ui';
import { Bot, ChevronDown, Construction, Info, Menu, MessageSquarePlus } from 'lucide-react';
import { assistantApi } from './assistant.api';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel, isConversationAgent, pickDefaultConversationAgent } from './assistant.agents';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type {
  AgentSummary,
  ConversationActionRecord,
  ConversationMessage,
  ConversationProposalItem,
  ConversationSession,
  ConversationSessionDetail,
  ScheduledTaskConversationProposalPayload,
} from './assistant.types';
import { GuardedPage, useAuthContext, useHouseholdContext, useI18n, useSetupContext, useTheme } from '../../runtime';
import './index.h5.scss';

type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

type ConversationRealtimeClient = ReturnType<typeof createConversationRealtimeClient>;

function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  return <EmptyStateCard className={`empty-state ${className}`.trim()} icon={icon} title={title} description={description ?? ''} action={action} />;
}

function createConversationRealtimeClient(options: {
  householdId: string;
  sessionId: string;
  onEvent: (event: BootstrapRealtimeEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: () => void;
}) {
  return createBrowserRealtimeClient({
    ...options,
    channel: 'conversation',
    baseUrl: '/api/v1',
    origin: window.location.origin,
  });
}

function formatRelativeTime(value: string, locale: string) {
  const lowerLocale = locale.toLowerCase();
  const normalizedLocale = lowerLocale.startsWith('en') ? 'en-US' : lowerLocale.startsWith('zh-tw') ? 'zh-TW' : 'zh-CN';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return getPageMessage(locale, 'assistant.time.justNow');
  }
  const diffMinutes = Math.max(1, Math.floor((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return getPageMessage(locale, 'assistant.time.minutesAgo', { count: diffMinutes });
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return getPageMessage(locale, 'assistant.time.hoursAgo', { count: diffHours });
  }
  return date.toLocaleDateString(normalizedLocale);
}

function formatLocalizedList(items: string[], locale: string) {
  const normalizedLocale = locale.toLowerCase().startsWith('en') ? 'en-US' : locale.toLowerCase().startsWith('zh-tw') ? 'zh-TW' : 'zh-CN';
  if (typeof Intl.ListFormat === 'function') {
    return new Intl.ListFormat(normalizedLocale, { style: 'long', type: 'conjunction' }).format(items);
  }
  const separator = getPageMessage(locale, 'assistant.separator.list');
  return items.reduce((result, item, index) => {
    if (index === 0) return item;
    return `${result}${separator}${item}`;
  }, '');
}

function buildFactIdentity(item: ConversationMessage['facts'][number]) {
  return [
    item.type,
    item.label,
    item.source,
    item.occurred_at ?? '',
    item.visibility,
    item.inferred ? '1' : '0',
  ].join('::');
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

function getActionStatusText(action: ConversationActionRecord, locale: string) {
  if (action.status === 'pending_confirmation') return getPageMessage(locale, 'assistant.action.status.pendingConfirmation');
  if (action.status === 'completed') return getPageMessage(locale, 'assistant.action.status.completed');
  if (action.status === 'dismissed') return getPageMessage(locale, 'assistant.action.status.dismissed');
  if (action.status === 'undone') return getPageMessage(locale, 'assistant.action.status.undone');
  if (action.status === 'undo_failed') return getPageMessage(locale, 'assistant.action.status.undoFailed');
  return getPageMessage(locale, 'assistant.action.status.failed');
}

function buildActionResultText(action: ConversationActionRecord, locale: string) {
  if (action.status === 'completed' && action.action_name === 'memory.write') return getPageMessage(locale, 'assistant.action.result.savedToMemory');
  if (action.status === 'completed' && action.action_name === 'config.apply') return getPageMessage(locale, 'assistant.action.result.configApplied');
  if (action.status === 'completed' && action.action_name === 'reminder.create') return getPageMessage(locale, 'assistant.action.result.reminderCreated');
  if (action.status === 'undone') return getPageMessage(locale, 'assistant.action.result.undone');
  if (action.status === 'dismissed') return getPageMessage(locale, 'assistant.action.result.dismissed');
  const error = action.result_payload?.error;
  return typeof error === 'string' && error ? error : getActionStatusText(action, locale);
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

function getProposalStatusText(item: ConversationProposalItem, locale: string) {
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_create') return getPageMessage(locale, 'assistant.proposal.status.taskCreated');
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_update') return getPageMessage(locale, 'assistant.proposal.status.taskUpdated');
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_pause') return getPageMessage(locale, 'assistant.proposal.status.taskPaused');
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_resume') return getPageMessage(locale, 'assistant.proposal.status.taskResumed');
  if (item.status === 'completed' && item.proposal_kind === 'scheduled_task_delete') return getPageMessage(locale, 'assistant.proposal.status.taskDeleted');
  if (item.status === 'pending_confirmation') return getPageMessage(locale, 'assistant.proposal.status.pendingConfirmation');
  if (item.status === 'completed' && item.proposal_kind === 'config_apply') return getPageMessage(locale, 'assistant.proposal.status.configApplied');
  if (item.status === 'completed' && item.proposal_kind === 'memory_write') return getPageMessage(locale, 'assistant.proposal.status.memorySaved');
  if (item.status === 'completed' && item.proposal_kind === 'reminder_create') return getPageMessage(locale, 'assistant.proposal.status.reminderCreated');
  if (item.status === 'dismissed' || item.status === 'ignored') return getPageMessage(locale, 'assistant.proposal.status.dismissed');
  if (item.status === 'failed') return getPageMessage(locale, 'assistant.proposal.status.failed');
  return getPageMessage(locale, 'assistant.proposal.status.generated');
}

function getProposalPrimaryActionText(item: ConversationProposalItem, locale: string) {
  if (item.proposal_kind === 'scheduled_task_create') return getPageMessage(locale, 'assistant.proposal.primary.create');
  if (item.proposal_kind === 'scheduled_task_update') return getPageMessage(locale, 'assistant.proposal.primary.update');
  if (item.proposal_kind === 'scheduled_task_pause') return getPageMessage(locale, 'assistant.proposal.primary.pause');
  if (item.proposal_kind === 'scheduled_task_resume') return getPageMessage(locale, 'assistant.proposal.primary.resume');
  if (item.proposal_kind === 'scheduled_task_delete') return getPageMessage(locale, 'assistant.proposal.primary.delete');
  return getPageMessage(locale, 'assistant.proposal.primary.apply');
}

function getProposalDismissText(item: ConversationProposalItem, locale: string) {
  if (item.proposal_kind === 'scheduled_task_create') return getPageMessage(locale, 'assistant.proposal.dismiss.notNow');
  if (item.proposal_kind.startsWith('scheduled_task_')) return getPageMessage(locale, 'assistant.proposal.dismiss.skipForNow');
  return getPageMessage(locale, 'assistant.proposal.dismiss.keepAsIs');
}

function getProposalMetaText(item: ConversationProposalItem, locale: string) {
  if (item.proposal_kind.startsWith('scheduled_task_')) {
    return item.status === 'pending_confirmation'
      ? getPageMessage(locale, 'assistant.proposal.meta.taskPending')
      : getProposalStatusText(item, locale);
  }
  return item.status === 'pending_confirmation'
    ? getPageMessage(locale, 'assistant.proposal.meta.actionPending')
    : getProposalStatusText(item, locale);
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

async function goToPage(url: string) {
  await Taro.navigateTo({ url }).catch(() => undefined);
}

function AssistantPageContent() {
  const { actor } = useAuthContext();
  const { setupStatus } = useSetupContext();
  const { currentHouseholdId, currentHousehold } = useHouseholdContext();
  const { t, locale } = useI18n();
  const { themeId } = useTheme();
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [activeSessionDetail, setActiveSessionDetail] = useState<ConversationSessionDetail | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [realtimeReady, setRealtimeReady] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [actionBusyId, setActionBusyId] = useState('');
  const [expandedAutoMessageId, setExpandedAutoMessageId] = useState('');
  const [activeChatTab, setActiveChatTab] = useState<'personal' | 'public' | 'moments'>('personal');
  const realtimeClientRef = useRef<ConversationRealtimeClient | null>(null);
  const pendingSyncTimerRef = useRef<number | null>(null);
  const sendingRef = useRef(false);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const listBullet = '•';

  const conversationAgents = useMemo(() => agents.filter(isConversationAgent), [agents]);
  const defaultAgent = useMemo(() => pickDefaultConversationAgent(agents), [agents]);
  const selectedAgent = useMemo(
    () => agents.find(item => item.id === selectedAgentId) ?? defaultAgent,
    [agents, defaultAgent, selectedAgentId],
  );
  const canSwitchAgent = conversationAgents.length > 1;
  const recentFacts = useMemo(() => {
    const uniqueFacts: ConversationMessage['facts'] = [];
    const seen = new Set<string>();

    for (const message of activeSessionDetail?.messages ?? []) {
      if (message.role !== 'assistant') continue;
      for (const fact of message.facts) {
        const identity = buildFactIdentity(fact);
        if (seen.has(identity)) continue;
        seen.add(identity);
        uniqueFacts.push(fact);
        if (uniqueFacts.length >= 3) {
          return uniqueFacts;
        }
      }
    }

    return uniqueFacts;
  }, [activeSessionDetail]);
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
    void Taro.setNavigationBarTitle({ title: t('nav.assistant') }).catch(() => undefined);
  }, [t, locale]);

  useEffect(() => {
    setError('');
    /*
        
          setError(loadError instanceof Error ? loadError.message : t('assistant.error.loadConversations'));
    */
  }, []);

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  useEffect(() => {
    setIsSidebarOpen(false);
    setContextPanelOpen(false);
  }, [actor?.authenticated, currentHouseholdId, locale, setupStatus?.is_required, themeId]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [activeSessionDetail?.messages, activeSessionDetail?.action_records]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setAgents([]);
      setSessions([]);
      setActiveSessionId('');
      setActiveSessionDetail(null);
      setSelectedAgentId('');
      setSuggestions([]);
      setStatus('');
      setLoading(false);
      return;
    }

    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError('');
      setStatus('');
      setSessions([]);
      setActiveSessionId('');
      setActiveSessionDetail(null);
      setSuggestions([]);
      setSelectedAgentId('');
      try {
        const [agentResult, sessionResult] = await Promise.all([
          assistantApi.listAgents(currentHouseholdId),
          assistantApi.listConversationSessions({ household_id: currentHouseholdId, limit: 50 }),
        ]);
        if (cancelled) return;
        setAgents(agentResult.items);
        setSessions(sessionResult.items);
        setActiveSessionId(sessionResult.items[0]?.id || '');
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : t('assistant.error.loadConversations'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
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
    void assistantApi.getConversationSession(activeSessionId)
      .then(detail => {
        if (cancelled) return;
        setActiveSessionDetail(detail);
        setSessions(current => upsertSession(current, detail));
      })
      .catch(detailError => {
        if (!cancelled) {
          setError(detailError instanceof Error ? detailError.message : t('assistant.error.loadConversationDetails'));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  async function syncActiveSessionDetail(sessionId?: string) {
    const targetSessionId = sessionId ?? activeSessionId;
    if (!targetSessionId) return;
    try {
      const detail = await assistantApi.getConversationSession(targetSessionId);
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
          setError(t('assistant.error.connectionClosed'));
        }
      },
      onError: () => {
        setRealtimeReady(false);
        if (sendingRef.current) {
          void syncActiveSessionDetail(activeSessionId);
          setSending(false);
        }
        setError(t('assistant.error.connectionFailed'));
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
    void assistantApi.getFamilyQaSuggestions(currentHouseholdId, undefined, selectedAgentId || undefined)
      .then(result => setSuggestions(result.items.map(item => item.question)))
      .catch(() => undefined);
  }, [currentHouseholdId, selectedAgentId]);

  async function refreshSessions(preferredSessionId?: string) {
    if (!currentHouseholdId) return;
    const result = await assistantApi.listConversationSessions({ household_id: currentHouseholdId, limit: 50 });
    setSessions(result.items);
    if (preferredSessionId) {
      setActiveSessionId(preferredSessionId);
    }
  }

  async function ensureSession() {
    if (activeSessionDetail) return activeSessionDetail;
    if (!currentHouseholdId) throw new Error(t('assistant.error.noHouseholdSelected'));
    const created = await assistantApi.createConversationSession({
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
    const created = await assistantApi.createConversationSession({
      household_id: currentHouseholdId,
      active_agent_id: selectedAgent?.id ?? undefined,
    });
    setSessions(current => upsertSession(current, created));
    setActiveSessionId(created.id);
    setActiveSessionDetail(created);
  }

  async function handleAgentSwitch(agentId: string) {
    if (!agentId || agentId === selectedAgent?.id) return;
    setSelectedAgentId(agentId);
    if (!activeSessionDetail || activeSessionDetail.messages.length === 0) return;
    const nextAgent = conversationAgents.find(item => item.id === agentId);
    if (!nextAgent) return;
    setStatus(t('assistant.status.switchedAgent', { name: nextAgent.display_name }));
    await handleNewChat();
  }

  function handleAgentAvatarClick() {
    if (!canSwitchAgent || conversationAgents.length === 0) return;
    const currentAgentId = selectedAgent?.id ?? selectedAgentId;
    const currentIndex = conversationAgents.findIndex(agent => agent.id === currentAgentId);
    const nextAgent = conversationAgents[(currentIndex + 1 + conversationAgents.length) % conversationAgents.length];
    if (!nextAgent || nextAgent.id === currentAgentId) return;
    void handleAgentSwitch(nextAgent.id);
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
        throw new Error(t('assistant.error.realtimeNotReady'));
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
      setError(submitError instanceof Error ? submitError.message : t('assistant.error.submitFailed'));
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
        await assistantApi.confirmConversationAction(actionId);
      } else if (actionType === 'dismiss') {
        await assistantApi.dismissConversationAction(actionId);
      } else {
        await assistantApi.undoConversationAction(actionId);
      }
      await syncActiveSessionDetail();
      setStatus(successText);
      setError('');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t('assistant.error.actionFailed'));
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
        await assistantApi.confirmConversationProposal(proposalItemId);
      } else {
        await assistantApi.dismissConversationProposal(proposalItemId);
      }
      await syncActiveSessionDetail();
      setStatus(successText);
      setError('');
    } catch (proposalError) {
      setError(proposalError instanceof Error ? proposalError.message : t('assistant.error.proposalFailed'));
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
        {action.summary ? <p className="message__action-text">{action.summary}</p> : null}
        <div className="message__action-meta">{t('assistant.action.askHint')}</div>
        <div className="message__actions">
          <button
            className="msg-action-btn"
            disabled={actionBusyId === action.id}
            onClick={() => void handleConversationAction(action.id, 'confirm', t('assistant.action.confirmSuccess'))}
          >
            {t('assistant.action.allow')}
          </button>
          <button
            className="msg-action-btn"
            disabled={actionBusyId === action.id}
            onClick={() => void handleConversationAction(action.id, 'dismiss', t('assistant.action.dismissSuccess'))}
          >
            {t('assistant.action.notNow')}
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
        {action.summary ? <p className="message__action-text">{action.summary}</p> : null}
        <div className="message__action-meta">{buildActionResultText(action, locale)}</div>
        {canUndo ? (
          <div className="message__actions">
            <button
              className="msg-action-btn"
              disabled={actionBusyId === action.id}
              onClick={() => void handleConversationAction(action.id, 'undo', t('assistant.action.undoLastSuccess'))}
            >
              {t('assistant.action.undo')}
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  function renderAskProposalCard(item: ConversationProposalItem) {
    const scheduledPayload = parseScheduledTaskProposalPayload(item);
    if (scheduledPayload && latestScheduledProposalIds.get(scheduledPayload.draft_id) !== item.id) {
      return null;
    }
    return (
      <div
        key={item.id}
        className={`message__action-card message__action-card--ask ${item.proposal_kind === 'scheduled_task_create' ? 'message__proposal-card--scheduled' : ''}`.trim()}
      >
        <div className="message__action-header">
          <span className="message__action-icon">{getProposalIcon(item)}</span>
          <strong>{item.title}</strong>
        </div>
        {item.summary ? <p className="message__action-text">{item.summary}</p> : null}
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
                {t('assistant.proposal.missingFields', {
                  fields: formatLocalizedList(scheduledPayload.missing_field_labels, locale),
                })}
              </div>
            ) : null}
            {!scheduledPayload.can_confirm && scheduledPayload.confirm_block_reason ? (
              <div className="message__proposal-hint">{scheduledPayload.confirm_block_reason}</div>
            ) : null}
          </div>
        ) : null}
        <div className="message__action-meta">{getProposalMetaText(item, locale)}</div>
        <div className="message__actions">
          <button
            className="msg-action-btn"
            disabled={actionBusyId === item.id || Boolean(scheduledPayload && !scheduledPayload.can_confirm)}
            onClick={() => void handleConversationProposal(item.id, 'confirm', item.proposal_kind === 'scheduled_task_create'
              ? t('assistant.proposal.confirmTaskSuccess')
              : t('assistant.proposal.confirmSuggestionSuccess'))}
          >
            {getProposalPrimaryActionText(item, locale)}
          </button>
          <button
            className="msg-action-btn"
            disabled={actionBusyId === item.id}
            onClick={() => void handleConversationProposal(item.id, 'dismiss', item.proposal_kind === 'scheduled_task_create'
              ? t('assistant.proposal.dismissTaskSuccess')
              : t('assistant.proposal.dismissSuggestionSuccess'))}
          >
            {getProposalDismissText(item, locale)}
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
      <div
        key={item.id}
        className={`message__action-card ${toneClass} ${item.proposal_kind === 'scheduled_task_create' ? 'message__proposal-card--scheduled' : ''}`.trim()}
      >
        <div className="message__action-header">
          <span className="message__action-icon">{getProposalIcon(item)}</span>
          <strong>{item.title}</strong>
        </div>
        {item.summary ? <p className="message__action-text">{item.summary}</p> : null}
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
        <div className="message__action-meta">{getProposalMetaText(item, locale)}</div>
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
          <span className="message__action-meta">{t('assistant.action.autoExecuted', { count: actions.length })}</span>
        </div>
        {expanded ? (
          <div className="message__action-details">
            {actions.map(action => (
              <div key={action.id} className="message__action-detail-row">
                <div className="message__action-header">
                  <span className="message__action-icon">{getActionIcon(action)}</span>
                  <strong>{action.title}</strong>
                </div>
                {action.summary ? <p className="message__action-text">{action.summary}</p> : null}
                <div className="message__action-meta">{buildActionResultText(action, locale)}</div>
                {action.status === 'completed' && Object.keys(action.undo_payload ?? {}).length > 0 ? (
                  <div className="message__actions">
                    <button
                      className="msg-action-btn"
                      disabled={actionBusyId === action.id}
                      onClick={() => void handleConversationAction(action.id, 'undo', t('assistant.action.undoAutoSuccess'))}
                    >
                      {t('assistant.action.undo')}
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
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
        {autoActions.length > 0 ? renderAutoActionGroup(message.id, autoActions) : null}
        {askProposals.map(renderAskProposalCard)}
        {completedProposals.map(renderCompletedProposalCard)}
      </div>
    );
  }

  if (!currentHouseholdId && !loading) {
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
          action={(
            <button className="btn btn--outline" type="button" onClick={() => void goToPage('/pages/settings/index')}>
              {t('settings.ai')}
            </button>
          )}
        />
      </div>
    );
  }

  const chatTabs = [
    { key: 'personal' as const, labelKey: 'assistant.tab.personal', available: true },
    { key: 'public' as const, labelKey: 'assistant.tab.public', available: false },
    { key: 'moments' as const, labelKey: 'assistant.tab.moments', available: false },
  ];

  function renderComingSoonTab() {
    return (
      <div className="assistant-coming-soon">
        <EmptyStateCard
          icon={<Construction size={48} className="text-text-tertiary" />}
          title={t('assistant.tab.comingSoonTitle')}
          description={t('assistant.tab.comingSoonDesc')}
        />
      </div>
    );
  }

  return (
    <div className="page page--assistant">
      <PageHeader title={t('nav.assistant')} />

      <div className="memory-main-tabs">
        {chatTabs.map(tab => (
          <button
            key={tab.key}
            type="button"
            className={`memory-main-tab ${activeChatTab === tab.key ? 'memory-main-tab--active' : ''}`}
            onClick={() => setActiveChatTab(tab.key)}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {activeChatTab !== 'personal' ? renderComingSoonTab() : (
        <>
      {contextPanelOpen ? <div className="assistant-panel-overlay" onClick={() => setContextPanelOpen(false)} /> : null}
      <div className={`assistant-panel assistant-panel--right ${contextPanelOpen ? 'is-open' : ''}`.trim()}>
        <div className="assistant-panel__header">
          <h3>{t('assistant.panel.details')}</h3>
          <button className="btn btn--icon btn--ghost p-sm" onClick={() => setContextPanelOpen(false)}>
            ✕
          </button>
        </div>
        <div className="assistant-panel__content">
          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.context')}</h4>
            <div className="context-item">
              <span className="context-item__label">{t('assistant.currentFamily')}</span>
              <span className="context-item__value">{currentHousehold?.name ?? t('assistant.unavailable')}</span>
            </div>
            <div className="context-item">
              <span className="context-item__label">{t('assistant.currentAgent')}</span>
              <span className="context-item__value">
                {selectedAgent
                  ? t('assistant.panel.currentAgentValue', {
                    name: selectedAgent.display_name,
                    status: getAgentStatusLabel(selectedAgent.status, locale),
                  })
                  : t('assistant.unavailable')}
              </span>
            </div>
            <div className="context-item">
              <span className="context-item__label">{t('assistant.panel.pendingActions')}</span>
              <span className="context-item__value">{t('assistant.panel.pendingActionsCount', { count: pendingActionCount })}</span>
            </div>
          </div>

          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.recentMemories')}</h4>
            <div className="context-memory-list">
              {recentFacts.length > 0 ? (
                recentFacts.map(item => (
                  <div key={buildFactIdentity(item)} className="context-memory-item">
                    <span>{listBullet}</span> {item.label}
                  </div>
                ))
              ) : (
                suggestions.slice(0, 3).map(question => (
                  <div key={question} className="context-memory-item">
                    <span>{listBullet}</span> {question}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="context-section">
            <h4 className="context-section__title">{t('assistant.panel.recentActions')}</h4>
            <div className="context-memory-list">
              {recentActionRecords.length > 0 ? (
                recentActionRecords.map(action => (
                  <div key={action.id} className="context-memory-item context-memory-item--block">
                    <div><span>{getActionIcon(action)}</span> {action.title}</div>
                    <div className="context-memory-item__sub">{buildActionResultText(action, locale)}</div>
                  </div>
                ))
              ) : (
                <div className="context-memory-item">
                  <span>{listBullet}</span> {t('assistant.panel.noActions')}
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

      <div className="assistant-main">
        {/* PC端合并后的标题栏：左边Agent信息、中间会话标题（点击弹出会话列表）、右侧操作按钮 */}
        <div className="assistant-toolbar">
          <div className="assistant-toolbar__agent">
            <button
              type="button"
              className={`assistant-toolbar__avatar ${canSwitchAgent ? 'assistant-toolbar__avatar--switchable' : ''}`.trim()}
              onClick={handleAgentAvatarClick}
              disabled={!canSwitchAgent}
              title={canSwitchAgent
                ? t('assistant.agent.switchTitle')
                : (selectedAgent?.display_name ?? t('assistant.agent.currentTitle'))}
            >
              {selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : <Bot size={18} />}
            </button>
            <div className="assistant-toolbar__agent-info">
              <span className="assistant-toolbar__agent-name">{selectedAgent?.display_name ?? t('assistant.agent.defaultName')}</span>
              {selectedAgent ? <span className="ai-pill ai-pill--outline">{getAgentTypeLabel(selectedAgent.agent_type, locale)}</span> : null}
            </div>
          </div>

          <button
            type="button"
            className="assistant-toolbar__session-title"
            onClick={() => setIsSidebarOpen(prev => !prev)}
            title={t('assistant.sessionList')}
          >
            <span className="assistant-toolbar__title-text">{activeSessionDetail?.title || t('nav.assistant')}</span>
            <ChevronDown size={16} className={`assistant-toolbar__chevron ${isSidebarOpen ? 'assistant-toolbar__chevron--open' : ''}`} />
          </button>

          <div className="assistant-toolbar__actions">
            <button className="assistant-toolbar__btn" onClick={() => void handleNewChat()} title={t('assistant.newChat')}>
              <MessageSquarePlus size={18} />
              <span>{t('assistant.newChat')}</span>
            </button>
            <button className="assistant-toolbar__btn" onClick={() => setContextPanelOpen(true)} title={t('assistant.panel.details')}>
              <Info size={18} />
              <span>{t('assistant.panel.details')}</span>
            </button>
          </div>
        </div>

        {/* 移动端合并后的标题栏 */}
        <div className="assistant-mobile-header">
          <div className="assistant-mobile-header__agent">
            <button
              type="button"
              className={`assistant-toolbar__avatar assistant-toolbar__avatar--sm ${canSwitchAgent ? 'assistant-toolbar__avatar--switchable' : ''}`.trim()}
              onClick={handleAgentAvatarClick}
              disabled={!canSwitchAgent}
            >
              {selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : <Bot size={16} />}
            </button>
            <span className="assistant-mobile-header__agent-name">{selectedAgent?.display_name ?? t('assistant.agent.defaultName')}</span>
          </div>

          <button
            type="button"
            className="assistant-mobile-header__session"
            onClick={() => setIsSidebarOpen(prev => !prev)}
          >
            <span className="assistant-mobile-title">{activeSessionDetail?.title || t('nav.assistant')}</span>
            <ChevronDown size={14} className={`assistant-toolbar__chevron ${isSidebarOpen ? 'assistant-toolbar__chevron--open' : ''}`} />
          </button>

          <div className="assistant-mobile-header__actions">
            <button className="btn btn--icon btn--ghost p-sm" onClick={() => void handleNewChat()} title={t('assistant.newChat')}>
              <MessageSquarePlus size={20} />
            </button>
            <button className="btn btn--icon btn--ghost p-sm" onClick={() => setContextPanelOpen(true)} title={t('assistant.panel.details')}>
              <Info size={20} />
            </button>
          </div>
        </div>

        {isSidebarOpen ? (
          <>
            <div className="assistant-popover-overlay" onClick={() => setIsSidebarOpen(false)} />
            <div className="assistant-popover">
              <div className="assistant-popover__header">
                <span>{t('nav.assistant')}</span>
                <button className="btn btn--icon btn--ghost p-xs" onClick={() => void handleNewChat()} title={t('assistant.newChat')}>
                  <MessageSquarePlus size={16} />
                </button>
              </div>
              <div className="assistant-popover__content">
                {loading ? (
                  <div className="context-memory-item">
                    <span>⏳</span> {t('assistant.error.loadConversations')}
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="context-memory-item">
                    <span>📝</span> {t('assistant.noSessions')}
                  </div>
                ) : (
                  sessions.map(session => (
                    <div
                      key={session.id}
                      className={`session-item session-item--compact ${activeSessionId === session.id ? 'session-item--active' : ''}`.trim()}
                      onClick={() => {
                        setActiveSessionId(session.id);
                        setIsSidebarOpen(false);
                      }}
                    >
                      <div className="session-item__content">
                        <span className="session-item__title">{session.title}</span>
                        <span className="session-item__preview">{session.latest_message_preview ?? t('assistant.welcomeHint')}</span>
                      </div>
                      <span className="session-item__time">{formatRelativeTime(session.last_message_at, locale)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        ) : null}

        {activeSessionId ? (
          <>
            <div ref={messagesContainerRef} className="assistant-main__messages">
              {(activeSessionDetail?.messages ?? []).length > 0 ? (
                (activeSessionDetail?.messages ?? []).map(message => (
                  <div key={message.id} className={`message message--${message.role}`.trim()}>
                    <div className={`message__avatar ${message.role === 'assistant' ? 'message__avatar--assistant' : 'message__avatar--user'}`.trim()}>
                      {message.role === 'assistant' ? (
                        <span>{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : '🤖'}</span>
                      ) : (
                        <span>{t('assistant.you')}</span>
                      )}
                    </div>
                    <div className="message__content-wrapper">
                      <div className="message__bubble">
                        <p className="message__content">{message.content || (message.status === 'pending' ? t('assistant.message.preparingReply') : '')}</p>
                        {message.degraded ? <span className="message__memory-tag">⚠️ {t('assistant.message.responseDegraded')}</span> : null}
                        {message.status === 'streaming' ? <span className="message__memory-tag">⏳ {t('assistant.message.generating')}</span> : null}
                        {message.status === 'failed' ? <span className="message__memory-tag">❌ {t('assistant.message.turnFailed')}</span> : null}
                      </div>
                      {renderMessageActions(message)}
                      {message.role === 'assistant' && message.status !== 'pending' ? (
                        <div className="message__actions">
                          <button
                            className="msg-action-btn"
                            onClick={() => void submitQuestion(t('assistant.message.followUpQuestion', { content: message.content.slice(0, 40) }))}
                          >
                            {t('assistant.askFollow')}
                          </button>
                          <button className="msg-action-btn" onClick={() => void goToPage('/pages/family/index')}>{t('nav.family')}</button>
                          <button className="msg-action-btn" onClick={() => void goToPage('/pages/settings/index')}>{t('settings.ai')}</button>
                          <button className="msg-action-btn" onClick={() => void goToPage('/pages/memories/index')}>{t('nav.memories')}</button>
                          {message.suggestions.slice(0, 2).map(suggestion => (
                            <button key={suggestion} className="msg-action-btn" onClick={() => void submitQuestion(suggestion)}>
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon="💬"
                  title={t('assistant.welcome')}
                  description={t('assistant.welcomeHint')}
                />
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
                  <span className="chat-composer__hint">{t('assistant.composer.hint')}</span>
                  <button type="submit" className="btn btn--primary" disabled={sending || !inputValue.trim() || !realtimeReady}>
                    {sending ? t('assistant.sending') : t('assistant.send')}
                  </button>
                </div>
              </form>
            </div>

            {error || status ? (
              <div className="text-text-secondary" style={{ marginTop: userAppFoundationTokens.spacing.sm }}>
                {error || status}
              </div>
            ) : null}
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
        </>
      )}
    </div>
  );
}

export default function AssistantPageH5() {
  return (
    <GuardedPage mode="protected" path="/pages/assistant/index">
      <AssistantPageContent />
    </GuardedPage>
  );
}
