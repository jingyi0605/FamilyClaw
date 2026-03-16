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

function getLocalizedThemeMeta(themeId: string, locale: string | undefined) {
  const pick = (values: { zhCN: string; zhTW: string; enUS: string }) => {
    if (locale?.toLowerCase().startsWith('en')) return values.enUS;
    if (locale?.toLowerCase().startsWith('zh-tw')) return values.zhTW;
    return values.zhCN;
  };

  switch (themeId) {
    case 'chun-he-jing-ming':
      return {
        label: pick({ zhCN: '春和景明', zhTW: '春和景明', enUS: 'Spring Light' }),
        description: pick({ zhCN: '温暖宁静，适合日常使用', zhTW: '溫暖寧靜，適合日常使用', enUS: 'Warm and calm for everyday use' }),
      };
    case 'yue-lang-xing-xi':
      return {
        label: pick({ zhCN: '月朗星稀', zhTW: '月朗星稀', enUS: 'Moonlit Night' }),
        description: pick({ zhCN: '沉静夜色，更适合专注浏览', zhTW: '沉靜夜色，更適合專注瀏覽', enUS: 'Quiet night tones for focused browsing' }),
      };
    case 'ming-cha-qiu-hao':
      return {
        label: pick({ zhCN: '明察秋毫', zhTW: '明察秋毫', enUS: 'Clear Insight' }),
        description: pick({ zhCN: '高对比老花主题，字更稳更清楚', zhTW: '高對比熟齡主題，文字更穩更清楚', enUS: 'High-contrast elder-friendly theme with clearer text' }),
      };
    case 'wan-zi-qian-hong':
      return {
        label: pick({ zhCN: '万紫千红', zhTW: '萬紫千紅', enUS: 'Bloom Burst' }),
        description: pick({ zhCN: '明快热闹，适合喜欢鲜艳配色', zhTW: '明快熱鬧，適合喜歡鮮豔配色', enUS: 'Bright and lively for vivid color lovers' }),
      };
    case 'feng-chi-dian-che':
      return {
        label: pick({ zhCN: '风驰电掣', zhTW: '風馳電掣', enUS: 'Velocity' }),
        description: pick({ zhCN: '冷感速度系，适合喜欢锐利科技感', zhTW: '冷調速度系，適合喜歡銳利科技感', enUS: 'Cool, sharp, and more technical' }),
      };
    case 'xing-he-wan-li':
      return {
        label: pick({ zhCN: '星河万里', zhTW: '星河萬里', enUS: 'Galaxy' }),
        description: pick({ zhCN: '深邃星空风格，层次感更强', zhTW: '深邃星空風格，層次感更強', enUS: 'Deep space style with stronger layering' }),
      };
    case 'qing-shan-lv-shui':
      return {
        label: pick({ zhCN: '青山绿水', zhTW: '青山綠水', enUS: 'Verdant Hills' }),
        description: pick({ zhCN: '清爽自然，适合长时间阅读', zhTW: '清爽自然，適合長時間閱讀', enUS: 'Fresh and natural for long reading sessions' }),
      };
    case 'jin-xiu-qian-cheng':
      return {
        label: pick({ zhCN: '锦绣前程', zhTW: '錦繡前程', enUS: 'Golden Prospect' }),
        description: pick({ zhCN: '金色暖调，适合偏正式和稳重风格', zhTW: '金色暖調，適合偏正式和穩重風格', enUS: 'Warm golden tones with a formal, steady feel' }),
      };
    default:
      return null;
  }
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
  const { t, locale } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.appearance.title')}>
        <div className="theme-grid">
          {themeList.map((theme) => {
            const localizedTheme = getLocalizedThemeMeta(theme.id, locale);
            return (
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
                  <span className="theme-card__label">{localizedTheme?.label ?? theme.label}</span>
                  <span className="theme-card__desc">{localizedTheme?.description ?? theme.description}</span>
                </div>
                {themeId === theme.id ? <span className="theme-card__check">✓</span> : null}
              </div>
            </div>
            );
          })}
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
