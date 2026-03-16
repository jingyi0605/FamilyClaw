import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import { useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { ApiError, settingsApi } from '../settingsApi';
import { SettingsDialog, SettingsEmptyState, SettingsNotice } from './SettingsSharedBlocks';
import type {
  ChannelBindingCandidateRead,
  Member,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginRegistryItem,
} from '../settingsTypes';

type ChannelAccountBindingsPanelProps = {
  householdId: string;
  accountId: string;
  members: Member[];
  plugin: PluginRegistryItem | null;
  supportsMemberBinding: boolean;
};

type BindingLabels = {
  identityLabel: string;
  identityPlaceholder: string;
  identityHelpText: string;
  chatLabel: string;
  chatPlaceholder: string;
  chatHelpText: string;
  candidateTitle: string;
  candidateHelpText: string;
};

function resolveDateLocale(locale: string | undefined) {
  if (locale?.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return 'zh-TW';
  }
  return 'zh-CN';
}

function formatTimestamp(value: string, locale: string | undefined): string {
  try {
    return new Date(value).toLocaleString(resolveDateLocale(locale));
  } catch {
    return value;
  }
}

function formatApiErrorMessage(error: ApiError, locale: string | undefined): string {
  const payload = error.payload as { detail?: unknown } | undefined;
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const message = 'msg' in item && typeof item.msg === 'string' ? item.msg : null;
        const location = 'loc' in item && Array.isArray(item.loc)
          ? item.loc
            .filter((part: unknown): part is string | number => typeof part === 'string' || typeof part === 'number')
            .join('.')
          : '';
        if (message && location) {
          return `${location}: ${message}`;
        }
        return message;
      })
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) {
      return messages.join('; ');
    }
  }
  return error.message || getPageMessage(locale, 'settings.channel.binding.saveFailed');
}

function buildDisplayHint(candidate: ChannelBindingCandidateRead): string {
  const parts = [
    candidate.sender_display_name,
    candidate.username ? `@${candidate.username}` : null,
  ].filter((item): item is string => Boolean(item && item.trim()));
  return parts.join(' ');
}

function resolveBindingLabels(plugin: PluginRegistryItem | null, locale: string | undefined): BindingLabels {
  const bindingUi = plugin?.capabilities.channel?.ui?.binding;
  return {
    identityLabel: bindingUi?.identity_label ?? getPageMessage(locale, 'settings.channel.binding.identityLabel'),
    identityPlaceholder: bindingUi?.identity_placeholder ?? getPageMessage(locale, 'settings.channel.binding.identityPlaceholder'),
    identityHelpText: bindingUi?.identity_help_text ?? getPageMessage(locale, 'settings.channel.binding.identityHelpText'),
    chatLabel: bindingUi?.chat_label ?? getPageMessage(locale, 'settings.channel.binding.chatLabel'),
    chatPlaceholder: bindingUi?.chat_placeholder ?? getPageMessage(locale, 'settings.channel.binding.chatPlaceholder'),
    chatHelpText: bindingUi?.chat_help_text ?? getPageMessage(locale, 'settings.channel.binding.chatHelpText'),
    candidateTitle: bindingUi?.candidate_title ?? getPageMessage(locale, 'settings.channel.binding.candidateTitle'),
    candidateHelpText: bindingUi?.candidate_help_text ?? getPageMessage(locale, 'settings.channel.binding.candidateHelpText'),
  };
}

