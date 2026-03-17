import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useI18n } from '../../runtime';
import { createBrowserRealtimeClient, newRealtimeRequestId, type BootstrapRealtimeEvent, type BootstrapRealtimeSessionSnapshot } from './setupRealtime';
import { Card } from './base';
import { parseTags, stringifyTags } from './setupAiConfig';
import { setupApi } from './setupApi';
import type { AgentDetail, AgentSummary, ButlerBootstrapSession } from './setupTypes';

type TranscriptMessage = { id: string; requestId?: string | null; role: 'assistant' | 'user'; content: string };

function newMessageId() { return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`; }
function toTranscriptMessages(session: ButlerBootstrapSession): TranscriptMessage[] {
  const source = session.messages.length > 0 ? session.messages : [{ role: 'assistant' as const, content: session.assistant_message }];
  return source.map(message => ({ id: message.id ?? `${message.request_id ?? 'message'}:${message.seq ?? newMessageId()}`, requestId: message.request_id ?? null, role: message.role, content: message.content }));
}
function getButlerEmoji(name: string): string {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('笨') || nameLower.includes('傻')) return '🤖'; if (nameLower.includes('萌') || nameLower.includes('可爱')) return '🥰'; if (nameLower.includes('智') || nameLower.includes('慧')) return '🧠'; if (nameLower.includes('暖') || nameLower.includes('温')) return '☀️'; if (nameLower.includes('星') || nameLower.includes('闪')) return '⭐'; if (nameLower.includes('月') || nameLower.includes('夜')) return '🌙'; if (nameLower.includes('云') || nameLower.includes('雾')) return '☁️'; if (nameLower.includes('风') || nameLower.includes('飞')) return '🍃'; if (nameLower.includes('小')) return '🐱'; if (nameLower.includes('大')) return '🦁'; if (nameLower.includes('花') || nameLower.includes('朵')) return '🌸'; if (nameLower.includes('猫') || nameLower.includes('喵')) return '😺'; if (nameLower.includes('狗') || nameLower.includes('汪')) return '🐕'; if (nameLower.includes('熊')) return '🐻'; if (nameLower.includes('兔')) return '🐰'; if (nameLower.includes('狐')) return '🦊'; if (nameLower.includes('龙')) return '🐉'; if (nameLower.includes('凤')) return '🦅';
  const defaultEmojis = ['🤖', '🧞', '🦸', '🥷', '🎭', '🎩', '✨', '🌟'];
  return defaultEmojis[name.length % defaultEmojis.length];
}
function normalizeMessageContent(content: string) { return content.replace(/\r\n/g, '\n').replace(/\n{2,}/g, '\n').trim(); }

export function ButlerBootstrapConversation(props: { householdId: string; source?: 'user-app' | 'setup-wizard'; existingButlerAgent?: AgentSummary | null; onCreated?: (agent: AgentDetail) => Promise<void> | void }) {
  const { t } = useI18n();
  const { householdId, source = 'user-app', existingButlerAgent = null, onCreated } = props;
  const [session, setSession] = useState<ButlerBootstrapSession | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [realtimeReady, setRealtimeReady] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createdAgent, setCreatedAgent] = useState<AgentDetail | null>(null);
  const autoStartedRef = useRef<string | null>(null);
  const composerRef = useRef<HTMLFormElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const realtimeClientRef = useRef<ReturnType<typeof createBrowserRealtimeClient> | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [composerHeight, setComposerHeight] = useState(0);

  function resolveRealtimeErrorMessage(errorCode?: string | null) {
    if (errorCode === 'auth_failed') return t('setup.butler.error.authFailed');
    if (errorCode === 'timeout') return t('setup.butler.error.timeout');
    if (errorCode === 'rate_limited') return t('setup.butler.error.rateLimited');
    if (errorCode === 'stream_not_supported') return t('setup.butler.error.streamNotSupported');
    return t('setup.butler.error.providerFailed');
  }

  useEffect(() => {
    setSession(null); setMessages([]); setInput(''); setLoading(false); setSending(false); setConfirming(false); setRestarting(false); setRealtimeReady(false); setError(''); setStatus(''); setCreatedAgent(null); autoStartedRef.current = null;
    if (reconnectTimerRef.current !== null) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
    reconnectAttemptsRef.current = 0;
  }, [householdId]);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => { messagesEndRef.current?.scrollIntoView({ block: 'end' }); });
    return () => window.cancelAnimationFrame(frameId);
  }, [messages, session?.status]);

  useEffect(() => {
    if (session?.status !== 'collecting') { setComposerHeight(0); return; }
    const composerElement = composerRef.current;
    if (!composerElement) return;
    const updateComposerHeight = () => setComposerHeight(composerElement.getBoundingClientRect().height);
    updateComposerHeight();
    if (typeof ResizeObserver === 'undefined') { window.addEventListener('resize', updateComposerHeight); return () => window.removeEventListener('resize', updateComposerHeight); }
    const resizeObserver = new ResizeObserver(() => updateComposerHeight());
    resizeObserver.observe(composerElement);
    window.addEventListener('resize', updateComposerHeight);
    return () => { resizeObserver.disconnect(); window.removeEventListener('resize', updateComposerHeight); };
  }, [session?.status]);

  useEffect(() => {
    if (existingButlerAgent || createdAgent || session || loading || autoStartedRef.current === householdId) return;
    autoStartedRef.current = householdId;
    void loadOrStartSession();
  }, [createdAgent, existingButlerAgent, householdId, loading, session]);

  useEffect(() => {
    if (!session?.session_id || createdAgent) {
      realtimeClientRef.current?.close(); realtimeClientRef.current = null; activeSessionIdRef.current = null;
      if (reconnectTimerRef.current !== null) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
      reconnectAttemptsRef.current = 0; setRealtimeReady(false); return;
    }
    if (activeSessionIdRef.current === session.session_id) return;
    realtimeClientRef.current?.close(); setRealtimeReady(false);
    if (reconnectTimerRef.current !== null) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
    activeSessionIdRef.current = session.session_id;
    realtimeClientRef.current = createBrowserRealtimeClient({
      householdId,
      sessionId: session.session_id,
      onEvent: handleRealtimeEvent,
      onOpen: () => { reconnectAttemptsRef.current = 0; setRealtimeReady(true); },
      onClose: event => {
        if (activeSessionIdRef.current !== session.session_id) return;
        realtimeClientRef.current = null; activeSessionIdRef.current = null; setRealtimeReady(false);
        if (!event.wasClean && !createdAgent) {
          const delayMs = Math.min(1000 * (reconnectAttemptsRef.current + 1), 5000);
          reconnectAttemptsRef.current += 1;
          setStatus('');
          reconnectTimerRef.current = window.setTimeout(() => { reconnectTimerRef.current = null; void syncLatestSession(session.session_id); }, delayMs);
        }
      },
      onError: () => { setRealtimeReady(false); setError(t('setup.butler.status.connectionError')); },
    });
    return () => { realtimeClientRef.current?.close(); realtimeClientRef.current = null; activeSessionIdRef.current = null; if (reconnectTimerRef.current !== null) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; } setRealtimeReady(false); };
  }, [createdAgent, householdId, session?.session_id]);

  async function loadOrStartSession() {
    setLoading(true); setError(''); setStatus('');
    try {
      const existingSession = await setupApi.getLatestButlerBootstrapSession(householdId);
      const nextSession = existingSession ?? await setupApi.createButlerBootstrapSession(householdId);
      setSession(nextSession); setMessages(toTranscriptMessages(nextSession));
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : t('setup.butler.error.startFailed')); setSession(null); setMessages([]);
    } finally { setLoading(false); }
  }
  async function handleRestart() {
    setRestarting(true); setError(''); setStatus('');
    try {
      const nextSession = await setupApi.restartButlerBootstrapSession(householdId);
      realtimeClientRef.current?.close(); realtimeClientRef.current = null; activeSessionIdRef.current = null;
      setSession(nextSession); setMessages(toTranscriptMessages(nextSession)); setInput('');
    } catch (restartError) { setError(restartError instanceof Error ? restartError.message : t('setup.butler.error.restartFailed')); } finally { setRestarting(false); }
  }
  function updateDraft(nextDraft: ButlerBootstrapSession['draft']) { setSession(current => current ? { ...current, draft: nextDraft } : current); }
  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !input.trim()) return;
    setSending(true); setError(''); setStatus('');
    const userMessage = input.trim(); const requestId = newRealtimeRequestId(); setInput('');
    setMessages(current => [...current, { id: `user:${requestId}`, requestId, role: 'user', content: userMessage }, { id: `assistant:${requestId}`, requestId, role: 'assistant', content: '' }]);
    try { realtimeClientRef.current?.sendUserMessage(requestId, userMessage); } catch (messageError) { setMessages(current => current.filter(message => message.requestId !== requestId)); setError(messageError instanceof Error ? messageError.message : t('setup.butler.error.sendFailed')); setSending(false); }
  }
  function handleRealtimeEvent(event: BootstrapRealtimeEvent) {
    if (event.type === 'session.ready') return;
    if (event.type === 'session.snapshot') {
      const nextSession = (event.payload as { snapshot: BootstrapRealtimeSessionSnapshot }).snapshot;
      setSession(nextSession as ButlerBootstrapSession); setMessages(toTranscriptMessages(nextSession as ButlerBootstrapSession)); setSending(Boolean(nextSession.current_request_id)); return;
    }
    if (event.type === 'user.message.accepted') { setSending(true); setSession(current => current ? { ...current, current_request_id: event.request_id ?? null } : current); return; }
    if (event.type === 'agent.chunk') {
      const payload = event.payload as { text: string };
      setMessages(current => {
        const targetId = `assistant:${event.request_id}`;
        const existing = current.find(message => message.id === targetId);
        if (existing) return current.map(message => message.id === targetId ? { ...message, content: message.content + payload.text } : message);
        return [...current, { id: targetId, requestId: event.request_id, role: 'assistant', content: payload.text }];
      });
      return;
    }
    if (event.type === 'agent.state_patch') { setSession(current => current ? { ...current, draft: { ...current.draft, ...event.payload } } : current); return; }
    if (event.type === 'agent.done') { setSending(false); void syncLatestSession(session?.session_id); return; }
    if (event.type === 'agent.error') {
      const payload = event.payload as { detail?: string; error_code?: string };
      setSending(false);
      setError(resolveRealtimeErrorMessage(payload.error_code));
      void syncLatestSession(session?.session_id);
    }
  }
  async function syncLatestSession(expectedSessionId?: string | null) {
    try {
      const nextSession = await setupApi.getLatestButlerBootstrapSession(householdId);
      if (!nextSession) return;
      if (expectedSessionId && nextSession.session_id !== expectedSessionId && activeSessionIdRef.current === expectedSessionId) return;
      setSession(nextSession); setMessages(toTranscriptMessages(nextSession)); setSending(Boolean(nextSession.current_request_id));
    } catch {
      return;
    }
  }
  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    if (sending || !input.trim()) return;
    event.currentTarget.form?.requestSubmit();
  }
  async function handleConfirm() {
    if (!session) return;
    setConfirming(true); setError('');
    try {
      const created = await setupApi.confirmButlerBootstrapSession(householdId, session.session_id, { draft: session.draft, created_by: source });
      setCreatedAgent(created); await onCreated?.(created);
    } catch (confirmError) { setError(confirmError instanceof Error ? confirmError.message : t('setup.butler.error.confirmFailed')); } finally { setConfirming(false); }
  }
  if (existingButlerAgent && !createdAgent) return <Card className="butler-bootstrap"><div className="butler-bootstrap__summary"><div><h3>{t('setup.butler.existsTitle')}</h3><p>{t('setup.butler.existsDesc', { name: existingButlerAgent.display_name })}</p></div></div></Card>;
  const butlerName = session?.draft.display_name || t('setup.butler.defaultName'); const butlerEmoji = session?.draft.display_name ? getButlerEmoji(session.draft.display_name) : '🤖';
  return (
    <div className="butler-bootstrap">
      <Card className="butler-bootstrap__hero">
        {error ? <p className="form-error">{error}</p> : null}
        {loading ? <p>{t('setup.butler.loading')}</p> : null}
        {!loading && session ? (
          <div className="butler-bootstrap__chat">
            <div className="butler-bootstrap__chat-actions"><button type="button" className="butler-bootstrap__restart-btn" onClick={() => void handleRestart()} disabled={loading || sending || confirming || restarting}>{restarting ? t('setup.butler.restarting') : t('setup.butler.restart')}</button></div>
            <div className="butler-bootstrap__messages" style={session.status === 'collecting' ? { paddingBottom: `${composerHeight + 24}px` } : undefined}>
              {messages.map(message => (
                <div key={message.id} className={`butler-bootstrap__message butler-bootstrap__message--${message.role}`}>
                  <div className="butler-bootstrap__message-identity"><span className={`butler-bootstrap__message-avatar butler-bootstrap__message-avatar--${message.role}`} aria-hidden="true">{message.role === 'assistant' ? butlerEmoji : t('setup.butler.userLabel')}</span><span className="butler-bootstrap__message-role">{message.role === 'assistant' ? butlerName : t('setup.butler.userLabel')}</span></div>
                  <div className="butler-bootstrap__message-content"><div className="butler-bootstrap__message-bubble"><p>{normalizeMessageContent(message.content || (message.role === 'assistant' && sending ? t('setup.butler.typing') : ''))}</p></div></div>
                </div>
              ))}
              <div ref={messagesEndRef} className="butler-bootstrap__messages-anchor" style={session.status === 'collecting' ? { scrollMarginBottom: `${composerHeight + 40}px` } : undefined} />
            </div>
            {session.status === 'collecting' ? (
              <form ref={composerRef} className="butler-bootstrap__composer" onSubmit={handleSend}>
                <div className="butler-bootstrap__composer-shell">
                  <textarea className="form-input butler-bootstrap__composer-input" value={input} onChange={event => setInput(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder={t('setup.butler.composerPlaceholder')} rows={2} />
                  <div className="butler-bootstrap__composer-footer"><span className="butler-bootstrap__composer-hint">{t('setup.butler.composerHint')}</span><button type="submit" className="btn btn--primary" disabled={sending || !input.trim() || !realtimeReady}>{sending ? t('setup.butler.sending') : t('setup.butler.send')}</button></div>
                </div>
              </form>
            ) : null}
            {session.status === 'reviewing' ? (
              <div className="butler-bootstrap__confirm">
                <div className="butler-bootstrap__review-grid">
                  <div className="form-group"><label>{t('setup.butler.field.name')}</label><input className="form-input" value={session.draft.display_name} onChange={event => updateDraft({ ...session.draft, display_name: event.target.value })} /></div>
                  <div className="form-group"><label>{t('setup.butler.field.style')}</label><input className="form-input" value={session.draft.speaking_style} onChange={event => updateDraft({ ...session.draft, speaking_style: event.target.value })} /></div>
                  <div className="form-group"><label>{t('setup.butler.field.traits')}</label><input className="form-input" value={stringifyTags(session.draft.personality_traits)} onChange={event => updateDraft({ ...session.draft, personality_traits: parseTags(event.target.value) })} /></div>
                </div>
                <button type="button" className="btn btn--primary btn--large" onClick={() => void handleConfirm()} disabled={confirming || !session.draft.display_name.trim() || !session.draft.speaking_style.trim() || session.draft.personality_traits.length < 2}>{confirming ? t('setup.butler.creating') : t('setup.butler.confirmCreate', { name: session.draft.display_name })}</button>
              </div>
            ) : null}
          </div>
        ) : null}
        {!loading && !session && !existingButlerAgent ? <div className="setup-inline-tip"><span>{t('setup.butler.needProvider')}</span></div> : null}
        {createdAgent ? <Card className="butler-bootstrap__result"><div className="butler-bootstrap__created"><span className="butler-bootstrap__avatar-emoji butler-bootstrap__avatar-emoji--large">{getButlerEmoji(createdAgent.display_name)}</span><h4>{createdAgent.display_name}</h4><p>{t('setup.butler.added')}</p></div></Card> : null}
      </Card>
    </div>
  );
}
