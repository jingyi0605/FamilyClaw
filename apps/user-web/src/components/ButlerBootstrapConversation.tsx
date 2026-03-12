import { useEffect, useRef, useState, type FormEvent } from 'react';

import { Card } from './base';
import { api } from '../lib/api';
import { parseTags, stringifyTags } from '../lib/aiConfig';
import type { AgentDetail, AgentSummary, ButlerBootstrapSession } from '../lib/types';

type Props = {
  householdId: string;
  source?: 'user-web' | 'setup-wizard';
  existingButlerAgent?: AgentSummary | null;
  onCreated?: (agent: AgentDetail) => Promise<void> | void;
};

type TranscriptMessage = {
  id: string;
  role: 'assistant' | 'user';
  content: string;
};

function newMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// 根据管家名字选择合适的 emoji 头像
function getButlerEmoji(name: string): string {
  const nameLower = name.toLowerCase();

  // 根据名字关键词匹配
  if (nameLower.includes('笨') || nameLower.includes('傻')) return '🤖';
  if (nameLower.includes('萌') || nameLower.includes('可爱')) return '🥰';
  if (nameLower.includes('智') || nameLower.includes('慧')) return '🧠';
  if (nameLower.includes('暖') || nameLower.includes('温')) return '☀️';
  if (nameLower.includes('星') || nameLower.includes('闪')) return '⭐';
  if (nameLower.includes('月') || nameLower.includes('夜')) return '🌙';
  if (nameLower.includes('云') || nameLower.includes('雾')) return '☁️';
  if (nameLower.includes('风') || nameLower.includes('飞')) return '🍃';
  if (nameLower.includes('小')) return '🐱';
  if (nameLower.includes('大')) return '🦁';
  if (nameLower.includes('花') || nameLower.includes('朵')) return '🌸';
  if (nameLower.includes('猫') || nameLower.includes('喵')) return '😺';
  if (nameLower.includes('狗') || nameLower.includes('汪')) return '🐕';
  if (nameLower.includes('熊')) return '🐻';
  if (nameLower.includes('兔')) return '🐰';
  if (nameLower.includes('狐')) return '🦊';
  if (nameLower.includes('龙')) return '🐉';
  if (nameLower.includes('凤')) return '🦅';

  // 默认根据名字长度选择
  const defaultEmojis = ['🤖', '🧞', '🦸', '🥷', '🎭', '🎩', '✨', '🌟'];
  const index = name.length % defaultEmojis.length;
  return defaultEmojis[index];
}

