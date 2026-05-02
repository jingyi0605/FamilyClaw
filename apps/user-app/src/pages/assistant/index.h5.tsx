import { isValidElement, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import { createBrowserRealtimeClient, newRealtimeRequestId, type BootstrapRealtimeEvent } from '@familyclaw/user-platform/web';
import { EmptyStateCard, UiText, userAppComponentTokens } from '@familyclaw/user-ui';
import { Bot, ChevronDown, Construction, Info, LoaderCircle, MessageSquarePlus, Trash2, Wifi, WifiOff } from 'lucide-react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { ApiError, assistantApi } from './assistant.api';
import { getAgentStatusLabel, getAgentTypeEmoji, isConversationAgent, pickDefaultConversationAgent } from './assistant.agents';
import { SettingsDialog, SettingsNotice } from '../settings/components/SettingsSharedBlocks';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type {
  AgentSummary,
  ConversationActionRecord,
  ConversationMessage,
  ConversationMessageStatus,
  ConversationProposalItem,
  ConversationSession,
  ConversationSessionDetail,
  ScheduledTaskConversationProposalPayload,
} from './assistant.types';
import { GuardedPage, useAuthContext, useHouseholdContext, useI18n, useSetupContext, useTheme } from '../../runtime';
import { useH5PageLayoutMode } from '../../runtime/h5-shell';
import './styles-entry';

type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

type ConversationRealtimeClient = ReturnType<typeof createConversationRealtimeClient>;

const AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 96;
const STREAM_DONE_SYNC_DELAY_MS = 800;
const REALTIME_RECONNECT_MAX_DELAY_MS = 15000;

type RealtimeIndicatorState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

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

function formatMessageTime(value: string, locale: string) {
  const lowerLocale = locale.toLowerCase();
  const normalizedLocale = lowerLocale.startsWith('en') ? 'en-US' : lowerLocale.startsWith('zh-tw') ? 'zh-TW' : 'zh-CN';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const now = new Date();
  const isToday = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
  if (isToday) {
    return date.toLocaleTimeString(normalizedLocale, { hour: '2-digit', minute: '2-digit' });
  }
  const isYesterday = new Date(now);
  isYesterday.setDate(isYesterday.getDate() - 1);
  const wasYesterday = date.getFullYear() === isYesterday.getFullYear()
    && date.getMonth() === isYesterday.getMonth()
    && date.getDate() === isYesterday.getDate();
  if (wasYesterday) {
    return getPageMessage(locale, 'assistant.time.yesterday') + ' ' + date.toLocaleTimeString(normalizedLocale, { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString(normalizedLocale, {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function joinClassNames(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(' ');
}

function getMarkdownLanguage(className?: string) {
  return className?.match(/language-([\w-]+)/)?.[1];
}

function getMarkdownPreLanguage(children: ReactNode) {
  const firstChild = Array.isArray(children) ? children[0] : children;
  if (!isValidElement(firstChild)) return undefined;
  const childProps = (firstChild.props ?? {}) as { className?: unknown };
  return getMarkdownLanguage(typeof childProps.className === 'string' ? childProps.className : undefined);
}

const markdownComponents: Components = {
  p: ({ className, children, ...props }) => (
    <p className={joinClassNames('md-paragraph', className)} {...props}>
      {children}
    </p>
  ),
  h1: ({ className, children, ...props }) => <h1 className={joinClassNames('md-heading', 'md-heading--h1', className)} {...props}>{children}</h1>,
  h2: ({ className, children, ...props }) => <h2 className={joinClassNames('md-heading', 'md-heading--h2', className)} {...props}>{children}</h2>,
  h3: ({ className, children, ...props }) => <h3 className={joinClassNames('md-heading', 'md-heading--h3', className)} {...props}>{children}</h3>,
  h4: ({ className, children, ...props }) => <h4 className={joinClassNames('md-heading', 'md-heading--h4', className)} {...props}>{children}</h4>,
  h5: ({ className, children, ...props }) => <h5 className={joinClassNames('md-heading', 'md-heading--h5', className)} {...props}>{children}</h5>,
  h6: ({ className, children, ...props }) => <h6 className={joinClassNames('md-heading', 'md-heading--h6', className)} {...props}>{children}</h6>,
  strong: ({ className, children, ...props }) => <strong className={joinClassNames('md-bold', className)} {...props}>{children}</strong>,
  em: ({ className, children, ...props }) => <em className={joinClassNames('md-italic', className)} {...props}>{children}</em>,
  del: ({ className, children, ...props }) => <del className={joinClassNames('md-strikethrough', className)} {...props}>{children}</del>,
  a: ({ className, children, href, ...props }) => {
    const isAnchorLink = typeof href === 'string' && href.startsWith('#');
    return (
      <a
        className={joinClassNames('md-link', className)}
        href={href}
        rel={isAnchorLink ? undefined : 'noreferrer'}
        target={isAnchorLink ? undefined : '_blank'}
        {...props}
      >
        {children}
      </a>
    );
  },
  blockquote: ({ className, children, ...props }) => <blockquote className={joinClassNames('md-blockquote', className)} {...props}>{children}</blockquote>,
  pre: ({ className, children, ...props }) => (
    <pre className={joinClassNames('md-code-block', className)} data-lang={getMarkdownPreLanguage(children)} {...props}>
      {children}
    </pre>
  ),
  code: ({ inline, className, children, ...props }: any) => {
    if (inline) {
      return <code className={joinClassNames('md-inline-code', className)} {...props}>{children}</code>;
    }
    return <code className={joinClassNames('md-code', className)} {...props}>{String(children).replace(/\n$/, '')}</code>;
  },
  ul: ({ className, children, ...props }) => <ul className={joinClassNames('md-list', className)} {...props}>{children}</ul>,
  ol: ({ className, children, ...props }) => <ol className={joinClassNames('md-list', 'md-list--ordered', className)} {...props}>{children}</ol>,
  li: ({ className, children, ...props }) => <li className={joinClassNames('md-list-item', className)} {...props}>{children}</li>,
  hr: ({ className, ...props }) => <hr className={joinClassNames('md-divider', className)} {...props} />,
  table: ({ className, children, ...props }) => (
    <div className="md-table-wrap">
      <table className={joinClassNames('md-table', className)} {...props}>{children}</table>
    </div>
  ),
  th: ({ className, children, ...props }) => <th className={joinClassNames('md-table-head', className)} {...props}>{children}</th>,
  td: ({ className, children, ...props }) => <td className={joinClassNames('md-table-cell', className)} {...props}>{children}</td>,
  img: ({ className, alt, src, ...props }) => (
    <img className={joinClassNames('md-image', className)} alt={alt ?? ''} src={src ?? ''} loading="lazy" {...props} />
  ),
  input: ({ className, type, checked, ...props }: any) => {
    if (type !== 'checkbox') return <input className={className} type={type} {...props} />;
    return <input className={joinClassNames('md-task-checkbox', className)} type="checkbox" checked={checked} disabled readOnly {...props} />;
  },
};

function normalizeMarkdownContent(content: string, trim = true): string {
  if (!content) return '';
  const normalized = content.replace(/\r\n/g, '\n');
  return trim ? normalized.trim() : normalized;
}

function normalizeContent(content: string): string {
  return normalizeMarkdownContent(content, true);
}

function normalizeStreamingContent(content: string): string {
  return normalizeMarkdownContent(content, false);
}

function appendStreamingChunk(currentContent: string, chunkText: string): string {
  return normalizeStreamingContent(currentContent) + normalizeStreamingContent(chunkText);
}

function renderMarkdown(content: string, options?: { trim?: boolean; className?: string }) {
  const normalized = normalizeMarkdownContent(content, options?.trim ?? true);
  if (!normalized) return null;
  return (
    <div className={joinClassNames('message__markdown', options?.className)}>
      <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm, remarkBreaks]}>
        {normalized}
      </ReactMarkdown>
    </div>
  );
}

function getMessageStatusPriority(status: ConversationMessageStatus): number {
  if (status === 'failed') return 3;
  if (status === 'completed') return 2;
  if (status === 'streaming') return 1;
  return 0;
}

function pickPreferredMessageStatus(currentStatus: ConversationMessageStatus, incomingStatus: ConversationMessageStatus): ConversationMessageStatus {
  return getMessageStatusPriority(incomingStatus) >= getMessageStatusPriority(currentStatus) ? incomingStatus : currentStatus;
}

function shouldPreserveCurrentAssistantMessage(currentMessage: ConversationMessage, incomingMessage: ConversationMessage): boolean {
  if (currentMessage.role !== 'assistant' || incomingMessage.role !== 'assistant') return false;
  if (currentMessage.id !== incomingMessage.id && currentMessage.request_id !== incomingMessage.request_id) return false;

  const currentContent = normalizeStreamingContent(currentMessage.content);
  const incomingContent = normalizeStreamingContent(incomingMessage.content);
  if (!currentContent || currentContent === incomingContent) return false;

  return currentContent.length > incomingContent.length
    && getMessageStatusPriority(currentMessage.status) >= getMessageStatusPriority(incomingMessage.status);
}

function areStringArraysEqual(current: string[], incoming: string[]): boolean {
  return current.length === incoming.length && current.every((item, index) => item === incoming[index]);
}

function areConversationMessagesEquivalent(currentMessage: ConversationMessage, incomingMessage: ConversationMessage): boolean {
  return currentMessage.id === incomingMessage.id
    && currentMessage.session_id === incomingMessage.session_id
    && currentMessage.request_id === incomingMessage.request_id
    && currentMessage.seq === incomingMessage.seq
    && currentMessage.role === incomingMessage.role
    && currentMessage.message_type === incomingMessage.message_type
    && currentMessage.content === incomingMessage.content
    && currentMessage.status === incomingMessage.status
    && currentMessage.effective_agent_id === incomingMessage.effective_agent_id
    && currentMessage.ai_provider_code === incomingMessage.ai_provider_code
    && currentMessage.ai_trace_id === incomingMessage.ai_trace_id
    && currentMessage.degraded === incomingMessage.degraded
    && currentMessage.error_code === incomingMessage.error_code
    && currentMessage.created_at === incomingMessage.created_at
    && currentMessage.updated_at === incomingMessage.updated_at
    && areStringArraysEqual(currentMessage.suggestions, incomingMessage.suggestions)
    && currentMessage.facts.length === incomingMessage.facts.length
    && currentMessage.facts.every((fact, index) => buildFactIdentity(fact) === buildFactIdentity(incomingMessage.facts[index]));
}

function mergeConversationMessage(currentMessage: ConversationMessage, incomingMessage: ConversationMessage): ConversationMessage {
  const preserveCurrentMessage = shouldPreserveCurrentAssistantMessage(currentMessage, incomingMessage);
  const mergedMessage: ConversationMessage = {
    ...incomingMessage,
    content: preserveCurrentMessage ? currentMessage.content : incomingMessage.content,
    status: preserveCurrentMessage
      ? currentMessage.status
      : pickPreferredMessageStatus(currentMessage.status, incomingMessage.status),
  };

  return areConversationMessagesEquivalent(currentMessage, mergedMessage) ? currentMessage : mergedMessage;
}

function mergeConversationSessionDetail(
  currentDetail: ConversationSessionDetail | null,
  incomingDetail: ConversationSessionDetail,
): ConversationSessionDetail {
  if (!currentDetail || currentDetail.id !== incomingDetail.id) {
    return incomingDetail;
  }

  const currentMessagesById = new Map(currentDetail.messages.map(message => [message.id, message]));
  const currentMessagesByRequestKey = new Map(
    currentDetail.messages
      .filter(message => message.request_id)
      .map(message => [`${message.role}:${message.request_id}`, message]),
  );
  return {
    ...incomingDetail,
    messages: incomingDetail.messages.map(message => {
      const currentMessage = currentMessagesById.get(message.id)
        ?? (message.request_id ? currentMessagesByRequestKey.get(`${message.role}:${message.request_id}`) : undefined);
      return currentMessage ? mergeConversationMessage(currentMessage, message) : message;
    }),
  };
}

function isScrolledNearBottom(container: HTMLDivElement): boolean {
  return container.scrollHeight - container.scrollTop - container.clientHeight <= AUTO_SCROLL_BOTTOM_THRESHOLD_PX;
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

function pickNextSessionIdAfterDeletion(
  sessions: ConversationSession[],
  deletedSessionId: string,
  activeSessionId: string,
) {
  if (deletedSessionId !== activeSessionId) {
    return activeSessionId;
  }
  const deletedIndex = sessions.findIndex(item => item.id === deletedSessionId);
  const remainingSessions = sessions.filter(item => item.id !== deletedSessionId);
  if (remainingSessions.length === 0) {
    return '';
  }
  return remainingSessions[deletedIndex]?.id
    ?? remainingSessions[Math.max(0, deletedIndex - 1)]?.id
    ?? remainingSessions[0]?.id
    ?? '';
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
  if (action.action_name === 'reminder.create') return 'REM';
  if (action.action_category === 'config') return 'CFG';
  return 'ACT';
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
  if (item.proposal_kind === 'scheduled_task_create') return 'NEW';
  if (item.proposal_kind === 'scheduled_task_update') return 'UPD';
  if (item.proposal_kind === 'scheduled_task_pause') return 'PAUSE';
  if (item.proposal_kind === 'scheduled_task_resume') return 'RUN';
  if (item.proposal_kind === 'scheduled_task_delete') return 'DEL';
  if (item.proposal_kind === 'reminder_create') return 'REM';
  if (item.proposal_kind === 'config_apply') return 'CFG';
  return 'ACT';
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

function getLatestConfigMutationKey(snapshot: ConversationSessionDetail): string {
  const latestConfigAction = [...(snapshot.action_records ?? [])]
    .reverse()
    .find(action => action.action_name === 'config.apply' && action.status === 'completed');
  if (latestConfigAction) {
    return `action:${latestConfigAction.id}:${latestConfigAction.updated_at}`;
  }

  for (const batch of [...(snapshot.proposal_batches ?? [])].reverse()) {
    const latestConfigProposal = [...batch.items]
      .reverse()
      .find(item => item.proposal_kind === 'config_apply' && item.status === 'completed');
    if (latestConfigProposal) {
      return `proposal:${latestConfigProposal.id}:${latestConfigProposal.updated_at}`;
    }
  }
  return '';
}

async function goToPage(url: string) {
  await Taro.navigateTo({ url }).catch(() => undefined);
}

function AssistantPageContent() {
  const { actor } = useAuthContext();
  const { setupStatus } = useSetupContext();
  const { currentHouseholdId, currentHousehold } = useHouseholdContext();
  const { t, locale } = useI18n();
  const layoutMode = useH5PageLayoutMode('assistant');
  const { themeId } = useTheme();
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [activeSessionDetail, setActiveSessionDetail] = useState<ConversationSessionDetail | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(false);
  const [isRealtimePopoverOpen, setIsRealtimePopoverOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState('');
  const [pendingDeleteSession, setPendingDeleteSession] = useState<ConversationSession | null>(null);
  const [realtimeReady, setRealtimeReady] = useState(false);
  const [realtimeState, setRealtimeState] = useState<RealtimeIndicatorState>('connecting');
  const [realtimeReconnectNonce, setRealtimeReconnectNonce] = useState(0);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [actionBusyId, setActionBusyId] = useState('');
  const [expandedAutoMessageId, setExpandedAutoMessageId] = useState('');
  const [activeChatTab, setActiveChatTab] = useState<'personal' | 'public' | 'moments'>('personal');
  const realtimeClientRef = useRef<ConversationRealtimeClient | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const realtimeConnectionTokenRef = useRef(0);
  const pendingSyncTimerRef = useRef<number | null>(null);
  const latestConfigMutationRef = useRef('');
  const scrollFrameRef = useRef<number | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const sendingRef = useRef(false);
  const sessionsRef = useRef<ConversationSession[]>([]);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const realtimeSignalAnchorRef = useRef<HTMLDivElement | null>(null);
  const listBullet = '-';
  const conversationAgents = useMemo(() => agents.filter(isConversationAgent), [agents]);
  const defaultAgent = useMemo(() => pickDefaultConversationAgent(agents), [agents]);
  const selectedAgent = useMemo(
    () => agents.find(item => item.id === selectedAgentId) ?? defaultAgent,
    [agents, defaultAgent, selectedAgentId],
  );
  const canSwitchAgent = conversationAgents.length > 1;
  const realtimeStatusLabel = useMemo(() => {
    if (realtimeState === 'connected') return t('assistant.realtime.connected');
    if (realtimeState === 'reconnecting') return t('assistant.realtime.reconnecting');
    if (realtimeState === 'disconnected') return t('assistant.realtime.disconnected');
    return t('assistant.realtime.connecting');
  }, [realtimeState, t]);
  const realtimeStatusClassName = useMemo(() => {
    if (realtimeState === 'connected') return 'assistant-page-header__btn--signal-online';
    if (realtimeState === 'reconnecting' || realtimeState === 'connecting') return 'assistant-page-header__btn--signal-pending';
    return 'assistant-page-header__btn--signal-offline';
  }, [realtimeState]);
  const realtimeStatusIcon = useMemo(() => {
    if (realtimeState === 'connected') return <Wifi size={18} />;
    if (realtimeState === 'reconnecting' || realtimeState === 'connecting') return <LoaderCircle size={18} className="assistant-page-header__signal-spinner" />;
    return <WifiOff size={18} />;
  }, [realtimeState]);
  const realtimeStatusDescription = useMemo(() => {
    if (realtimeState === 'connected') return t('assistant.realtime.help.connected');
    if (realtimeState === 'reconnecting') return t('assistant.realtime.help.reconnecting');
    if (realtimeState === 'disconnected') return t('assistant.realtime.help.disconnected');
    return t('assistant.realtime.help.connecting');
  }, [realtimeState, t]);
  const realtimeReconnectBusy = realtimeState === 'connecting' || realtimeState === 'reconnecting';
  const realtimeReconnectAvailable = Boolean(currentHouseholdId && activeSessionId);

  useEffect(() => {
    if (!layoutMode.isTouchLayout) {
      return;
    }
    setContextPanelOpen(false);
  }, [layoutMode.isTouchLayout]);

  useEffect(() => {
    if (!layoutMode.isTouchLayout) {
      return;
    }
    setIsRealtimePopoverOpen(false);
  }, [layoutMode.isTouchLayout]);

  useEffect(() => {
    if (!isRealtimePopoverOpen) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (realtimeSignalAnchorRef.current?.contains(target)) {
        return;
      }
      setIsRealtimePopoverOpen(false);
    };
    window.addEventListener('mousedown', handlePointerDown);
    return () => {
      window.removeEventListener('mousedown', handlePointerDown);
    };
  }, [isRealtimePopoverOpen]);

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

  async function refreshConversationAgents(preferredAgentId?: string) {
    if (!currentHouseholdId) return;
    try {
      const result = await assistantApi.listAgents(currentHouseholdId);
      const nextAgents = result.items;
      setAgents(nextAgents);
      const nextConversationAgents = nextAgents.filter(isConversationAgent);
      const fallbackAgentId = pickDefaultConversationAgent(nextAgents)?.id ?? '';
      const preferred = preferredAgentId ?? selectedAgentId;
      const preferredIsValid = preferred ? nextConversationAgents.some(agent => agent.id === preferred) : false;
      const nextSelectedAgentId = preferredIsValid ? preferred : fallbackAgentId;
      setSelectedAgentId(current => (current === nextSelectedAgentId ? current : nextSelectedAgentId));
    } catch {
      // 蹇界暐鍒锋柊澶辫触锛岄伩鍏嶆墦鏂富瀵硅瘽娴佺▼銆?
    }
  }

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
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    setIsSidebarOpen(false);
    setContextPanelOpen(false);
  }, [actor?.authenticated, currentHouseholdId, locale, setupStatus?.is_required, themeId]);

  useEffect(() => {
    shouldStickToBottomRef.current = true;
  }, [activeSessionId]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const updateStickToBottom = () => {
      shouldStickToBottomRef.current = isScrolledNearBottom(container);
    };
    updateStickToBottom();
    container.addEventListener('scroll', updateStickToBottom, { passive: true });
    return () => {
      container.removeEventListener('scroll', updateStickToBottom);
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    };
  }, [activeSessionId]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || !shouldStickToBottomRef.current) return;

    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
    }
    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'auto',
      });
    });
  }, [activeSessionDetail?.messages, activeSessionDetail?.action_records, activeSessionDetail?.proposal_batches]);

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
        setSelectedAgentId(pickDefaultConversationAgent(agentResult.items)?.id ?? '');
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
        applyIncomingSessionDetail(detail);
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

  function applyIncomingSessionDetail(detail: ConversationSessionDetail, expectedSessionId?: string) {
    const targetSessionId = expectedSessionId ?? activeSessionId;
    setActiveSessionDetail(current => {
      if (targetSessionId && targetSessionId !== detail.id && current?.id !== detail.id) {
        return current;
      }
      return mergeConversationSessionDetail(current, detail);
    });
    setSessions(current => upsertSession(current, detail));
    if (detail.id === targetSessionId) {
      const latestMessage = [...detail.messages].reverse().find(item => item.role === 'assistant');
      setSuggestions(latestMessage?.suggestions ?? []);
    }
  }

  async function syncActiveSessionDetail(sessionId?: string) {
    const targetSessionId = sessionId ?? activeSessionId;
    if (!targetSessionId) return;
    try {
      const detail = await assistantApi.getConversationSession(targetSessionId);
      applyIncomingSessionDetail(detail, targetSessionId);
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

  function resetRealtimeReconnectTimer() {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }

  function schedulePendingSync(sessionId: string, delayMs: number, stopSendingAfterSync = false) {
    resetPendingSyncTimer();
    pendingSyncTimerRef.current = window.setTimeout(() => {
      pendingSyncTimerRef.current = null;
      void syncActiveSessionDetail(sessionId);
      if (stopSendingAfterSync) {
        setSending(false);
      }
    }, delayMs);
  }

  useEffect(() => {
    if (!currentHouseholdId || !activeSessionId) {
      realtimeConnectionTokenRef.current += 1;
      resetRealtimeReconnectTimer();
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setRealtimeReady(false);
      setRealtimeState('disconnected');
      return;
    }

    let disposed = false;
    reconnectAttemptRef.current = 0;
    setRealtimeState('connecting');

    const scheduleRealtimeReconnect = () => {
      if (disposed || reconnectTimerRef.current !== null) return;
      const delay = Math.min(1000 * 2 ** reconnectAttemptRef.current, REALTIME_RECONNECT_MAX_DELAY_MS);
      setRealtimeState('reconnecting');
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        reconnectAttemptRef.current += 1;
        connectRealtime();
      }, delay);
    };

    const handleRealtimeDisconnected = (token: number) => {
      if (disposed || token !== realtimeConnectionTokenRef.current) return;
      setRealtimeReady(false);
      if (sendingRef.current) {
        void syncActiveSessionDetail(activeSessionId);
        setSending(false);
      }
      scheduleRealtimeReconnect();
    };

    const connectRealtime = () => {
      if (disposed) return;
      const token = realtimeConnectionTokenRef.current + 1;
      realtimeConnectionTokenRef.current = token;
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setRealtimeReady(false);
      setRealtimeState(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting');
      let disconnectHandled = false;

      realtimeClientRef.current = createConversationRealtimeClient({
        householdId: currentHouseholdId,
        sessionId: activeSessionId,
        onOpen: () => {
          if (disposed || token !== realtimeConnectionTokenRef.current) return;
          resetRealtimeReconnectTimer();
          resetPendingSyncTimer();
          reconnectAttemptRef.current = 0;
          setRealtimeReady(true);
          setRealtimeState('connected');
          void syncActiveSessionDetail(activeSessionId);
        },
        onClose: () => {
          if (disconnectHandled) return;
          disconnectHandled = true;
          handleRealtimeDisconnected(token);
        },
        onError: () => {
          if (disconnectHandled) return;
          disconnectHandled = true;
          handleRealtimeDisconnected(token);
        },
        onEvent: event => {
          if (disposed || token !== realtimeConnectionTokenRef.current) return;
          if (event.type === 'session.snapshot') {
            const nextSession = (event.payload as { snapshot: ConversationSessionDetail }).snapshot;
            applyIncomingSessionDetail(nextSession);
            if (nextSession.messages.some(message => message.status === 'completed' || message.status === 'failed')) {
              resetPendingSyncTimer();
            }
            const mutationKey = getLatestConfigMutationKey(nextSession);
            if (mutationKey && mutationKey !== latestConfigMutationRef.current) {
              latestConfigMutationRef.current = mutationKey;
              void refreshConversationAgents(nextSession.active_agent_id ?? undefined);
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
                      content: appendStreamingChunk(message.content, chunkText),
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
            schedulePendingSync(activeSessionId, STREAM_DONE_SYNC_DELAY_MS);
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
    };

    connectRealtime();

    return () => {
      disposed = true;
      realtimeConnectionTokenRef.current += 1;
      resetRealtimeReconnectTimer();
      resetPendingSyncTimer();
      realtimeClientRef.current?.close();
      realtimeClientRef.current = null;
      setRealtimeReady(false);
      setRealtimeState('disconnected');
    };
  }, [activeSessionId, currentHouseholdId, realtimeReconnectNonce]);

  useEffect(() => {
    const nextSessionAgent = agents.find(agent => agent.id === activeSessionDetail?.active_agent_id);
    const nextAgentId = nextSessionAgent && isConversationAgent(nextSessionAgent)
      ? nextSessionAgent.id
      : (defaultAgent?.id ?? '');
    if (nextAgentId && nextAgentId !== selectedAgentId) {
      setSelectedAgentId(nextAgentId);
    }
  }, [activeSessionDetail?.active_agent_id, agents, defaultAgent?.id, selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const isSelectedConversationAgent = conversationAgents.some(agent => agent.id === selectedAgentId);
    if (!isSelectedConversationAgent) {
      setSelectedAgentId(defaultAgent?.id ?? '');
    }
  }, [conversationAgents, defaultAgent?.id, selectedAgentId]);

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

  function handleSessionSelect(session: ConversationSession) {
    if (!session.id || session.id === activeSessionId) {
      setIsSidebarOpen(false);
      return;
    }
    shouldStickToBottomRef.current = true;
    setError('');
    setStatus('');
    setSuggestions([]);
    setActiveSessionId(session.id);
    setActiveSessionDetail(null);
    setIsSidebarOpen(false);
    void syncActiveSessionDetail(session.id);
  }

  function handleRealtimeIndicatorClick() {
    setIsSidebarOpen(false);
    setIsRealtimePopoverOpen(current => !current);
  }

  function handleManualRealtimeReconnect() {
    if (!currentHouseholdId || !activeSessionId || realtimeReconnectBusy) {
      return;
    }
    setError('');
    setStatus('');
    setIsRealtimePopoverOpen(true);
    resetRealtimeReconnectTimer();
    reconnectAttemptRef.current = 0;
    realtimeConnectionTokenRef.current += 1;
    realtimeClientRef.current?.close();
    realtimeClientRef.current = null;
    setRealtimeReady(false);
    setRealtimeState('connecting');
    setRealtimeReconnectNonce(current => current + 1);
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

  function handleSessionDeleteRequest(session: ConversationSession) {
    const isDeletingActiveSession = session.id === activeSessionId;
    if (isDeletingActiveSession && sending) {
      setError(t('assistant.error.deleteSessionBusy'));
      setStatus('');
      return;
    }
    setPendingDeleteSession(session);
  }

  async function handleSessionDelete(session: ConversationSession) {
    const isDeletingActiveSession = session.id === activeSessionId;
    setDeletingSessionId(session.id);
    setError('');
    setStatus('');
    try {
      await assistantApi.deleteConversationSession(session.id);
      const currentSessions = sessionsRef.current;
      const remainingSessions = currentSessions.filter(item => item.id !== session.id);
      const nextActiveSessionId = pickNextSessionIdAfterDeletion(currentSessions, session.id, activeSessionId);
      sessionsRef.current = remainingSessions;
      setSessions(remainingSessions);

      if (isDeletingActiveSession) {
        // 当前会话被删掉后，必须立刻清空旧详情，避免残留消息短暂回闪。
        shouldStickToBottomRef.current = true;
        setSending(false);
        setSuggestions([]);
        setExpandedAutoMessageId('');
        setActiveSessionDetail(null);
        setActiveSessionId(nextActiveSessionId);
      }

      setPendingDeleteSession(null);
      setStatus(t('assistant.deleteSessionSuccess'));
      setError('');
    } catch (deleteError) {
      if (deleteError instanceof ApiError) {
        if (deleteError.status === 409) {
          setError(t('assistant.error.deleteSessionBusy'));
        } else {
          setError(deleteError.message || t('assistant.error.deleteSessionFailed'));
        }
      } else {
        setError(t('assistant.error.deleteSessionFailed'));
      }
      setPendingDeleteSession(null);
      setStatus('');
    } finally {
      setDeletingSessionId('');
    }
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
    shouldStickToBottomRef.current = true;
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
      schedulePendingSync(session.id, 20000, true);
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
        <div className="message__action-meta">{t('assistant.action.notifyModeLabel')}</div>
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
          <span className="message__action-meta">{t('assistant.action.autoModeLabel')}</span>
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

  function renderMessageBody(message: ConversationMessage) {
    if (message.role === 'assistant' && message.status === 'streaming') {
      return renderMarkdown(
        message.content || t('assistant.message.preparingReply'),
        { trim: false, className: 'message__markdown--streaming' },
      );
    }

    return renderMarkdown(message.content || (message.status === 'pending' ? t('assistant.message.preparingReply') : ''));
  }

  function renderSessionHistoryPopover(extraClassName = '') {
    const isDeletingAnySession = Boolean(deletingSessionId);
    return (
      <div className={`assistant-popover ${extraClassName}`.trim()} onClick={event => event.stopPropagation()}>
        <div className="assistant-popover__header">
          <span>{t('nav.assistant')}</span>
          <button className="btn btn--icon btn--ghost p-xs" onClick={() => void handleNewChat()} title={t('assistant.newChat')}>
            <MessageSquarePlus size={16} />
          </button>
        </div>
        <div className="assistant-popover__content">
          {loading ? (
            <div className="context-memory-item">
              <span>!</span> {t('assistant.error.loadConversations')}
            </div>
          ) : sessions.length === 0 ? (
            <div className="context-memory-item">
              <span>[ ]</span> {t('assistant.noSessions')}
            </div>
          ) : (
            sessions.map(session => (
              <div
                key={session.id}
                className={`session-item session-item--compact ${activeSessionId === session.id ? 'session-item--active' : ''} ${deletingSessionId === session.id ? 'session-item--busy' : ''}`.trim()}
              >
                <button
                  type="button"
                  className="session-item__main"
                  disabled={isDeletingAnySession}
                  onClick={event => {
                    event.stopPropagation();
                    handleSessionSelect(session);
                  }}
                >
                  <div className="session-item__content">
                    <span className="session-item__title">{session.title}</span>
                    <span className="session-item__preview">{session.latest_message_preview ?? t('assistant.welcomeHint')}</span>
                  </div>
                  <span className="session-item__time">{formatRelativeTime(session.last_message_at, locale)}</span>
                </button>
                <button
                  type="button"
                  className="session-item__delete btn btn--icon btn--ghost p-xs"
                  title={t('assistant.deleteSession')}
                  aria-label={t('assistant.deleteSession')}
                  disabled={isDeletingAnySession || (session.id === activeSessionId && sending)}
                  onClick={event => {
                    event.stopPropagation();
                    handleSessionDeleteRequest(session);
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  function renderRealtimeStatusPopover(extraClassName = '') {
    return (
      <div className={`assistant-popover assistant-popover--signal ${extraClassName}`.trim()} onClick={event => event.stopPropagation()}>
        <div className="assistant-popover__header">
          <span>{t('assistant.realtime.title')}</span>
        </div>
        <div className="assistant-popover__content assistant-realtime-popover">
          <div className={`assistant-realtime-popover__status ${realtimeStatusClassName}`.trim()}>
            {realtimeStatusIcon}
            <span>{realtimeStatusLabel}</span>
          </div>
          <div className="assistant-realtime-popover__description">{realtimeStatusDescription}</div>
          <div className="assistant-realtime-popover__hint">
            {realtimeReconnectAvailable
              ? t('assistant.realtime.autoReconnectHint')
              : t('assistant.realtime.manualReconnectUnavailable')}
          </div>
          <button
            type="button"
            className="btn btn--primary assistant-realtime-popover__reconnect-btn"
            onClick={() => handleManualRealtimeReconnect()}
            disabled={!realtimeReconnectAvailable || realtimeReconnectBusy}
          >
            {realtimeReconnectBusy ? t('assistant.realtime.manualReconnectBusy') : t('assistant.realtime.manualReconnect')}
          </button>
        </div>
      </div>
    );
  }

  if (!currentHouseholdId && !loading) {
    return (
      <div className="page page--assistant">
        <EmptyState icon="CHAT" title={t('assistant.noSessions')} description={t('assistant.noSessionsHint')} />
      </div>
    );
  }

  if (!loading && conversationAgents.length === 0) {
    return (
      <div className="page page--assistant">
        <EmptyState
          icon="BOT"
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
    <div
      className="page page--assistant"
      data-layout-mode={layoutMode.id}
      data-layout-touch={layoutMode.isTouchLayout ? 'true' : 'false'}
      data-layout-panel={layoutMode.panelBehavior}
    >
      {!layoutMode.isTouchLayout && isSidebarOpen ? <div className="assistant-popover-overlay" onClick={() => setIsSidebarOpen(false)} /> : null}

      <div className="assistant-desktop-header">
        <UiText
          className="assistant-desktop-header__page-title page-header__title"
          variant="title"
          style={{ fontSize: userAppComponentTokens.pageHeader.titleFontSize }}
        >
          {t('nav.assistant')}
        </UiText>

        <div className="assistant-desktop-header__body">
          <div className="memory-main-tabs assistant-desktop-header__tabs" role="tablist" aria-label={t('nav.assistant')}>
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

          <div className="assistant-page-header__session-anchor">
            <button
              type="button"
              className="memory-main-tab assistant-page-header__session-title"
              onClick={() => setIsSidebarOpen(prev => !prev)}
              title={t('assistant.sessionList')}
            >
              <span className="assistant-page-header__title-text">{activeSessionDetail?.title || t('assistant.newChat')}</span>
              <ChevronDown size={16} className={`assistant-page-header__chevron ${isSidebarOpen ? 'assistant-page-header__chevron--open' : ''}`} />
            </button>

            {!layoutMode.isTouchLayout && isSidebarOpen ? renderSessionHistoryPopover('assistant-popover--desktop') : null}
          </div>

          <div className="assistant-page-header__actions">
            <div className="assistant-page-header__signal-anchor" ref={realtimeSignalAnchorRef}>
              <button
                className={`memory-main-tab assistant-page-header__btn assistant-page-header__btn--signal ${realtimeStatusClassName}`.trim()}
                type="button"
                title={realtimeStatusLabel}
                aria-label={realtimeStatusLabel}
                onClick={handleRealtimeIndicatorClick}
                aria-expanded={isRealtimePopoverOpen ? 'true' : 'false'}
              >
                {realtimeStatusIcon}
              </button>
              {isRealtimePopoverOpen ? renderRealtimeStatusPopover() : null}
            </div>
            <button
              className="memory-main-tab assistant-page-header__btn"
              onClick={() => void handleNewChat()}
              title={t('assistant.newChat')}
              aria-label={t('assistant.newChat')}
            >
              <MessageSquarePlus size={18} />
            </button>
            <button
              className="memory-main-tab assistant-page-header__btn"
              onClick={() => setContextPanelOpen(true)}
              title={t('assistant.panel.details')}
              aria-label={t('assistant.panel.details')}
            >
              <Info size={18} />
            </button>
          </div>
        </div>
      </div>

      {error ? (
        <div className="assistant-feedback assistant-feedback--error" role="alert">
          {error}
        </div>
      ) : null}
      {!error && status ? (
        <div className="assistant-feedback assistant-feedback--success" role="status" aria-live="polite">
          {status}
        </div>
      ) : null}

      {activeChatTab !== 'personal' ? renderComingSoonTab() : (
        <>
          {contextPanelOpen ? <div className="assistant-panel-overlay" onClick={() => setContextPanelOpen(false)} /> : null}
          <div className={`assistant-panel assistant-panel--right ${contextPanelOpen ? 'is-open' : ''}`.trim()}>
            <div className="assistant-panel__header">
              <h3>{t('assistant.panel.details')}</h3>
              <button className="btn btn--icon btn--ghost p-sm" onClick={() => setContextPanelOpen(false)}>
                x
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
        {/* 绉诲姩绔悎骞跺悗鐨勬爣棰樻爮銆?*/}
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

        {layoutMode.isTouchLayout && isSidebarOpen ? (
          <>
            <div className="assistant-popover-overlay" onClick={() => setIsSidebarOpen(false)} />
            {renderSessionHistoryPopover()}
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
                        <span>{selectedAgent ? getAgentTypeEmoji(selectedAgent.agent_type) : 'AI'}</span>
                      ) : (
                        <span>{t('assistant.you')}</span>
                      )}
                    </div>
                    <div className="message__content-wrapper">
                      <div className="message__bubble">
                        <div className="message__content">
                          {renderMessageBody(message)}
                        </div>
                        {message.degraded ? <span className="message__memory-tag">[!] {t('assistant.message.responseDegraded')}</span> : null}
                        {message.status === 'streaming' ? <span className="message__memory-tag">[...] {t('assistant.message.generating')}</span> : null}
                        {message.status === 'failed' ? <span className="message__memory-tag">[x] {t('assistant.message.turnFailed')}</span> : null}
                        {message.created_at ? (
                          <div className="message__time">{formatMessageTime(message.created_at, locale)}</div>
                        ) : null}
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
                <div className="assistant-main__empty">
                  <EmptyState
                    icon="CHAT"
                    title={t('assistant.welcome')}
                    description={t('assistant.welcomeHint')}
                    className="assistant-main__empty-card"
                  />
                </div>
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

          </>
        ) : (
          <EmptyState
            icon="CHAT"
            title={t('assistant.noSessions')}
            description={t('assistant.noSessionsHint')}
            action={<button className="btn btn--primary" onClick={() => void handleNewChat()}>{t('assistant.newChat')}</button>}
          />
        )}
          </div>
        </>
      )}

      {pendingDeleteSession ? (
        <SettingsDialog
          open
          title={t('assistant.deleteSession')}
          description={t('assistant.deleteSessionDialogDesc')}
          className="assistant-delete-session-modal"
          closeDisabled={Boolean(deletingSessionId)}
          onClose={() => setPendingDeleteSession(null)}
          actions={(
            <>
              <button
                type="button"
                className="btn btn--outline btn--sm"
                onClick={() => setPendingDeleteSession(null)}
                disabled={Boolean(deletingSessionId)}
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={() => void handleSessionDelete(pendingDeleteSession)}
                disabled={Boolean(deletingSessionId)}
              >
                {deletingSessionId === pendingDeleteSession.id
                  ? t('assistant.deleteSessionDeleting')
                  : t('assistant.deleteSessionConfirmAction')}
              </button>
            </>
          )}
        >
          <div className="settings-form__body">
            <SettingsNotice tone="error" icon={<Trash2 size={18} />}>
              {t('assistant.deleteSessionConfirm', {
                title: pendingDeleteSession.title?.trim() || t('assistant.newChat'),
              })}
            </SettingsNotice>
          </div>
        </SettingsDialog>
      ) : null}
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
