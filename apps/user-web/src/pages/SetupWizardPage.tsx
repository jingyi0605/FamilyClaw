import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card, EmptyState, PageHeader, Section } from '../components/base';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';
import { ButlerBootstrapConversation } from '../components/ButlerBootstrapConversation';
import { api } from '../lib/api';
import { SETUP_ROUTE_CAPABILITIES } from '../lib/aiConfig';
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
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');
  const [familySubmitting, setFamilySubmitting] = useState(false);
  const [memberSubmitting, setMemberSubmitting] = useState(false);
  const [familyError, setFamilyError] = useState('');
  const [memberError, setMemberError] = useState('');
  const [familyStatus, setFamilyStatus] = useState('');
  const [memberStatus, setMemberStatus] = useState('');

  useEffect(() => {
    setFamilyForm({
      name: currentHousehold?.name ?? '',
      city: currentHousehold?.city ?? '',
      timezone: currentHousehold?.timezone ?? getDefaultTimezone(),
      locale: currentHousehold?.locale ?? getDefaultLocale(),
    });
  }, [currentHousehold?.name, currentHousehold?.city, currentHousehold?.timezone, currentHousehold?.locale, currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setProviders([]);
      setRoutes([]);
      setAgents([]);
      return;
    }
    void loadAiSummary(currentHouseholdId);
  }, [currentHouseholdId]);

  const currentStep = setupStatus?.current_step ?? 'family_profile';
  const currentProvider = useMemo(() => {
    const route = routes.find(item => item.capability === 'qa_generation' && item.enabled && item.primary_provider_profile_id);
    return providers.find(item => item.id === route?.primary_provider_profile_id) ?? null;
  }, [providers, routes]);
  const currentButlerAgent = useMemo(
    () => agents.find(item => item.agent_type === 'butler' && item.status === 'active') ?? null,
    [agents],
  );

  async function loadAiSummary(householdId: string) {
    setAiLoading(true);
    setAiError('');
    try {
      const [providerRows, routeRows, agentRows] = await Promise.all([
        api.listHouseholdAiProviders(householdId),
        api.listHouseholdAiRoutes(householdId),
        api.listAgents(householdId),
      ]);
      setProviders(providerRows);
      setRoutes(routeRows);
      setAgents(agentRows.items);
    } catch (error) {
      setAiError(error instanceof Error ? error.message : '加载 AI 概览失败');
      setProviders([]);
      setRoutes([]);
      setAgents([]);
    } finally {
      setAiLoading(false);
    }
  }

  async function refreshAiSummary() {
    if (!currentHouseholdId) {
      return;
    }
    await Promise.all([
      refreshSetupStatus(currentHouseholdId),
      loadAiSummary(currentHouseholdId),
    ]);
  }

  async function handleFamilySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      return;
    }
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
    if (!currentHouseholdId) {
      return;
    }
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
      setMemberStatus('首位成员和正式账号已创建，默认 bootstrap 账号已失效。');
      setMemberForm(current => ({ ...current, name: '', nickname: '', phone: '', password: '', confirmPassword: '' }));
    } catch (error) {
      setMemberError(error instanceof Error ? error.message : '创建首位成员失败');
    } finally {
      setMemberSubmitting(false);
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
          <div className="setup-form-actions"><button type="submit" className="btn btn--primary" disabled={familySubmitting || !familyForm.name.trim() || !familyForm.city.trim()}>{familySubmitting ? '保存中…' : '保存家庭资料'}</button></div>
        </form>
      );
    }

    if (currentStep === 'first_member') {
      return (
        <form className="settings-form" onSubmit={handleMemberSubmit}>
          <div className="form-group"><label htmlFor="setup-member-name">成员姓名</label><input id="setup-member-name" className="form-input" value={memberForm.name} onChange={event => setMemberForm(current => ({ ...current, name: event.target.value }))} required /></div>
          <div className="form-group"><label htmlFor="setup-member-nickname">称呼 / 昵称</label><input id="setup-member-nickname" className="form-input" value={memberForm.nickname} onChange={event => setMemberForm(current => ({ ...current, nickname: event.target.value }))} /></div>
          <div className="setup-form-grid">
            <div className="form-group"><label htmlFor="setup-member-role">角色</label><select id="setup-member-role" className="form-select" value={memberForm.role} onChange={event => setMemberForm(current => ({ ...current, role: event.target.value as Member['role'] }))}><option value="admin">管理员</option><option value="adult">成人</option><option value="elder">老人</option><option value="child">儿童</option><option value="guest">访客</option></select></div>
            <div className="form-group"><label htmlFor="setup-member-gender">性别</label><select id="setup-member-gender" className="form-select" value={memberForm.gender} onChange={event => setMemberForm(current => ({ ...current, gender: event.target.value as '' | NonNullable<Member['gender']> }))}><option value="">未设置</option><option value="male">男</option><option value="female">女</option></select></div>
            <div className="form-group"><label htmlFor="setup-member-age-group">年龄段</label><select id="setup-member-age-group" className="form-select" value={memberForm.age_group} onChange={event => setMemberForm(current => ({ ...current, age_group: event.target.value as NonNullable<Member['age_group']> }))}><option value="adult">成人</option><option value="elder">老人</option><option value="teen">青少年</option><option value="child">儿童</option><option value="toddler">幼儿</option></select></div>
            <div className="form-group"><label htmlFor="setup-member-phone">手机号</label><input id="setup-member-phone" className="form-input" value={memberForm.phone} onChange={event => setMemberForm(current => ({ ...current, phone: event.target.value }))} /></div>
          </div>
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
        <div className="setup-step-panel">
          <div className="setup-inline-tip"><strong>当前绑定：</strong><span>{currentProvider ? `${currentProvider.display_name}（${currentProvider.provider_code}）` : '还没有配置'}</span></div>
          {aiError && <div className="form-error">{aiError}</div>}
          {aiLoading && <p>正在读取 AI 配置概览…</p>}
          <AiProviderConfigPanel
            householdId={currentHouseholdId}
            compact
            capabilityFilter={SETUP_ROUTE_CAPABILITIES}
            onChanged={refreshAiSummary}
          />
        </div>
      );
    }

    if (currentStep === 'first_butler_agent') {
      return (
        <div className="setup-step-panel">
          <div className="setup-inline-tip"><strong>当前供应商：</strong><span>{currentProvider ? currentProvider.display_name : '未配置'}</span></div>
          {aiError && <div className="form-error">{aiError}</div>}
          {aiLoading && <p>正在读取 AI 配置概览…</p>}
          <ButlerBootstrapConversation
            householdId={currentHouseholdId}
            source="setup-wizard"
            existingButlerAgent={currentButlerAgent}
            onCreated={() => void refreshAiSummary()}
          />
        </div>
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
        description="先把主路径走通：家庭资料、首成员、供应商、首个管家。现在后两步已经复用正式 AI 配置能力，不再继续堆临时表单。"
        actions={<button className="btn btn--outline" onClick={() => void refreshAiSummary()}>刷新状态</button>}
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