export function ButlerBootstrapConversation({
  householdId,
  source = 'user-web',
  existingButlerAgent = null,
  onCreated,
}: Props) {
  const [session, setSession] = useState<ButlerBootstrapSession | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createdAgent, setCreatedAgent] = useState<AgentDetail | null>(null);
  const autoStartedRef = useRef<string | null>(null);

  useEffect(() => {
    setSession(null);
    setMessages([]);
    setInput('');
    setLoading(false);
    setSending(false);
    setConfirming(false);
    setError('');
    setStatus('');
    setCreatedAgent(null);
    autoStartedRef.current = null;
  }, [householdId]);

  useEffect(() => {
    if (existingButlerAgent || createdAgent || session || loading || autoStartedRef.current === householdId) {
      return;
    }
    autoStartedRef.current = householdId;
    void startSession();
  }, [createdAgent, existingButlerAgent, householdId, loading, session]);

  async function startSession() {
    setLoading(true);
    setError('');
    setStatus('');
    try {
      const nextSession = await api.createButlerBootstrapSession(householdId);
      setSession(nextSession);
      setMessages([{ id: newMessageId(), role: 'assistant', content: nextSession.assistant_message }]);
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : '启动首个管家引导失败');
      setSession(null);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(nextDraft: ButlerBootstrapSession['draft']) {
    setSession(current => (current ? { ...current, draft: nextDraft } : current));
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !input.trim()) {
      return;
    }
    setSending(true);
    setError('');
    const userMessage = input.trim();

    const assistantMessageId = newMessageId();

    setInput('');
    setMessages(current => {
      return [
        ...current,
        { id: newMessageId(), role: 'user', content: userMessage },
        { id: assistantMessageId, role: 'assistant', content: '' },
      ];
    });

    try {
      await api.streamButlerBootstrapMessage(
        householdId,
        session.session_id,
        {
          message: userMessage,
        },
        (chunk) => {
          setMessages(current => {
            return current.map(message => (
              message.id === assistantMessageId
                ? { ...message, content: message.content + chunk }
                : message
            ));
          });
        },
        (nextSession) => {
          setSession(nextSession);
          setSending(false);
        },
        (errorMsg) => {
          setError(errorMsg);
          setSending(false);
        },
        // 实时更新 draft（用于更新管家名称和头像）
        (updatedDraft) => {
          setSession(current => current ? { ...current, draft: updatedDraft } : current);
        },
      );
    } catch (messageError) {
      setError(messageError instanceof Error ? messageError.message : '发送引导消息失败');
      setSending(false);
    }
  }

  async function handleConfirm() {
    if (!session) {
      return;
    }
    setConfirming(true);
    setError('');
    try {
      const created = await api.confirmButlerBootstrapSession(householdId, session.session_id, {
        draft: session.draft,
        created_by: source,
      });
      setCreatedAgent(created);
      setStatus('管家创建完成！');
      await onCreated?.(created);
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : '确认创建失败');
    } finally {
      setConfirming(false);
    }
  }

  if (existingButlerAgent && !createdAgent) {
    return (
      <Card className="butler-bootstrap">
        <div className="butler-bootstrap__summary">
          <div>
            <h3>管家已存在</h3>
            <p>这个家庭已有管家 {existingButlerAgent.display_name}，无需重复创建。</p>
          </div>
        </div>
      </Card>
    );
  }

  // 动态获取管家名称和头像
  const butlerName = session?.draft.display_name || 'AI 管家';
  const butlerEmoji = session?.draft.display_name ? getButlerEmoji(session.draft.display_name) : '🤖';

  return (
    <div className="butler-bootstrap">
      <Card className="butler-bootstrap__hero">
        {/* 管家头像和名称 - 实时更新 */}
        {session && (
          <div className="butler-bootstrap__avatar-header">
            <div className="butler-bootstrap__avatar">
              <span className="butler-bootstrap__avatar-emoji">{butlerEmoji}</span>
            </div>
            <div className="butler-bootstrap__avatar-info">
              <h3>{butlerName}</h3>
              <p className="butler-bootstrap__avatar-hint">
                {session.status === 'collecting' ? '正在了解自己...' : '准备好了！'}
              </p>
            </div>
          </div>
        )}

        {error && <p className="form-error">{error}</p>}
        {status && <div className="setup-form-status">{status}</div>}
        {loading && <p>正在准备...</p>}

        {!loading && session && (
          <div className="butler-bootstrap__chat">
            <div className="butler-bootstrap__messages">
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`butler-bootstrap__message butler-bootstrap__message--${message.role}`}
                >
                  {message.role === 'assistant' && (
                    <span className="butler-bootstrap__message-avatar">{butlerEmoji}</span>
                  )}
                  <div className="butler-bootstrap__message-content">
                    <span className="butler-bootstrap__message-role">
                      {message.role === 'assistant' ? butlerName : '你'}
                    </span>
                    <p>{message.content}</p>
                  </div>
                </div>
              ))}
            </div>

            {session.status === 'collecting' && (
              <form className="butler-bootstrap__composer" onSubmit={handleSend}>
                <textarea
                  className="form-input"
                  value={input}
                  onChange={event => setInput(event.target.value)}
                  placeholder="直接说就行..."
                  rows={2}
                />
                <button type="submit" className="btn btn--primary" disabled={sending || !input.trim()}>
                  {sending ? '...' : '发送'}
                </button>
              </form>
            )}

            {session.status === 'reviewing' && (
              <div className="butler-bootstrap__confirm">
                <div className="butler-bootstrap__review-grid">
                  <div className="form-group">
                    <label>管家名称</label>
                    <input
                      className="form-input"
                      value={session.draft.display_name}
                      onChange={event => updateDraft({ ...session.draft, display_name: event.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>说话风格</label>
                    <input
                      className="form-input"
                      value={session.draft.speaking_style}
                      onChange={event => updateDraft({ ...session.draft, speaking_style: event.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>性格特点</label>
                    <input
                      className="form-input"
                      value={stringifyTags(session.draft.personality_traits)}
                      onChange={event => updateDraft({
                        ...session.draft,
                        personality_traits: parseTags(event.target.value),
                      })}
                    />
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn--primary btn--large"
                  onClick={() => void handleConfirm()}
                  disabled={
                    confirming
                    || !session.draft.display_name.trim()
                    || !session.draft.speaking_style.trim()
                    || session.draft.personality_traits.length < 2
                  }
                >
                  {confirming ? '创建中...' : `确认创建 ${session.draft.display_name}`}
                </button>
              </div>
            )}
          </div>
        )}

        {!loading && !session && !existingButlerAgent && (
          <div className="setup-inline-tip">
            <span>请先完成 AI 供应商配置</span>
          </div>
        )}

        {createdAgent && (
          <Card className="butler-bootstrap__result">
            <div className="butler-bootstrap__created">
              <span className="butler-bootstrap__avatar-emoji butler-bootstrap__avatar-emoji--large">
                {getButlerEmoji(createdAgent.display_name)}
              </span>
              <h4>{createdAgent.display_name}</h4>
              <p>已加入家庭！</p>
            </div>
          </Card>
        )}
      </Card>
    </div>
  );
}
