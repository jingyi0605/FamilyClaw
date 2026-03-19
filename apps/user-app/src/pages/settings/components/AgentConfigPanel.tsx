import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../../assistant/assistant.agents';
import { Card } from '../../family/base';
import { parseTags } from '../../setup/setupAiConfig';
import { SettingsDialog, SettingsEmptyState, SettingsPanelCard } from './SettingsSharedBlocks';
import { AgentDetailDialog } from './AgentDetailDialog';
import { settingsApi } from '../settingsApi';
import type {
  AgentDetail,
  AgentSummary,
  AiProviderProfile,
  Member,
  PluginRegistryItem,
} from '../settingsTypes';

type CreateFormState = {
  displayName: string;
  agentType: 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
  selfIdentity: string;
  roleSummary: string;
  introMessage: string;
  speakingStyle: string;
  personalityTraits: string;
  serviceFocus: string;
};

function buildCreateForm(t: (key: string, params?: Record<string, string | number>) => string): CreateFormState {
  return {
    displayName: t('settings.ai.agent.defaultName'),
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: t('settings.ai.agent.defaultRoleSummary'),
    introMessage: t('settings.ai.agent.defaultIntro'),
    speakingStyle: t('settings.ai.agent.defaultSpeakingStyle'),
    personalityTraits: t('settings.ai.agent.defaultTraits'),
    serviceFocus: t('settings.ai.agent.defaultFocus'),
  };
}

