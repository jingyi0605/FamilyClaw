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
  role: 'assistant' | 'user';
  content: string;
};

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
      setMessages([{ role: 'assistant', content: nextSession.assistant_message }]);
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
    setStatus('');
    const userMessage = input.trim();
    try {
      const nextSession = await api.sendButlerBootstrapMessage(householdId, session.session_id, {
        message: userMessage,
        draft: session.draft,
        pending_field: session.pending_field,
      });
      setMessages(current => [
        ...current,
        { role: 'user', content: userMessage },
        { role: 'assistant', content: nextSession.assistant_message },
      ]);
      setSession(nextSession);
      setInput('');
    } catch (messageError) {
      setError(messageError instanceof Error ? messageError.message : '发送引导消息失败');
    } finally {
      setSending(false);
    }
  }

  async function handleConfirm() {
    if (!session) {
      return;
    }
    setConfirming(true);
    setError('');
    setStatus('');
    try {
      const created = await api.confirmButlerBootstrapSession(householdId, session.session_id, {
        draft: session.draft,
        created_by: source,
      });
      setCreatedAgent(created);
      setStatus('首个管家已经创建完成。接下来改细节，走普通 Agent 配置页就行。');
      await onCreated?.(created);
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : '确认创建首个管家失败');
    } finally {
      setConfirming(false);
    }
  }

  if (existingButlerAgent && !createdAgent) {
    return (
      <Card className="butler-bootstrap">
        <div className="butler-bootstrap__summary">
          <div>
            <h3>首个管家已经存在</h3>
            <p>这个家庭已经有启用中的管家了，别重复造轮子。后续维护直接走下面的 Agent 配置中心。</p>
          </div>
          <div className="butler-bootstrap__agent-pill">
            <strong>{existingButlerAgent.display_name}</strong>
            <span>{existingButlerAgent.code}</span>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="butler-bootstrap">
      <Card className="butler-bootstrap__hero">
        <div className="setup-step-panel__header">
          <div>
            <h3>首个管家对话式创建</h3>
            <p>这一步只做 onboarding。先通过几轮对话把首个管家定下来，创建成功后再去普通 Agent 编辑器里细调。</p>
          </div>
          <div className="setup-form-actions">
            <button type="button" className="btn btn--outline" onClick={() => void startSession()} disabled={loading || sending || confirming}>
              重新开始
            </button>
          </div>
        </div>
        {error && <p className="form-error">{error}</p>}
        {status && <div className="setup-form-status">{status}</div>}
        {loading && <p>正在准备首个管家引导…</p>}
        {!loading && session && (
          <div className="butler-bootstrap__layout">
            <div className="butler-bootstrap__messages">
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`butler-bootstrap__message butler-bootstrap__message--${message.role}`}
                >
                  <span className="butler-bootstrap__message-role">{message.role === 'assistant' ? '引导助手' : '你'}</span>
                  <p>{message.content}</p>
                </div>
              ))}
            </div>

            {session.status === 'collecting' && (
              <form className="butler-bootstrap__composer" onSubmit={handleSend}>
                <label htmlFor={`butler-bootstrap-input-${householdId}`}>继续回答当前问题</label>
                <textarea
                  id={`butler-bootstrap-input-${householdId}`}
                  className="form-input setup-textarea"
                  value={input}
                  onChange={event => setInput(event.target.value)}
                  placeholder="直接说人话就行，不需要写成规范文档。"
                />
                <div className="setup-form-actions">
                  <button type="submit" className="btn btn--primary" disabled={sending || !input.trim()}>
                    {sending ? '发送中…' : '发送回答'}
                  </button>
                </div>
              </form>
            )}

            {session.status === 'reviewing' && (
              <Card className="ai-config-detail-card">
                <h4>创建草稿</h4>
                <div className="setup-form-grid">
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
                    <label>角色摘要</label>
                    <textarea
                      className="form-input setup-textarea"
                      value={session.draft.role_summary}
                      onChange={event => updateDraft({ ...session.draft, role_summary: event.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>人格特征</label>
                    <input
                      className="form-input"
                      value={stringifyTags(session.draft.personality_traits)}
                      onChange={event => updateDraft({ ...session.draft, personality_traits: parseTags(event.target.value) })}
                    />
                  </div>
                  <div className="form-group">
                    <label>服务重点</label>
                    <input
                      className="form-input"
                      value={stringifyTags(session.draft.service_focus)}
                      onChange={event => updateDraft({ ...session.draft, service_focus: parseTags(event.target.value) })}
                    />
                  </div>
                </div>
                <div className="setup-form-actions">
                  <button type="button" className="btn btn--primary" onClick={() => void handleConfirm()} disabled={confirming}>
                    {confirming ? '创建中…' : '确认创建首个管家'}
                  </button>
                </div>
              </Card>
            )}
          </div>
        )}

        {!loading && !session && !existingButlerAgent && (
          <div className="setup-inline-tip">
            <strong>当前还没法开始：</strong>
            <span>通常是 AI 供应商还没配好，或者这个家庭其实已经有首个管家了。把前置条件补齐后再重试。</span>
          </div>
        )}

        {createdAgent && (
          <Card className="butler-bootstrap__result">
            <h4>已创建：{createdAgent.display_name}</h4>
            <p>类型：首个管家 · 编号：{createdAgent.code}</p>
            <p>{createdAgent.soul?.role_summary ?? '人格摘要已创建。'}</p>
          </Card>
        )}
      </Card>
    </div>
  );
}
