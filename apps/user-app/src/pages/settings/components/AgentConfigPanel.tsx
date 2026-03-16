import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../../assistant/assistant.agents';
import { Card } from '../../family/base';
import { parseTags, stringifyTags } from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type { AgentDetail, AgentSummary, Member } from '../settingsTypes';

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
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState<CreateFormState>(buildCreateForm(t));
  const [baseForm, setBaseForm] = useState({ displayName: '', status: 'active', sortOrder: '100' });
  const [soulForm, setSoulForm] = useState({
    selfIdentity: '',
    roleSummary: '',
    introMessage: '',
    speakingStyle: '',
    personalityTraits: '',
    serviceFocus: '',
  });
  const [runtimeForm, setRuntimeForm] = useState({
    conversationEnabled: true,
    defaultEntry: false,
    routingTags: '',
    memoryActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    configActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    operationActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
  });
  const [cognitionForm, setCognitionForm] = useState<Record<string, {
    displayAddress: string;
    closenessLevel: string;
    servicePriority: string;
    communicationStyle: string;
    promptNotes: string;
  }>>({});

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
    saveBaseSuccess: t('settings.ai.agent.saveBaseSuccess'),
    saveBaseFailed: t('settings.ai.agent.saveBaseFailed'),
    saveSoulSuccess: t('settings.ai.agent.saveSoulSuccess'),
    saveSoulFailed: t('settings.ai.agent.saveSoulFailed'),
    saveRuntimeSuccess: t('settings.ai.agent.saveRuntimeSuccess'),
    saveRuntimeFailed: t('settings.ai.agent.saveRuntimeFailed'),
    saveCognitionSuccess: t('settings.ai.agent.saveCognitionSuccess'),
    saveCognitionFailed: t('settings.ai.agent.saveCognitionFailed'),
    panelTitleCompact: t('settings.ai.agent.createFirst'),
    panelTitleButler: t('settings.ai.agent.panelTitleButler'),
    panelTitleAgent: t('settings.ai.agent.panelTitleAgent'),
    panelDescriptionCompact: t('settings.ai.agent.panelDescCompact'),
    panelDescriptionDefault: t('settings.ai.agent.panelDescDefault'),
    loading: t('settings.ai.agent.loading'),
    conversationEnabled: t('settings.ai.agent.conversationEnabled'),
    conversationPaused: t('settings.ai.agent.conversationPaused'),
    summaryEmpty: t('settings.ai.agent.summaryEmpty'),
    baseTitle: t('settings.ai.agent.baseTitle'),
    displayNameLabel: t('settings.ai.agent.displayName'),
    statusLabel: t('settings.ai.agent.status'),
    sortOrderLabel: t('settings.ai.agent.sortOrder'),
    saveBaseButton: t('settings.ai.agent.saveBase'),
    soulTitle: t('settings.ai.agent.soulTitle'),
    selfIdentityLabel: t('settings.ai.agent.selfIdentity'),
    roleSummaryLabel: t('settings.ai.agent.roleSummary'),
    introMessageLabel: t('settings.ai.agent.introMessage'),
    speakingStyleLabel: t('settings.ai.agent.speakingStyle'),
    personalityTraitsLabel: t('settings.ai.agent.personalityTraits'),
    serviceFocusLabel: t('settings.ai.agent.serviceFocus'),
    saveSoulButton: t('settings.ai.agent.saveSoul'),
    runtimeTitle: t('settings.ai.agent.runtimeTitle'),
    conversationOption: t('settings.ai.agent.conversationOption'),
    defaultEntryOption: t('settings.ai.agent.defaultEntry'),
    routingTagsLabel: t('settings.ai.agent.routingTags'),
    memoryActionLabel: t('settings.ai.agent.memoryAction'),
    configActionLabel: t('settings.ai.agent.configAction'),
    operationActionLabel: t('settings.ai.agent.operationAction'),
    saveRuntimeButton: t('settings.ai.agent.saveRuntime'),
    cognitionTitle: t('settings.ai.agent.cognitionTitle'),
    displayAddressLabel: t('settings.ai.agent.displayAddress'),
    closenessLevelLabel: t('settings.ai.agent.closenessLevel'),
    servicePriorityLabel: t('settings.ai.agent.servicePriority'),
    communicationStyleLabel: t('settings.ai.agent.communicationStyle'),
    promptNotesLabel: t('settings.ai.agent.promptNotes'),
    saveCognitionButton: t('settings.ai.agent.saveCognition'),
    emptyButlerTitle: t('settings.ai.agent.emptyButler'),
    emptyAgentTitle: t('settings.ai.agent.emptyAgent'),
    emptyDescription: t('settings.ai.agent.emptyHint'),
    createModalDescription: t('settings.ai.agent.createModalHint'),
    agentTypeLabel: t('settings.ai.agent.agentType'),
    personalityTraitsHint: t('settings.ai.agent.traitsHint'),
    serviceFocusHint: t('settings.ai.agent.focusHint'),
    cancel: t('common.cancel'),
    creating: t('settings.ai.agent.addAgent'),
  };
  const agentTypeOptions: Array<CreateFormState['agentType']> = ['butler', 'nutritionist', 'fitness_coach', 'study_coach', 'custom'];
  const statusOptions: Array<AgentDetail['status']> = ['active', 'inactive', 'draft'];

  function applyDetail(result: AgentDetail) {
    setDetail(result);
    setBaseForm({
      displayName: result.display_name,
      status: result.status,
      sortOrder: String(result.sort_order),
    });
    setSoulForm({
      selfIdentity: result.soul?.self_identity ?? '',
      roleSummary: result.soul?.role_summary ?? '',
      introMessage: result.soul?.intro_message ?? '',
      speakingStyle: result.soul?.speaking_style ?? '',
      personalityTraits: stringifyTags(result.soul?.personality_traits ?? []),
      serviceFocus: stringifyTags(result.soul?.service_focus ?? []),
    });
    setRuntimeForm({
      conversationEnabled: result.runtime_policy?.conversation_enabled ?? true,
      defaultEntry: result.runtime_policy?.default_entry ?? false,
      routingTags: stringifyTags(result.runtime_policy?.routing_tags ?? []),
      memoryActionLevel: result.runtime_policy?.autonomous_action_policy?.memory ?? 'ask',
      configActionLevel: result.runtime_policy?.autonomous_action_policy?.config ?? 'ask',
      operationActionLevel: result.runtime_policy?.autonomous_action_policy?.action ?? 'ask',
    });
    setCognitionForm(Object.fromEntries(result.member_cognitions.map(item => [
      item.member_id,
      {
        displayAddress: item.display_address ?? '',
        closenessLevel: String(item.closeness_level),
        servicePriority: String(item.service_priority),
        communicationStyle: item.communication_style ?? '',
        promptNotes: item.prompt_notes ?? '',
      },
    ])));
  }

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

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [agentRows, memberRows] = await Promise.all([
          settingsApi.listAgents(householdId),
          settingsApi.listMembers(householdId),
        ]);
        if (cancelled) return;
        const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setSelectedAgentId(current => (nextAgents.some(item => item.id === current) ? current : (nextAgents[0]?.id ?? '')));
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

  useEffect(() => {
    if (!selectedAgentId) {
      setDetail(null);
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      setLoading(true);
      setError('');
      try {
        const result = await settingsApi.getAgentDetail(householdId, selectedAgentId);
        if (!cancelled) {
          applyDetail(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadDetailFailed);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [householdId, selectedAgentId]);

  async function reload(selectAgentId?: string) {
    const agentRows = await settingsApi.listAgents(householdId);
    const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
    const nextSelectedId = selectAgentId ?? (
      nextAgents.some(item => item.id === selectedAgentId) ? selectedAgentId : (nextAgents[0]?.id ?? '')
    );
    setAgents(nextAgents);
    setSelectedAgentId(nextSelectedId);
    if (nextSelectedId) {
      applyDetail(await settingsApi.getAgentDetail(householdId, nextSelectedId));
    } else {
      setDetail(null);
    }
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
      await reload(created.id);
      setCreateModalOpen(false);
      resetCreateForm();
      setStatus(copy.createdStatus(created.display_name));
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : copy.createFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveBase() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.updateAgent(householdId, detail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status as AgentDetail['status'],
        sort_order: Number(baseForm.sortOrder),
      });
      await reload(detail.id);
      setStatus(copy.saveBaseSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveBaseFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSoul() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentSoul(householdId, detail.id, {
        self_identity: soulForm.selfIdentity.trim(),
        role_summary: soulForm.roleSummary.trim(),
        intro_message: soulForm.introMessage.trim() || null,
        speaking_style: soulForm.speakingStyle.trim() || null,
        personality_traits: parseTags(soulForm.personalityTraits),
        service_focus: parseTags(soulForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-app',
      });
      await reload(detail.id);
      setStatus(copy.saveSoulSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveSoulFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRuntime() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentRuntimePolicy(householdId, detail.id, {
        conversation_enabled: runtimeForm.conversationEnabled,
        default_entry: runtimeForm.defaultEntry,
        routing_tags: parseTags(runtimeForm.routingTags),
        memory_scope: null,
        autonomous_action_policy: {
          memory: runtimeForm.memoryActionLevel,
          config: runtimeForm.configActionLevel,
          action: runtimeForm.operationActionLevel,
        },
      });
      await reload(detail.id);
      setStatus(copy.saveRuntimeSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveRuntimeFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveCognitions() {
    if (!detail) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentMemberCognitions(householdId, detail.id, {
        items: members.map(member => {
          const item = cognitionForm[member.id] ?? {
            displayAddress: '',
            closenessLevel: '3',
            servicePriority: '3',
            communicationStyle: '',
            promptNotes: '',
          };
          return {
            member_id: member.id,
            display_address: item.displayAddress.trim() || null,
            closeness_level: Number(item.closenessLevel),
            service_priority: Number(item.servicePriority),
            communication_style: item.communicationStyle.trim() || null,
            prompt_notes: item.promptNotes.trim() || null,
            care_notes: null,
          };
        }),
      });
      await reload(detail.id);
      setStatus(copy.saveCognitionSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveCognitionFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      <Card className="ai-config-detail-card">
        <div className="agent-config-center__toolbar">
          <div className="agent-config-center__intro">
            <h3>{compact ? copy.panelTitleCompact : (onlyButler ? copy.panelTitleButler : copy.panelTitleAgent)}</h3>
            <p>
              {compact
                ? copy.panelDescriptionCompact
                : copy.panelDescriptionDefault}
            </p>
          </div>
          <button className="btn btn--primary" type="button" onClick={openCreateModal}>
            {createActionLabel}
          </button>
        </div>
        {status ? <div className="setup-form-status">{status}</div> : null}
      </Card>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">{copy.loading}</div> : null}

      {!loading && !compact ? (
        visibleAgents.length > 0 ? (
          <>
            <div className="ai-config-list">
              {visibleAgents.map(agent => (
                <button
                  key={agent.id}
                  type="button"
                  className={`card ai-config-card ${selectedAgentId === agent.id ? 'ai-config-card--selected' : ''}`}
                  onClick={() => setSelectedAgentId(agent.id)}
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

            {detail ? (
              <div className="ai-config-detail__grid">
                <Card className="ai-config-detail-card">
                  <h4>{copy.baseTitle}</h4>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.displayNameLabel}</label><input className="form-input" value={baseForm.displayName} onChange={(event) => setBaseForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.statusLabel}</label><select className="form-select" value={baseForm.status} onChange={(event) => setBaseForm(current => ({ ...current, status: event.target.value }))}>{statusOptions.map(option => <option key={option} value={option}>{getAgentStatusLabel(option, t)}</option>)}</select></div>
                    <div className="form-group"><label>{copy.sortOrderLabel}</label><input className="form-input" type="number" value={baseForm.sortOrder} onChange={(event) => setBaseForm(current => ({ ...current, sortOrder: event.target.value }))} /></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveBase()} disabled={saving}>{copy.saveBaseButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.soulTitle}</h4>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.selfIdentityLabel}</label><textarea className="form-input setup-textarea" value={soulForm.selfIdentity} onChange={(event) => setSoulForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.roleSummaryLabel}</label><textarea className="form-input setup-textarea" value={soulForm.roleSummary} onChange={(event) => setSoulForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.introMessageLabel}</label><input className="form-input" value={soulForm.introMessage} onChange={(event) => setSoulForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.speakingStyleLabel}</label><input className="form-input" value={soulForm.speakingStyle} onChange={(event) => setSoulForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.personalityTraitsLabel}</label><input className="form-input" value={soulForm.personalityTraits} onChange={(event) => setSoulForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
                    <div className="form-group"><label>{copy.serviceFocusLabel}</label><input className="form-input" value={soulForm.serviceFocus} onChange={(event) => setSoulForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveSoul()} disabled={saving}>{copy.saveSoulButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.runtimeTitle}</h4>
                  <div className="setup-choice-group">
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.conversationEnabled} onChange={(event) => setRuntimeForm(current => ({ ...current, conversationEnabled: event.target.checked }))} /><span>{copy.conversationOption}</span></label>
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.defaultEntry} onChange={(event) => setRuntimeForm(current => ({ ...current, defaultEntry: event.target.checked }))} /><span>{copy.defaultEntryOption}</span></label>
                  </div>
                  <div className="form-group"><label>{copy.routingTagsLabel}</label><input className="form-input" value={runtimeForm.routingTags} onChange={(event) => setRuntimeForm(current => ({ ...current, routingTags: event.target.value }))} /></div>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>{copy.memoryActionLabel}</label><select className="form-select" value={runtimeForm.memoryActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>{copy.configActionLabel}</label><select className="form-select" value={runtimeForm.configActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>{copy.operationActionLabel}</label><select className="form-select" value={runtimeForm.operationActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>{copy.saveRuntimeButton}</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>{copy.cognitionTitle}</h4>
                  <div className="ai-cognition-list">
                    {members.map(member => {
                      const cognition = cognitionForm[member.id] ?? { displayAddress: '', closenessLevel: '3', servicePriority: '3', communicationStyle: '', promptNotes: '' };
                      return (
                        <div key={member.id} className="ai-cognition-item">
                          <div className="ai-cognition-item__top"><strong>{member.name}</strong><span className="ai-config-muted">{member.role}</span></div>
                          <div className="setup-form-grid">
                            <div className="form-group"><label>{copy.displayAddressLabel}</label><input className="form-input" value={cognition.displayAddress} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.closenessLevelLabel}</label><input className="form-input" type="number" min="1" max="5" value={cognition.closenessLevel} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, closenessLevel: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.servicePriorityLabel}</label><input className="form-input" type="number" min="1" max="5" value={cognition.servicePriority} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, servicePriority: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.communicationStyleLabel}</label><input className="form-input" value={cognition.communicationStyle} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))} /></div>
                            <div className="form-group"><label>{copy.promptNotesLabel}</label><textarea className="form-input setup-textarea" value={cognition.promptNotes} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))} /></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>{copy.saveCognitionButton}</button></div>
                </Card>
              </div>
            ) : null}
          </>
        ) : (
          <Card className="ai-config-detail-card agent-config-empty">
            <h4>{onlyButler ? copy.emptyButlerTitle : copy.emptyAgentTitle}</h4>
            <p className="ai-config-muted">{copy.emptyDescription}</p>
          </Card>
        )
      ) : null}

      {createModalOpen ? (
        <div className="member-modal-overlay" onClick={saving ? undefined : closeCreateModal}>
          <div className="member-modal agent-create-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{createActionLabel}</h3>
                <p>{copy.createModalDescription}</p>
              </div>
            </div>
            <form className="settings-form agent-create-form" onSubmit={handleCreate}>
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
              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={saving}>{copy.cancel}</button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={createDisabled}>{saving ? t('common.saving') : createActionLabel}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
