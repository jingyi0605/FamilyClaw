import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import {
  resolveSupportedLocale,
  type HouseholdSetupStepCode,
  type Member,
} from '@familyclaw/user-core';
import { pinyin } from 'pinyin-pro';
import { Card, EmptyState, PageHeader } from './base';
import { ButlerBootstrapConversation } from './ButlerBootstrapConversation';
import {
  DEFAULT_REGION_COUNTRY,
  DEFAULT_REGION_PROVIDER,
  RegionSelector,
  type RegionSelectionFormValue,
} from './RegionSelector';
import { SimpleAiProviderSetup } from './SimpleAiProviderSetup';
import { WelcomeStep } from './WelcomeStep';
import { setupApi } from './setupApi';
import {
  GuardedPage,
  useAuthContext,
  useHouseholdContext,
  useI18n,
  useSetupContext,
  useTheme,
} from '../../runtime';
import './index.h5.scss';

const WELCOME_SEEN_KEY = 'familyclaw_welcome_seen';
const ENTRY_PAGE_URL = '/pages/entry/index';

const STEP_ORDER: HouseholdSetupStepCode[] = [
  'family_profile',
  'first_member',
  'provider_setup',
  'first_butler_agent',
];

const STEP_LABEL_KEYS: Record<HouseholdSetupStepCode, string> = {
  family_profile: 'setup.step.familyProfile',
  first_member: 'setup.step.firstMember',
  provider_setup: 'setup.step.providerSetup',
  first_butler_agent: 'setup.step.firstButler',
  finish: 'setup.step.finish',
};

function getDefaultTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
  } catch {
    return 'Asia/Shanghai';
  }
}

function getDefaultLocale(preferredLocale?: string | null) {
  return resolveSupportedLocale(
    preferredLocale ?? (typeof navigator !== 'undefined' ? navigator.language : 'zh-CN'),
  );
}

function getWelcomeSeen() {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    return window.sessionStorage.getItem(WELCOME_SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

function markWelcomeSeen() {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.sessionStorage.setItem(WELCOME_SEEN_KEY, '1');
  } catch {
    // 这里只是欢迎页动效开关，持久化失败不该阻断流程。
  }
}

async function enterApp() {
  try {
    await Taro.reLaunch({ url: ENTRY_PAGE_URL });
  } catch {
    await Taro.redirectTo({ url: ENTRY_PAGE_URL });
  }
}

function calculatePasswordStrength(
  password: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): {
  score: number;
  label: string;
  classSuffix: string;
} {
  if (!password) {
    return { score: 0, label: '', classSuffix: '' };
  }

  let score = 0;
  if (password.length >= 6) score += 1;
  if (password.length >= 10) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score < 2) {
    return { score, label: t('setup.password.weak'), classSuffix: 'weak' };
  }
  if (score < 4) {
    return { score, label: t('setup.password.fair'), classSuffix: 'fair' };
  }
  if (score < 5) {
    return { score, label: t('setup.password.good'), classSuffix: 'good' };
  }
  return { score, label: t('setup.password.strong'), classSuffix: 'strong' };
}

