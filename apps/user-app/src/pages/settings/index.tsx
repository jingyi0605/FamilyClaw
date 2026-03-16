import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import { useRouter } from '@tarojs/taro';
import { getLocaleSourceLabel } from '@familyclaw/user-core';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n, useTheme } from '../../runtime/h5-shell';
import { Card, Section, ToggleSwitch } from '../family/base';
import { SettingsPageShell } from './SettingsPageShell';
import { settingsApi } from './settingsApi';
import type { ContextConfigRead } from './settingsTypes';

type SettingsSection = 'appearance' | 'language' | 'notifications' | 'accessibility';
type SettingsNoticeTone = 'info' | 'success' | 'error';

function resolveSection(value?: string | string[]): SettingsSection {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === 'language' || raw === 'notifications' || raw === 'accessibility') {
    return raw;
  }
  return 'appearance';
}

function SettingsNotice(props: {
  tone?: SettingsNoticeTone;
  icon: ReactNode;
  children: ReactNode;
}) {
  const toneClass = props.tone === 'success'
    ? 'settings-note--success'
    : props.tone === 'error'
      ? 'settings-note--error'
      : '';

  return (
    <div className={`settings-note ${toneClass}`.trim()}>
      <span>{props.icon}</span>
      <span>{props.children}</span>
    </div>
  );
}

