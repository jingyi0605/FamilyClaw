import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../../assistant/assistant.agents';
import { Card } from '../../family/base';
import { parseTags, stringifyTags } from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type { AgentDetail, AgentSummary, Member } from '../settingsTypes';

export function AgentConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  onlyButler?: boolean;
  onChanged?: () => Promise<void> | void;
}) {
  const { householdId, compact = false, onlyButler = false, onChanged } = props;
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState({
    displayName: '灏忕埅绠″',
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: '???????????????????',
    introMessage: '????????????',
    speakingStyle: '????????',
    personalityTraits: '缁嗗績, 绋冲畾, 鏈夎竟鐣屾劅',
    serviceFocus: '瀹跺涵闂瓟, 鏃ュ父鎻愰啋, 鎴愬憳鍏虫€€',
  });
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
    () => agents.filter((item) => !onlyButler || item.agent_type === 'butler'),
    [agents, onlyButler],
  );

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
    setCognitionForm(Object.fromEntries(result.member_cognitions.map((item) => [
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
        if (cancelled) {
          return;
        }
        const nextAgents = onlyButler ? agentRows.items.filter((item) => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setSelectedAgentId((current) => (
          nextAgents.some((item) => item.id === current) ? current : (nextAgents[0]?.id ?? '')
        ));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '鍔犺浇 Agent 閰嶇疆澶辫触');
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
        if (cancelled) {
          return;
        }
        applyDetail(result);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '鍔犺浇 Agent 璇︽儏澶辫触');
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
    const nextAgents = onlyButler ? agentRows.items.filter((item) => item.agent_type === 'butler') : agentRows.items;
    const nextSelectedId = selectAgentId ?? (
      nextAgents.some((item) => item.id === selectedAgentId) ? selectedAgentId : (nextAgents[0]?.id ?? '')
    );
    setAgents(nextAgents);
    setSelectedAgentId(nextSelectedId);
    if (nextSelectedId) {
      const result = await settingsApi.getAgentDetail(householdId, nextSelectedId);
      applyDetail(result);
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
        agent_type: (onlyButler ? 'butler' : createForm.agentType) as 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom',
        self_identity: createForm.selfIdentity.trim(),
        role_summary: createForm.roleSummary.trim(),
        intro_message: createForm.introMessage.trim() || null,
        speaking_style: createForm.speakingStyle.trim() || null,
        personality_traits: parseTags(createForm.personalityTraits),
        service_focus: parseTags(createForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-app',
      });
      setStatus('Agent ???');
      setSelectedAgentId(created.id);
      await reload(created.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '鍒涘缓 Agent 澶辫触');
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveBase() {
    if (!detail) {
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.updateAgent(householdId, detail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status as AgentDetail['status'],
        sort_order: Number(baseForm.sortOrder),
      });
      setStatus('Agent ???????');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '淇濆瓨 Agent 鍩虹璧勬枡澶辫触');
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSoul() {
    if (!detail) {
      return;
    }
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
      setStatus('???????');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '淇濆瓨浜烘牸璧勬枡澶辫触');
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRuntime() {
    if (!detail) {
      return;
    }
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
      setStatus('杩愯鏃剁瓥鐣ュ凡淇濆瓨');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '?????????');
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveCognitions() {
    if (!detail) {
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.upsertAgentMemberCognitions(householdId, detail.id, {
        items: members.map((member) => {
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
      setStatus('???????');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '淇濆瓨鎴愬憳璁ょ煡澶辫触');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy">正在读取 Agent 配置...</div> : null}
      {!loading ? (
        <>
          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{compact ? '鍒涘缓棣栦釜绠″ Agent' : '鏂板 Agent'}</h3>
                <p>{compact ? '???????????????????????' : '????????????????'}</p>
              </div>
            </div>
            <form onSubmit={handleCreate}>
              <div className="setup-form-grid">
                {!onlyButler ? (
                  <div className="form-group">
                    <label htmlFor={`agent-type-${householdId}`}>Agent 绫诲瀷</label>
                    <select
                      id={`agent-type-${householdId}`}
                      className="form-select"
                      value={createForm.agentType}
                      onChange={(event) => setCreateForm((current) => ({ ...current, agentType: event.target.value }))}
                    >
                      <option value="butler">Butler</option>
                      <option value="nutritionist">Nutritionist</option>
                      <option value="fitness_coach">鍋ヨ韩鏁欑粌</option>
                      <option value="study_coach">瀛︿範鏁欑粌</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                ) : null}
                <div className="form-group"><label>鏄剧ず鍚嶇О</label><input className="form-input" value={createForm.displayName} onChange={(event) => setCreateForm((current) => ({ ...current, displayName: event.target.value }))} /></div>
                <div className="form-group"><label>鑷垜韬唤</label><textarea className="form-input setup-textarea" value={createForm.selfIdentity} onChange={(event) => setCreateForm((current) => ({ ...current, selfIdentity: event.target.value }))} /></div>
                <div className="form-group"><label>瑙掕壊鎽樿</label><textarea className="form-input setup-textarea" value={createForm.roleSummary} onChange={(event) => setCreateForm((current) => ({ ...current, roleSummary: event.target.value }))} /></div>
                <div className="form-group"><label>寮€鍦虹櫧</label><input className="form-input" value={createForm.introMessage} onChange={(event) => setCreateForm((current) => ({ ...current, introMessage: event.target.value }))} /></div>
                <div className="form-group"><label>璇磋瘽椋庢牸</label><input className="form-input" value={createForm.speakingStyle} onChange={(event) => setCreateForm((current) => ({ ...current, speakingStyle: event.target.value }))} /></div>
                <div className="form-group"><label>浜烘牸鐗瑰緛</label><input className="form-input" value={createForm.personalityTraits} onChange={(event) => setCreateForm((current) => ({ ...current, personalityTraits: event.target.value }))} /></div>
                <div className="form-group"><label>鏈嶅姟閲嶇偣</label><input className="form-input" value={createForm.serviceFocus} onChange={(event) => setCreateForm((current) => ({ ...current, serviceFocus: event.target.value }))} /></div>
              </div>
              {status ? <div className="setup-form-status">{status}</div> : null}
              <div className="setup-form-actions">
                <button
                  className="btn btn--primary"
                  type="submit"
                  disabled={
                    saving
                    || !createForm.displayName.trim()
                    || !createForm.selfIdentity.trim()
                    || !createForm.roleSummary.trim()
                    || parseTags(createForm.personalityTraits).length === 0
                    || parseTags(createForm.serviceFocus).length === 0
                  }
                >
                  {saving ? '淇濆瓨涓?..' : compact ? '鍒涘缓棣栦釜绠″' : '鍒涘缓 Agent'}
                </button>
              </div>
            </form>
          </Card>

          {!compact ? (
            <>
              <div className="ai-config-list">
                {visibleAgents.map((agent) => (
                  <button
                    key={agent.id}
                    type="button"
                    className={`ai-config-card ${selectedAgentId === agent.id ? 'ai-config-card--selected' : ''}`}
                    onClick={() => setSelectedAgentId(agent.id)}
                  >
                    <div className="ai-config-card__top">
                      <div className="ai-config-card__avatar">{getAgentTypeEmoji(agent.agent_type)}</div>
                      <div className="ai-config-card__text">
                        <div className="ai-config-card__title-row">
                          <h3>{agent.display_name}</h3>
                          <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                          <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>{agent.conversation_enabled ? '???' : '???'}</span>
                          </span>
                        </div>
                        <p className="ai-config-card__meta">{getAgentTypeLabel(agent.agent_type)} 路 {getAgentStatusLabel(agent.status)}</p>
                        <p className="ai-config-card__summary">{agent.summary ?? '??????????'}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              {detail ? (
                <div className="ai-config-detail__grid">
                  <Card className="ai-config-detail-card">
                    <h4>鍩虹璧勬枡</h4>
                    <div className="setup-form-grid">
                      <div className="form-group"><label>鏄剧ず鍚嶇О</label><input className="form-input" value={baseForm.displayName} onChange={(event) => setBaseForm((current) => ({ ...current, displayName: event.target.value }))} /></div>
                      <div className="form-group"><label>Status</label><select className="form-select" value={baseForm.status} onChange={(event) => setBaseForm((current) => ({ ...current, status: event.target.value }))}><option value="active">Active</option><option value="inactive">Inactive</option><option value="draft">Draft</option></select></div>
                      <div className="form-group"><label>鎺掑簭</label><input className="form-input" type="number" value={baseForm.sortOrder} onChange={(event) => setBaseForm((current) => ({ ...current, sortOrder: event.target.value }))} /></div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveBase()} disabled={saving}>淇濆瓨鍩虹璧勬枡</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>浜烘牸璧勬枡</h4>
                    <div className="setup-form-grid">
                      <div className="form-group"><label>鑷垜韬唤</label><textarea className="form-input setup-textarea" value={soulForm.selfIdentity} onChange={(event) => setSoulForm((current) => ({ ...current, selfIdentity: event.target.value }))} /></div>
                      <div className="form-group"><label>瑙掕壊鎽樿</label><textarea className="form-input setup-textarea" value={soulForm.roleSummary} onChange={(event) => setSoulForm((current) => ({ ...current, roleSummary: event.target.value }))} /></div>
                      <div className="form-group"><label>寮€鍦虹櫧</label><input className="form-input" value={soulForm.introMessage} onChange={(event) => setSoulForm((current) => ({ ...current, introMessage: event.target.value }))} /></div>
                      <div className="form-group"><label>璇磋瘽椋庢牸</label><input className="form-input" value={soulForm.speakingStyle} onChange={(event) => setSoulForm((current) => ({ ...current, speakingStyle: event.target.value }))} /></div>
                      <div className="form-group"><label>浜烘牸鐗瑰緛</label><input className="form-input" value={soulForm.personalityTraits} onChange={(event) => setSoulForm((current) => ({ ...current, personalityTraits: event.target.value }))} /></div>
                      <div className="form-group"><label>鏈嶅姟閲嶇偣</label><input className="form-input" value={soulForm.serviceFocus} onChange={(event) => setSoulForm((current) => ({ ...current, serviceFocus: event.target.value }))} /></div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveSoul()} disabled={saving}>淇濆瓨浜烘牸璧勬枡</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>Runtime Policy</h4>
                    <div className="setup-choice-group">
                      <label className="setup-choice"><input type="checkbox" checked={runtimeForm.conversationEnabled} onChange={(event) => setRuntimeForm((current) => ({ ...current, conversationEnabled: event.target.checked }))} /> <span>鍏佽杩涘叆瀵硅瘽</span></label>
                      <label className="setup-choice"><input type="checkbox" checked={runtimeForm.defaultEntry} onChange={(event) => setRuntimeForm((current) => ({ ...current, defaultEntry: event.target.checked }))} /> <span>璁句负榛樿鍏ュ彛</span></label>
                    </div>
                    <div className="form-group"><label>璺敱鏍囩</label><input className="form-input" value={runtimeForm.routingTags} onChange={(event) => setRuntimeForm((current) => ({ ...current, routingTags: event.target.value }))} /></div>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>璁板繂鍔ㄤ綔鎬庝箞澶勭悊</label>
                        <select className="form-select" value={runtimeForm.memoryActionLevel} onChange={(event) => setRuntimeForm((current) => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">Ask first, then write</option>
                          <option value="notify">Write first, then notify</option>
                          <option value="auto">鑷姩鎵ц锛屽彧鐣欑棔</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>閰嶇疆寤鸿鎬庝箞澶勭悊</label>
                        <select className="form-select" value={runtimeForm.configActionLevel} onChange={(event) => setRuntimeForm((current) => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">Ask first, then change</option>
                          <option value="notify">Change first, then notify</option>
                          <option value="auto">鑷姩淇敼锛屽彧鐣欑棔</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>鎻愰啋鍜屽悗缁姩浣滄€庝箞澶勭悊</label>
                        <select className="form-select" value={runtimeForm.operationActionLevel} onChange={(event) => setRuntimeForm((current) => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">Ask first, then act</option>
                          <option value="notify">Act first, then notify</option>
                          <option value="auto">鑷姩鎵ц锛屽彧鐣欑棔</option>
                        </select>
                      </div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>Save Runtime Policy</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>鎴愬憳璁ょ煡</h4>
                    <div className="ai-cognition-list">
                      {members.map((member) => {
                        const cognition = cognitionForm[member.id] ?? { displayAddress: '', closenessLevel: '3', servicePriority: '3', communicationStyle: '', promptNotes: '' };
                        return (
                          <div key={member.id} className="ai-cognition-item">
                            <div className="ai-cognition-item__top">
                              <strong>{member.name}</strong>
                              <span className="ai-config-muted">{member.role}</span>
                            </div>
                            <div className="setup-form-grid">
                              <div className="form-group"><label>绉板懠</label><input className="form-input" value={cognition.displayAddress} onChange={(event) => setCognitionForm((current) => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))} /></div>
                              <div className="form-group"><label>Closeness</label><input className="form-input" type="number" min="1" max="5" value={cognition.closenessLevel} onChange={(event) => setCognitionForm((current) => ({ ...current, [member.id]: { ...cognition, closenessLevel: event.target.value } }))} /></div>
                              <div className="form-group"><label>Service Priority</label><input className="form-input" type="number" min="1" max="5" value={cognition.servicePriority} onChange={(event) => setCognitionForm((current) => ({ ...current, [member.id]: { ...cognition, servicePriority: event.target.value } }))} /></div>
                              <div className="form-group"><label>Communication Style</label><input className="form-input" value={cognition.communicationStyle} onChange={(event) => setCognitionForm((current) => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))} /></div>
                              <div className="form-group"><label>鎻愮ず澶囨敞</label><textarea className="form-input setup-textarea" value={cognition.promptNotes} onChange={(event) => setCognitionForm((current) => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))} /></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>淇濆瓨鎴愬憳璁ょ煡</button></div>
                  </Card>
                </div>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
