/* ============================================================
 * 对话页 - 会话列表、Agent 切换、问答主链路
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { Bot, Menu, MessageSquarePlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/base';
import { useI18n } from '../i18n';
import { api } from '../lib/api';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel, isConversationAgent, pickDefaultConversationAgent } from '../lib/agents';
import type { AgentSummary, FamilyQaFactReference } from '../lib/types';
import { useHouseholdContext } from '../state/household';

const CONVERSATION_STORAGE_KEY = 'familyclaw-conversation-sessions';

interface Session {
  id: string;
  title: string;
  lastMessage: string;
  time: string;
  pinned: boolean;
  agentId: string | null;
  agentName: string | null;
  agentType: AgentSummary['agent_type'] | null;
  agentSummary: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  usedMemory?: boolean;
  degraded?: boolean;
  facts?: FamilyQaFactReference[];
  suggestions?: string[];
  effectiveAgentName?: string | null;
}

type PersistedConversationState = {
  sessions: Session[];
  messagesBySession: Record<string, Message[]>;
  activeSession: string;
};

function buildSessionTitle(question: string) {
  return question.length > 18 ? `${question.slice(0, 18)}...` : question;
}

function loadPersistedConversationState(householdId: string): PersistedConversationState | null {
  try {
    const raw = localStorage.getItem(`${CONVERSATION_STORAGE_KEY}:${householdId}`);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<PersistedConversationState>;
    if (!Array.isArray(parsed.sessions) || !parsed.messagesBySession || typeof parsed.activeSession !== 'string') {
      return null;
    }

    return {
      sessions: parsed.sessions,
      messagesBySession: parsed.messagesBySession,
      activeSession: parsed.activeSession,
    };
  } catch {
    return null;
  }
}

function toSessionMeta(agent: AgentSummary | null) {
  return {
    agentId: agent?.id ?? null,
    agentName: agent?.display_name ?? null,
    agentType: agent?.agent_type ?? null,
    agentSummary: agent?.summary ?? null,
  };
}

export function ConversationPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { currentHousehold, currentHouseholdId } = useHouseholdContext();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messagesBySession, setMessagesBySession] = useState<Record<string, Message[]>>({});
  const [activeSession, setActiveSession] = useState('');
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [actionStatus, setActionStatus] = useState('');
  const [actionDraft, setActionDraft] = useState<
    | { type: 'reminder'; message: Message; title: string; description: string; triggerAt: string }
    | { type: 'memory'; message: Message; title: string; summary: string }
    | null
  >(null);
  const [storageReady, setStorageReady] = useState(false);

  useEffect(() => {
    if (!currentHouseholdId) {
      setStorageReady(false);
      setSessions([]);
      setMessagesBySession({});
      setActiveSession('');
      setSelectedAgentId('');
      setSuggestions([]);
      return;
    }

    const persisted = loadPersistedConversationState(currentHouseholdId);
    setSessions(persisted?.sessions ?? []);
    setMessagesBySession(persisted?.messagesBySession ?? {});
    setActiveSession(persisted?.activeSession ?? '');
    setStorageReady(true);
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setAgents([]);
      return;
    }

    let cancelled = false;

    const loadAgents = async () => {
      setLoadingAgents(true);
      setError('');
      try {
        const result = await api.listAgents(currentHouseholdId);
        if (!cancelled) {
          setAgents(result.items);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 Agent 列表失败');
        }
      } finally {
        if (!cancelled) {
          setLoadingAgents(false);
        }
      }
    };

    void loadAgents();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  const activeSessionData = useMemo(
    () => sessions.find(item => item.id === activeSession) ?? null,
    [activeSession, sessions],
  );
  const conversationAgents = useMemo(
    () => agents.filter(isConversationAgent),
    [agents],
  );
  const defaultAgent = useMemo(
    () => pickDefaultConversationAgent(agents),
    [agents],
  );

  useEffect(() => {
    const candidateId =
      (activeSessionData?.agentId && agents.some(item => item.id === activeSessionData.agentId) ? activeSessionData.agentId : null) ??
      (selectedAgentId && agents.some(item => item.id === selectedAgentId) ? selectedAgentId : null) ??
      defaultAgent?.id ??
      '';

    if (candidateId !== selectedAgentId) {
      setSelectedAgentId(candidateId);
    }
  }, [activeSessionData?.agentId, agents, defaultAgent?.id, selectedAgentId]);

  useEffect(() => {
    if (!currentHouseholdId || !storageReady) {
      return;
    }

    const payload: PersistedConversationState = {
      sessions,
      messagesBySession,
      activeSession,
    };

    try {
      localStorage.setItem(`${CONVERSATION_STORAGE_KEY}:${currentHouseholdId}`, JSON.stringify(payload));
    } catch {
      // 忽略本地存储异常
    }
  }, [activeSession, currentHouseholdId, messagesBySession, sessions, storageReady]);

  useEffect(() => {
    if (!currentHouseholdId || !storageReady) {
      return;
    }

    let cancelled = false;

    const loadSuggestions = async () => {
      setLoadingSuggestions(true);
      setError('');
      try {
        const result = await api.getFamilyQaSuggestions(currentHouseholdId, undefined, selectedAgentId || undefined);
        if (!cancelled) {
          setSuggestions(result.items.map(item => item.question));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载推荐问题失败');
        }
      } finally {
        if (!cancelled) {
          setLoadingSuggestions(false);
        }
      }
    };

    void loadSuggestions();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, selectedAgentId, storageReady]);

  const selectedAgent = useMemo(
    () => agents.find(item => item.id === selectedAgentId) ?? defaultAgent,
    [agents, defaultAgent, selectedAgentId],
  );
  const activeMessages = messagesBySession[activeSession] ?? [];
  const recentMemoryFacts = useMemo(() => {
    const assistantMessages = activeMessages.filter(message => message.role === 'assistant');
    return assistantMessages.flatMap(message => message.facts ?? []).slice(0, 3);
  }, [activeMessages]);

  function createSession(agent: AgentSummary | null) {
    const sessionId = `session-${Date.now()}`;
    const nextSession: Session = {
      id: sessionId,
      title: '新对话',
      lastMessage: '等待你的第一个问题',
      time: '刚刚',
      pinned: false,
      ...toSessionMeta(agent),
    };

    setSessions(current => [nextSession, ...current.filter(item => item.id !== sessionId)]);
    setMessagesBySession(current => ({
      ...current,
      [sessionId]: [],
    }));
    setActiveSession(sessionId);
    setIsSidebarOpen(false);
    return sessionId;
  }

  function updateSession(sessionId: string, updates: Partial<Session>) {
    setSessions(current => {
      const existing = current.find(item => item.id === sessionId);
      if (!existing) {
        return current;
      }

      const next = {
        ...existing,
        ...updates,
      };

      return [next, ...current.filter(item => item.id !== sessionId)];
    });
  }

  function handleNewChat() {
    createSession(selectedAgent ?? defaultAgent);
  }

  function handleAgentSwitch(agentId: string) {
    const nextAgent = conversationAgents.find(item => item.id === agentId) ?? null;
    setSelectedAgentId(agentId);

    if (!nextAgent) {
      return;
    }

    if (!activeSession) {
      return;
    }

    const currentSession = sessions.find(item => item.id === activeSession) ?? null;
    const currentMessages = messagesBySession[activeSession] ?? [];

    if (currentSession?.agentId === nextAgent.id) {
      return;
    }

    if (currentMessages.length === 0) {
      updateSession(activeSession, {
        ...toSessionMeta(nextAgent),
        time: '刚刚',
      });
      return;
    }

    createSession(nextAgent);
    setActionStatus(`已切换到 ${nextAgent.display_name}，新对话会按这个角色继续。`);
  }

  async function submitQuestion(rawQuestion: string) {
    if (!currentHouseholdId || !rawQuestion.trim()) {
      return;
    }

    const question = rawQuestion.trim();
    const requestAgent = conversationAgents.find(item => item.id === selectedAgentId) ?? defaultAgent ?? null;

    setSending(true);
    setError('');

    let sessionId = activeSession;
    if (!sessionId) {
      sessionId = createSession(requestAgent);
    }

    const currentMessages = messagesBySession[sessionId] ?? [];
    if (currentMessages.length === 0) {
      updateSession(sessionId, {
        title: buildSessionTitle(question),
        lastMessage: question,
        time: '刚刚',
        ...toSessionMeta(requestAgent),
      });
    } else {
      updateSession(sessionId, {
        lastMessage: question,
        time: '刚刚',
      });
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
    };

    setMessagesBySession(current => ({
      ...current,
      [sessionId]: [...(current[sessionId] ?? []), userMessage],
    }));
    setInputValue('');

    try {
      const result = await api.queryFamilyQa({
        household_id: currentHouseholdId,
        agent_id: requestAgent?.id ?? undefined,
        question,
        channel: 'user_web',
      });

      const effectiveAgent = agents.find(item => item.id === result.effective_agent_id) ?? requestAgent ?? null;
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: result.answer,
        usedMemory: result.facts.some(item => item.source.includes('memory') || item.type.includes('memory')),
        degraded: result.degraded || result.ai_degraded,
        facts: result.facts,
        suggestions: result.suggestions,
        effectiveAgentName: result.effective_agent_name ?? effectiveAgent?.display_name ?? null,
      };

      setMessagesBySession(current => ({
        ...current,
        [sessionId]: [...(current[sessionId] ?? []), assistantMessage],
      }));
      updateSession(sessionId, {
        title: buildSessionTitle(question),
        lastMessage: question,
        time: '刚刚',
        ...toSessionMeta(effectiveAgent),
      });
      setSuggestions(current => (result.suggestions.length > 0 ? result.suggestions : current));
      setActionStatus('');

      if (effectiveAgent?.id && effectiveAgent.id !== selectedAgentId) {
        setSelectedAgentId(effectiveAgent.id);
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '提问失败');
      setMessagesBySession(current => ({
        ...current,
        [sessionId]: [
          ...(current[sessionId] ?? []),
          {
            id: `assistant-error-${Date.now()}`,
            role: 'assistant',
            content: '这次没有答上来。我先把你的问题保留着，你可以稍后再试，或者换个问法。',
            degraded: true,
          },
        ],
      }));
    } finally {
      setSending(false);
    }
  }

  function openReminderDraft(message: Message) {
    const now = new Date();
    const triggerAt = new Date(now.getTime() + 30 * 60 * 1000).toISOString().slice(0, 16);
    setActionDraft({
      type: 'reminder',
      message,
      title: `助手建议：${message.content.slice(0, 18)}`,
      description: message.content,
      triggerAt,
    });
    setError('');
  }

  function openMemoryDraft(message: Message) {
    setActionDraft({
      type: 'memory',
      message,
      title: `助手记录：${message.content.slice(0, 18)}`,
      summary: message.content,
    });
    setError('');
  }

  function openRelatedPage(target: 'family' | 'settings' | 'memories') {
    const routeMap = {
      family: '/family',
      settings: '/settings/ai',
      memories: '/memories',
    } as const;

    navigate(routeMap[target]);
  }

  async function submitActionDraft() {
    if (!currentHouseholdId || !actionDraft) {
      return;
    }

    try {
      setActionStatus('');
      if (actionDraft.type === 'reminder') {
        await api.createReminderTask({
          household_id: currentHouseholdId,
          owner_member_id: null,
          title: actionDraft.title,
          description: actionDraft.description,
          reminder_type: 'family',
          target_member_ids: [],
          preferred_room_ids: [],
          schedule_kind: 'once',
          schedule_rule: { trigger_at: new Date(actionDraft.triggerAt).toISOString() },
          priority: 'normal',
          delivery_channels: ['in_app'],
          ack_required: false,
          escalation_policy: {},
          enabled: true,
          updated_by: 'user-web',
        });
        setActionStatus('已根据这条回答创建提醒。');
      } else {
        await api.createManualMemoryCard({
          household_id: currentHouseholdId,
          memory_type: 'fact',
          title: actionDraft.title,
          summary: actionDraft.summary,
          content: {
            source: 'assistant_answer',
            facts: actionDraft.message.facts ?? [],
          },
          visibility: 'family',
          status: 'active',
          importance: 3,
          confidence: 0.8,
          reason: '由用户在对话页手动保存',
        });
        setActionStatus('已把这条回答写入家庭记忆。');
      }
      setActionDraft(null);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '提交动作失败');
    }
  }

  if (!currentHouseholdId) {
    return (
      <div className="page page--assistant">
        <EmptyState icon="💬" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} />
      </div>
    );
  }

  if (!loadingAgents && conversationAgents.length === 0) {
    return (
      <div className="page page--assistant">
        <EmptyState
          icon="🤖"
          title={t('assistant.noAgents')}
          description={t('assistant.noAgentsHint')}
          action={<button className="btn btn--outline" type="button" onClick={() => navigate('/settings/ai')}>{t('settings.ai')}</button>}
        />
      </div>
    );
  }

  return (
    <div className="page page--assistant">
      {isSidebarOpen && <div className="assistant-sidebar-overlay" onClick={() => setIsSidebarOpen(false)} />}
      {actionDraft && (
        <div className="assistant-action-modal-overlay" onClick={() => setActionDraft(null)}>
          <div className="assistant-action-modal" onClick={event => event.stopPropagation()}>
            <div className="assistant-action-modal__header">
              <h3>{actionDraft.type === 'reminder' ? t('assistant.toReminder') : t('assistant.toMemory')}</h3>
              <button className="close-btn" type="button" onClick={() => setActionDraft(null)}>✕</button>
            </div>
            <div className="settings-form">
              {actionDraft.type === 'reminder' ? (
                <>
                  <div className="form-group">
                    <label>提醒标题</label>
                    <input className="form-input" value={actionDraft.title} onChange={event => setActionDraft(current => current && current.type === 'reminder' ? { ...current, title: event.target.value } : current)} />
                  </div>
                  <div className="form-group">
                    <label>提醒内容</label>
                    <textarea className="form-input" rows={4} value={actionDraft.description} onChange={event => setActionDraft(current => current && current.type === 'reminder' ? { ...current, description: event.target.value } : current)} />
                  </div>
                  <div className="form-group">
                    <label>提醒时间</label>
                    <input className="form-input" type="datetime-local" value={actionDraft.triggerAt} onChange={event => setActionDraft(current => current && current.type === 'reminder' ? { ...current, triggerAt: event.target.value } : current)} />
                  </div>
                </>
              ) : (
                <>
                  <div className="form-group">
                    <label>记忆标题</label>
                    <input className="form-input" value={actionDraft.title} onChange={event => setActionDraft(current => current && current.type === 'memory' ? { ...current, title: event.target.value } : current)} />
                  </div>
                  <div className="form-group">
                    <label>记忆摘要</label>
                    <textarea className="form-input" rows={4} value={actionDraft.summary} onChange={event => setActionDraft(current => current && current.type === 'memory' ? { ...current, summary: event.target.value } : current)} />
                  </div>
                </>
              )}
              <div className="assistant-action-modal__actions">
                <button className="btn btn--primary" type="button" onClick={() => void submitActionDraft()}>{t('common.confirm')}</button>
                <button className="btn btn--outline" type="button" onClick={() => setActionDraft(null)}>{t('common.cancel')}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className={`assistant-sidebar ${isSidebarOpen ? 'is-open' : ''}`}>
        <div className="assistant-sidebar__header">
          <h2>{t('nav.assistant')}</h2>
          <button className="btn btn--icon btn--ghost p-sm" onClick={handleNewChat}>
            <MessageSquarePlus size={20} />
          </button>
        </div>
        <div className="assistant-sidebar__search">
          <div className="assistant-sidebar__search-note">{t('assistant.sessionNote')}</div>
        </div>
        <div className="assistant-sidebar__list">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`session-item ${activeSession === session.id ? 'session-item--active' : ''}`}
              onClick={() => {
                setActiveSession(session.id);
                setIsSidebarOpen(false);
              }}
            >
              {session.pinned && <span className="session-item__pin">📌</span>}
              <div className="session-item__content">
                <span className="session-item__title">{session.title}</span>
                <span className="session-item__preview">{session.lastMessage}</span>
                {session.agentName && <span className="session-item__agent">{session.agentName}</span>}
              </div>
              <span className="session-item__time">{session.time}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="assistant-main">
        <div className="assistant-mobile-header">
          <button className="btn btn--icon btn--ghost p-sm assistant-menu-btn" onClick={() => setIsSidebarOpen(true)}>
            <Menu size={24} />
          </button>
          <div className="assistant-mobile-title">{activeSessionData?.title || t('nav.assistant')}</div>
          <button className="btn btn--icon btn--ghost p-sm" onClick={handleNewChat}>
            <MessageSquarePlus size={20} />
          </button>
        </div>

        <div className="conversation-agent-banner">
          <div className="conversation-agent-banner__main">
            <div className="conversation-agent-banner__avatar">{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : <Bot size={18} />}</div>
            <div className="conversation-agent-banner__text">
              <div className="conversation-agent-banner__title-row">
                <h2>{selectedAgent?.display_name ?? t('assistant.loadingAgents')}</h2>
                {selectedAgent && <span className="ai-pill">{getAgentTypeLabel(selectedAgent.agent_type)}</span>}
                {selectedAgent?.default_entry && <span className="ai-pill ai-pill--primary">{t('settings.ai.defaultEntry')}</span>}
              </div>
              <p>{selectedAgent?.summary ?? t('assistant.agentSummaryFallback')}</p>
            </div>
          </div>
          <div className="conversation-agent-switcher">
            {conversationAgents.map(agent => (
              <button
                key={agent.id}
                type="button"
                className={`conversation-agent-switcher__item ${selectedAgentId === agent.id ? 'conversation-agent-switcher__item--active' : ''}`}
                onClick={() => handleAgentSwitch(agent.id)}
              >
                <span>{getAgentTypeEmoji(agent.agent_type)}</span>
                <span>{agent.display_name}</span>
              </button>
            ))}
          </div>
          {loadingAgents && <div className="conversation-agent-banner__note">{t('assistant.loadingAgents')}</div>}
        </div>

        {activeSession ? (
          <>
            <div className="assistant-main__messages">
              {activeMessages.length > 0 ? activeMessages.map(msg => (
                <div key={msg.id} className={`message message--${msg.role}`}>
                  <div className="message__bubble">
                    {msg.role === 'assistant' && msg.effectiveAgentName && (
                      <span className="message__agent-tag">{msg.effectiveAgentName}</span>
                    )}
                    <p className="message__content">{msg.content}</p>
                    {msg.usedMemory && <span className="message__memory-tag">🧠 引用了家庭记忆</span>}
                    {msg.degraded && <span className="message__memory-tag">⚠️ 当前回答已降级</span>}
                  </div>
                  {msg.role === 'assistant' && (
                    <div className="message__actions">
                      <button className="msg-action-btn" onClick={() => void submitQuestion(`继续追问：${msg.content.slice(0, 40)}`)}>{t('assistant.askFollow')}</button>
                      <button className="msg-action-btn" onClick={() => openReminderDraft(msg)}>{t('assistant.toReminder')}</button>
                      <button className="msg-action-btn" onClick={() => openMemoryDraft(msg)}>{t('assistant.toMemory')}</button>
                      <button className="msg-action-btn" onClick={() => openRelatedPage('family')}>去家庭页</button>
                      <button className="msg-action-btn" onClick={() => openRelatedPage('settings')}>去 AI 配置</button>
                      <button className="msg-action-btn" onClick={() => openRelatedPage('memories')}>去记忆页</button>
                      {(msg.suggestions ?? []).slice(0, 2).map(suggestion => (
                        <button key={suggestion} className="msg-action-btn" onClick={() => void submitQuestion(suggestion)}>{suggestion}</button>
                      ))}
                    </div>
                  )}
                </div>
              )) : (
                <EmptyState icon="💬" title={t('assistant.welcome')} description={t('assistant.welcomeHint')} />
              )}
            </div>
            <div className="assistant-main__input">
              <input
                type="text"
                value={inputValue}
                onChange={event => setInputValue(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !sending) {
                    void submitQuestion(inputValue);
                  }
                }}
                placeholder={t('assistant.inputPlaceholder')}
                className="chat-input"
              />
              <button className="btn btn--primary" onClick={() => void submitQuestion(inputValue)} disabled={sending || !currentHouseholdId}>
                {sending ? '发送中...' : t('assistant.send')}
              </button>
            </div>
            {(error || actionStatus) && <div className="text-text-secondary" style={{ marginTop: '0.75rem' }}>{error || actionStatus}</div>}
          </>
        ) : (
          <EmptyState
            icon="💬"
            title={t('assistant.noSessions')}
            description={t('assistant.noSessionsHint')}
            action={<button className="btn btn--primary" onClick={handleNewChat}>{t('assistant.newChat')}</button>}
          />
        )}
      </div>

      <div className="assistant-context">
        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.context')}</h3>
          <div className="context-item">
            <span className="context-item__label">{t('assistant.currentFamily')}</span>
            <span className="context-item__value">{currentHousehold?.name ?? '-'}</span>
          </div>
          <div className="context-item">
            <span className="context-item__label">{t('assistant.currentAgent')}</span>
            <span className="context-item__value">
              {selectedAgent ? `${selectedAgent.display_name} · ${getAgentStatusLabel(selectedAgent.status)}` : '-'}
            </span>
          </div>
        </div>

        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.recentMemories')}</h3>
          <div className="context-memory-list">
            {recentMemoryFacts.length > 0 ? recentMemoryFacts.map(item => (
              <div key={`${item.type}-${item.label}`} className="context-memory-item">
                <span>🧠</span> {item.label}
              </div>
            )) : (
              suggestions.slice(0, 3).map(question => (
                <div key={question} className="context-memory-item">
                  <span>💡</span> {question}
                </div>
              ))
            )}
            {loadingSuggestions && <div className="context-memory-item"><span>⏳</span> 正在加载推荐问题</div>}
          </div>
        </div>

        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.quickActions')}</h3>
          <div className="context-actions">
            {suggestions.slice(0, 3).map(question => (
              <button key={question} className="context-action-btn" onClick={() => void submitQuestion(question)}>
                {question}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
