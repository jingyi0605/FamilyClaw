import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Menu, MessageSquarePlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/base';
import { useI18n } from '../i18n';
import { api } from '../lib/api';
import { createConversationRealtimeClient, newRealtimeRequestId, type ConversationRealtimeClient } from '../lib/conversationRealtime';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel, isConversationAgent, pickDefaultConversationAgent } from '../lib/agents';
import type { AgentSummary, ConversationMemoryCandidate, ConversationMessage, ConversationSession, ConversationSessionDetail } from '../lib/types';
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

function buildPendingMessages(current: ConversationSessionDetail, requestId: string, question: string, userMessageId: string, assistantMessageId: string, selectedAgentId: string | null) {
  const createdAt = new Date().toISOString();
  const base = current.messages.length;
  return [
    ...current.messages,
    {
      id: userMessageId, session_id: current.id, request_id: requestId, seq: base + 1, role: 'user', message_type: 'text',
      content: question, status: 'completed', effective_agent_id: selectedAgentId, ai_provider_code: null, ai_trace_id: null,
      degraded: false, error_code: null, facts: [], suggestions: [], created_at: createdAt, updated_at: createdAt,
    } satisfies ConversationMessage,
    {
      id: assistantMessageId, session_id: current.id, request_id: requestId, seq: base + 2, role: 'assistant', message_type: 'text',
      content: '', status: 'pending', effective_agent_id: selectedAgentId, ai_provider_code: null, ai_trace_id: null,
      degraded: false, error_code: null, facts: [], suggestions: [], created_at: createdAt, updated_at: createdAt,
    } satisfies ConversationMessage,
  ];
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
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [realtimeReady, setRealtimeReady] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [candidateActionId, setCandidateActionId] = useState('');
  const realtimeClientRef = useRef<ConversationRealtimeClient | null>(null);
  const pendingSyncTimerRef = useRef<number | null>(null);
  const sendingRef = useRef(false);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const conversationAgents = useMemo(() => agents.filter(isConversationAgent), [agents]);
  const defaultAgent = useMemo(() => pickDefaultConversationAgent(agents), [agents]);
  const selectedAgent = useMemo(() => agents.find(item => item.id === selectedAgentId) ?? defaultAgent, [agents, defaultAgent, selectedAgentId]);
  const recentFacts = useMemo(() => (activeSessionDetail?.messages ?? []).filter(item => item.role === 'assistant').flatMap(item => item.facts).slice(0, 3), [activeSessionDetail]);
  const pendingCandidates = useMemo(() => (activeSessionDetail?.memory_candidates ?? []).filter(item => item.status === 'pending_review'), [activeSessionDetail]);

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [activeSessionDetail?.messages]);

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
    return () => { cancelled = true; };
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!activeSessionId) { setActiveSessionDetail(null); return; }
    let cancelled = false;
    void api.getConversationSession(activeSessionId).then(detail => {
      if (cancelled) return;
      setActiveSessionDetail(detail);
      setSessions(current => upsertSession(current, detail));
    }).catch(detailError => {
      if (!cancelled) setError(detailError instanceof Error ? detailError.message : '加载会话详情失败');
    });
    return () => { cancelled = true; };
  }, [activeSessionId]);

  async function syncActiveSessionDetail(sessionId?: string) {
    const targetSessionId = sessionId ?? activeSessionId;
    if (!targetSessionId) return;
    try {
      const detail = await api.getConversationSession(targetSessionId);
      setActiveSessionDetail(detail);
      setSessions(current => upsertSession(current, detail));
      const latestMessage = detail.messages[detail.messages.length - 1];
      setSuggestions(latestMessage?.suggestions ?? []);
    } catch {
      // 这里不覆盖更有用的实时错误
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
          const latestMessage = nextSession.messages[nextSession.messages.length - 1];
          setSuggestions(latestMessage?.suggestions ?? []);
          if (nextSession.messages.some(message => message.status === 'completed' || message.status === 'failed')) {
            resetPendingSyncTimer();
          }
          return;
        }
        if (event.type === 'agent.chunk') {
          const chunkText = 'text' in event.payload ? event.payload.text : '';
          setActiveSessionDetail(current => {
            if (!current) {
              return current;
            }
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
    if (nextAgentId && nextAgentId !== selectedAgentId) setSelectedAgentId(nextAgentId);
  }, [activeSessionDetail?.active_agent_id, defaultAgent?.id, selectedAgentId]);

  useEffect(() => {
    if (!currentHouseholdId) return;
    void api.getFamilyQaSuggestions(currentHouseholdId, undefined, selectedAgentId || undefined).then(result => {
      setSuggestions(result.items.map(item => item.question));
    }).catch(() => undefined);
  }, [currentHouseholdId, selectedAgentId]);

  async function refreshSessions(preferredSessionId?: string) {
    if (!currentHouseholdId) return;
    const result = await api.listConversationSessions({ household_id: currentHouseholdId, limit: 50 });
    setSessions(result.items);
    if (preferredSessionId) setActiveSessionId(preferredSessionId);
  }

  async function ensureSession() {
    if (activeSessionDetail) return activeSessionDetail;
    if (!currentHouseholdId) throw new Error('当前家庭不存在');
    const created = await api.createConversationSession({ household_id: currentHouseholdId, active_agent_id: selectedAgent?.id ?? undefined });
    setSessions(current => upsertSession(current, created));
    setActiveSessionId(created.id);
    setActiveSessionDetail(created);
    return created;
  }

  async function handleNewChat() {
    setStatus('');
    setError('');
    if (!currentHouseholdId) return;
    const created = await api.createConversationSession({ household_id: currentHouseholdId, active_agent_id: selectedAgent?.id ?? undefined });
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
      setActiveSessionDetail(current => current && current.id === session.id ? {
        ...current,
        messages: buildPendingMessages(current, requestId, question, `user:${requestId}`, `assistant:${requestId}`, selectedAgent?.id ?? current.active_agent_id ?? null),
      } : current);
      realtimeClientRef.current.sendUserMessage(requestId, question);
      resetPendingSyncTimer();
      pendingSyncTimerRef.current = window.setTimeout(() => {
        void syncActiveSessionDetail(session.id);
        setSending(false);
      }, 20000);
      await refreshSessions(session.id);
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

  async function resolveCandidate(candidate: ConversationMemoryCandidate, action: 'confirm' | 'dismiss') {
    try {
      setCandidateActionId(candidate.id);
      if (action === 'confirm') await api.confirmConversationMemoryCandidate(candidate.id);
      else await api.dismissConversationMemoryCandidate(candidate.id);
      const detail = await api.getConversationSession(candidate.session_id);
      setActiveSessionDetail(detail);
      setStatus(action === 'confirm' ? '已写入正式记忆。' : '已忽略这条记忆候选。');
    } catch (candidateError) {
      setError(candidateError instanceof Error ? candidateError.message : '处理记忆候选失败');
    } finally {
      setCandidateActionId('');
    }
  }

  if (!currentHouseholdId) return <div className="page page--assistant"><EmptyState icon="💬" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} /></div>;
  if (!loading && conversationAgents.length === 0) return <div className="page page--assistant"><EmptyState icon="🤖" title={t('assistant.noAgents')} description={t('assistant.noAgentsHint')} action={<button className="btn btn--outline" type="button" onClick={() => navigate('/settings/ai')}>{t('settings.ai')}</button>} /></div>;

  return (
    <div className="page page--assistant">
      {isSidebarOpen && <div className="assistant-sidebar-overlay" onClick={() => setIsSidebarOpen(false)} />}
      <div className={`assistant-sidebar ${isSidebarOpen ? 'is-open' : ''}`}>
        <div className="assistant-sidebar__header"><h2>{t('nav.assistant')}</h2><button className="btn btn--icon btn--ghost p-sm" onClick={() => void handleNewChat()}><MessageSquarePlus size={20} /></button></div>
        <div className="assistant-sidebar__search"><div className="assistant-sidebar__search-note">会话已保存在当前账号的服务端记录里；切换 Agent 时会自动分新对话，避免上下文串线。</div></div>
        <div className="assistant-sidebar__list">{loading ? <div className="context-memory-item"><span>⏳</span> 正在加载会话</div> : sessions.map(session => <div key={session.id} className={`session-item ${activeSessionId === session.id ? 'session-item--active' : ''}`} onClick={() => { setActiveSessionId(session.id); setIsSidebarOpen(false); }}><div className="session-item__content"><span className="session-item__title">{session.title}</span><span className="session-item__preview">{session.latest_message_preview ?? '等待你的第一条消息'}</span>{session.active_agent_name && <span className="session-item__agent">{session.active_agent_name}</span>}</div><span className="session-item__time">{formatRelativeTime(session.last_message_at)}</span></div>)}</div>
      </div>

      <div className="assistant-main">
        <div className="assistant-mobile-header"><button className="btn btn--icon btn--ghost p-sm assistant-menu-btn" onClick={() => setIsSidebarOpen(true)}><Menu size={24} /></button><div className="assistant-mobile-title">{activeSessionDetail?.title || t('nav.assistant')}</div><button className="btn btn--icon btn--ghost p-sm" onClick={() => void handleNewChat()}><MessageSquarePlus size={20} /></button></div>
        <div className="conversation-agent-banner"><div className="conversation-agent-banner__main"><div className="conversation-agent-banner__avatar">{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : <Bot size={18} />}</div><div className="conversation-agent-banner__text"><div className="conversation-agent-banner__title-row"><h2>{selectedAgent?.display_name ?? 'AI 助手'}</h2>{selectedAgent && <span className="ai-pill ai-pill--outline">{getAgentTypeLabel(selectedAgent.agent_type)}</span>}</div><p>{selectedAgent?.summary ?? 'AI 管家，协助家庭日常事务'}</p></div></div><div className="conversation-agent-switcher">{conversationAgents.map(agent => <button key={agent.id} type="button" className={`conversation-agent-switcher__item ${selectedAgentId === agent.id ? 'conversation-agent-switcher__item--active' : ''}`} onClick={() => void handleAgentSwitch(agent.id)}><span>{getAgentTypeEmoji(agent.agent_type)}</span><span>{agent.display_name}</span></button>)}</div></div>
        {activeSessionId ? (
          <>
            <div ref={messagesContainerRef} className="assistant-main__messages">{(activeSessionDetail?.messages ?? []).length > 0 ? activeSessionDetail!.messages.map(message => <div key={message.id} className={`message message--${message.role}`}><div className="message__avatar">{message.role === 'assistant' ? <span>{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : '🤖'}</span> : <span>你</span>}</div><div className="message__content-wrapper"><div className="message__bubble"><p className="message__content">{message.content || (message.status === 'pending' ? '正在准备回复...' : '')}</p>{message.degraded && <span className="message__memory-tag">⚠️ 当前回答已降级</span>}{message.status === 'streaming' && <span className="message__memory-tag">⏳ 正在生成</span>}{message.status === 'failed' && <span className="message__memory-tag">❌ 本轮失败</span>}</div>{message.role === 'assistant' && message.status !== 'pending' && <div className="message__actions"><button className="msg-action-btn" onClick={() => void submitQuestion(`继续追问：${message.content.slice(0, 40)}`)}>{t('assistant.askFollow')}</button><button className="msg-action-btn" onClick={() => navigate('/family')}>去家庭页</button><button className="msg-action-btn" onClick={() => navigate('/settings/ai')}>去 AI 配置</button><button className="msg-action-btn" onClick={() => navigate('/memories')}>去记忆页</button>{message.suggestions.slice(0, 2).map(suggestion => <button key={suggestion} className="msg-action-btn" onClick={() => void submitQuestion(suggestion)}>{suggestion}</button>)}</div>}</div></div>) : <EmptyState icon="💬" title={t('assistant.welcome')} description={t('assistant.welcomeHint')} />}</div>
            <div className="assistant-main__input"><form className="chat-composer" onSubmit={event => { event.preventDefault(); void submitQuestion(inputValue); }}><textarea value={inputValue} onChange={event => setInputValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !sending) { event.preventDefault(); void submitQuestion(inputValue); } }} placeholder={t('assistant.inputPlaceholder')} className="chat-composer__input form-input" rows={2} /><div className="chat-composer__footer"><span className="chat-composer__hint">Enter 发送，Shift + Enter 换行</span><button type="submit" className="btn btn--primary" disabled={sending || !inputValue.trim() || !realtimeReady}>{sending ? '发送中...' : t('assistant.send')}</button></div></form></div>
            {(error || status) && <div className="text-text-secondary" style={{ marginTop: '0.75rem' }}>{error || status}</div>}
          </>
        ) : <EmptyState icon="💬" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} action={<button className="btn btn--primary" onClick={() => void handleNewChat()}>{t('assistant.newChat')}</button>} />}
      </div>

      <div className="assistant-context">
        <div className="context-section"><h3 className="context-section__title">{t('assistant.context')}</h3><div className="context-item"><span className="context-item__label">{t('assistant.currentFamily')}</span><span className="context-item__value">{currentHousehold?.name ?? '-'}</span></div><div className="context-item"><span className="context-item__label">{t('assistant.currentAgent')}</span><span className="context-item__value">{selectedAgent ? `${selectedAgent.display_name} · ${getAgentStatusLabel(selectedAgent.status)}` : '-'}</span></div></div>
        <div className="context-section"><h3 className="context-section__title">{t('assistant.recentMemories')}</h3><div className="context-memory-list">{recentFacts.length > 0 ? recentFacts.map(item => <div key={`${item.type}-${item.label}`} className="context-memory-item"><span>🧠</span> {item.label}</div>) : suggestions.slice(0, 3).map(question => <div key={question} className="context-memory-item"><span>💡</span> {question}</div>)}</div></div>
        <div className="context-section"><h3 className="context-section__title">记忆候选</h3><div className="context-memory-list">{pendingCandidates.length > 0 ? pendingCandidates.map(candidate => <div key={candidate.id} className="context-memory-item" style={{ display: 'block' }}><div><span>📝</span> {candidate.title}</div><div style={{ marginTop: '0.35rem', color: 'var(--color-text-secondary)' }}>{candidate.summary}</div><div className="context-actions" style={{ marginTop: '0.5rem' }}><button className="context-action-btn" disabled={candidateActionId === candidate.id} onClick={() => void resolveCandidate(candidate, 'confirm')}>确认写入</button><button className="context-action-btn" disabled={candidateActionId === candidate.id} onClick={() => void resolveCandidate(candidate, 'dismiss')}>忽略</button></div></div>) : <div className="context-memory-item"><span>🪶</span> 当前还没有待确认的记忆候选</div>}</div></div>
        <div className="context-section"><h3 className="context-section__title">{t('assistant.quickActions')}</h3><div className="context-actions">{suggestions.slice(0, 3).map(question => <button key={question} className="context-action-btn" onClick={() => void submitQuestion(question)}>{question}</button>)}</div></div>
      </div>
    </div>
  );
}
