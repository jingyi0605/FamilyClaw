import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card, EmptyState, PageHeader, Section } from '../components/base';
import { api } from '../lib/api';
import type { AgentSummary, AiCapabilityRoute, AiProviderProfile, HouseholdSetupStepCode, Member } from '../lib/types';
import { useAuthContext } from '../state/auth';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';

const STEP_LABELS: Record<HouseholdSetupStepCode, string> = {
  family_profile: '家庭资料',
  first_member: '首位成员',
  provider_setup: 'AI 供应商',
  first_butler_agent: '首个管家 Agent',
  finish: '完成放行',
};

const SETUP_ROUTE_CAPABILITIES = ['qa_generation', 'qa_structured_answer'];

function parseTags(raw: string) {
  return Array.from(new Set(raw.split(/[,，、\n]/).map(item => item.trim()).filter(Boolean)));
}

function getDefaultTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
  } catch {
    return 'Asia/Shanghai';
  }
}

function getDefaultLocale() {
  return typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'zh-CN';
}

function buildWizardProviderCode(householdId: string) {
  return `wizard.sim.${householdId.slice(0, 8).toLowerCase()}.${Date.now().toString(36)}`;
}

export function SetupWizardPage() {
  const { refreshAuth } = useAuthContext();
  const {
    currentHousehold,
    currentHouseholdId,
    households,
    setCurrentHouseholdId,
    refreshCurrentHousehold,
    refreshHouseholds,
  } = useHouseholdContext();
  const { setupStatus, setupStatusLoading, setupStatusError, refreshSetupStatus } = useSetupContext();

  const [familyForm, setFamilyForm] = useState({ name: '', city: '', timezone: getDefaultTimezone(), locale: getDefaultLocale() });
  const [memberForm, setMemberForm] = useState({
    name: '',
    nickname: '',
    role: 'admin' as Member['role'],
    gender: '' as '' | NonNullable<Member['gender']>,
    age_group: 'adult' as NonNullable<Member['age_group']>,
    phone: '',
    username: 'user',
    password: '',
    confirmPassword: '',
  });
  const [providerMode, setProviderMode] = useState<'existing' | 'simulated'>('simulated');
  const [providerForm, setProviderForm] = useState({ providerId: '', displayName: '', modelName: 'familyclaw-simulated-qa' });
  const [agentForm, setAgentForm] = useState({
    displayName: '小爪管家',
    selfIdentity: '',
    roleSummary: '负责家庭问答、日常提醒和基础陪伴服务。',
    introMessage: '你好，我是你的家庭管家。',
    speakingStyle: '温和、直接、靠谱',
    personalityTraits: '细心, 稳定, 有边界感',
    serviceFocus: '家庭问答, 日常提醒, 成员关怀',
  });
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [familySubmitting, setFamilySubmitting] = useState(false);
  const [memberSubmitting, setMemberSubmitting] = useState(false);
  const [providerSubmitting, setProviderSubmitting] = useState(false);
  const [agentSubmitting, setAgentSubmitting] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [familyError, setFamilyError] = useState('');
  const [memberError, setMemberError] = useState('');
  const [providerError, setProviderError] = useState('');
  const [agentError, setAgentError] = useState('');
  const [aiError, setAiError] = useState('');
  const [familyStatus, setFamilyStatus] = useState('');
  const [memberStatus, setMemberStatus] = useState('');
  const [providerStatus, setProviderStatus] = useState('');
  const [agentStatus, setAgentStatus] = useState('');

  useEffect(() => {
    setFamilyForm({
      name: currentHousehold?.name ?? '',
      city: currentHousehold?.city ?? '',
      timezone: currentHousehold?.timezone ?? getDefaultTimezone(),
      locale: currentHousehold?.locale ?? getDefaultLocale(),
    });
  }, [currentHousehold?.name, currentHousehold?.city, currentHousehold?.timezone, currentHousehold?.locale, currentHouseholdId]);

  useEffect(() => {
    if (!agentForm.selfIdentity.trim()) {
      setAgentForm(current => ({
        ...current,
        selfIdentity: currentHousehold?.name
          ? `我是 ${currentHousehold.name} 的家庭管家，负责帮助家人完成日常问答与提醒。`
          : '我是这个家庭的家庭管家，负责帮助家人完成日常问答与提醒。',
      }));
    }
  }, [currentHousehold?.name]);

  async function loadAiResources(householdId: string) {
    setAiLoading(true);
    setAiError('');
    try {
      const [providerRows, routeRows, agentRows] = await Promise.all([
        api.listAiProviders(),
        api.listAiRoutes(householdId),
        api.listAgents(householdId),
      ]);
      setProviders(providerRows);
      setRoutes(routeRows);
      setAgents(agentRows.items);
      if (!providerForm.providerId && providerRows.length > 0) {
        setProviderForm(current => ({ ...current, providerId: providerRows[0].id }));
      }
    } catch (error) {
      setAiError(error instanceof Error ? error.message : '加载 AI 初始化资源失败');
      setProviders([]);
      setRoutes([]);
      setAgents([]);
    } finally {
      setAiLoading(false);
    }
  }

  useEffect(() => {
    if (!currentHouseholdId) {
      setProviders([]);
      setRoutes([]);
      setAgents([]);
      return;
    }
    void loadAiResources(currentHouseholdId);
  }, [currentHouseholdId]);

  const currentStep = setupStatus?.current_step ?? 'family_profile';
  const currentProviderRoute = useMemo(
    () => routes.find(route => route.capability === 'qa_generation' && route.enabled && route.primary_provider_profile_id),
    [routes],
  );
  const currentProvider = useMemo(
    () => providers.find(provider => provider.id === currentProviderRoute?.primary_provider_profile_id) ?? null,
    [providers, currentProviderRoute?.primary_provider_profile_id],
  );
  const currentButlerAgent = useMemo(
    () => agents.find(agent => agent.agent_type === 'butler' && agent.status === 'active') ?? null,
    [agents],
  );

  async function handleFamilySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setFamilySubmitting(true);
    setFamilyError('');
    setFamilyStatus('');
    try {
      await api.updateHousehold(currentHouseholdId, {
        name: familyForm.name.trim(),
        city: familyForm.city.trim(),
        timezone: familyForm.timezone.trim(),
        locale: familyForm.locale.trim(),
      });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
      await refreshSetupStatus(currentHouseholdId);
      setFamilyStatus('家庭资料已保存。');
    } catch (error) {
      setFamilyError(error instanceof Error ? error.message : '保存家庭资料失败');
    } finally {
      setFamilySubmitting(false);
    }
  }

  async function handleMemberSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setMemberSubmitting(true);
    setMemberError('');
    setMemberStatus('');
    try {
      if (!memberForm.password.trim()) {
        throw new Error('请先设置正式密码');
      }
      if (memberForm.password !== memberForm.confirmPassword) {
        throw new Error('两次输入的密码不一致');
      }
      const member = await api.createMember({
        household_id: currentHouseholdId,
        name: memberForm.name.trim(),
        nickname: memberForm.nickname.trim() || null,
        role: memberForm.role,
        gender: memberForm.gender || null,
        age_group: memberForm.age_group || null,
        phone: memberForm.phone.trim() || null,
        guardian_member_id: null,
      });
      await api.completeBootstrapAccount({
        household_id: currentHouseholdId,
        member_id: member.id,
        username: memberForm.username.trim() || 'user',
        password: memberForm.password,
      });
      await refreshAuth();
      await refreshHouseholds();
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshSetupStatus(currentHouseholdId);
      setMemberStatus('首位成员和正式账号已创建，默认 user/user 已失效。');
      setMemberForm(current => ({ ...current, name: '', nickname: '', phone: '', password: '', confirmPassword: '' }));
    } catch (error) {
      setMemberError(error instanceof Error ? error.message : '创建首位成员失败');
    } finally {
      setMemberSubmitting(false);
    }
  }

  async function handleProviderSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setProviderSubmitting(true);
    setProviderError('');
    setProviderStatus('');
    try {
      let providerId = providerForm.providerId;
      if (providerMode === 'simulated') {
        const createdProvider = await api.createAiProvider({
          provider_code: buildWizardProviderCode(currentHouseholdId),
          display_name: providerForm.displayName.trim() || '向导模拟供应商',
          transport_type: 'native_sdk',
          base_url: null,
          api_version: providerForm.modelName.trim() || 'familyclaw-simulated-qa',
          secret_ref: null,
          enabled: true,
          supported_capabilities: SETUP_ROUTE_CAPABILITIES,
          privacy_level: 'private_cloud',
          latency_budget_ms: 3000,
          cost_policy: {},
          extra_config: { model_name: providerForm.modelName.trim() || 'familyclaw-simulated-qa', setup_source: 'wizard' },
        });
        providerId = createdProvider.id;
      }
      if (!providerId) throw new Error('请先选择一个可用供应商');
      await Promise.all(
        SETUP_ROUTE_CAPABILITIES.map(capability => api.upsertAiRoute(capability, {
          capability,
          household_id: currentHouseholdId,
          primary_provider_profile_id: providerId,
          fallback_provider_profile_ids: [],
          routing_mode: 'primary_then_fallback',
          timeout_ms: 15000,
          max_retry_count: 0,
          allow_remote: true,
          prompt_policy: {},
          response_policy: { template_fallback_enabled: true },
          enabled: true,
        })),
      );
      await loadAiResources(currentHouseholdId);
      await refreshSetupStatus(currentHouseholdId);
      setProviderStatus('供应商配置已完成。');
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : '配置供应商失败');
    } finally {
      setProviderSubmitting(false);
    }
  }

  async function handleAgentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setAgentSubmitting(true);
    setAgentError('');
    setAgentStatus('');
    try {
      await api.createAgent(currentHouseholdId, {
        display_name: agentForm.displayName.trim(),
        agent_type: 'butler',
        self_identity: agentForm.selfIdentity.trim(),
        role_summary: agentForm.roleSummary.trim(),
        intro_message: agentForm.introMessage.trim() || null,
        speaking_style: agentForm.speakingStyle.trim() || null,
        personality_traits: parseTags(agentForm.personalityTraits),
        service_focus: parseTags(agentForm.serviceFocus),
        service_boundaries: null,
        conversation_enabled: true,
        default_entry: true,
        created_by: 'user-web',
      });
      await loadAiResources(currentHouseholdId);
      await refreshSetupStatus(currentHouseholdId);
      setAgentStatus('首个管家 Agent 已创建。');
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : '创建首个管家失败');
    } finally {
      setAgentSubmitting(false);
    }
  }

  function renderCurrentStep() {
    if (currentStep === 'family_profile') {
      return (
        <form className="settings-form" onSubmit={handleFamilySubmit}>
          <div className="form-group"><label htmlFor="setup-family-name">家庭名称</label><input id="setup-family-name" className="form-input" value={familyForm.name} onChange={event => setFamilyForm(current => ({ ...current, name: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-family-city">城市</label><input id="setup-family-city" className="form-input" value={familyForm.city} onChange={event => setFamilyForm(current => ({ ...current, city: event.target.value }))} required /></div>
          <div className="setup-form-grid">
            <div className="form-group"><label htmlFor="setup-family-timezone">时区</label><input id="setup-family-timezone" className="form-input" value={familyForm.timezone} onChange={event => setFamilyForm(current => ({ ...current, timezone: event.target.value }))} required /></div>
            <div className="form-group"><label htmlFor="setup-family-locale">语言区域</label><input id="setup-family-locale" className="form-input" value={familyForm.locale} onChange={event => setFamilyForm(current => ({ ...current, locale: event.target.value }))} required /></div>
          </div>
          {familyError && <div className="form-error">{familyError}</div>}
          {familyStatus && <div className="setup-form-status">{familyStatus}</div>}
          <div className="setup-form-actions"><button type="submit" className="btn btn--primary" disabled={familySubmitting || !familyForm.name.trim() || !familyForm.city.trim()}> {familySubmitting ? '保存中…' : '保存家庭资料'} </button></div>
        </form>
      );
    }

    if (currentStep === 'first_member') {
      return (
        <form className="settings-form" onSubmit={handleMemberSubmit}>
          <div className="form-group"><label htmlFor="setup-member-name">成员姓名</label><input id="setup-member-name" className="form-input" value={memberForm.name} onChange={event => setMemberForm(current => ({ ...current, name: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-member-nickname">称呼 / 昵称</label><input id="setup-member-nickname" className="form-input" value={memberForm.nickname} onChange={event => setMemberForm(current => ({ ...current, nickname: event.target.value }))} /></div>
          <div className="setup-form-grid">
            <div className="form-group"><label htmlFor="setup-member-role">角色</label><select id="setup-member-role" className="form-select" value={memberForm.role} onChange={event => setMemberForm(current => ({ ...current, role: event.target.value as Member['role'] }))}><option value="admin">管理员</option><option value="adult">成人</option><option value="child">儿童</option><option value="elder">长辈</option><option value="guest">访客</option></select></div>
            <div className="form-group"><label htmlFor="setup-member-age">年龄段</label><select id="setup-member-age" className="form-select" value={memberForm.age_group} onChange={event => setMemberForm(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}><option value="adult">成人</option><option value="teen">青少年</option><option value="child">儿童</option><option value="toddler">幼童</option><option value="elder">长辈</option></select></div>
          </div>
          <div className="setup-form-grid">
            <div className="form-group"><label htmlFor="setup-member-gender">性别</label><select id="setup-member-gender" className="form-select" value={memberForm.gender} onChange={event => setMemberForm(current => ({ ...current, gender: event.target.value as '' | NonNullable<Member['gender']> }))}><option value="">暂不填写</option><option value="male">男</option><option value="female">女</option></select></div>
            <div className="form-group"><label htmlFor="setup-member-phone">手机号</label><input id="setup-member-phone" className="form-input" value={memberForm.phone} onChange={event => setMemberForm(current => ({ ...current, phone: event.target.value }))} /></div>
          </div>
          <div className="setup-inline-tip"><strong>账号说明：</strong><span>初始化阶段默认口令是 `user/user`。这一步会创建正式账号，并立刻让默认口令失效。</span></div>
          <div className="setup-form-grid">
            <div className="form-group"><label htmlFor="setup-member-username">正式用户名</label><input id="setup-member-username" className="form-input" value={memberForm.username} onChange={event => setMemberForm(current => ({ ...current, username: event.target.value }))} required /></div>
            <div className="form-group"><label htmlFor="setup-member-password">正式密码</label><input id="setup-member-password" type="password" className="form-input" value={memberForm.password} onChange={event => setMemberForm(current => ({ ...current, password: event.target.value }))} required /></div>
          </div>
          <div className="form-group"><label htmlFor="setup-member-password-confirm">确认密码</label><input id="setup-member-password-confirm" type="password" className="form-input" value={memberForm.confirmPassword} onChange={event => setMemberForm(current => ({ ...current, confirmPassword: event.target.value }))} required /></div>
          {memberError && <div className="form-error">{memberError}</div>}
          {memberStatus && <div className="setup-form-status">{memberStatus}</div>}
          <div className="setup-form-actions"><button type="submit" className="btn btn--primary" disabled={memberSubmitting || !memberForm.name.trim() || !memberForm.username.trim() || !memberForm.password || !memberForm.confirmPassword}>{memberSubmitting ? '创建中…' : '创建首位成员并完成账号初始化'}</button></div>
        </form>
      );
    }

    if (currentStep === 'provider_setup') {
      return (
        <form className="settings-form" onSubmit={handleProviderSubmit}>
          <div className="setup-inline-tip"><strong>当前绑定：</strong><span>{currentProvider ? `${currentProvider.display_name}（${currentProvider.provider_code}）` : '还没有配置'}</span></div>
          <div className="form-group">
            <label>配置方式</label>
            <div className="setup-choice-group">
              <label className="setup-choice"><input type="radio" checked={providerMode === 'simulated'} onChange={() => setProviderMode('simulated')} /> <span>快速创建模拟供应商</span></label>
              <label className="setup-choice"><input type="radio" checked={providerMode === 'existing'} onChange={() => setProviderMode('existing')} /> <span>绑定已有供应商</span></label>
            </div>
          </div>
          {providerMode === 'simulated' ? (
            <>
              <div className="form-group"><label htmlFor="setup-provider-name">供应商显示名</label><input id="setup-provider-name" className="form-input" value={providerForm.displayName} onChange={event => setProviderForm(current => ({ ...current, displayName: event.target.value }))} required /></div>
              <div className="form-group"><label htmlFor="setup-provider-model">模型名</label><input id="setup-provider-model" className="form-input" value={providerForm.modelName} onChange={event => setProviderForm(current => ({ ...current, modelName: event.target.value }))} /></div>
            </>
          ) : (
            <div className="form-group"><label htmlFor="setup-provider-select">选择已有供应商</label><select id="setup-provider-select" className="form-select" value={providerForm.providerId} onChange={event => setProviderForm(current => ({ ...current, providerId: event.target.value }))}><option value="">请选择</option>{providers.map(provider => <option key={provider.id} value={provider.id}>{provider.display_name} / {provider.provider_code}</option>)}</select></div>
          )}
          {aiError && <div className="form-error">{aiError}</div>}
          {providerError && <div className="form-error">{providerError}</div>}
          {providerStatus && <div className="setup-form-status">{providerStatus}</div>}
          <div className="setup-form-actions"><button type="submit" className="btn btn--primary" disabled={providerSubmitting || aiLoading || (providerMode === 'simulated' && !providerForm.displayName.trim()) || (providerMode === 'existing' && !providerForm.providerId)}>{providerSubmitting ? '配置中…' : '保存供应商配置'}</button></div>
        </form>
      );
    }

    if (currentStep === 'first_butler_agent') {
      return (
        <form className="settings-form" onSubmit={handleAgentSubmit}>
          <div className="setup-inline-tip"><strong>当前供应商：</strong><span>{currentProvider ? currentProvider.display_name : '未配置'}</span></div>
          <div className="form-group"><label htmlFor="setup-agent-name">管家名称</label><input id="setup-agent-name" className="form-input" value={agentForm.displayName} onChange={event => setAgentForm(current => ({ ...current, displayName: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-agent-self">自我身份</label><textarea id="setup-agent-self" className="form-input setup-textarea" value={agentForm.selfIdentity} onChange={event => setAgentForm(current => ({ ...current, selfIdentity: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-agent-role">角色摘要</label><textarea id="setup-agent-role" className="form-input setup-textarea" value={agentForm.roleSummary} onChange={event => setAgentForm(current => ({ ...current, roleSummary: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-agent-intro">开场白</label><input id="setup-agent-intro" className="form-input" value={agentForm.introMessage} onChange={event => setAgentForm(current => ({ ...current, introMessage: event.target.value }))} /></div>
          <div className="form-group"><label htmlFor="setup-agent-style">说话风格</label><input id="setup-agent-style" className="form-input" value={agentForm.speakingStyle} onChange={event => setAgentForm(current => ({ ...current, speakingStyle: event.target.value }))} /></div>
          <div className="form-group"><label htmlFor="setup-agent-traits">人格特征</label><input id="setup-agent-traits" className="form-input" value={agentForm.personalityTraits} onChange={event => setAgentForm(current => ({ ...current, personalityTraits: event.target.value }))} /></div>
          <div className="form-group"><label htmlFor="setup-agent-focus">服务重点</label><input id="setup-agent-focus" className="form-input" value={agentForm.serviceFocus} onChange={event => setAgentForm(current => ({ ...current, serviceFocus: event.target.value }))} /></div>
          {agentError && <div className="form-error">{agentError}</div>}
          {agentStatus && <div className="setup-form-status">{agentStatus}</div>}
          <div className="setup-form-actions"><button type="submit" className="btn btn--primary" disabled={agentSubmitting || !agentForm.displayName.trim() || !agentForm.selfIdentity.trim() || !agentForm.roleSummary.trim() || parseTags(agentForm.personalityTraits).length === 0 || parseTags(agentForm.serviceFocus).length === 0}>{agentSubmitting ? '创建中…' : '创建首个管家'}</button></div>
        </form>
      );
    }

    return (
      <div className="setup-step-panel">
        <div className="setup-inline-tip"><strong>当前供应商：</strong><span>{currentProvider ? `${currentProvider.display_name} / ${currentProvider.provider_code}` : '未配置'}</span></div>
        <div className="setup-inline-tip"><strong>当前管家：</strong><span>{currentButlerAgent ? `${currentButlerAgent.display_name} / ${currentButlerAgent.code}` : '未创建'}</span></div>
      </div>
    );
  }

  if (!currentHouseholdId) {
    return (
      <div className="setup-page">
        <PageHeader title="家庭初始化向导" description="当前还没有选中家庭，先选一个家庭再说。" />
        <EmptyState title="没有可初始化的家庭" description="先从家庭列表里选中一个家庭。" />
      </div>
    );
  }

  return (
    <div className="setup-page">
      <PageHeader
        title="家庭初始化向导"
        description="先把主路径走通：家庭资料、首成员、供应商、首个管家。复杂配置先别塞进来。"
        actions={<button className="btn btn--outline" onClick={() => { void refreshSetupStatus(); void loadAiResources(currentHouseholdId); }}>刷新状态</button>}
      />

      <Section title="当前家庭">
        <Card className="setup-page__card">
          <div className="setup-page__household">
            <div><strong>{currentHousehold?.name ?? '未命名家庭'}</strong><p>{currentHouseholdId}</p></div>
            <div className="setup-page__selector">
              <label htmlFor="setup-household-select">切换家庭</label>
              <select id="setup-household-select" className="household-select" value={currentHouseholdId} onChange={event => setCurrentHouseholdId(event.target.value)}>
                {households.map(household => <option key={household.id} value={household.id}>{household.name}</option>)}
              </select>
            </div>
          </div>
        </Card>
      </Section>

      <Section title="初始化状态">
        <Card className="setup-page__card">
          {setupStatusLoading && <p>正在读取初始化状态…</p>}
          {!setupStatusLoading && setupStatusError && <p>{setupStatusError}</p>}
          {!setupStatusLoading && !setupStatusError && setupStatus && (
            <>
              <div className="setup-page__summary">
                <span className="setup-page__badge">{setupStatus.status}</span>
                <span>当前步骤：{STEP_LABELS[currentStep]}</span>
                <span>{setupStatus.is_required ? '当前家庭必须先完成初始化' : '当前家庭已放行，不强制拦截'}</span>
              </div>
              <div className="setup-page__grid">
                <div>
                  <h3>已完成</h3>
                  {(setupStatus.completed_steps ?? []).length > 0 ? (
                    <ul className="setup-step-list">{(setupStatus.completed_steps ?? []).map(step => <li key={step} className="setup-step-list__item setup-step-list__item--done">{STEP_LABELS[step]}</li>)}</ul>
                  ) : <p>还没完成任何关键步骤。</p>}
                </div>
                <div>
                  <h3>还缺什么</h3>
                  {(setupStatus.missing_requirements ?? []).length > 0 ? (
                    <ul className="setup-step-list">{(setupStatus.missing_requirements ?? []).map(step => <li key={step} className="setup-step-list__item">{STEP_LABELS[step]}</li>)}</ul>
                  ) : <p>关键步骤已经齐了。</p>}
                </div>
              </div>
            </>
          )}
        </Card>
      </Section>

      <Section title="当前步骤">
        <Card className="setup-page__card">
          {renderCurrentStep()}
        </Card>
      </Section>
    </div>
  );
}
