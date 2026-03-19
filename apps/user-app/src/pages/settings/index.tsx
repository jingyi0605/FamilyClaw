import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import Taro, { useRouter } from '@tarojs/taro';
import { getLocaleSourceLabel } from '@familyclaw/user-core';
import { PageSection, ToggleSwitch, UiButton, UiCard, UiText, userAppFoundationTokens } from '@familyclaw/user-ui';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n, useTheme } from '../../runtime/h5-shell';
import type { ThemeRuntimeSelection, ThemeRuntimeThemeOption } from '../../runtime/shared/theme-plugin/types';
import { SettingsPageShell } from './SettingsPageShell';
import { SettingsNotice } from './components/SettingsSharedBlocks';
import { settingsApi } from './settingsApi';
import type { ContextConfigRead, SystemVersionRead } from './settingsTypes';

type SettingsSection = 'appearance' | 'language' | 'notifications' | 'accessibility' | 'version-management';
function resolveSection(value?: string | string[]): SettingsSection {
  const raw = Array.isArray(value) ? value[0] : value;
  if (
    raw === 'language'
    || raw === 'notifications'
    || raw === 'accessibility'
    || raw === 'version-management'
  ) {
    return raw;
  }
  return 'appearance';
}

function pickThemeSelection(
  themeList: ThemeRuntimeThemeOption[],
  themeId: string,
): ThemeRuntimeSelection | null {
  const matched = themeList.find(theme => theme.id === themeId && theme.source_type === 'builtin')
    ?? themeList.find(theme => theme.id === themeId)
    ?? null;
  if (!matched) {
    return null;
  }
  return {
    plugin_id: matched.plugin_id,
    theme_id: matched.id,
  };
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
  const {
    theme: currentTheme,
    themeId,
    themeList,
    themeListLoading,
    themeListError,
    themeFallbackNotice,
    setTheme,
    getThemeVersionInfo,
  } = useTheme();
  const { t } = useI18n();

  return (
    <div className="settings-page">
      <PageSection title={t('settings.appearance.title')} contentStyle={{ marginTop: 0 }}>
        {themeFallbackNotice ? (
          <SettingsNotice tone="info" icon="!">
            {t('settings.appearance.themeDisabledNotice', {
              theme: themeFallbackNotice.disabledThemeId,
            })}
            {themeFallbackNotice.disabledReason
              ? ` ${t('settings.appearance.disabledReason', { reason: themeFallbackNotice.disabledReason })}`
              : ''}
          </SettingsNotice>
        ) : null}
        {themeListError ? <SettingsNotice tone="error" icon="!">{themeListError}</SettingsNotice> : null}
        {themeListLoading ? <SettingsNotice icon="...">{t('settings.appearance.loading')}</SettingsNotice> : null}
        {!themeListLoading && !themeListError && !themeList.length ? (
          <SettingsNotice tone="info" icon="!">{t('settings.appearance.noAvailableThemes')}</SettingsNotice>
        ) : null}
        <div className="theme-grid">
          {themeList.map((theme) => {
            const themeVersionInfo = getThemeVersionInfo(theme.id);
            const isActive = currentTheme.id === theme.id && currentTheme.plugin_id === theme.plugin_id;
            return (
            <div
              key={`${theme.plugin_id}:${theme.id}`}
              className={`theme-card ${isActive ? 'theme-card--active' : ''}`}
              onClick={() => setTheme({
                plugin_id: theme.plugin_id,
                theme_id: theme.id,
              })}
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
                  {themeVersionInfo ? (
                    <span className="theme-card__desc">
                      v{themeVersionInfo.installedVersion ?? themeVersionInfo.version}
                    </span>
                  ) : null}
                </div>
                {isActive ? <span className="theme-card__check">✓</span> : null}
              </div>
            </div>
            );
          })}
        </div>
      </PageSection>
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
      <PageSection title={t('settings.language.title')} contentStyle={{ marginTop: 0 }}>
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
      </PageSection>
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
      <PageSection title={t('settings.notifications.title')} contentStyle={{ marginTop: 0 }}>
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
      </PageSection>
    </div>
  );
}

