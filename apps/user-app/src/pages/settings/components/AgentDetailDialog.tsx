import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../../../runtime';
import { getAgentStatusLabel } from '../../assistant/assistant.agents';
import { getCapabilityLabel, getProviderModelName, parseTags, providerSupportsCapability, stringifyTags } from '../../setup/setupAiConfig';
import type {
  AgentDetail,
  AgentModelBinding,
  AgentSkillModelBinding,
  AiCapability,
  AiProviderProfile,
  Member,
  PluginRegistryItem,
} from '../settingsTypes';
import { settingsApi } from '../settingsApi';

const AI_CAPABILITIES: AiCapability[] = ['text', 'intent_recognition', 'vision', 'audio_generation', 'audio_recognition', 'image_generation'];

type ModelBindingFormState = Record<AiCapability, string>;
type AgentSkillBindingFormState = Record<string, ModelBindingFormState>;

function buildEmptyModelBindingForm(): ModelBindingFormState {
  return {
    text: '',
    intent_recognition: '',
    vision: '',
    audio_generation: '',
    audio_recognition: '',
    image_generation: '',
  };
}

function buildModelBindingForm(bindings: AgentModelBinding[]): ModelBindingFormState {
  const result = buildEmptyModelBindingForm();
  for (const item of bindings) {
    result[item.capability] = item.provider_profile_id;
  }
  return result;
}

function buildAgentSkillBindingForm(
  bindings: AgentSkillModelBinding[],
  plugins: PluginRegistryItem[],
): AgentSkillBindingFormState {
  const result: AgentSkillBindingFormState = {};
  for (const plugin of plugins) {
    result[plugin.id] = buildEmptyModelBindingForm();
  }
  for (const item of bindings) {
    result[item.plugin_id] ??= buildEmptyModelBindingForm();
    result[item.plugin_id][item.capability] = item.provider_profile_id;
  }
  return result;
}

function serializeModelBindings(form: ModelBindingFormState): AgentModelBinding[] {
  return AI_CAPABILITIES.flatMap(capability => (
    form[capability]
      ? [{ capability, provider_profile_id: form[capability] }]
      : []
  ));
}

function serializeAgentSkillBindings(form: AgentSkillBindingFormState): AgentSkillModelBinding[] {
  return Object.entries(form).flatMap(([pluginId, bindings]) => (
    AI_CAPABILITIES.flatMap(capability => (
      bindings[capability]
        ? [{ plugin_id: pluginId, capability, provider_profile_id: bindings[capability] }]
        : []
    ))
  ));
}

