import { useEffect, useState, type FormEvent } from 'react';
import { Card, EmptyState, PageHeader } from '../components/base';
import { SimpleAiProviderSetup } from '../components/SimpleAiProviderSetup';
import { ButlerBootstrapConversation } from '../components/ButlerBootstrapConversation';
import { WelcomeStep } from '../components/WelcomeStep';
import { api } from '../lib/api';
import type { HouseholdSetupStepCode, Member } from '../lib/types';
import { useAuthContext } from '../state/auth';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';
import { themeList, type ThemeId } from '../theme/tokens';
import { useTheme } from '../theme';
import { pinyin } from 'pinyin-pro';

const STEP_ORDER: HouseholdSetupStepCode[] = [
  'family_profile',
  'first_member',
  'provider_setup',
  'first_butler_agent',
];

const STEP_LABELS: Record<HouseholdSetupStepCode, string> = {
  family_profile: '创建家庭',
  first_member: '首位成员',
  provider_setup: '配置 AI',
  first_butler_agent: '管家档案',
  finish: '完成',
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

function calculatePasswordStrength(password: string): { score: number; label: string; classSuffix: string } {
  if (!password) return { score: 0, label: '', classSuffix: '' };
  let score = 0;
  if (password.length >= 6) score += 1;
  if (password.length >= 10) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  
  if (score < 2) return { score, label: '弱', classSuffix: 'weak' };
  if (score < 4) return { score, label: '中等', classSuffix: 'fair' };
  if (score < 5) return { score, label: '良好', classSuffix: 'good' };
  return { score, label: '强', classSuffix: 'strong' };
}

export function SetupWizardPage() {
  const { actor, refreshAuth } = useAuthContext();
  const {
    currentHousehold,
    currentHouseholdId,
    refreshCurrentHousehold,
    households,
    refreshHouseholds,
  } = useHouseholdContext();
  const { setupStatus, setupStatusLoading, refreshSetupStatus } = useSetupContext();
  const { themeId, setTheme } = useTheme();

  const [familyForm, setFamilyForm] = useState({ name: '', city: '', timezone: getDefaultTimezone(), locale: getDefaultLocale() });
  const [memberForm, setMemberForm] = useState({
    name: '',
    nickname: '',
    role: 'admin' as Member['role'],
    gender: '' as '' | NonNullable<Member['gender']>,
    birthday: '',
    age_group: 'adult' as NonNullable<Member['age_group']>,
    phone: '',
    username: '',
    password: '',
    confirmPassword: '',
  });

  const [usernameEdited, setUsernameEdited] = useState(false);
  const [existingMemberId, setExistingMemberId] = useState<string | null>(null);
  const [familySubmitting, setFamilySubmitting] = useState(false);
  const [memberSubmitting, setMemberSubmitting] = useState(false);
  const [familyError, setFamilyError] = useState('');
  const [memberError, setMemberError] = useState('');
  const canCreateFirstHousehold = actor?.account_type === 'system'
    || (actor?.account_type === 'bootstrap' && actor.must_change_password);

  // 记录用户手动点击的步骤位置，如果不为 -1，则覆盖后端当前的进度限制展示
  const [activeStepIndexOverride, setActiveStepIndexOverride] = useState<number>(-1);

  const [hasSeenWelcome, setHasSeenWelcome] = useState(() => {
    return sessionStorage.getItem('familyclaw_welcome_seen') === '1';
  });

  useEffect(() => {
    setFamilyForm({
      name: currentHousehold?.name ?? '',
      city: currentHousehold?.city ?? '',
      timezone: currentHousehold?.timezone ?? getDefaultTimezone(),
      locale: currentHousehold?.locale ?? getDefaultLocale(),
    });
  }, [currentHousehold?.name, currentHousehold?.city, currentHousehold?.timezone, currentHousehold?.locale, currentHouseholdId]);

  useEffect(() => {
    let cancelled = false;

    async function loadExistingMember() {
      if (!currentHouseholdId || !setupStatus?.completed_steps.includes('first_member')) {
        if (!cancelled) {
          setExistingMemberId(null);
        }
        return;
      }

      try {
        const result = await api.listMembers(currentHouseholdId);
        if (cancelled) return;

        const existingMember = result.items.find(member => member.id === actor?.member_id)
          ?? result.items.find(member => member.role === 'admin' && member.status === 'active')
          ?? result.items.find(member => member.status === 'active')
          ?? null;

        if (!existingMember) {
          setExistingMemberId(null);
          return;
        }

        setExistingMemberId(existingMember.id);
        setMemberForm(current => ({
          ...current,
          name: existingMember.name ?? '',
          nickname: existingMember.nickname ?? '',
          gender: existingMember.gender ?? '',
          birthday: existingMember.birthday ?? '',
          username: actor?.username ?? current.username,
          password: '',
          confirmPassword: '',
        }));
        setUsernameEdited(Boolean(actor?.username));
      } catch {
        if (!cancelled) {
          setExistingMemberId(null);
        }
      }
    }

    void loadExistingMember();

    return () => {
      cancelled = true;
    };
  }, [actor?.member_id, actor?.username, currentHouseholdId, setupStatus?.completed_steps]);

  const currentStep = setupStatus?.current_step ?? 'family_profile';
  const backendIndex = STEP_ORDER.indexOf(currentStep) >= 0 ? STEP_ORDER.indexOf(currentStep) : 4;
  
  // 实际渲染展示的进度索引，受限于后端进展（不允许跳到未解锁的后续步骤）
  const renderIndex = activeStepIndexOverride !== -1 && activeStepIndexOverride <= backendIndex 
    ? activeStepIndexOverride 
    : backendIndex;

  function handleNameChange(name: string) {
    setMemberForm(current => {
      const updates: typeof current = { ...current, name };
      // 若未手动编辑过账号，利用姓名全拼自动生成账号名
      if (!usernameEdited && name.trim()) {
        const py = pinyin(name.trim(), { toneType: 'none', nonZh: 'consecutive' }).replace(/\s+/g, '').toLowerCase() || '';
        updates.username = py;
      } else if (!usernameEdited && !name.trim()) {
        updates.username = '';
      }
      return updates;
    });
  }

  function handleUsernameChange(username: string) {
    setUsernameEdited(true);
    setMemberForm(current => ({ ...current, username }));
  }

  function handleStepClick(index: number) {
    if (index <= backendIndex) {
      setActiveStepIndexOverride(index);
    }
  }

  function handleBack() {
    if (renderIndex > 0) {
      handleStepClick(renderIndex - 1);
    }
  }

  function advanceToNextStep() {
    setActiveStepIndexOverride(-1); // 恢复跟随后端进度
  }

  async function handleFamilySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFamilySubmitting(true);
    setFamilyError('');
    try {
      if (!currentHouseholdId) {
        if (!canCreateFirstHousehold) {
          throw new Error('当前账号没有创建家庭的权限');
        }
        const created = await api.createHousehold({
          name: familyForm.name.trim(),
          city: familyForm.city.trim(),
          timezone: familyForm.timezone.trim(),
          locale: familyForm.locale.trim(),
        });
        await refreshHouseholds();
        await refreshCurrentHousehold(created.id);
        await refreshSetupStatus(created.id);
        advanceToNextStep();
        return;
      }

      await api.updateHousehold(currentHouseholdId, {
        name: familyForm.name.trim(),
        city: familyForm.city.trim(),
        timezone: familyForm.timezone.trim(),
        locale: familyForm.locale.trim(),
      });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
      await refreshSetupStatus(currentHouseholdId);
      advanceToNextStep();
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
    try {
      if (existingMemberId) {
        await api.updateMember(existingMemberId, {
          name: memberForm.name.trim(),
          nickname: memberForm.nickname.trim() || null,
          gender: memberForm.gender || null,
          birthday: memberForm.birthday || null,
        });
      } else {
        if (!memberForm.password.trim()) throw new Error('请先设置正式密码');
        if (memberForm.password !== memberForm.confirmPassword) throw new Error('两次输入的密码不一致');

        const member = await api.createMember({
          household_id: currentHouseholdId,
          name: memberForm.name.trim(),
          nickname: memberForm.nickname.trim() || null,
          role: memberForm.role,
          gender: memberForm.gender || null,
          birthday: memberForm.birthday || null,
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
      }

      await refreshHouseholds();
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshSetupStatus(currentHouseholdId);
      setMemberForm(current => ({ ...current, password: '', confirmPassword: '' }));
      advanceToNextStep();
    } catch (error) {
      setMemberError(error instanceof Error ? error.message : '创建首位成员失败');
    } finally {
      setMemberSubmitting(false);
    }
  }

  function renderStepper() {
    return (
      <div className="setup-stepper">
        {STEP_ORDER.map((step, index) => {
          let statusClass = 'setup-step--pending';
          if (index < backendIndex) statusClass = 'setup-step--completed';
          if (index === renderIndex) statusClass = 'setup-step--active';

          // 是否允许点击：只要不是未解锁的步骤，都可以点击
          const isClickable = index <= backendIndex;

          return (
            <button 
              type="button"
              key={step} 
              className={`setup-step ${statusClass}`}
              onClick={() => isClickable && handleStepClick(index)}
              style={{ cursor: isClickable ? 'pointer' : 'default', background: 'transparent', border: 'none', padding: 0 }}
            >
              <div className="setup-step__indicator">
                {index < backendIndex && index !== renderIndex  ? '✓' : (index + 1)}
              </div>
              <div className="setup-step__label">{STEP_LABELS[step]}</div>
            </button>
          );
        })}
      </div>
    );
  }

  function renderThemeSwitcher() {
    return (
      <div className="setup-theme-switcher" style={{ display: 'flex', gap: '8px', justifyContent: 'center', margin: '1rem 0 2rem' }}>
        {themeList.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTheme(t.id)}
            title={t.label}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px',
              border: themeId === t.id ? `2px solid var(--brand-primary)` : `1px solid var(--border)`,
              background: t.bgCard,
              cursor: 'pointer',
              transition: 'all var(--transition)'
            }}
          >
            {t.emoji}
          </button>
        ))}
      </div>
    );
  }

  function renderCurrentStep() {
    if (STEP_ORDER[renderIndex] === 'family_profile') {
      return (
        <Card className="setup-wizard-card">
          <div className="setup-wizard-header">
            <h2>欢迎！先给你的家庭起个名字吧。</h2>
            <p>这个名字将用来标识你的家庭专属空间。</p>
          </div>
          <form className="settings-form" onSubmit={handleFamilySubmit}>
            <div className="form-group">
              <label htmlFor="setup-family-name">主家庭名称</label>
              <input id="setup-family-name" className="form-input" placeholder="例如：观澜园 / 张家大院" value={familyForm.name} onChange={event => setFamilyForm(current => ({ ...current, name: event.target.value }))} required autoFocus />
            </div>
            <div className="form-group">
              <label htmlFor="setup-family-city">所在城市</label>
              <input id="setup-family-city" className="form-input" placeholder="例如：北京" value={familyForm.city} onChange={event => setFamilyForm(current => ({ ...current, city: event.target.value }))} required />
            </div>
            
            {familyError && <div className="form-error">{familyError}</div>}
            
            <div className="setup-form-actions" style={{ justifyContent: 'center', marginTop: '2rem' }}>
              <button type="submit" className="btn btn--primary btn--large" disabled={familySubmitting || !familyForm.name.trim() || !familyForm.city.trim()}>
                {familySubmitting ? '保存中…' : (backendIndex > 0 ? '保存修改并下一步' : '下一步')}
              </button>
            </div>
          </form>
        </Card>
      );
    }

    if (STEP_ORDER[renderIndex] === 'first_member') {
      const pwdStrength = calculatePasswordStrength(memberForm.password);
      const hasExistingMember = Boolean(existingMemberId);
      const canSubmitMember = hasExistingMember
        ? Boolean(memberForm.name.trim() && memberForm.username.trim())
        : Boolean(
            memberForm.name.trim()
            && memberForm.username.trim()
            && memberForm.password
            && memberForm.confirmPassword
            && pwdStrength.score >= 2,
          );

      return (
        <Card className="setup-wizard-card">
          <div className="setup-wizard-header">
            <h2>完善您的个人资料</h2>
            <p>作为引导者，您将是首位加入的家庭成员，并享有管理权限。</p>
          </div>
          <form className="settings-form" onSubmit={handleMemberSubmit}>
            <div className="setup-form-grid">
              <div className="form-group"><label htmlFor="setup-member-name">真实姓名</label><input id="setup-member-name" className="form-input" value={memberForm.name} onChange={event => handleNameChange(event.target.value)} required /></div>
              <div className="form-group">
                 <label htmlFor="setup-member-birthday">生日</label>
                 <input id="setup-member-birthday" type="date" className="form-input" value={memberForm.birthday} onChange={event => setMemberForm(current => ({ ...current, birthday: event.target.value }))} required />
               </div>
            </div>
            
            <div className="setup-form-grid" style={{ marginTop: '0.5rem' }}>
               <div className="form-group"><label htmlFor="setup-member-nickname">日常称呼 / 昵称</label><input id="setup-member-nickname" className="form-input" value={memberForm.nickname} onChange={event => setMemberForm(current => ({ ...current, nickname: event.target.value }))} required /></div>
               <div className="form-group">
                 <label htmlFor="setup-member-gender">性别</label>
                 <select id="setup-member-gender" className="form-select" value={memberForm.gender} onChange={event => setMemberForm(current => ({ ...current, gender: event.target.value as '' | NonNullable<Member['gender']> }))} required>
                   <option value="">请选择</option>
                   <option value="male">男</option>
                   <option value="female">女</option>
                 </select>
               </div>
            </div>

            <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
              <div className="setup-wizard-header" style={{ marginBottom: '1.5rem', textAlign: 'left' }}>
                <h3 style={{ fontSize: 'var(--font-size-md)' }}>设置您的专属登录账号</h3>
                <p style={{ fontSize: 'var(--font-size-sm)' }}>这个账号会顶替掉你当前登录所用的临时凭证，请牢记。</p>
              </div>
              
              <div className="form-group">
                <label htmlFor="setup-member-username">登录账号</label>
                <input id="setup-member-username" className="form-input" value={memberForm.username} onChange={event => handleUsernameChange(event.target.value)} required disabled={hasExistingMember} />
                {hasExistingMember && <div className="form-help">正式账号已创建，这里只回显当前登录账号。</div>}
              </div>
              {!hasExistingMember && (
                <div className="setup-form-grid">
                  <div className="form-group">
                    <label htmlFor="setup-member-password">访问密码</label>
                    <input id="setup-member-password" type="password" className="form-input" value={memberForm.password} onChange={event => setMemberForm(current => ({ ...current, password: event.target.value }))} required />
                    {memberForm.password.length > 0 && (
                      <div className="password-strength-container">
                        <div className="password-strength">
                          {[...Array(4)].map((_, i) => (
                             <div key={i} className={`password-strength__bar ${i < pwdStrength.score ? `password-strength__bar--active-${pwdStrength.classSuffix}` : ''}`} />
                          ))}
                        </div>
                        <div className="password-strength-text" style={{ color: `var(--color-${pwdStrength.classSuffix === 'weak' ? 'danger' : pwdStrength.classSuffix === 'fair' ? 'warning' : pwdStrength.classSuffix === 'strong' ? 'success' : 'brand-secondary'})` }}>
                          密码强度: {pwdStrength.label}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="form-group"><label htmlFor="setup-member-password-confirm">确认密码</label><input id="setup-member-password-confirm" type="password" className="form-input" value={memberForm.confirmPassword} onChange={event => setMemberForm(current => ({ ...current, confirmPassword: event.target.value }))} required /></div>
                </div>
              )}
            </div>
            
            {memberError && <div className="form-error">{memberError}</div>}
            
            <div className="setup-form-actions" style={{ justifyContent: 'center', gap: '1rem', marginTop: '2rem' }}>
              <button type="button" className="btn btn--outline btn--large" onClick={handleBack}>
                返回上一步
              </button>
              <button type="submit" className="btn btn--primary btn--large" disabled={memberSubmitting || !canSubmitMember}>
                {memberSubmitting ? '验证中…' : (hasExistingMember ? '保存资料并下一步' : (backendIndex > 1 ? '保存修改并下一步' : '创建账号并下一步'))}
              </button>
            </div>
          </form>
        </Card>
      );
    }

    if (STEP_ORDER[renderIndex] === 'provider_setup') {
      return (
        <div className="setup-wizard-card--transparent">
          <div className="setup-wizard-header">
            <h2>为家庭接入 AI 大脑</h2>
            <p>选择一个您信赖的 AI 供应商。配置完毕后，它将驱动整个家庭的对话交互和智能分析。</p>
          </div>
          <SimpleAiProviderSetup 
            householdId={currentHouseholdId} 
            onCompleted={() => {
              void refreshSetupStatus(currentHouseholdId);
              advanceToNextStep();
            }} 
          />
          <div className="setup-form-actions" style={{ justifyContent: 'center', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn--outline btn--large" onClick={handleBack}>
              返回上一步
            </button>
            {backendIndex > 2 && (
               <button type="button" className="btn btn--primary btn--large" style={{ marginLeft: '1rem' }} onClick={() => advanceToNextStep()}>
                 跳过 (已配置)
               </button>
            )}
          </div>
        </div>
      );
    }

    if (STEP_ORDER[renderIndex] === 'first_butler_agent') {
      return (
        <div className="setup-wizard-card--transparent">
          <div className="setup-wizard-header">
            <h2>定制您的专属 AI 管家</h2>
            <p>通过对话来描述您心目中管家的形象、性格以及服务偏好，系统将自动生成他的设定档案。</p>
          </div>
          <ButlerBootstrapConversation
            householdId={currentHouseholdId}
            source="setup-wizard"
            onCreated={() => {
              void refreshSetupStatus(currentHouseholdId);
              advanceToNextStep();
            }}
          />
          <div className="setup-form-actions" style={{ justifyContent: 'center', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn--outline btn--large" onClick={handleBack}>
              返回上一步
            </button>
          </div>
        </div>
      );
    }

    return (
      <Card className="setup-wizard-card">
        <div className="setup-wizard-header">
          <h2>全搞定了！</h2>
          <p>家庭数据、账号和 AI 管家均已就绪。这就起航吧。</p>
        </div>
        <div className="setup-form-actions" style={{ justifyContent: 'center', gap: '1rem', marginTop: '2rem' }}>
          <button type="button" className="btn btn--outline btn--large" onClick={handleBack}>
            返回上一步
          </button>
          <button type="button" className="btn btn--primary btn--large" onClick={() => window.location.href = '/'}>
            进入主页
          </button>
        </div>
      </Card>
    );
  }

  if (!currentHouseholdId && !canCreateFirstHousehold) {
    return (
      <div className="setup-page">
        <PageHeader title="家庭向导" />
        <EmptyState title="未找到家庭关联" description="环境异常：您的账号尚未关联任何家庭上下文。" />
      </div>
    );
  }

  if (setupStatusLoading) {
    return (
      <div className="setup-page setup-page--centered">
        <p>正在读取初始化状态…</p>
      </div>
    );
  }

  if (!hasSeenWelcome && !currentHouseholdId && backendIndex === 0) {
    return (
      <WelcomeStep 
        onComplete={() => {
          sessionStorage.setItem('familyclaw_welcome_seen', '1');
          setHasSeenWelcome(true);
        }} 
      />
    );
  }

  return (
    <div className="setup-page setup-page--centered">
      {renderThemeSwitcher()}
      <div className="setup-wizard-container">
        {renderStepper()}
        <div className="setup-wizard-content">
          {renderCurrentStep()}
        </div>
      </div>
    </div>
  );
}
