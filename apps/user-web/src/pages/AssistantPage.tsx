/* ============================================================
 * 助手页 - 三栏布局：会话列表 + 对话区 + 上下文侧栏
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { Menu, MessageSquarePlus } from 'lucide-react';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { EmptyState } from '../components/base';
import { api } from '../lib/api';
import type { FamilyQaFactReference } from '../lib/types';

interface Session {
  id: string;
  title: string;
  lastMessage: string;
  time: string;
  pinned: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  usedMemory?: boolean;
  degraded?: boolean;
  facts?: FamilyQaFactReference[];
  suggestions?: string[];
}

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '刚刚';
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return `${Math.round(diffHours / 24)} 天前`;
}

function buildSessionTitle(question: string) {
  return question.length > 14 ? `${question.slice(0, 14)}...` : question;
}

export function AssistantPage() {
  const { t } = useI18n();
  const { currentHousehold, currentHouseholdId } = useHouseholdContext();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messagesBySession, setMessagesBySession] = useState<Record<string, Message[]>>({});
  const [activeSession, setActiveSession] = useState<string>('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [actionStatus, setActionStatus] = useState('');

  useEffect(() => {
    if (!currentHouseholdId) {
      setSuggestions([]);
      setSessions([]);
      setMessagesBySession({});
      setActiveSession('');
      return;
    }

    let cancelled = false;

    const loadSuggestions = async () => {
      setLoadingSuggestions(true);
      setError('');
      try {
        const result = await api.getFamilyQaSuggestions(currentHouseholdId);
        if (!cancelled) {
          setSuggestions(result.items.map(item => item.question));
          if (result.items.length > 0 && sessions.length === 0) {
            const seedQuestion = result.items[0].question;
            const seedSessionId = `session-${Date.now()}`;
            setSessions([{ id: seedSessionId, title: buildSessionTitle(seedQuestion), lastMessage: seedQuestion, time: '刚刚', pinned: true }]);
            setMessagesBySession({
              [seedSessionId]: [{ id: `msg-${Date.now()}`, role: 'assistant', content: '已拿到真实推荐问题，你可以直接点右侧问题，或者自己提问。' }],
            });
            setActiveSession(seedSessionId);
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setSuggestions([]);
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
  }, [currentHouseholdId]);

  const activeMessages = messagesBySession[activeSession] ?? [];
  const activeSessionData = sessions.find(s => s.id === activeSession);
  const recentMemoryFacts = useMemo(() => {
    const assistantMessages = activeMessages.filter(message => message.role === 'assistant');
    return assistantMessages.flatMap(message => message.facts ?? []).slice(0, 3);
  }, [activeMessages]);

  function handleNewChat() {
    const sessionId = `session-${Date.now()}`;
    const nextSession: Session = {
      id: sessionId,
      title: '新对话',
      lastMessage: '等待你的第一个问题',
      time: '刚刚',
      pinned: false,
    };
    setSessions(current => [nextSession, ...current]);
    setMessagesBySession(current => ({
      ...current,
      [sessionId]: [],
    }));
    setActiveSession(sessionId);
    setIsSidebarOpen(false);
  }

  async function submitQuestion(question: string) {
    if (!currentHouseholdId || !question.trim()) {
      return;
    }

    setSending(true);
    setError('');

    const sessionId = activeSession || `session-${Date.now()}`;
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question.trim(),
    };

    if (!activeSession) {
      setSessions(current => [{
        id: sessionId,
        title: buildSessionTitle(question.trim()),
        lastMessage: question.trim(),
        time: '刚刚',
        pinned: false,
      }, ...current]);
      setActiveSession(sessionId);
    } else {
      setSessions(current => current.map(session => session.id === sessionId ? {
        ...session,
        title: session.title === '新对话' ? buildSessionTitle(question.trim()) : session.title,
        lastMessage: question.trim(),
        time: '刚刚',
      } : session));
    }

    setMessagesBySession(current => ({
      ...current,
      [sessionId]: [...(current[sessionId] ?? []), userMessage],
    }));
    setInputValue('');

    try {
      const result = await api.queryFamilyQa({
        household_id: currentHouseholdId,
        question: question.trim(),
        channel: 'user_web',
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: result.answer,
        usedMemory: result.facts.some(item => item.source.includes('memory') || item.type.includes('memory')),
        degraded: result.degraded || result.ai_degraded,
        facts: result.facts,
        suggestions: result.suggestions,
      };

      setMessagesBySession(current => ({
        ...current,
        [sessionId]: [...(current[sessionId] ?? []), assistantMessage],
      }));
      setSuggestions(result.suggestions.length > 0 ? result.suggestions : suggestions);
      setActionStatus('');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '提问失败');
      setMessagesBySession(current => ({
        ...current,
        [sessionId]: [
          ...(current[sessionId] ?? []),
          {
            id: `assistant-error-${Date.now()}`,
            role: 'assistant',
            content: '这次没问成功，我先保留你的问题。你可以稍后重试，或者换个问法。',
            degraded: true,
          },
        ],
      }));
    } finally {
      setSending(false);
    }
  }

  async function handleCreateReminder(message: Message) {
    if (!currentHouseholdId) {
      setError('当前还没有选中的家庭，无法创建提醒。');
      return;
    }

    try {
      setActionStatus('');
      const now = new Date();
      const triggerAt = new Date(now.getTime() + 30 * 60 * 1000).toISOString();
      await api.createReminderTask({
        household_id: currentHouseholdId,
        owner_member_id: null,
        title: `助手建议：${message.content.slice(0, 18)}`,
        description: message.content,
        reminder_type: 'family',
        target_member_ids: [],
        preferred_room_ids: [],
        schedule_kind: 'once',
        schedule_rule: { trigger_at: triggerAt },
        priority: 'normal',
        delivery_channels: ['in_app'],
        ack_required: false,
        escalation_policy: {},
        enabled: true,
        updated_by: 'user-web',
      });
      setActionStatus('已用这条回答创建提醒。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '创建提醒失败');
    }
  }

  async function handleSaveMemory(message: Message) {
    if (!currentHouseholdId) {
      setError('当前还没有选中的家庭，无法写入记忆。');
      return;
    }

    try {
      setActionStatus('');
      await api.createManualMemoryCard({
        household_id: currentHouseholdId,
        memory_type: 'fact',
        title: `助手记录：${message.content.slice(0, 18)}`,
        summary: message.content,
        content: {
          source: 'assistant_answer',
          facts: message.facts ?? [],
        },
        visibility: 'family',
        status: 'active',
        importance: 3,
        confidence: 0.8,
        reason: '由用户在助手页手动保存',
      });
      setActionStatus('已把这条回答写入家庭记忆。');
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '写入记忆失败');
    }
  }

  return (
    <div className="page page--assistant">
      {isSidebarOpen && (
        <div className="assistant-sidebar-overlay" onClick={() => setIsSidebarOpen(false)} />
      )}

      <div className={`assistant-sidebar ${isSidebarOpen ? 'is-open' : ''}`}>
        <div className="assistant-sidebar__header">
          <h2>{t('nav.assistant')}</h2>
          <button className="btn btn--icon btn--ghost p-sm" onClick={handleNewChat}>
            <MessageSquarePlus size={20} />
          </button>
        </div>
        <div className="assistant-sidebar__search">
          <input type="text" placeholder={t('assistant.search')} className="search-input" disabled />
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

        {activeSession ? (
          <>
            <div className="assistant-main__messages">
              {activeMessages.length > 0 ? activeMessages.map(msg => (
                <div key={msg.id} className={`message message--${msg.role}`}>
                  <div className="message__bubble">
                    <p className="message__content">{msg.content}</p>
                    {msg.usedMemory && <span className="message__memory-tag">📝 引用了家庭记忆/事实</span>}
                    {msg.degraded && <span className="message__memory-tag">⚠️ 当前回答已降级</span>}
                  </div>
                  {msg.role === 'assistant' && (
                    <div className="message__actions">
                      <button className="msg-action-btn" onClick={() => void submitQuestion(`继续追问：${msg.content.slice(0, 40)}`)}>{t('assistant.askFollow')}</button>
                      <button className="msg-action-btn" onClick={() => void handleCreateReminder(msg)}>{t('assistant.toReminder')}</button>
                      <button className="msg-action-btn" onClick={() => void handleSaveMemory(msg)}>{t('assistant.toMemory')}</button>
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
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !sending) {
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
          <EmptyState icon="💬" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} action={<button className="btn btn--primary" onClick={handleNewChat}>{t('assistant.newChat')}</button>} />
        )}
      </div>

      <div className="assistant-context">
        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.context')}</h3>
          <div className="context-item">
            <span className="context-item__label">{t('assistant.currentFamily')}</span>
            <span className="context-item__value">{currentHousehold?.name ?? '-'}</span>
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