export function ChannelAccountBindingsPanel({
  householdId,
  accountId,
  members,
  plugin,
  supportsMemberBinding,
}: ChannelAccountBindingsPanelProps) {
  const { locale } = useI18n();
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [candidates, setCandidates] = useState<ChannelBindingCandidateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<MemberChannelBindingRead | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [formError, setFormError] = useState('');
  const [form, setForm] = useState<{
    member_id: string;
    external_user_id: string;
    external_chat_id: string;
    display_hint: string;
    binding_status: 'active' | 'disabled';
  }>({
    member_id: '',
    external_user_id: '',
    external_chat_id: '',
    display_hint: '',
    binding_status: 'active',
  });

  const labels = useMemo(() => resolveBindingLabels(plugin, locale), [locale, plugin]);
  const memberMap = useMemo(() => new Map(members.map((member) => [member.id, member])), [members]);
  const copy = useMemo(() => ({
    saveFailed: getPageMessage(locale, 'settings.channel.binding.saveFailed'),
    loadFailed: getPageMessage(locale, 'settings.channel.binding.loadFailed'),
    selectMember: getPageMessage(locale, 'settings.channel.binding.selectMember'),
    fillIdentity: (label: string) => getPageMessage(locale, 'settings.channel.binding.fillIdentity', { label }),
    updated: getPageMessage(locale, 'settings.channel.binding.updated'),
    created: getPageMessage(locale, 'settings.channel.binding.created'),
    restored: getPageMessage(locale, 'settings.channel.binding.restored'),
    disabled: getPageMessage(locale, 'settings.channel.binding.disabled'),
    toggleFailed: getPageMessage(locale, 'settings.channel.binding.toggleFailed'),
    deleteTitle: getPageMessage(locale, 'settings.channel.binding.deleteTitle'),
    deleteContent: getPageMessage(locale, 'settings.channel.binding.deleteContent'),
    deleted: getPageMessage(locale, 'settings.channel.binding.deleted'),
    deleteFailed: getPageMessage(locale, 'settings.channel.binding.deleteFailed'),
    unsupported: getPageMessage(locale, 'settings.channel.binding.unsupported'),
    loadingCandidates: getPageMessage(locale, 'settings.channel.binding.loadingCandidates'),
    emptyCandidates: getPageMessage(locale, 'settings.channel.binding.emptyCandidates'),
    latestMessage: getPageMessage(locale, 'settings.channel.binding.latestMessage'),
    chatTypeGroup: getPageMessage(locale, 'settings.channel.binding.chatType.group'),
    chatTypeDirect: getPageMessage(locale, 'settings.channel.binding.chatType.direct'),
    bindNow: getPageMessage(locale, 'settings.channel.binding.bindNow'),
    loading: getPageMessage(locale, 'settings.channel.binding.loading'),
    empty: getPageMessage(locale, 'settings.channel.binding.empty'),
    add: getPageMessage(locale, 'settings.channel.binding.add'),
    count: (count: number) => getPageMessage(locale, 'settings.channel.binding.count', { count }),
    unknownMember: getPageMessage(locale, 'settings.channel.binding.unknownMember'),
    active: getPageMessage(locale, 'settings.channel.binding.active'),
    inactive: getPageMessage(locale, 'settings.channel.binding.inactive'),
    edit: getPageMessage(locale, 'settings.channel.binding.edit'),
    disable: getPageMessage(locale, 'settings.channel.binding.disable'),
    restore: getPageMessage(locale, 'settings.channel.binding.restore'),
    delete: getPageMessage(locale, 'settings.channel.binding.delete'),
    modalEditTitle: getPageMessage(locale, 'settings.channel.binding.modalEditTitle'),
    modalCreateTitle: getPageMessage(locale, 'settings.channel.binding.modalCreateTitle'),
    modalDesc: getPageMessage(locale, 'settings.channel.binding.modalDesc'),
    memberLabel: getPageMessage(locale, 'settings.channel.binding.memberLabel'),
    memberPlaceholder: getPageMessage(locale, 'settings.channel.binding.memberPlaceholder'),
    noteLabel: getPageMessage(locale, 'settings.channel.binding.noteLabel'),
    notePlaceholder: getPageMessage(locale, 'settings.channel.binding.notePlaceholder'),
    statusLabel: getPageMessage(locale, 'settings.channel.binding.statusLabel'),
    cancel: getPageMessage(locale, 'settings.channel.binding.cancel'),
    saving: getPageMessage(locale, 'settings.channel.binding.saving'),
    save: getPageMessage(locale, 'settings.channel.binding.save'),
  }), [locale]);

  async function reloadData() {
    if (!householdId || !accountId || !supportsMemberBinding) {
      setBindings([]);
      setCandidates([]);
      return;
    }

    setLoading(true);
    setCandidateLoading(true);
    setError('');
    try {
      const [bindingResult, candidateResult] = await Promise.all([
        settingsApi.listChannelAccountBindings(householdId, accountId),
        settingsApi.listChannelAccountBindingCandidates(householdId, accountId),
      ]);
      setBindings(bindingResult);
      setCandidates(candidateResult);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
    } finally {
      setLoading(false);
      setCandidateLoading(false);
    }
  }

  useEffect(() => {
    void reloadData();
  }, [accountId, householdId, supportsMemberBinding]);

  function openCreateModal(candidate?: ChannelBindingCandidateRead) {
    setEditingBinding(null);
    setForm({
      member_id: '',
      external_user_id: candidate?.external_user_id ?? '',
      external_chat_id: candidate?.external_chat_id ?? '',
      display_hint: candidate ? buildDisplayHint(candidate) : '',
      binding_status: 'active',
    });
    setFormError('');
    setModalOpen(true);
  }

  function openEditModal(binding: MemberChannelBindingRead) {
    setEditingBinding(binding);
    setForm({
      member_id: binding.member_id,
      external_user_id: binding.external_user_id,
      external_chat_id: binding.external_chat_id ?? '',
      display_hint: binding.display_hint ?? '',
      binding_status: binding.binding_status,
    });
    setFormError('');
    setModalOpen(true);
  }

  async function handleSaveBinding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!householdId || !accountId) {
      return;
    }
    if (!editingBinding && !form.member_id) {
      setFormError(copy.selectMember);
      return;
    }
    if (!form.external_user_id.trim()) {
      setFormError(copy.fillIdentity(labels.identityLabel));
      return;
    }

    setModalLoading(true);
    setFormError('');

    try {
      if (editingBinding) {
        const payload: MemberChannelBindingUpdate = {
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        await settingsApi.updateChannelAccountBinding(householdId, accountId, editingBinding.id, payload);
        setStatus(copy.updated);
      } else {
        const payload: MemberChannelBindingCreate = {
          channel_account_id: accountId,
          member_id: form.member_id,
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        await settingsApi.createChannelAccountBinding(householdId, accountId, payload);
        setStatus(copy.created);
      }
      setModalOpen(false);
      await reloadData();
    } catch (saveError) {
      const message = saveError instanceof ApiError
        ? formatApiErrorMessage(saveError, locale)
        : saveError instanceof Error
          ? saveError.message
          : copy.saveFailed;
      setFormError(message);
    } finally {
      setModalLoading(false);
    }
  }

  async function handleToggleBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) {
      return;
    }

    const nextStatus = binding.binding_status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      await settingsApi.updateChannelAccountBinding(householdId, accountId, binding.id, {
        binding_status: nextStatus,
      });
      setStatus(nextStatus === 'active' ? copy.restored : copy.disabled);
      await reloadData();
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : copy.toggleFailed);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) {
      return;
    }

    const modalResult = await Taro.showModal({
      title: copy.deleteTitle,
      content: copy.deleteContent,
      confirmText: copy.delete,
      cancelText: copy.cancel,
    });
    if (!modalResult.confirm) {
      return;
    }

    setLoading(true);
    setError('');
    try {
      await settingsApi.deleteChannelAccountBinding(householdId, accountId, binding.id);
      setStatus(copy.deleted);
      await reloadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : copy.deleteFailed);
    } finally {
      setLoading(false);
    }
  }

  if (!supportsMemberBinding) {
    return (
      <div className="channel-bindings-panel">
        <div className="form-help">{copy.unsupported}</div>
      </div>
    );
  }

  return (
    <div className="channel-bindings-panel">
      {error ? <SettingsNotice tone="error" icon="⚠️">{error}</SettingsNotice> : null}
      {status ? <SettingsNotice tone="success" icon="✓">{status}</SettingsNotice> : null}

      <div className="channel-detail-section">
        <h5>{labels.candidateTitle}</h5>
        <div className="form-help">{labels.candidateHelpText}</div>
        {candidateLoading ? (
          <div className="text-text-secondary">{copy.loadingCandidates}</div>
        ) : candidates.length === 0 ? (
          <div className="form-help">{copy.emptyCandidates}</div>
        ) : (
          <div className="channel-bindings-list">
            {candidates.map((candidate) => (
              <div key={candidate.inbound_event_id} className="channel-binding-item">
                <div className="channel-binding-item__info">
                  <span className="channel-binding-item__member">
                    {labels.identityLabel}: {candidate.external_user_id}
                  </span>
                  {candidate.username ? <span className="channel-binding-item__hint">@{candidate.username}</span> : null}
                  {candidate.sender_display_name ? <span className="channel-binding-item__hint">{candidate.sender_display_name}</span> : null}
                  {candidate.external_chat_id ? (
                    <span className="channel-binding-item__external">
                      {labels.chatLabel}: {candidate.external_chat_id}
                    </span>
                  ) : null}
                  {candidate.last_message_text ? (
                    <span className="channel-binding-item__external">
                      {copy.latestMessage}: {candidate.last_message_text}
                    </span>
                  ) : null}
                </div>
                <div className="channel-binding-item__meta">
                  <span className="badge badge--warning">
                    {candidate.chat_type === 'group' ? copy.chatTypeGroup : copy.chatTypeDirect}
                  </span>
                  <span className="channel-binding-item__time">{formatTimestamp(candidate.last_seen_at, locale)}</span>
                </div>
                <div className="channel-binding-item__actions">
                  <button
                    className="btn btn--primary btn--sm"
                    type="button"
                    onClick={() => openCreateModal(candidate)}
                    disabled={loading || modalLoading}
                  >
                    {copy.bindNow}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading && bindings.length === 0 ? (
        <div className="text-text-secondary">{copy.loading}</div>
      ) : bindings.length === 0 ? (
        <SettingsEmptyState
          className="channel-bindings-empty"
          icon="🔗"
          title={copy.empty}
          description={labels.candidateHelpText}
          action={(
            <button className="btn btn--primary btn--sm" type="button" onClick={() => openCreateModal()}>
              {copy.add}
            </button>
          )}
        />
      ) : (
        <>
          <div className="channel-bindings-header">
            <span>{copy.count(bindings.length)}</span>
            <button className="btn btn--primary btn--sm" type="button" onClick={() => openCreateModal()}>
              {copy.add}
            </button>
          </div>

          <div className="channel-bindings-list">
            {bindings.map((binding) => {
              const member = memberMap.get(binding.member_id);
              const isActive = binding.binding_status === 'active';

              return (
                <div
                  key={binding.id}
                  className={`channel-binding-item ${!isActive ? 'channel-binding-item--disabled' : ''}`}
                >
                  <div className="channel-binding-item__info">
                    <span className="channel-binding-item__member">
                      {member?.name ?? copy.unknownMember}
                    </span>
                    <span className="channel-binding-item__external">
                      {labels.identityLabel}: {binding.external_user_id}
                      {binding.external_chat_id ? ` / ${labels.chatLabel}: ${binding.external_chat_id}` : ''}
                    </span>
                    {binding.display_hint ? <span className="channel-binding-item__hint">{binding.display_hint}</span> : null}
                  </div>
                  <div className="channel-binding-item__meta">
                    <span className={`badge badge--${isActive ? 'success' : 'secondary'}`}>
                      {isActive ? copy.active : copy.inactive}
                    </span>
                    <span className="channel-binding-item__time">{formatTimestamp(binding.updated_at, locale)}</span>
                  </div>
                  <div className="channel-binding-item__actions">
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => openEditModal(binding)} disabled={loading}>
                      {copy.edit}
                    </button>
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleToggleBinding(binding)} disabled={loading}>
                      {isActive ? copy.disable : copy.restore}
                    </button>
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleDeleteBinding(binding)} disabled={loading}>
                      {copy.delete}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <SettingsDialog
        open={modalOpen}
        title={editingBinding ? copy.modalEditTitle : copy.modalCreateTitle}
        description={copy.modalDesc}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSaveBinding}
        actions={(
          <>
            <button className="btn btn--outline btn--sm" type="button" onClick={() => setModalOpen(false)} disabled={modalLoading}>
              {copy.cancel}
            </button>
            <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>
              {modalLoading ? copy.saving : copy.save}
            </button>
          </>
        )}
      >
        <div className="form-group">
          <label>{copy.memberLabel}</label>
          <select
            className="form-select"
            value={form.member_id}
            onChange={(event) => setForm((current) => ({ ...current, member_id: event.target.value }))}
            disabled={Boolean(editingBinding)}
            required
          >
            <option value="">{copy.memberPlaceholder}</option>
            {members.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name} ({member.role})
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>{labels.identityLabel}</label>
          <input
            className="form-input"
            value={form.external_user_id}
            onChange={(event) => setForm((current) => ({ ...current, external_user_id: event.target.value }))}
            placeholder={labels.identityPlaceholder}
            required
          />
          <div className="form-help">{labels.identityHelpText}</div>
        </div>

        <div className="form-group">
          <label>{labels.chatLabel}</label>
          <input
            className="form-input"
            value={form.external_chat_id}
            onChange={(event) => setForm((current) => ({ ...current, external_chat_id: event.target.value }))}
            placeholder={labels.chatPlaceholder}
          />
          <div className="form-help">{labels.chatHelpText}</div>
        </div>

        <div className="form-group">
          <label>{copy.noteLabel}</label>
          <input
            className="form-input"
            value={form.display_hint}
            onChange={(event) => setForm((current) => ({ ...current, display_hint: event.target.value }))}
            placeholder={copy.notePlaceholder}
          />
        </div>

        <div className="form-group">
          <label>{copy.statusLabel}</label>
          <select
            className="form-select"
            value={form.binding_status}
            onChange={(event) => setForm((current) => ({
              ...current,
              binding_status: event.target.value as 'active' | 'disabled',
            }))}
          >
            <option value="active">{copy.active}</option>
            <option value="disabled">{copy.inactive}</option>
          </select>
        </div>

        {formError ? <SettingsNotice tone="error" icon="⚠️">{formError}</SettingsNotice> : null}
      </SettingsDialog>
    </div>
  );
}