function useContextConfigSettings() {
  const { currentHouseholdId } = useHouseholdContext();
  const { t } = useI18n();
  const [config, setConfig] = useState<ContextConfigRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    if (!currentHouseholdId) {
      setConfig(null);
      return;
    }

    let cancelled = false;

    async function loadConfig() {
      setLoading(true);
      setError('');
      setStatus('');

      try {
        const result = await settingsApi.getContextConfig(currentHouseholdId);
        if (!cancelled) {
          setConfig(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : t('settings.error.loadFailed'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadConfig();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, t]);

  async function savePatch(
    patch: Partial<Omit<ContextConfigRead, 'household_id' | 'version' | 'updated_by' | 'updated_at'>>,
  ) {
    if (!currentHouseholdId || !config) {
      return;
    }

    setLoading(true);
    setError('');
    setStatus('');

    try {
      const result = await settingsApi.updateContextConfig(currentHouseholdId, {
        home_mode: config.home_mode,
        privacy_mode: config.privacy_mode,
        automation_level: config.automation_level,
        home_assistant_status: config.home_assistant_status,
        active_member_id: config.active_member_id,
        voice_fast_path_enabled: config.voice_fast_path_enabled,
        guest_mode_enabled: config.guest_mode_enabled,
        child_protection_enabled: config.child_protection_enabled,
        elder_care_watch_enabled: config.elder_care_watch_enabled,
        quiet_hours_enabled: config.quiet_hours_enabled,
        quiet_hours_start: config.quiet_hours_start,
        quiet_hours_end: config.quiet_hours_end,
        member_states: config.member_states,
        room_settings: config.room_settings,
        ...patch,
      });
      setConfig(result);
      setStatus(t('settings.status.saved'));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings.error.saveFailed'));
    } finally {
      setLoading(false);
    }
  }

  return { config, loading, error, status, savePatch };
}

function SettingsAppearanceSection() {
  const { themeId, themeList, setTheme } = useTheme();
  const { t } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.appearance.title')}>
        <div className="theme-grid">
          {themeList.map((theme) => (
            <div
              key={theme.id}
              className={`theme-card ${themeId === theme.id ? 'theme-card--active' : ''}`}
              onClick={() => setTheme(theme.id)}
              style={{
                '--preview-bg': theme.bgApp,
                '--preview-card': theme.bgCard,
                '--preview-brand': theme.brandPrimary,
                '--preview-text': theme.textPrimary,
                '--preview-glow': theme.glowColor,
              } as CSSProperties}
            >
              <div className="theme-card__preview">
                <div className="theme-card__preview-bg">
                  <div className="theme-card__preview-sidebar" />
                  <div className="theme-card__preview-content">
                    <div className="theme-card__preview-bar" />
                    <div className="theme-card__preview-cards">
                      <div className="theme-card__preview-mini" />
                      <div className="theme-card__preview-mini" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="theme-card__info">
                <span className="theme-card__emoji">{theme.emoji}</span>
                <div className="theme-card__text">
                  <span className="theme-card__label">{theme.label}</span>
                  <span className="theme-card__desc">{theme.description}</span>
                </div>
                {themeId === theme.id ? <span className="theme-card__check">✓</span> : null}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function SettingsLanguageSection() {
  const { locale, locales, setLocale, formatLocaleLabel, t } = useI18n();
  const {
    currentHouseholdId,
    currentHousehold,
    refreshCurrentHousehold,
    refreshHouseholds,
  } = useHouseholdContext();
  const [timezone, setTimezone] = useState(
    currentHousehold?.timezone ?? (Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const timezoneOptions = useMemo(() => [
    { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
    { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
    { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
    { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
    { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
    { value: 'UTC', label: 'UTC (UTC+0)' },
  ], []);

  const localeSourceLabels = useMemo(
    () => ({
      builtin: t('locale.source.builtin'),
      official: t('locale.source.official'),
      third_party: t('locale.source.thirdParty'),
    }),
    [t],
  );

  useEffect(() => {
    if (currentHousehold?.timezone) {
      setTimezone(currentHousehold.timezone);
    }
  }, [currentHousehold?.timezone]);

  async function saveHouseholdLanguageSettings(
    patch: { locale?: string; timezone?: string },
    successMessage: string,
  ) {
    if (!currentHouseholdId) {
      setError(t('settings.language.noHousehold'));
      setStatus('');
      return false;
    }

    setSaving(true);
    setError('');
    setStatus('');

    try {
      await settingsApi.updateHousehold(currentHouseholdId, patch);
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
      setStatus(successMessage);
      return true;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings.language.saveFailed'));
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handleLocaleChange(nextLocale: string) {
    const previousLocale = locale;
    setLocale(nextLocale);

    const saved = await saveHouseholdLanguageSettings(
      { locale: nextLocale },
      t('settings.language.localeSaved'),
    );

    if (!saved) {
      setLocale(previousLocale);
    }
  }

  async function handleTimezoneChange(nextTimezone: string) {
    const previousTimezone = timezone;
    setTimezone(nextTimezone);

    const saved = await saveHouseholdLanguageSettings(
      { timezone: nextTimezone },
      t('settings.language.timezoneSaved'),
    );

    if (!saved) {
      setTimezone(previousTimezone);
    }
  }

  return (
    <div className="settings-page">
      <Section title={t('settings.language.title')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.language.interface')}</label>
            <select
              className="form-select"
              value={locale}
              onChange={(event) => void handleLocaleChange(event.target.value)}
              disabled={saving}
            >
              {locales.map((item) => {
                const sourceKey = getLocaleSourceLabel(item) as keyof typeof localeSourceLabels;
                const sourceLabel = localeSourceLabels[sourceKey] ?? getLocaleSourceLabel(item);

                return (
                  <option key={item.id} value={item.id}>
                    {formatLocaleLabel(item)} · {sourceLabel}
                  </option>
                );
              })}
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.timezone')}</label>
            <select
              className="form-select"
              value={timezone}
              onChange={(event) => void handleTimezoneChange(event.target.value)}
              disabled={saving || !currentHouseholdId}
            >
              {timezoneOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
              {!timezoneOptions.some((option) => option.value === timezone) && timezone ? (
                <option value={timezone}>{timezone}</option>
              ) : null}
            </select>
          </div>
        </div>
        {error ? <SettingsNotice tone="error" icon="⚠️">{error}</SettingsNotice> : null}
        {status ? <SettingsNotice tone="success" icon="✓">{status}</SettingsNotice> : null}
      </Section>
    </div>
  );
}

function SettingsNotificationsSection() {
  const { config, loading, error, status, savePatch } = useContextConfigSettings();
  const { t } = useI18n();
  const quietHoursDescription = t('settings.notifications.quietHoursDesc')
    .replace('{start}', config?.quiet_hours_start ?? '22:00')
    .replace('{end}', config?.quiet_hours_end ?? '07:00');

  return (
    <div className="settings-page">
      <Section title={t('settings.notifications.title')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.notifications.channel')}</label>
            <select className="form-select" value={t('settings.notifications.channelBrowserAndInApp')} disabled>
              <option>{t('settings.notifications.channelBrowserAndInApp')}</option>
              <option>{t('settings.notifications.channelInAppOnly')}</option>
              <option>{t('settings.notifications.channelOff')}</option>
            </select>
            <div className="form-help">
              {t('settings.notifications.channelHint')}
            </div>
          </div>

          <div className="settings-toggles">
            <ToggleSwitch
              checked={config?.quiet_hours_enabled ?? false}
              label={t('settings.notifications.quietHours')}
              description={quietHoursDescription}
              onChange={(value) => void savePatch({ quiet_hours_enabled: value })}
            />
          </div>

          <div className="form-group">
            <label>{t('settings.notifications.scope')}</label>
            <select className="form-select" disabled>
              <option>{t('settings.notifications.scopeAll')}</option>
              <option>{t('settings.notifications.scopeUrgent')}</option>
              <option>{t('settings.notifications.scopeMine')}</option>
            </select>
            <div className="form-help">
              {t('settings.notifications.scopeHint')}
            </div>
          </div>
        </div>
        {error ? <SettingsNotice tone="error" icon="⚠️">{error}</SettingsNotice> : null}
        {status ? <SettingsNotice tone="success" icon="✓">{status}</SettingsNotice> : null}
        {loading ? <SettingsNotice icon="⏳">{t('settings.notifications.loading')}</SettingsNotice> : null}
      </Section>
    </div>
  );
}

function SettingsAccessibilitySection() {
  const { themeId, setTheme } = useTheme();
  const { t } = useI18n();
  const isElder = themeId === 'ming-cha-qiu-hao';

  return (
    <div className="settings-page">
      <Section title={t('settings.accessibility.title')}>
        <div className="settings-toggles">
          <ToggleSwitch
            checked={isElder}
            label={t('settings.accessibility.elderMode')}
            description={t('settings.accessibility.elderModeDesc')}
            onChange={(value) => setTheme(value ? 'ming-cha-qiu-hao' : 'chun-he-jing-ming')}
          />
        </div>

        <div className="elder-preview">
          <Card className="elder-preview-card">
            <h3>{t('settings.accessibility.previewTitle')}</h3>
            <p style={{ fontSize: isElder ? '1.125rem' : '0.9375rem' }}>
              {isElder ? t('settings.accessibility.previewEnabled') : t('settings.accessibility.previewDisabled')}
            </p>
          </Card>
        </div>
      </Section>
    </div>
  );
}

function SettingsIndexContent() {
  const router = useRouter();
  const section = resolveSection(router.params?.section);

  return (
    <SettingsPageShell activeKey={section}>
      {section === 'appearance' ? <SettingsAppearanceSection /> : null}
      {section === 'language' ? <SettingsLanguageSection /> : null}
      {section === 'notifications' ? <SettingsNotificationsSection /> : null}
      {section === 'accessibility' ? <SettingsAccessibilitySection /> : null}
    </SettingsPageShell>
  );
}

export default function SettingsIndexPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/index">
      <SettingsIndexContent />
    </GuardedPage>
  );
}
