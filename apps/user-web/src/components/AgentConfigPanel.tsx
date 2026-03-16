import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from './base';
import { api } from '../lib/api';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../lib/agents';
import { parseTags, stringifyTags } from '../lib/aiConfig';
import type { AgentDetail, AgentSummary, Member } from '../lib/types';

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

function buildCreateForm(): CreateFormState {
  return {
    displayName: '家庭管家',
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: '负责家庭问答、提醒和日常陪伴。',
    introMessage: '你好，我是你的家庭管家。',
    speakingStyle: '温和、清晰、让人安心',
    personalityTraits: '细心, 稳定, 可靠',
    serviceFocus: '家庭问答, 日常提醒, 成员关怀',
  };
}

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
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState<CreateFormState>(buildCreateForm());
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

  const createActionLabel = compact ? '创建第一个 AI 管家' : (onlyButler ? '添加 AI 管家' : '添加 AI 助手');
  const createDisabled = (
    saving
    || !createForm.displayName.trim()
    || !createForm.selfIdentity.trim()
    || !createForm.roleSummary.trim()
    || parseTags(createForm.personalityTraits).length === 0
    || parseTags(createForm.serviceFocus).length === 0
  );

  const actionOptions = [
    { value: 'ask', label: '先询问我' },
    { value: 'notify', label: '先处理再告诉我' },
    { value: 'auto', label: '自动处理' },
  ] as const;

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
    setCreateForm(buildCreateForm());
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
          api.listAgents(householdId),
          api.listMembers(householdId),
        ]);
        if (cancelled) return;
        const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setSelectedAgentId(current => (nextAgents.some(item => item.id === current) ? current : (nextAgents[0]?.id ?? '')));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 AI 助手失败');
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
        const result = await api.getAgentDetail(householdId, selectedAgentId);
        if (!cancelled) {
          applyDetail(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载助手详情失败');
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
    const agentRows = await api.listAgents(householdId);
    const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
    const nextSelectedId = selectAgentId ?? (
      nextAgents.some(item => item.id === selectedAgentId) ? selectedAgentId : (nextAgents[0]?.id ?? '')
    );
    setAgents(nextAgents);
    setSelectedAgentId(nextSelectedId);
    if (nextSelectedId) {
      applyDetail(await api.getAgentDetail(householdId, nextSelectedId));
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
      const created = await api.createAgent(householdId, {
        display_name: createForm.displayName.trim(),
        agent_type: (onlyButler ? 'butler' : createForm.agentType) as CreateFormState['agentType'],
        self_identity: createForm.selfIdentity.trim(),
        role_summary: createForm.roleSummary.trim(),
        intro_message: createForm.introMessage.trim() || null,
        speaking_style: createForm.speakingStyle.trim() || null,
        personality_traits: parseTags(createForm.personalityTraits),
        service_focus: parseTags(createForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-web',
      });
      await reload(created.id);
      setCreateModalOpen(false);
      resetCreateForm();
      setStatus(`已添加 AI 助手：${created.display_name}`);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '添加 AI 助手失败');
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
      await api.updateAgent(householdId, detail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status as AgentDetail['status'],
        sort_order: Number(baseForm.sortOrder),
      });
      await reload(detail.id);
      setStatus('基本信息已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存基本信息失败');
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
      await api.upsertAgentSoul(householdId, detail.id, {
        self_identity: soulForm.selfIdentity.trim(),
        role_summary: soulForm.roleSummary.trim(),
        intro_message: soulForm.introMessage.trim() || null,
        speaking_style: soulForm.speakingStyle.trim() || null,
        personality_traits: parseTags(soulForm.personalityTraits),
        service_focus: parseTags(soulForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-web',
      });
      await reload(detail.id);
      setStatus('角色设定已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存角色设定失败');
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
      await api.upsertAgentRuntimePolicy(householdId, detail.id, {
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
      setStatus('使用方式已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存使用方式失败');
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
      await api.upsertAgentMemberCognitions(householdId, detail.id, {
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
      setStatus('与家人的互动方式已保存');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存互动方式失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      <Card className="ai-config-detail-card">
        <div className="agent-config-center__toolbar">
          <div className="agent-config-center__intro">
            <h3>{compact ? '创建第一个 AI 管家' : (onlyButler ? 'AI 管家' : 'AI 助手')}</h3>
            <p>
              {compact
                ? '先创建一个 AI 管家，之后还可以继续完善名字、语气和服务内容。'
                : '你可以在这里添加不同的 AI 助手，比如家庭管家、营养师或学习教练。'}
            </p>
          </div>
          <button className="btn btn--primary" type="button" onClick={openCreateModal}>
            {createActionLabel}
          </button>
        </div>
        {status ? <div className="setup-form-status">{status}</div> : null}
      </Card>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">正在读取 AI 助手信息...</div> : null}

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
                          {agent.conversation_enabled ? '可对话' : '已暂停对话'}
                        </span>
                      </div>
                      <p className="ai-config-card__meta">{getAgentTypeLabel(agent.agent_type)} · {getAgentStatusLabel(agent.status)}</p>
                      <p className="ai-config-card__summary">{agent.summary ?? '还没有填写角色简介。'}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {detail ? (
              <div className="ai-config-detail__grid">
                <Card className="ai-config-detail-card">
                  <h4>基本信息</h4>
                  <div className="setup-form-grid">
                    <div className="form-group">
                      <label>显示名称</label>
                      <input className="form-input" value={baseForm.displayName} onChange={(event) => setBaseForm(current => ({ ...current, displayName: event.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>当前状态</label>
                      <select className="form-select" value={baseForm.status} onChange={(event) => setBaseForm(current => ({ ...current, status: event.target.value }))}>
                        <option value="active">启用</option>
                        <option value="inactive">停用</option>
                        <option value="draft">草稿</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>显示顺序</label>
                      <input className="form-input" type="number" value={baseForm.sortOrder} onChange={(event) => setBaseForm(current => ({ ...current, sortOrder: event.target.value }))} />
                    </div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveBase()} disabled={saving}>保存基本信息</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>角色设定</h4>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>Ta 是谁</label><textarea className="form-input setup-textarea" value={soulForm.selfIdentity} onChange={(event) => setSoulForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                    <div className="form-group"><label>角色简介</label><textarea className="form-input setup-textarea" value={soulForm.roleSummary} onChange={(event) => setSoulForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                    <div className="form-group"><label>开场问候</label><input className="form-input" value={soulForm.introMessage} onChange={(event) => setSoulForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                    <div className="form-group"><label>说话风格</label><input className="form-input" value={soulForm.speakingStyle} onChange={(event) => setSoulForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                    <div className="form-group"><label>性格特点</label><input className="form-input" value={soulForm.personalityTraits} onChange={(event) => setSoulForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
                    <div className="form-group"><label>擅长内容</label><input className="form-input" value={soulForm.serviceFocus} onChange={(event) => setSoulForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveSoul()} disabled={saving}>保存角色设定</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>使用方式</h4>
                  <div className="setup-choice-group">
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.conversationEnabled} onChange={(event) => setRuntimeForm(current => ({ ...current, conversationEnabled: event.target.checked }))} /><span>允许和家人对话</span></label>
                    <label className="setup-choice"><input type="checkbox" checked={runtimeForm.defaultEntry} onChange={(event) => setRuntimeForm(current => ({ ...current, defaultEntry: event.target.checked }))} /><span>设为默认助手</span></label>
                  </div>
                  <div className="form-group"><label>适用标签</label><input className="form-input" value={runtimeForm.routingTags} onChange={(event) => setRuntimeForm(current => ({ ...current, routingTags: event.target.value }))} /></div>
                  <div className="setup-form-grid">
                    <div className="form-group"><label>涉及记忆内容时</label><select className="form-select" value={runtimeForm.memoryActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>涉及设置调整时</label><select className="form-select" value={runtimeForm.configActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                    <div className="form-group"><label>涉及后续操作时</label><select className="form-select" value={runtimeForm.operationActionLevel} onChange={(event) => setRuntimeForm(current => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>{actionOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>保存使用方式</button></div>
                </Card>

                <Card className="ai-config-detail-card">
                  <h4>与家人的互动方式</h4>
                  <div className="ai-cognition-list">
                    {members.map(member => {
                      const cognition = cognitionForm[member.id] ?? { displayAddress: '', closenessLevel: '3', servicePriority: '3', communicationStyle: '', promptNotes: '' };
                      return (
                        <div key={member.id} className="ai-cognition-item">
                          <div className="ai-cognition-item__top"><strong>{member.name}</strong><span className="ai-config-muted">{member.role}</span></div>
                          <div className="setup-form-grid">
                            <div className="form-group"><label>怎么称呼 Ta</label><input className="form-input" value={cognition.displayAddress} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))} /></div>
                            <div className="form-group"><label>熟悉程度</label><input className="form-input" type="number" min="1" max="5" value={cognition.closenessLevel} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, closenessLevel: event.target.value } }))} /></div>
                            <div className="form-group"><label>关注优先级</label><input className="form-input" type="number" min="1" max="5" value={cognition.servicePriority} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, servicePriority: event.target.value } }))} /></div>
                            <div className="form-group"><label>沟通方式</label><input className="form-input" value={cognition.communicationStyle} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))} /></div>
                            <div className="form-group"><label>补充备注</label><textarea className="form-input setup-textarea" value={cognition.promptNotes} onChange={(event) => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))} /></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>保存互动方式</button></div>
                </Card>
              </div>
            ) : null}
          </>
        ) : (
          <Card className="ai-config-detail-card agent-config-empty">
            <h4>{onlyButler ? '还没有 AI 管家' : '还没有 AI 助手'}</h4>
            <p className="ai-config-muted">先添加一个 AI 助手，再继续完善它的资料。</p>
          </Card>
        )
      ) : null}

      {createModalOpen ? (
        <div className="member-modal-overlay" onClick={saving ? undefined : closeCreateModal}>
          <div className="member-modal agent-create-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{createActionLabel}</h3>
                <p>先填写基础信息，创建后还可以继续完善。</p>
              </div>
            </div>
            <form className="settings-form agent-create-form" onSubmit={handleCreate}>
              <div className="setup-form-grid">
                {!onlyButler ? (
                  <div className="form-group">
                    <label htmlFor={`agent-type-${householdId}`}>助手类型</label>
                    <select id={`agent-type-${householdId}`} className="form-select" value={createForm.agentType} onChange={(event) => setCreateForm(current => ({ ...current, agentType: event.target.value as CreateFormState['agentType'] }))}>
                      <option value="butler">家庭管家</option>
                      <option value="nutritionist">营养师</option>
                      <option value="fitness_coach">健身教练</option>
                      <option value="study_coach">学习教练</option>
                      <option value="custom">自定义角色</option>
                    </select>
                  </div>
                ) : null}
                <div className="form-group"><label>显示名称</label><input className="form-input" value={createForm.displayName} onChange={(event) => setCreateForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                <div className="form-group"><label>Ta 是谁</label><textarea className="form-input setup-textarea" value={createForm.selfIdentity} onChange={(event) => setCreateForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                <div className="form-group"><label>角色简介</label><textarea className="form-input setup-textarea" value={createForm.roleSummary} onChange={(event) => setCreateForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                <div className="form-group"><label>开场问候</label><input className="form-input" value={createForm.introMessage} onChange={(event) => setCreateForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                <div className="form-group"><label>说话风格</label><input className="form-input" value={createForm.speakingStyle} onChange={(event) => setCreateForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                <div className="form-group"><label>性格特点</label><input className="form-input" value={createForm.personalityTraits} onChange={(event) => setCreateForm(current => ({ ...current, personalityTraits: event.target.value }))} /><div className="form-help">多个特点请用逗号分隔。</div></div>
                <div className="form-group"><label>擅长内容</label><input className="form-input" value={createForm.serviceFocus} onChange={(event) => setCreateForm(current => ({ ...current, serviceFocus: event.target.value }))} /><div className="form-help">多个内容请用逗号分隔。</div></div>
              </div>
              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={saving}>取消</button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={createDisabled}>{saving ? '添加中...' : createActionLabel}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