export default function SetupPageH5() {
  const { actor, refreshAuth } = useAuthContext();
  const {
    currentHousehold,
    currentHouseholdId,
    refreshCurrentHousehold,
    refreshHouseholds,
  } = useHouseholdContext();
  const { locale, t } = useI18n();
  const { setupStatus, setupStatusLoading, refreshSetupStatus } = useSetupContext();
  const { themeId, themeList, setTheme } = useTheme();

  const defaultLocale = useMemo(() => getDefaultLocale(locale), [locale]);

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('setup.page.title') }).catch(() => undefined);
  }, [t, locale]);

  const [familyForm, setFamilyForm] = useState({
    name: '',
    timezone: getDefaultTimezone(),
    locale: defaultLocale,
    region: {
      countryCode: DEFAULT_REGION_COUNTRY,
      provinceCode: '',
      cityCode: '',
      districtCode: '',
    } as RegionSelectionFormValue,
  });
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
  const [activeStepIndexOverride, setActiveStepIndexOverride] = useState(-1);
  const [hasSeenWelcome, setHasSeenWelcome] = useState(getWelcomeSeen);

  const canCreateFirstHousehold = actor?.account_type === 'system'
    || (actor?.account_type === 'bootstrap' && actor.must_change_password);

  async function refreshShellState(preferredHouseholdId?: string) {
    const targetHouseholdId = preferredHouseholdId ?? currentHouseholdId;

    await refreshHouseholds(preferredHouseholdId);

    if (!targetHouseholdId) {
      await refreshSetupStatus();
      return;
    }

    await Promise.all([
      refreshCurrentHousehold(targetHouseholdId),
      refreshSetupStatus(targetHouseholdId),
    ]);
  }

  useEffect(() => {
    setFamilyForm({
      name: currentHousehold?.name ?? '',
      timezone: currentHousehold?.timezone ?? getDefaultTimezone(),
      locale: currentHousehold?.locale ?? defaultLocale,
      region: {
        countryCode: currentHousehold?.region?.country_code ?? DEFAULT_REGION_COUNTRY,
        provinceCode: currentHousehold?.region?.province?.code ?? '',
        cityCode: currentHousehold?.region?.city?.code ?? '',
        districtCode: currentHousehold?.region?.district?.code ?? '',
      },
    });
  }, [
    currentHousehold?.locale,
    currentHousehold?.name,
    currentHousehold?.region?.city?.code,
    currentHousehold?.region?.district?.code,
    currentHousehold?.region?.province?.code,
    currentHousehold?.timezone,
    currentHouseholdId,
    defaultLocale,
  ]);

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
        const result = await setupApi.listMembers(currentHouseholdId);
        if (cancelled) {
          return;
        }

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
  const renderIndex = activeStepIndexOverride !== -1 && activeStepIndexOverride <= backendIndex
    ? activeStepIndexOverride
    : backendIndex;

  function handleNameChange(name: string) {
    setMemberForm(current => {
      const updates = { ...current, name };
      if (!usernameEdited && name.trim()) {
        const py = pinyin(name.trim(), {
          toneType: 'none',
          nonZh: 'consecutive',
        }).replace(/\s+/g, '').toLowerCase();
        updates.username = py || '';
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
    setActiveStepIndexOverride(-1);
  }

  async function handleFamilySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFamilySubmitting(true);
    setFamilyError('');

    try {
      if (!currentHouseholdId) {
        if (!canCreateFirstHousehold) {
          throw new Error(t('setup.page.emptyDesc'));
        }

        const created = await setupApi.createHousehold({
          name: familyForm.name.trim(),
          timezone: familyForm.timezone.trim(),
          locale: familyForm.locale.trim(),
          region_selection: {
            provider_code: DEFAULT_REGION_PROVIDER,
            country_code: familyForm.region.countryCode,
            region_code: familyForm.region.districtCode,
          },
        });

        await refreshShellState(created.id);
        advanceToNextStep();
        return;
      }

      await setupApi.updateHousehold(currentHouseholdId, {
        name: familyForm.name.trim(),
        timezone: familyForm.timezone.trim(),
        locale: familyForm.locale.trim(),
        region_selection: {
          provider_code: DEFAULT_REGION_PROVIDER,
          country_code: familyForm.region.countryCode,
          region_code: familyForm.region.districtCode,
        },
      });

      await refreshShellState(currentHouseholdId);
      advanceToNextStep();
    } catch (error) {
      setFamilyError(error instanceof Error ? error.message : t('settings.error.saveFailed'));
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

    try {
      if (existingMemberId) {
        await setupApi.updateMember(existingMemberId, {
          name: memberForm.name.trim(),
          nickname: memberForm.nickname.trim() || null,
          gender: memberForm.gender || null,
          birthday: memberForm.birthday || null,
        });
      } else {
        if (!memberForm.password.trim()) {
          throw new Error(t('setup.member.passwordLabel'));
        }
        if (memberForm.password !== memberForm.confirmPassword) {
          throw new Error(t('setup.member.confirmPasswordLabel'));
        }

        const member = await setupApi.createMember({
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

        await setupApi.completeBootstrapAccount({
          household_id: currentHouseholdId,
          member_id: member.id,
          username: memberForm.username.trim() || 'user',
          password: memberForm.password,
        });

        await refreshAuth();
      }

      await refreshShellState(currentHouseholdId);
      setMemberForm(current => ({
        ...current,
        password: '',
        confirmPassword: '',
      }));
      advanceToNextStep();
    } catch (error) {
      setMemberError(error instanceof Error ? error.message : t('setup.step.firstMember'));
    } finally {
      setMemberSubmitting(false);
    }
  }

  function renderStepper() {
    return (
      <div className="setup-stepper">
        {STEP_ORDER.map((step, index) => {
          let statusClass = 'setup-step--pending';
          if (index < backendIndex) {
            statusClass = 'setup-step--completed';
          }
          if (index === renderIndex) {
            statusClass = 'setup-step--active';
          }

          const isClickable = index <= backendIndex;

          return (
            <button
              type="button"
              key={step}
              className={`setup-step ${statusClass}`}
              onClick={() => isClickable && handleStepClick(index)}
              style={{
                cursor: isClickable ? 'pointer' : 'default',
                background: 'transparent',
                border: 'none',
                padding: 0,
              }}
            >
              <div className="setup-step__indicator">
                {index < backendIndex && index !== renderIndex ? '✓' : index + 1}
              </div>
                <div className="setup-step__label">{t(STEP_LABEL_KEYS[step])}</div>
            </button>
          );
        })}
      </div>
    );
  }

  function renderThemeSwitcher() {
    return (
      <div
        className="setup-theme-switcher"
        style={{
          display: 'flex',
          gap: '8px',
          justifyContent: 'center',
          margin: '1rem 0 2rem',
        }}
      >
        {themeList.map(theme => (
          <button
            key={theme.id}
            type="button"
            onClick={() => setTheme(theme.id)}
            title={theme.label}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px',
              border: themeId === theme.id
                ? '2px solid var(--brand-primary)'
                : '1px solid var(--border)',
              background: theme.bgCard,
              cursor: 'pointer',
              transition: 'all var(--transition)',
            }}
          >
            {theme.emoji}
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
            <h2>{t('setup.family.title')}</h2>
            <p>{t('setup.family.desc')}</p>
          </div>
          <form className="settings-form" onSubmit={handleFamilySubmit}>
            <div className="form-group">
              <label htmlFor="setup-family-name">{t('setup.family.nameLabel')}</label>
              <input
                id="setup-family-name"
                className="form-input"
                placeholder={t('setup.family.namePlaceholder')}
                value={familyForm.name}
                onChange={event => setFamilyForm(current => ({
                  ...current,
                  name: event.target.value,
                }))}
                required
                autoFocus
              />
            </div>
            <RegionSelector
              value={familyForm.region}
              onChange={region => setFamilyForm(current => ({ ...current, region }))}
              disabled={familySubmitting}
            />
            {currentHousehold?.region?.status === 'unconfigured' && currentHousehold?.city ? (
              <div className="form-hint">
                {t('setup.family.legacyRegionHint', { city: currentHousehold.city })}
              </div>
            ) : null}
            {familyError ? <div className="form-error">{familyError}</div> : null}
            <div
              className="setup-form-actions"
              style={{ justifyContent: 'center', marginTop: '2rem' }}
            >
              <button
                type="submit"
                className="btn btn--primary btn--large"
                disabled={
                  familySubmitting
                  || !familyForm.name.trim()
                  || !familyForm.region.districtCode
                }
              >
                {familySubmitting
                  ? t('setup.family.saving')
                  : backendIndex > 0
                    ? t('setup.family.saveAndNext')
                    : t('setup.family.next')}
              </button>
            </div>
          </form>
        </Card>
      );
    }

    if (STEP_ORDER[renderIndex] === 'first_member') {
      const passwordStrength = calculatePasswordStrength(memberForm.password, t);
      const hasExistingMember = Boolean(existingMemberId);
      const canSubmitMember = hasExistingMember
        ? Boolean(memberForm.name.trim() && memberForm.username.trim())
        : Boolean(
          memberForm.name.trim()
            && memberForm.username.trim()
            && memberForm.password
            && memberForm.confirmPassword
            && passwordStrength.score >= 2,
        );

      return (
        <Card className="setup-wizard-card">
          <div className="setup-wizard-header">
            <h2>{t('setup.member.title')}</h2>
            <p>{t('setup.member.desc')}</p>
          </div>
          <form className="settings-form" onSubmit={handleMemberSubmit}>
            <div className="setup-form-grid">
              <div className="form-group">
                <label htmlFor="setup-member-name">{t('setup.member.nameLabel')}</label>
                <input
                  id="setup-member-name"
                  className="form-input"
                  value={memberForm.name}
                  onChange={event => handleNameChange(event.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="setup-member-birthday">{t('setup.member.birthdayLabel')}</label>
                <input
                  id="setup-member-birthday"
                  type="date"
                  className="form-input"
                  value={memberForm.birthday}
                  onChange={event => setMemberForm(current => ({
                    ...current,
                    birthday: event.target.value,
                  }))}
                  required
                />
              </div>
            </div>

            <div className="setup-form-grid" style={{ marginTop: '0.5rem' }}>
              <div className="form-group">
                <label htmlFor="setup-member-nickname">{t('setup.member.nicknameLabel')}</label>
                <input
                  id="setup-member-nickname"
                  className="form-input"
                  value={memberForm.nickname}
                  onChange={event => setMemberForm(current => ({
                    ...current,
                    nickname: event.target.value,
                  }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="setup-member-gender">{t('setup.member.genderLabel')}</label>
                <select
                  id="setup-member-gender"
                  className="form-select"
                  value={memberForm.gender}
                  onChange={event => setMemberForm(current => ({
                    ...current,
                    gender: event.target.value as '' | NonNullable<Member['gender']>,
                  }))}
                  required
                >
                  <option value="">{t('setup.member.genderPlaceholder')}</option>
                  <option value="male">{t('setup.member.genderMale')}</option>
                  <option value="female">{t('setup.member.genderFemale')}</option>
                </select>
              </div>
            </div>

            <div
              style={{
                marginTop: '2rem',
                padding: '1.5rem',
                background: 'var(--bg-input)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
              }}
            >
              <div
                className="setup-wizard-header"
                style={{ marginBottom: '1.5rem', textAlign: 'left' }}
              >
                <h3 style={{ fontSize: 'var(--font-size-md)' }}>{t('setup.member.accountTitle')}</h3>
                <p style={{ fontSize: 'var(--font-size-sm)' }}>
                  {t('setup.member.accountDesc')}
                </p>
              </div>

              <div className="form-group">
                <label htmlFor="setup-member-username">{t('setup.member.usernameLabel')}</label>
                <input
                  id="setup-member-username"
                  className="form-input"
                  value={memberForm.username}
                  onChange={event => handleUsernameChange(event.target.value)}
                  required
                  disabled={hasExistingMember}
                />
                {hasExistingMember ? (
                  <div className="form-help">{t('setup.member.usernameReadonlyHelp')}</div>
                ) : null}
              </div>

              {!hasExistingMember ? (
                <div className="setup-form-grid">
                  <div className="form-group">
                    <label htmlFor="setup-member-password">{t('setup.member.passwordLabel')}</label>
                    <input
                      id="setup-member-password"
                      type="password"
                      className="form-input"
                      value={memberForm.password}
                      onChange={event => setMemberForm(current => ({
                        ...current,
                        password: event.target.value,
                      }))}
                      required
                    />
                    {memberForm.password.length > 0 ? (
                      <div className="password-strength-container">
                        <div className="password-strength">
                          {[...Array(4)].map((_, index) => (
                            <div
                              key={index}
                              className={`password-strength__bar ${
                                index < passwordStrength.score
                                  ? `password-strength__bar--active-${passwordStrength.classSuffix}`
                                  : ''
                              }`}
                            />
                          ))}
                        </div>
                        <div
                          className="password-strength-text"
                          style={{
                            color: `var(--color-${
                              passwordStrength.classSuffix === 'weak'
                                ? 'danger'
                                : passwordStrength.classSuffix === 'fair'
                                  ? 'warning'
                                  : passwordStrength.classSuffix === 'strong'
                                    ? 'success'
                                    : 'brand-secondary'
                            })`,
                          }}
                        >
                          {t('setup.member.passwordStrength', { label: passwordStrength.label })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                  <div className="form-group">
                    <label htmlFor="setup-member-password-confirm">{t('setup.member.confirmPasswordLabel')}</label>
                    <input
                      id="setup-member-password-confirm"
                      type="password"
                      className="form-input"
                      value={memberForm.confirmPassword}
                      onChange={event => setMemberForm(current => ({
                        ...current,
                        confirmPassword: event.target.value,
                      }))}
                      required
                    />
                  </div>
                </div>
              ) : null}
            </div>

            {memberError ? <div className="form-error">{memberError}</div> : null}

            <div
              className="setup-form-actions"
              style={{ justifyContent: 'center', gap: '1rem', marginTop: '2rem' }}
            >
              <button
                type="button"
                className="btn btn--outline btn--large"
                onClick={handleBack}
              >
                {t('setup.member.back')}
              </button>
              <button
                type="submit"
                className="btn btn--primary btn--large"
                disabled={memberSubmitting || !canSubmitMember}
              >
                {memberSubmitting
                  ? t('setup.member.verifying')
                  : hasExistingMember
                    ? t('setup.member.saveProfileAndNext')
                    : backendIndex > 1
                      ? t('setup.member.saveChangesAndNext')
                      : t('setup.member.createAccountAndNext')}
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
            <h2>{t('setup.provider.title')}</h2>
            <p>{t('setup.provider.desc')}</p>
          </div>
          <SimpleAiProviderSetup
            householdId={currentHouseholdId}
            onCompleted={() => {
              void refreshShellState(currentHouseholdId).then(advanceToNextStep);
            }}
          />
          <div className="setup-form-actions" style={{ justifyContent: 'center', marginTop: '1.5rem' }}>
            <button
              type="button"
              className="btn btn--outline btn--large"
              onClick={handleBack}
            >
              {t('setup.provider.back')}
            </button>
            {backendIndex > 2 ? (
              <button
                type="button"
                className="btn btn--primary btn--large"
                style={{ marginLeft: '1rem' }}
                onClick={() => advanceToNextStep()}
              >
                {t('setup.provider.skipConfigured')}
              </button>
            ) : null}
          </div>
        </div>
      );
    }

    if (STEP_ORDER[renderIndex] === 'first_butler_agent') {
      return (
        <div className="setup-wizard-card--transparent">
          <div className="setup-wizard-header">
            <h2>{t('setup.butler.title')}</h2>
            <p>{t('setup.butler.desc')}</p>
          </div>
          <ButlerBootstrapConversation
            householdId={currentHouseholdId}
            source="setup-wizard"
            onCreated={() => refreshShellState(currentHouseholdId).then(advanceToNextStep)}
          />
          <div className="setup-form-actions" style={{ justifyContent: 'center', marginTop: '1.5rem' }}>
            <button
              type="button"
              className="btn btn--outline btn--large"
              onClick={handleBack}
            >
              {t('setup.butler.back')}
            </button>
          </div>
        </div>
      );
    }

    return (
      <Card className="setup-wizard-card">
        <div className="setup-wizard-header">
          <h2>{t('setup.finish.title')}</h2>
          <p>{t('setup.finish.desc')}</p>
        </div>
        <div
          className="setup-form-actions"
          style={{ justifyContent: 'center', gap: '1rem', marginTop: '2rem' }}
        >
          <button
            type="button"
            className="btn btn--outline btn--large"
            onClick={handleBack}
          >
            {t('setup.finish.back')}
          </button>
          <button
            type="button"
            className="btn btn--primary btn--large"
            onClick={() => {
              void enterApp();
            }}
          >
            {t('setup.finish.enterApp')}
          </button>
        </div>
      </Card>
    );
  }

  const guardedContent = !currentHouseholdId && !canCreateFirstHousehold && !setupStatusLoading
    ? (
      <div className="setup-page">
        <PageHeader title={t('setup.page.title')} />
        <EmptyState
          title={t('setup.page.emptyTitle')}
          description={t('setup.page.emptyDesc')}
        />
      </div>
    )
    : setupStatusLoading
      ? (
        <div className="setup-page setup-page--centered">
          <p>{t('setup.page.loading')}</p>
        </div>
      )
      : !hasSeenWelcome && !currentHouseholdId && backendIndex === 0
        ? (
          <div>
            <WelcomeStep
              onComplete={() => {
                markWelcomeSeen();
                setHasSeenWelcome(true);
              }}
            />
          </div>
        )
        : (
          <div className="setup-page setup-page--centered">
            {renderThemeSwitcher()}
            <div className="setup-wizard-container">
              {renderStepper()}
              <div className="setup-wizard-content">{renderCurrentStep()}</div>
            </div>
          </div>
        );

  return (
    <GuardedPage mode="setup" path="/pages/setup/index">
      {guardedContent}
    </GuardedPage>
  );
}
