import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from './base';
import { api } from '../lib/api';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../lib/agents';
import { parseTags, stringifyTags } from '../lib/aiConfig';
import type { AgentDetail, AgentSummary, Member } from '../lib/types';

type Props = {
  householdId: string;
  compact?: boolean;
  onlyButler?: boolean;
  onChanged?: () => Promise<void> | void;
};

export function AgentConfigPanel({ householdId, compact = false, onlyButler = false, onChanged }: Props) {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState({
    displayName: '小爪管家',
    agentType: 'butler',
    selfIdentity: '',
    roleSummary: '负责家庭问答、日常提醒和基础陪伴服务。',
    introMessage: '你好，我是你的家庭管家。',
    speakingStyle: '温和、直接、靠谱',
    personalityTraits: '细心, 稳定, 有边界感',
    serviceFocus: '家庭问答, 日常提醒, 成员关怀',
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
    () => agents.filter(item => !onlyButler || item.agent_type === 'butler'),
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
        if (cancelled) {
          return;
        }
        const nextAgents = onlyButler ? agentRows.items.filter(item => item.agent_type === 'butler') : agentRows.items;
        setAgents(nextAgents);
        setMembers(memberRows.items);
        setSelectedAgentId(current => (nextAgents.some(item => item.id === current) ? current : (nextAgents[0]?.id ?? '')));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 Agent 配置失败');
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
        if (cancelled) {
          return;
        }
        applyDetail(result);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 Agent 详情失败');
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
    const nextSelectedId = selectAgentId ?? (nextAgents.some(item => item.id === selectedAgentId) ? selectedAgentId : (nextAgents[0]?.id ?? ''));
    setAgents(nextAgents);
    setSelectedAgentId(nextSelectedId);
    if (nextSelectedId) {
      const result = await api.getAgentDetail(householdId, nextSelectedId);
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
      const created = await api.createAgent(householdId, {
        display_name: createForm.displayName.trim(),
        agent_type: (onlyButler ? 'butler' : createForm.agentType) as 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom',
        self_identity: createForm.selfIdentity.trim(),
        role_summary: createForm.roleSummary.trim(),
        intro_message: createForm.introMessage.trim() || null,
        speaking_style: createForm.speakingStyle.trim() || null,
        personality_traits: parseTags(createForm.personalityTraits),
        service_focus: parseTags(createForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-web',
      });
      setStatus('Agent 已创建。');
      setSelectedAgentId(created.id);
      await reload(created.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '创建 Agent 失败');
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
      await api.updateAgent(householdId, detail.id, {
        display_name: baseForm.displayName.trim(),
        status: baseForm.status as AgentDetail['status'],
        sort_order: Number(baseForm.sortOrder),
      });
      setStatus('Agent 基础资料已保存。');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 Agent 基础资料失败');
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
      await api.upsertAgentSoul(householdId, detail.id, {
        self_identity: soulForm.selfIdentity.trim(),
        role_summary: soulForm.roleSummary.trim(),
        intro_message: soulForm.introMessage.trim() || null,
        speaking_style: soulForm.speakingStyle.trim() || null,
        personality_traits: parseTags(soulForm.personalityTraits),
        service_focus: parseTags(soulForm.serviceFocus),
        created_by: compact ? 'setup-wizard' : 'user-web',
      });
      setStatus('人格资料已保存。');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存人格资料失败');
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
      setStatus('运行时策略已保存。');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存运行时策略失败');
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
      setStatus('成员认知已保存。');
      await reload(detail.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员认知失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-config-center">
      {error && <Card><p className="form-error">{error}</p></Card>}
      {loading && <Card><p>正在读取 Agent 配置…</p></Card>}
      {!loading && (
        <>
          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{compact ? '创建首个管家 Agent' : '新增 Agent'}</h3>
                <p>{compact ? '这里复用正式创建逻辑，不再维护第二套向导表单。' : '先把创建入口做正，再谈人格细节。'}</p>
              </div>
            </div>
            <form onSubmit={handleCreate}>
              <div className="setup-form-grid">
                {!onlyButler && (
                  <div className="form-group">
                    <label htmlFor={`agent-type-${householdId}`}>Agent 类型</label>
                    <select id={`agent-type-${householdId}`} className="form-select" value={createForm.agentType} onChange={event => setCreateForm(current => ({ ...current, agentType: event.target.value }))}>
                      <option value="butler">主管家</option>
                      <option value="nutritionist">营养师</option>
                      <option value="fitness_coach">健身教练</option>
                      <option value="study_coach">学习教练</option>
                      <option value="custom">自定义角色</option>
                    </select>
                  </div>
                )}
                <div className="form-group"><label>显示名称</label><input className="form-input" value={createForm.displayName} onChange={event => setCreateForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                <div className="form-group"><label>自我身份</label><textarea className="form-input setup-textarea" value={createForm.selfIdentity} onChange={event => setCreateForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                <div className="form-group"><label>角色摘要</label><textarea className="form-input setup-textarea" value={createForm.roleSummary} onChange={event => setCreateForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                <div className="form-group"><label>开场白</label><input className="form-input" value={createForm.introMessage} onChange={event => setCreateForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                <div className="form-group"><label>说话风格</label><input className="form-input" value={createForm.speakingStyle} onChange={event => setCreateForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                <div className="form-group"><label>人格特征</label><input className="form-input" value={createForm.personalityTraits} onChange={event => setCreateForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
                <div className="form-group"><label>服务重点</label><input className="form-input" value={createForm.serviceFocus} onChange={event => setCreateForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
              </div>
              {status && <div className="setup-form-status">{status}</div>}
              <div className="setup-form-actions">
                <button className="btn btn--primary" type="submit" disabled={saving || !createForm.displayName.trim() || !createForm.selfIdentity.trim() || !createForm.roleSummary.trim() || parseTags(createForm.personalityTraits).length === 0 || parseTags(createForm.serviceFocus).length === 0}>
                  {saving ? '保存中…' : compact ? '创建首个管家' : '创建 Agent'}
                </button>
              </div>
            </form>
          </Card>

          {!compact && (
            <>
              <div className="ai-config-list">
                {visibleAgents.map(agent => (
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
                          <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>{agent.conversation_enabled ? '可对话' : '已静默'}</span>
                        </div>
                        <p className="ai-config-card__meta">{getAgentTypeLabel(agent.agent_type)} · {getAgentStatusLabel(agent.status)}</p>
                        <p className="ai-config-card__summary">{agent.summary ?? '还没写角色摘要。'}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              {detail && (
                <div className="ai-config-detail__grid">
                  <Card className="ai-config-detail-card">
                    <h4>基础资料</h4>
                    <div className="setup-form-grid">
                      <div className="form-group"><label>显示名称</label><input className="form-input" value={baseForm.displayName} onChange={event => setBaseForm(current => ({ ...current, displayName: event.target.value }))} /></div>
                      <div className="form-group"><label>状态</label><select className="form-select" value={baseForm.status} onChange={event => setBaseForm(current => ({ ...current, status: event.target.value }))}><option value="active">启用</option><option value="inactive">停用</option><option value="draft">草稿</option></select></div>
                      <div className="form-group"><label>排序</label><input className="form-input" type="number" value={baseForm.sortOrder} onChange={event => setBaseForm(current => ({ ...current, sortOrder: event.target.value }))} /></div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveBase()} disabled={saving}>保存基础资料</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>人格资料</h4>
                    <div className="setup-form-grid">
                      <div className="form-group"><label>自我身份</label><textarea className="form-input setup-textarea" value={soulForm.selfIdentity} onChange={event => setSoulForm(current => ({ ...current, selfIdentity: event.target.value }))} /></div>
                      <div className="form-group"><label>角色摘要</label><textarea className="form-input setup-textarea" value={soulForm.roleSummary} onChange={event => setSoulForm(current => ({ ...current, roleSummary: event.target.value }))} /></div>
                      <div className="form-group"><label>开场白</label><input className="form-input" value={soulForm.introMessage} onChange={event => setSoulForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
                      <div className="form-group"><label>说话风格</label><input className="form-input" value={soulForm.speakingStyle} onChange={event => setSoulForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
                      <div className="form-group"><label>人格特征</label><input className="form-input" value={soulForm.personalityTraits} onChange={event => setSoulForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
                      <div className="form-group"><label>服务重点</label><input className="form-input" value={soulForm.serviceFocus} onChange={event => setSoulForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveSoul()} disabled={saving}>保存人格资料</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>运行时策略</h4>
                    <div className="setup-choice-group">
                      <label className="setup-choice"><input type="checkbox" checked={runtimeForm.conversationEnabled} onChange={event => setRuntimeForm(current => ({ ...current, conversationEnabled: event.target.checked }))} /> <span>允许进入对话</span></label>
                      <label className="setup-choice"><input type="checkbox" checked={runtimeForm.defaultEntry} onChange={event => setRuntimeForm(current => ({ ...current, defaultEntry: event.target.checked }))} /> <span>设为默认入口</span></label>
                    </div>
                    <div className="form-group"><label>路由标签</label><input className="form-input" value={runtimeForm.routingTags} onChange={event => setRuntimeForm(current => ({ ...current, routingTags: event.target.value }))} /></div>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>记忆动作怎么处理</label>
                        <select className="form-select" value={runtimeForm.memoryActionLevel} onChange={event => setRuntimeForm(current => ({ ...current, memoryActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">先问我，再写入</option>
                          <option value="notify">先执行，再通知我</option>
                          <option value="auto">自动执行，只留痕</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>配置建议怎么处理</label>
                        <select className="form-select" value={runtimeForm.configActionLevel} onChange={event => setRuntimeForm(current => ({ ...current, configActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">先问我，再修改</option>
                          <option value="notify">先修改，再通知我</option>
                          <option value="auto">自动修改，只留痕</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>提醒和后续动作怎么处理</label>
                        <select className="form-select" value={runtimeForm.operationActionLevel} onChange={event => setRuntimeForm(current => ({ ...current, operationActionLevel: event.target.value as 'ask' | 'notify' | 'auto' }))}>
                          <option value="ask">先问我，再执行</option>
                          <option value="notify">先执行，再通知我</option>
                          <option value="auto">自动执行，只留痕</option>
                        </select>
                      </div>
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveRuntime()} disabled={saving}>保存运行时策略</button></div>
                  </Card>

                  <Card className="ai-config-detail-card">
                    <h4>成员认知</h4>
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
                              <div className="form-group"><label>称呼</label><input className="form-input" value={cognition.displayAddress} onChange={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, displayAddress: event.target.value } }))} /></div>
                              <div className="form-group"><label>亲密度</label><input className="form-input" type="number" min="1" max="5" value={cognition.closenessLevel} onChange={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, closenessLevel: event.target.value } }))} /></div>
                              <div className="form-group"><label>服务优先级</label><input className="form-input" type="number" min="1" max="5" value={cognition.servicePriority} onChange={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, servicePriority: event.target.value } }))} /></div>
                              <div className="form-group"><label>沟通风格</label><input className="form-input" value={cognition.communicationStyle} onChange={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, communicationStyle: event.target.value } }))} /></div>
                              <div className="form-group"><label>提示备注</label><textarea className="form-input setup-textarea" value={cognition.promptNotes} onChange={event => setCognitionForm(current => ({ ...current, [member.id]: { ...cognition, promptNotes: event.target.value } }))} /></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="setup-form-actions"><button type="button" className="btn btn--primary" onClick={() => void handleSaveCognitions()} disabled={saving}>保存成员认知</button></div>
                  </Card>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