export function AgentConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  onlyButler?: boolean;
  onChanged?: () => Promise<void> | void;
}) {
  const { t } = useI18n();
  const { householdId, compact = false, onlyButler = false, onChanged } = props;
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [agentSkillPlugins, setAgentSkillPlugins] = useState<PluginRegistryItem[]>([]);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState<CreateFormState>(buildCreateForm(t));

  const visibleAgents = useMemo(
    () => agents.filter(item => !onlyButler || item.agent_type === 'butler'),
    [agents, onlyButler],
  );

  const createActionLabel = compact
    ? t('settings.ai.agent.createFirst')
    : (onlyButler
      ? t('settings.ai.agent.addButler')
      : t('settings.ai.agent.addAgent'));
  const createDisabled = (
    saving
    || !createForm.displayName.trim()
    || !createForm.selfIdentity.trim()
    || !createForm.roleSummary.trim()
    || parseTags(createForm.personalityTraits).length === 0
    || parseTags(createForm.serviceFocus).length === 0
  );

  const actionOptions = [
    { value: 'ask', label: t('settings.ai.agent.action.ask') },
    { value: 'notify', label: t('settings.ai.agent.action.notify') },
    { value: 'auto', label: t('settings.ai.agent.action.auto') },
  ] as const;
  const copy = {
    loadFailed: t('settings.ai.agent.loadFailed'),
    loadDetailFailed: t('settings.ai.agent.loadDetailFailed'),
    createdStatus: (name: string) => t('settings.ai.agent.createdStatus', { name }),
    createFailed: t('settings.ai.agent.createFailed'),
    panelTitleCompact: t('settings.ai.agent.createFirst'),
    panelTitleButler: t('settings.ai.agent.panelTitleButler'),
    panelTitleAgent: t('settings.ai.agent.panelTitleAgent'),
    panelDescriptionCompact: t('settings.ai.agent.panelDescCompact'),
    panelDescriptionDefault: t('settings.ai.agent.panelDescDefault'),
    loading: t('settings.ai.agent.loading'),
    conversationEnabled: t('settings.ai.agent.conversationEnabled'),
    conversationPaused: t('settings.ai.agent.conversationPaused'),
    summaryEmpty: t('settings.ai.agent.summaryEmpty'),
    emptyButlerTitle: t('settings.ai.agent.emptyButler'),
    emptyAgentTitle: t('settings.ai.agent.emptyAgent'),
    emptyDescription: t('settings.ai.agent.emptyHint'),
    createModalDescription: t('settings.ai.agent.createModalHint'),
    agentTypeLabel: t('settings.ai.agent.agentType'),
    displayNameLabel: t('settings.ai.agent.displayName'),
    selfIdentityLabel: t('settings.ai.agent.selfIdentity'),
    roleSummaryLabel: t('settings.ai.agent.roleSummary'),
    introMessageLabel: t('settings.ai.agent.introMessage'),
    speakingStyleLabel: t('settings.ai.agent.speakingStyle'),
    personalityTraitsLabel: t('settings.ai.agent.personalityTraits'),
    serviceFocusLabel: t('settings.ai.agent.serviceFocus'),
    personalityTraitsHint: t('settings.ai.agent.traitsHint'),
    serviceFocusHint: t('settings.ai.agent.focusHint'),
    cancel: t('common.cancel'),
    creating: t('settings.ai.agent.addAgent'),
  };
  const agentTypeOptions: Array<CreateFormState['agentType']> = ['butler', 'nutritionist', 'fitness_coach', 'study_coach', 'custom'];

  function resetCreateForm() {
    setCreateForm(buildCreateForm(t));
  }

  function openCreateModal() {
    resetCreateForm();
    setError('');
    setStatus('');
    setCreateModalOpen(true);
  }

  function closeCreateModal() {
    if (saving) return;
    setCreateModalOpen(false);
    resetCreateForm();
  }

  async function openEditModal(agentId: string) {
    setLoading(true);
    setError('');
    try {
      const result = await settingsApi.getAgentDetail(householdId, agentId);
      setDetail(result);
      setEditModalOpen(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : copy.loadDetailFailed);
    } finally {
      setLoading(false);
    }
  }

  function closeEditModal() {
    setEditModalOpen(false);
    setDetail(null);
  }

  async function handleEditSaved() {
    if (detail) {
      try {
        const result = await settingsApi.getAgentDetail(householdId, detail.id);
        setDetail(result);
      } catch {
        // 忽略错误
      }
    }
    await reload();
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [agentRows, memberRows, providerRows, pluginSnapshot] = await Promise.all([
          settingsApi.listAgents(householdId),
          settingsApi.listMembers(householdId),
          settingsApi.listHouseholdAiProviders(householdId),
          settingsApi.listRegisteredPlugins(householdId),
        ]);
        if (cancelled) return;
        const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setProviders(providerRows);
        setAgentSkillPlugins(pluginSnapshot.items.filter(item => item.types.includes('agent-skill') && item.enabled));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [householdId, onlyButler]);

  async function reload() {
    const [agentRows, providerRows, pluginSnapshot] = await Promise.all([
      settingsApi.listAgents(householdId),
      settingsApi.listHouseholdAiProviders(householdId),
      settingsApi.listRegisteredPlugins(householdId),
    ]);
    const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
    setAgents(nextAgents);
    setProviders(providerRows);
    setAgentSkillPlugins(pluginSnapshot.items.filter(item => item.types.includes('agent-skill') && item.enabled));
    await onChanged?.();
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setStatus('');
    try {
      const created = await settingsApi.createAgent(householdId, {
        display_name: createForm.displayName.trim(),
        agent_type: (onlyButler ? 'butler' : createForm.agentType) as CreateFormState['agentType'],
        self_identity: createForm.selfIdentity.trim(),
        role_summary: createForm.roleSummary.trim(),
        intro_message: createForm.introMessage.trim() || null,
        speaking_style: createForm.speakingStyle.trim() || null,
        personality_traits: parseTags(createForm.personalityTraits),
        service_focus: parseTags(createForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-app',
      });
      await reload();
      setCreateModalOpen(false);
      resetCreateForm();
      setStatus(copy.createdStatus(created.display_name));
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      <SettingsPanelCard
        title={compact ? copy.panelTitleCompact : (onlyButler ? copy.panelTitleButler : copy.panelTitleAgent)}
        description={compact ? copy.panelDescriptionCompact : copy.panelDescriptionDefault}
        actions={(
          <button className="btn btn--primary" type="button" onClick={openCreateModal}>
            {createActionLabel}
          </button>
        )}
      >
        {status ? <div className="setup-form-status">{status}</div> : null}
      </SettingsPanelCard>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">{copy.loading}</div> : null}

      {!loading && !compact ? (
        visibleAgents.length > 0 ? (
          <div className="ai-config-list">
            {visibleAgents.map(agent => (
              <button
                key={agent.id}
                type="button"
                className="card ai-config-card"
                onClick={() => void openEditModal(agent.id)}
              >
                <div className="ai-config-card__top">
                  <div className="ai-config-card__avatar">{getAgentTypeEmoji(agent.agent_type)}</div>
                  <div className="ai-config-card__text">
                    <div className="ai-config-card__title-row">
                      <h3>{agent.display_name}</h3>
                      <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                        {agent.conversation_enabled ? copy.conversationEnabled : copy.conversationPaused}
                      </span>
                    </div>
                    <p className="ai-config-card__meta">{getAgentTypeLabel(agent.agent_type, t)} · {getAgentStatusLabel(agent.status, t)}</p>
                    <p className="ai-config-card__summary">{agent.summary ?? copy.summaryEmpty}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <SettingsEmptyState
            icon={onlyButler ? '🧑‍💼' : '🤖'}
            title={onlyButler ? copy.emptyButlerTitle : copy.emptyAgentTitle}
            description={copy.emptyDescription}
            action={(
              <button className="btn btn--primary" type="button" onClick={openCreateModal}>
                {createActionLabel}
              </button>
            )}
          />
        )
      ) : null}

      <AgentDetailDialog
        open={editModalOpen}
        householdId={householdId}
        agent={detail}
        members={members}
        providers={providers}
        agentSkillPlugins={agentSkillPlugins}
        onClose={closeEditModal}
        onSaved={handleEditSaved}
      />

      <SettingsDialog
        open={createModalOpen}
        title={createActionLabel}
        description={copy.createModalDescription}
        className="agent-create-modal"
        formClassName="agent-create-form"
        closeDisabled={saving}
        onClose={closeCreateModal}
        onSubmit={handleCreate}
        actions={(
          <>
            <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={saving}>{copy.cancel}</button>
            <button className="btn btn--primary btn--sm" type="submit" disabled={createDisabled}>{saving ? t('common.saving') : createActionLabel}</button>
          </>
        )}
      >
        <div className="setup-form-grid">
          {!onlyButler ? (
            <div className="form-group">
              <label htmlFor={`agent-type-${householdId}`}>{copy.agentTypeLabel}</label>
              <select id={`agent-type-${householdId}`} className="form-select" value={createForm.agentType} onChange={(event) => setCreateForm(current => ({ ...current, agentType: event.target.value as CreateFormState['agentType'] }))}>
                {agentTypeOptions.map(option => <option key={option} value={option}>{getAgentTypeLabel(option, t)}</option>)}
              </select>
            </div>
          ) : null}
          <div className="form-group"><label>{copy.displayNameLabel}</label><input className="form-input" value={createForm.displayName} onChange={(event) => setCreateForm(current => ({ ...current, displayName: event.target.value }))} /></div>
          <div className="form-group"><label>{copy.selfIdentityLabel}</label><textarea className="form-input setup-textarea" value={createForm.selfIdentity} onChange={(event) => setCreateForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
          <div className="form-group"><label>{copy.roleSummaryLabel}</label><textarea className="form-input setup-textarea" value={createForm.roleSummary} onChange={(event) => setCreateForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
          <div className="form-group"><label>{copy.introMessageLabel}</label><input className="form-input" value={createForm.introMessage} onChange={(event) => setCreateForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
          <div className="form-group"><label>{copy.speakingStyleLabel}</label><input className="form-input" value={createForm.speakingStyle} onChange={(event) => setCreateForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
          <div className="form-group"><label>{copy.personalityTraitsLabel}</label><input className="form-input" value={createForm.personalityTraits} onChange={(event) => setCreateForm(current => ({ ...current, personalityTraits: event.target.value }))} /><div className="form-help">{copy.personalityTraitsHint}</div></div>
          <div className="form-group"><label>{copy.serviceFocusLabel}</label><input className="form-input" value={createForm.serviceFocus} onChange={(event) => setCreateForm(current => ({ ...current, serviceFocus: event.target.value }))} /><div className="form-help">{copy.serviceFocusHint}</div></div>
        </div>
      </SettingsDialog>
    </div>
  );
}