function SettingsAccessibilitySection() {
  const { theme, themeId, themeList, setTheme, isThemeAvailable, getThemeDisabledReason } = useTheme();
  const { t } = useI18n();
  const isElder = themeId === 'ming-cha-qiu-hao';
  const elderThemeSelection = pickThemeSelection(themeList, 'ming-cha-qiu-hao');
  const defaultThemeSelection = pickThemeSelection(themeList, 'chun-he-jing-ming');
  const elderThemeAvailable = elderThemeSelection !== null || isThemeAvailable('ming-cha-qiu-hao');
  const elderThemeDisabledReason = getThemeDisabledReason('ming-cha-qiu-hao');
  const elderModeDescription = elderThemeAvailable
    ? t('settings.accessibility.elderModeDesc')
    : elderThemeDisabledReason
      ? t('settings.accessibility.elderModeDisabledReason', { reason: elderThemeDisabledReason })
      : t('settings.accessibility.elderModeUnavailable');

  return (
    <div className="settings-page">
      <PageSection title={t('settings.accessibility.title')} contentStyle={{ marginTop: 0 }}>
        <div className="settings-toggles">
          <ToggleSwitch
            checked={isElder && elderThemeAvailable && (theme.plugin_id === elderThemeSelection?.plugin_id || elderThemeSelection === null)}
            label={t('settings.accessibility.elderMode')}
            description={elderModeDescription}
            disabled={!elderThemeAvailable}
            onChange={(value) => {
              const nextSelection = value ? elderThemeSelection : defaultThemeSelection;
              if (nextSelection) {
                setTheme(nextSelection);
              }
            }}
          />
        </div>

        <div className="elder-preview">
          <UiCard className="elder-preview-card">
            <UiText variant="label">{t('settings.accessibility.previewTitle')}</UiText>
            <UiText style={{ fontSize: isElder ? userAppFoundationTokens.fontSize.lg : userAppFoundationTokens.fontSize.md }}>
              {isElder ? t('settings.accessibility.previewEnabled') : t('settings.accessibility.previewDisabled')}
            </UiText>
          </UiCard>
        </div>
      </PageSection>
    </div>
  );
}