export function AgentDetailDialog(props: {
  open: boolean;
  householdId: string;
  agent: AgentDetail | null;
  members: Member[];
  providers: AiProviderProfile[];
  agentSkillPlugins: PluginRegistryItem[];
  onClose: () => void;
  onSaved: () => Promise<void> | void;
}) {
  const { locale, t } = useI18n();
  const {
    open,
    householdId,
    agent,
    members,
    providers,
    agentSkillPlugins,
    onClose,
    onSaved,
  } = props;

  const [activeSection, setActiveSection] = useState<'base' | 'runtime' | 'cognition'>('base');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const [baseForm, setBaseForm] = useState({ displayName: '', status: 'active' as AgentDetail['status'], sortOrder: '100' });
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
    memoryActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    configActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
    operationActionLevel: 'ask' as 'ask' | 'notify' | 'auto',
  });
  const [modelBindingForm, setModelBindingForm] = useState<ModelBindingFormState>(buildEmptyModelBindingForm());
  const [agentSkillBindingForm, setAgentSkillBindingForm] = useState<AgentSkillBindingFormState>({});
  const [cognitionForm, setCognitionForm] = useState<Record<string, {
    displayAddress: string;
    closenessLevel: string;
    servicePriority: string;
    communicationStyle: string;
    promptNotes: string;
  }>>({});

  const enabledProviders = useMemo(
    () => providers.filter(item => item.enabled && item.plugin_enabled !== false),
    [providers],
  );
  const providerOptionsByCapability = useMemo(
    () => Object.fromEntries(
      AI_CAPABILITIES.map(capability => [
        capability,
        enabledProviders.filter(item => providerSupportsCapability(item, capability)),
      ]),
    ) as Record<AiCapability, AiProviderProfile[]>,
    [enabledProviders],
  );

  const actionOptions = [
    { value: 'ask', label: t('settings.ai.agent.action.ask') },
    { value: 'notify', label: t('settings.ai.agent.action.notify') },
    { value: 'auto', label: t('settings.ai.agent.action.auto') },
  ] as const;

  const copy = {
    saveBaseSuccess: t('settings.ai.agent.saveBaseSuccess'),
    saveBaseFailed: t('settings.ai.agent.saveBaseFailed'),
    saveSoulSuccess: t('settings.ai.agent.saveSoulSuccess'),
    saveSoulFailed: t('settings.ai.agent.saveSoulFailed'),
    saveProfileSuccess: t('settings.ai.agent.saveProfileSuccess'),
    saveProfileFailed: t('settings.ai.agent.saveProfileFailed'),
    saveRuntimeSuccess: t('settings.ai.agent.saveRuntimeSuccess'),
    saveRuntimeFailed: t('settings.ai.agent.saveRuntimeFailed'),
    saveCognitionSuccess: t('settings.ai.agent.saveCognitionSuccess'),
    saveCognitionFailed: t('settings.ai.agent.saveCognitionFailed'),
    modelBindingsTitle: t('settings.ai.agent.modelBindingsTitle'),
    modelBindingsHint: t('settings.ai.agent.modelBindingsHint'),
    agentDefaultBindingsTitle: t('settings.ai.agent.agentDefaultBindingsTitle'),
    agentSkillBindingsTitle: t('settings.ai.agent.agentSkillBindingsTitle'),
    noAgentSkillPlugins: t('settings.ai.agent.noAgentSkillPlugins'),
    inheritHouseholdRoute: t('settings.ai.agent.inheritHouseholdRoute'),
    profileTitle: t('settings.ai.agent.profileTitle'),
    baseTitle: t('settings.ai.agent.baseTitle'),
    displayNameLabel: t('settings.ai.agent.displayName'),
    statusLabel: t('settings.ai.agent.status'),
    sortOrderLabel: t('settings.ai.agent.sortOrder'),
    roleSummaryLabel: t('settings.ai.agent.roleSummary'),
    introMessageLabel: t('settings.ai.agent.introMessage'),
    speakingStyleLabel: t('settings.ai.agent.speakingStyle'),
    personalityTraitsLabel: t('settings.ai.agent.personalityTraits'),
    serviceFocusLabel: t('settings.ai.agent.serviceFocus'),
    soulTitle: t('settings.ai.agent.soulTitle'),
    saveProfileButton: t('settings.ai.agent.saveProfile'),
    runtimeTitle: t('settings.ai.agent.runtimeTitle'),
    conversationOption: t('settings.ai.agent.conversationOption'),
    defaultEntryOption: t('settings.ai.agent.defaultEntry'),
    memoryActionLabel: t('settings.ai.agent.memoryAction'),
    configActionLabel: t('settings.ai.agent.configAction'),
    operationActionLabel: t('settings.ai.agent.operationAction'),
    saveRuntimeButton: t('settings.ai.agent.saveRuntime'),
    cognitionTitle: t('settings.ai.agent.cognitionTitle'),
    displayAddressLabel: t('settings.ai.agent.displayAddress'),
    communicationStyleLabel: t('settings.ai.agent.communicationStyle'),
    promptNotesLabel: t('settings.ai.agent.promptNotes'),
    saveCognitionButton: t('settings.ai.agent.saveCognition'),
    close: t('common.close'),
    saving: t('common.saving'),
    editHint: t('settings.ai.agent.editHint'),
  };
  const statusOptions: Array<AgentDetail['status']> = ['active', 'inactive', 'draft'];

  useEffect(() => {
    if (agent) {
      setBaseForm({
        displayName: agent.display_name,
        status: agent.status,
        sortOrder: String(agent.sort_order),
      });
      setSoulForm({
        selfIdentity: agent.soul?.self_identity ?? '',
        roleSummary: agent.soul?.role_summary ?? '',
        introMessage: agent.soul?.intro_message ?? '',
        speakingStyle: agent.soul?.speaking_style ?? '',
        personalityTraits: stringifyTags(agent.soul?.personality_traits ?? []),
        serviceFocus: stringifyTags(agent.soul?.service_focus ?? []),
      });
      setRuntimeForm({
        conversationEnabled: agent.runtime_policy?.conversation_enabled ?? true,
        defaultEntry: agent.runtime_policy?.default_entry ?? false,
        memoryActionLevel: agent.runtime_policy?.autonomous_action_policy?.memory ?? 'ask',
        configActionLevel: agent.runtime_policy?.autonomous_action_policy?.config ?? 'ask',
        operationActionLevel: agent.runtime_policy?.autonomous_action_policy?.action ?? 'ask',
      });
      setModelBindingForm(buildModelBindingForm(agent.runtime_policy?.model_bindings ?? []));
      setAgentSkillBindingForm(
        buildAgentSkillBindingForm(agent.runtime_policy?.agent_skill_model_bindings ?? [], agentSkillPlugins),
      );
      setCognitionForm(Object.fromEntries(agent.member_cognitions.map(item => [
        item.member_id,
        {
          displayAddress: item.display_address ?? '',
          closenessLevel: String(item.closeness_level),
          servicePriority: String(item.service_priority),
          communicationStyle: item.communication_style ?? '',
          promptNotes: item.prompt_notes ?? '',
        },
      ])));
      setError('');
      setStatus('');
      setActiveSection('base');
    }
  }, [agent, agentSkillPlugins]);

  async function handleSaveProfile() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await Promise.all([
        settingsApi.updateAgent(householdId, agent.id, {
          display_name: baseForm.displayName.trim(),
          status: baseForm.status,
          sort_order: Number(baseForm.sortOrder),
        }),
        settingsApi.upsertAgentSoul(householdId, agent.id, {
          self_identity: soulForm.selfIdentity.trim(),
          role_summary: soulForm.roleSummary.trim(),
          intro_message: soulForm.introMessage.trim() || null,
          speaking_style: soulForm.speakingStyle.trim() || null,
          personality_traits: parseTags(soulForm.personalityTraits),
          service_focus: parseTags(soulForm.serviceFocus),
          created_by: 'user-app',
        }),
      ]);
      await onSaved();
      setStatus(copy.saveProfileSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveProfileFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRuntime() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentRuntimePolicy(householdId, agent.id, {
        conversation_enabled: runtimeForm.conversationEnabled,
        default_entry: runtimeForm.defaultEntry,
        routing_tags: agent.runtime_policy?.routing_tags ?? [],
        memory_scope: null,
        autonomous_action_policy: {
          memory: runtimeForm.memoryActionLevel,
          config: runtimeForm.configActionLevel,
          action: runtimeForm.operationActionLevel,
        },
        model_bindings: serializeModelBindings(modelBindingForm),
        agent_skill_model_bindings: serializeAgentSkillBindings(agentSkillBindingForm),
      });
      await onSaved();
      setStatus(copy.saveRuntimeSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveRuntimeFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveCognitions() {
    if (!agent) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentMemberCognitions(householdId, agent.id, {
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
      await onSaved();
      setStatus(copy.saveCognitionSuccess);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveCognitionFailed);
    } finally {
      setSaving(false);
    }
  }

  if (!open || !agent) {
    return null;
  }

  const sections: Array<{ key: typeof activeSection; label: string }> = [
    { key: 'base', label: copy.profileTitle },
    { key: 'runtime', label: copy.runtimeTitle },
    { key: 'cognition', label: copy.cognitionTitle },
  ];

  const content = (
    <div className="member-modal-overlay" onClick={saving ? undefined : onClose}>
      <div className="member-modal agent-detail-modal" onClick={(event) => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{agent.display_name}</h3>
            <p>{copy.editHint}</p>
          </div>
          <button
            className="member-modal__close"
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label={copy.close}
          >
            ×
          </button>
        </div>

        {status ? <div className="setup-form-status">{status}</div> : null}
        {error ? <div className="form-error">{error}</div> : null}

        <div className="agent-detail-tabs" role="tablist">
          {sections.map(section => (
            <button
              key={section.key}
              type="button"
              className={`agent-detail-tab ${activeSection === section.key ? 'agent-detail-tab--active' : ''}`}
              role="tab"
              aria-selected={activeSection === section.key}
              onClick={() => setActiveSection(section.key)}
            >
              {section.label}
            </button>
          ))}
        </div>

        <div className="agent-detail-content">
          {activeSection === 'base' && (
            <div className="agent-detail-section">
              <h4 className="agent-detail-subtitle">{copy.baseTitle}</h4>
              <div className="setup-form-grid">
                <div className="form-group">
                  <label>{copy.displayNameLabel}</label>
                  <input
                    className="form-input"
                    value={baseForm.displayName}
                    onChange={(event) => setBaseForm(current => ({ ...current, displayName: event.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>{copy.statusLabel}</label>
                  <select
                    className="form-select"
                    value={baseForm.status}
                    onChange={(event) => setBaseForm(current => ({ ...current, status: event.target.value as AgentDetail['status'] }))}
                  >
                    {statusOptions.map(option => (
                      <option key={option} value={option}>{getAgentStatusLabel(option, t)}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>{copy.sortOrderLabel}</label>
                  <input
                    className="form-input"
                    type="number"
                    value={baseForm.sortOrder}
                    onChange={(event) => setBaseForm(current => ({ ...current, sortOrder: event.target.value }))}
                  />
                </div>
              </div>

              <div className="ai-config-section-separator" />

              <h4 className="agent-detail-subtitle">{copy.soulTitle}</h4>
              <div className="setup-form-grid">
                <div className="form-group">
                  <label>{copy.roleSummaryLabel}</label>
                  <input
                    className="form-input"
                    value={soulForm.roleSummary}
                    onChange={(event) => setSoulForm(current => ({ ...current, roleSummary: event.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>{copy.introMessageLabel}</label>
                  <input
                    className="form-input"
                    value={soulForm.introMessage}
                    onChange={(event) => setSoulForm(current => ({ ...current, introMessage: event.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>{copy.speakingStyleLabel}</label>
                  <input
                    className="form-input"
                    value={soulForm.speakingStyle}
                    onChange={(event) => setSoulForm(current => ({ ...current, speakingStyle: event.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>{copy.personalityTraitsLabel}</label>
                  <input
                    className="form-input"
                    value={soulForm.personalityTraits}
                    onChange={(event) => setSoulForm(current => ({ ...current, personalityTraits: event.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>{copy.serviceFocusLabel}</label>
                  <input
                    className="form-input"
                    value={soulForm.serviceFocus}
                    onChange={(event) => setSoulForm(current => ({ ...current, serviceFocus: event.target.value }))}
                  />
                </div>
              </div>

              <div className="setup-form-actions">
                <button type="button" className="btn btn--primary" onClick={() => void handleSaveProfile()} disabled={saving}>
                  {saving ? copy.saving : copy.saveProfileButton}
                </button>
              </div>
            </div>
          )}

          {activeSection === 'runtime' && (
            <div className="agent-detail-section">
              <div className="setup-choice-group">
                <label className="setup-choice">
                  <input
                    type="checkbox"
                    checked={runtimeForm.conversationEnabled}
                    onChange={(event) => setRuntimeForm(current => ({ ...current, conversationEnabled: event.target.checked }))}
                  />
                  <span>{copy.conversationOption}</span>
                </label>
                <label className="setup-choice">
                  <input
                    type="checkbox"
                    checked={runtimeForm.defaultEntry}
                    onChange={(event) => setRuntimeForm(current => ({ ...current, defaultEntry: event.target.checked }))}
                  />
                  <span>{copy.defaultEntryOption}</span>
                </label>
              </div>
              <div className="setup-form-grid">
                <div className="form-group">
                  <label>{copy.memoryActionLabel}</label>
                  <select
                    className="form-select"
                    value={runtimeForm.memoryActionLevel}
                    onChange={(event) => setRuntimeForm(current => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}
                  >
                    {actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>{copy.configActionLabel}</label>
                  <select
                    className="form-select"
                    value={runtimeForm.configActionLevel}
                    onChange={(event) => setRuntimeForm(current => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}
                  >
                    {actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>{copy.operationActionLabel}</label>
                  <select
                    className="form-select"
                    value={runtimeForm.operationActionLevel}
                    onChange={(event) => setRuntimeForm(current => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}
                  >
                    {actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
              </div>

              <div className="ai-config-section-separator" />

              <div className="ai-config-subsection">
                <h5>{copy.modelBindingsTitle}</h5>
                <p className="ai-config-muted">{copy.modelBindingsHint}</p>
                <div className="ai-cognition-item">
                  <div className="ai-cognition-item__top">
                    <strong>{copy.agentDefaultBindingsTitle}</strong>
                  </div>
                  <div className="setup-form-grid">
                    {AI_CAPABILITIES.map(capability => (
                      <div key={capability} className="form-group">
                        <label>{getCapabilityLabel(capability, locale)}</label>
                        <select
                          className="form-select"
                          value={modelBindingForm[capability]}
                          onChange={(event) => setModelBindingForm(current => ({ ...current, [capability]: event.target.value }))}
                        >
                          <option value="">{copy.inheritHouseholdRoute}</option>
                          {providerOptionsByCapability[capability].map(provider => (
                            <option key={provider.id} value={provider.id}>
                              {provider.display_name}
                              {getProviderModelName(provider) ? ` · ${getProviderModelName(provider)}` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="ai-cognition-item">
                  <div className="ai-cognition-item__top">
                    <strong>{copy.agentSkillBindingsTitle}</strong>
                  </div>
                  {agentSkillPlugins.length === 0 ? (
                    <p className="ai-config-muted">{copy.noAgentSkillPlugins}</p>
                  ) : (
                    <div className="ai-cognition-list">
                      {agentSkillPlugins.map(plugin => {
                        const skillBindings = agentSkillBindingForm[plugin.id] ?? buildEmptyModelBindingForm();
                        return (
                          <div key={plugin.id} className="ai-cognition-item">
                            <div className="ai-cognition-item__top">
                              <strong>{plugin.name}</strong>
                              <span className="ai-config-muted">{plugin.id}</span>
                            </div>
                            <div className="setup-form-grid">
                              {AI_CAPABILITIES.map(capability => (
                                <div key={`${plugin.id}-${capability}`} className="form-group">
                                  <label>{getCapabilityLabel(capability, locale)}</label>
                                  <select
                                    className="form-select"
                                    value={skillBindings[capability]}
                                    onChange={(event) => setAgentSkillBindingForm(current => ({
                                      ...current,
                                      [plugin.id]: {
                                        ...(current[plugin.id] ?? buildEmptyModelBindingForm()),
                                        [capability]: event.target.value,
                                      },
                                    }))}
                                  >
                                    <option value="">{copy.inheritHouseholdRoute}</option>
                                    {providerOptionsByCapability[capability].map(provider => (
                                      <option key={provider.id} value={provider.id}>
                                        {provider.display_name}
                                        {getProviderModelName(provider) ? ` · ${getProviderModelName(provider)}` : ''}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              <div className="setup-form-actions">
                <button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>
                  {saving ? copy.saving : copy.saveRuntimeButton}
                </button>
              </div>
            </div>
          )}

          {activeSection === 'cognition' && (
            <div className="agent-detail-section">
              <div className="ai-cognition-list">
                {members.map(member => {
                  const cognition = cognitionForm[member.id] ?? { displayAddress: '', closenessLevel: '3', servicePriority: '3', communicationStyle: '', promptNotes: '' };
                  return (
                    <div key={member.id} className="ai-cognition-item">
                      <div className="ai-cognition-item__top">
                        <strong>{member.name}</strong>
                        <span className="ai-config-muted">{member.role}</span>
                      </div>
                      <div className="setup-form-grid">
                        <div className="form-group">
                          <label>{copy.displayAddressLabel}</label>
                          <input
                            className="form-input"
                            value={cognition.displayAddress}
                            onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))}
                          />
                        </div>
                        <div className="form-group">
                          <label>{copy.communicationStyleLabel}</label>
                          <input
                            className="form-input"
                            value={cognition.communicationStyle}
                            onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))}
                          />
                        </div>
                        <div className="form-group">
                          <label>{copy.promptNotesLabel}</label>
                          <input
                            className="form-input"
                            value={cognition.promptNotes}
                            onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="setup-form-actions">
                <button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>
                  {saving ? copy.saving : copy.saveCognitionButton}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  if (typeof document === 'undefined') {
    return content;
  }

  return createPortal(content, document.body);
}