function SettingsVersionManagementSection() {
  const { t, locale } = useI18n();
  const [versionInfo, setVersionInfo] = useState<SystemVersionRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadVersionInfo() {
      setLoading(true);
      setLoadFailed(false);

      try {
        const result = await settingsApi.getSystemVersion();
        if (!cancelled) {
          setVersionInfo(result);
        }
      } catch {
        if (!cancelled) {
          setVersionInfo(null);
          setLoadFailed(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadVersionInfo();

    return () => {
      cancelled = true;
    };
  }, []);

  function formatDateLabel(value: string | null) {
    if (!value) {
      return '';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '';
    }

    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
    }).format(date);
  }

  function openReleaseNotes(url: string) {
    if (typeof window === 'undefined') {
      return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  const currentVersion = versionInfo?.current_version ?? null;
  const latestVersion = versionInfo?.latest_version ?? versionInfo?.current_version ?? null;
  const latestVersionValue = latestVersion ?? '';
  const publishedAtLabel = formatDateLabel(versionInfo?.latest_release_published_at ?? null);
  const showLatestVersionPill = versionInfo?.update_status === 'update_available'
    && Boolean(latestVersionValue)
    && latestVersion !== currentVersion;
  const releaseNotesUrl = versionInfo?.update_status === 'update_available'
    ? versionInfo.latest_release_notes_url ?? versionInfo.release_notes_url
    : versionInfo?.release_notes_url ?? versionInfo?.latest_release_notes_url ?? null;
  const releaseNotesLabel = versionInfo?.update_status === 'update_available'
    ? t('settings.versionManagement.viewNewReleaseNotes')
    : t('settings.versionManagement.viewReleaseNotes');
  const statusToneClass = loading
    ? 'version-management-overview--loading'
    : versionInfo?.update_status === 'update_available'
      ? 'version-management-overview--available'
      : versionInfo?.update_status === 'up_to_date'
        ? 'version-management-overview--up-to-date'
        : 'version-management-overview--unknown';
  const statusBadgeLabel = loading
    ? t('settings.versionManagement.loadingValue')
    : versionInfo?.update_status === 'update_available'
      ? t('settings.versionManagement.statusBadge.updateAvailable')
      : versionInfo?.update_status === 'up_to_date'
        ? t('settings.versionManagement.statusBadge.upToDate')
        : t('settings.versionManagement.statusBadge.unavailable');
  const statusTitle = loading
    ? t('settings.versionManagement.loadingTitle')
    : versionInfo?.update_status === 'update_available'
      ? t('settings.versionManagement.statusTitle.updateAvailable', {
        version: latestVersion ?? t('settings.versionManagement.versionFallback'),
      })
      : versionInfo?.update_status === 'up_to_date'
        ? t('settings.versionManagement.statusTitle.upToDate')
        : t('settings.versionManagement.statusTitle.unavailable');
  const statusDescription = loading
    ? t('settings.versionManagement.loadingDescription')
    : versionInfo?.update_status === 'update_available'
      ? t('settings.versionManagement.statusDescription.updateAvailable', {
        current: currentVersion ?? t('settings.versionManagement.versionFallback'),
        latest: latestVersion ?? t('settings.versionManagement.versionFallback'),
      })
      : versionInfo?.update_status === 'up_to_date'
        ? t('settings.versionManagement.statusDescription.upToDate', {
          version: currentVersion ?? t('settings.versionManagement.versionFallback'),
        })
        : t('settings.versionManagement.statusDescription.unavailable', {
          version: currentVersion ?? t('settings.versionManagement.versionFallback'),
        });
  const releaseTitle = loading
    ? t('settings.versionManagement.releaseCard.loadingTitle')
    : versionInfo?.latest_release_title
      ? versionInfo.latest_release_title
      : versionInfo?.update_status === 'update_available'
        ? t('settings.versionManagement.releaseCard.fallbackTitleAvailable', {
          version: latestVersion ?? t('settings.versionManagement.versionFallback'),
        })
        : t('settings.versionManagement.releaseCard.fallbackTitleCurrent', {
          version: latestVersion ?? currentVersion ?? t('settings.versionManagement.versionFallback'),
        });
  const releaseSummary = loading
    ? t('settings.versionManagement.loadingDescription')
    : versionInfo?.latest_release_summary
      ? versionInfo.latest_release_summary
      : versionInfo?.update_status === 'update_available'
        ? t('settings.versionManagement.releaseCard.fallbackSummaryAvailable')
        : versionInfo?.update_status === 'up_to_date'
          ? t('settings.versionManagement.releaseCard.fallbackSummaryCurrent')
          : t('settings.versionManagement.releaseCard.fallbackSummaryUnavailable');

  return (
    <div className="settings-page settings-page--version-management">
      <PageSection title={t('settings.versionManagement.title')} contentStyle={{ marginTop: 0 }}>
        {loadFailed ? (
          <SettingsNotice tone="error" icon="!">
            {t('settings.versionManagement.loadFailed')}
          </SettingsNotice>
        ) : null}

        <UiCard className={`version-management-overview ${statusToneClass}`}>
          <div className="version-management-overview__body">
            <span className="version-management-overview__badge">{statusBadgeLabel}</span>
            <h3 className="version-management-overview__title">{statusTitle}</h3>
            <p className="version-management-overview__desc">{statusDescription}</p>
            <div className="version-management-overview__meta">
              {currentVersion ? (
                <span className="version-management-overview__meta-item">
                  {t('settings.versionManagement.currentVersionPill', { version: currentVersion })}
                </span>
              ) : null}
              {showLatestVersionPill ? (
                <span className="version-management-overview__meta-item">
                  {t('settings.versionManagement.latestVersionPill', { version: latestVersionValue })}
                </span>
              ) : null}
            </div>
          </div>
        </UiCard>

        <UiCard className="version-management-release">
          <div className="version-management-release__header">
            <div>
              <UiText variant="label">{t('settings.versionManagement.releaseCard.eyebrow')}</UiText>
              <h3 className="version-management-release__title">{releaseTitle}</h3>
              {publishedAtLabel ? (
                <p className="version-management-release__meta">
                  {t('settings.versionManagement.releaseCard.publishedAt', { date: publishedAtLabel })}
                </p>
              ) : null}
            </div>
          </div>
          <p className="version-management-release__summary">{releaseSummary}</p>
          {releaseNotesUrl ? (
            <div className="version-management-release__actions">
              <UiButton variant="secondary" size="sm" onClick={() => openReleaseNotes(releaseNotesUrl)}>
                {releaseNotesLabel}
              </UiButton>
            </div>
          ) : null}
          {!releaseNotesUrl && !loading ? (
            <p className="version-management-release__hint">
              {t('settings.versionManagement.releaseCard.noLinkHint')}
            </p>
          ) : null}
        </UiCard>
      </PageSection>
    </div>
  );
}

function SettingsIndexContent() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const section = resolveSection(router.params?.section);

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('nav.settings') }).catch(() => undefined);
  }, [t, locale]);

  return (
    <SettingsPageShell activeKey={section}>
      {section === 'appearance' ? <SettingsAppearanceSection /> : null}
      {section === 'language' ? <SettingsLanguageSection /> : null}
      {section === 'notifications' ? <SettingsNotificationsSection /> : null}
      {section === 'accessibility' ? <SettingsAccessibilitySection /> : null}
      {section === 'version-management' ? <SettingsVersionManagementSection /> : null}
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
