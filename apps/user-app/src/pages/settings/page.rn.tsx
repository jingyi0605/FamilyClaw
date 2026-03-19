import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Taro, { useRouter } from '@tarojs/taro';
import { GuardedPage, useHouseholdContext, useI18n } from '../../runtime/index.rn';
import { useTheme } from '../../runtime/h5-shell/index.rn';
import {
  RnCard,
  RnPageHeader,
  RnPageShell,
  RnSection,
  RnTabBar,
  RnText,
  rnFoundationTokens,
  rnSemanticTokens,
} from '../../runtime/rn-shell';
import type {
  ThemeFallbackNotice,
  ThemeRuntimeSelection,
  ThemeRuntimeThemeOption,
} from '../../runtime/shared/theme-plugin/types';
import { settingsApi } from './settingsApi';
import type { SystemVersionRead } from './settingsTypes';

type SettingsSection = 'appearance' | 'language' | 'about';
type T = ReturnType<typeof useI18n>['t'];

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'UTC', label: 'UTC (UTC+0)' },
];

function SegmentedControl({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <View style={segStyles.container}>
      {options.map(option => {
        const active = option.key === value;
        return (
          <Pressable
            key={option.key}
            style={[segStyles.item, active && segStyles.itemActive]}
            onPress={() => onChange(option.key)}
          >
            <RnText
              variant="caption"
              tone={active ? 'primary' : 'secondary'}
              style={{ fontWeight: active ? '600' : '400' }}
            >
              {option.label}
            </RnText>
          </Pressable>
        );
      })}
    </View>
  );
}

const segStyles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: rnSemanticTokens.surface.muted,
    borderRadius: rnFoundationTokens.radius.md,
    padding: rnFoundationTokens.spacing.xs,
    marginBottom: rnFoundationTokens.spacing.md,
  },
  item: {
    flex: 1,
    paddingVertical: rnFoundationTokens.spacing.sm,
    alignItems: 'center',
    borderRadius: rnFoundationTokens.radius.sm,
  },
  itemActive: {
    backgroundColor: rnSemanticTokens.surface.card,
  },
});

function ThemeCard({
  theme,
  isActive,
  versionLabel,
  onPress,
}: {
  theme: ThemeRuntimeThemeOption;
  isActive: boolean;
  versionLabel: string | null;
  onPress: () => void;
}) {
  return (
    <Pressable style={[themeCardStyles.container, isActive && themeCardStyles.containerActive]} onPress={onPress}>
      <View style={themeCardStyles.preview}>
        <View style={[themeCardStyles.previewBg, { backgroundColor: theme.bgApp || rnSemanticTokens.surface.page }]}>
          <View
            style={[
              themeCardStyles.previewCard,
              { backgroundColor: theme.bgCard || rnSemanticTokens.surface.card },
            ]}
          />
        </View>
      </View>
      <View style={themeCardStyles.info}>
        <RnText variant="label" style={themeCardStyles.flex1}>
          {theme.emoji} {theme.label}
        </RnText>
        {isActive ? <RnText variant="caption" tone="primary">✓</RnText> : null}
      </View>
      <RnText variant="caption" tone="tertiary" numberOfLines={1}>
        {theme.description}
      </RnText>
      {versionLabel ? (
        <RnText variant="caption" tone="secondary" style={themeCardStyles.version}>
          {versionLabel}
        </RnText>
      ) : null}
    </Pressable>
  );
}

const themeCardStyles = StyleSheet.create({
  container: {
    backgroundColor: rnSemanticTokens.surface.card,
    borderColor: rnSemanticTokens.border.subtle,
    borderWidth: 1,
    borderRadius: rnFoundationTokens.radius.md,
    padding: rnFoundationTokens.spacing.sm,
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  containerActive: {
    borderColor: rnSemanticTokens.action.primary,
    borderWidth: 2,
  },
  preview: {
    height: 48,
    marginBottom: rnFoundationTokens.spacing.sm,
    borderRadius: rnFoundationTokens.radius.sm,
    overflow: 'hidden',
  },
  previewBg: {
    flex: 1,
    padding: 6,
  },
  previewCard: {
    flex: 1,
    borderRadius: 4,
  },
  info: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  flex1: {
    flex: 1,
  },
  version: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
});

function OptionChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={[chipStyles.chip, active && chipStyles.chipActive]} onPress={onPress}>
      <RnText variant="caption" tone={active ? 'primary' : 'secondary'}>
        {label}
      </RnText>
    </Pressable>
  );
}

const chipStyles = StyleSheet.create({
  chip: {
    backgroundColor: rnSemanticTokens.surface.muted,
    borderRadius: rnFoundationTokens.radius.md,
    paddingHorizontal: rnFoundationTokens.spacing.sm,
    paddingVertical: rnFoundationTokens.spacing.xs,
    marginRight: rnFoundationTokens.spacing.xs,
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  chipActive: {
    backgroundColor: rnSemanticTokens.action.primaryLight,
    borderWidth: 1,
    borderColor: rnSemanticTokens.action.primary,
  },
});

function NoticeCard({
  tone,
  children,
}: {
  tone: 'default' | 'warning' | 'error';
  children: ReactNode;
}) {
  const style = tone === 'warning'
    ? noticeStyles.warning
    : tone === 'error'
      ? noticeStyles.error
      : noticeStyles.default;

  return (
    <RnCard variant="muted" style={[noticeStyles.base, style]}>
      <RnText variant="caption" tone={tone === 'error' ? 'danger' : tone === 'warning' ? 'warning' : 'secondary'}>
        {children}
      </RnText>
    </RnCard>
  );
}

const noticeStyles = StyleSheet.create({
  base: {
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  default: {},
  warning: {
    borderColor: rnSemanticTokens.state.warning,
  },
  error: {
    borderColor: rnSemanticTokens.state.danger,
  },
});

function resolveFallbackNoticeLabel(themeList: ThemeRuntimeThemeOption[], notice: ThemeFallbackNotice | null) {
  if (!notice) {
    return '';
  }
  return themeList.find(theme => theme.id === notice.disabledThemeId)?.label ?? notice.disabledThemeId;
}

function AppearanceSection({
  currentTheme,
  themeList,
  themeListLoading,
  themeListError,
  themeFallbackNotice,
  getThemeVersionInfo,
  onThemeChange,
  t,
}: {
  currentTheme: ThemeRuntimeThemeOption;
  themeList: ThemeRuntimeThemeOption[];
  themeListLoading: boolean;
  themeListError: string;
  themeFallbackNotice: ThemeFallbackNotice | null;
  getThemeVersionInfo: (themeId: string) => { pluginId: string; version: string; installedVersion: string | null } | null;
  onThemeChange: (selection: ThemeRuntimeSelection) => void;
  t: T;
}) {
  const disabledThemeLabel = resolveFallbackNoticeLabel(themeList, themeFallbackNotice);

  return (
    <RnSection title={t('settings.appearance.title')}>
      <RnText variant="body" tone="secondary" style={{ marginBottom: rnFoundationTokens.spacing.md }}>
        {t('settings.appearance.desc')}
      </RnText>

      {themeFallbackNotice ? (
        <NoticeCard tone="warning">
          {t('settings.appearance.themeDisabledNotice', { theme: disabledThemeLabel })}
          {themeFallbackNotice.disabledReason
            ? ` ${t('settings.appearance.disabledReason', { reason: themeFallbackNotice.disabledReason })}`
            : ''}
        </NoticeCard>
      ) : null}

      {themeListError ? <NoticeCard tone="error">{themeListError}</NoticeCard> : null}
      {themeListLoading ? <NoticeCard tone="default">{t('settings.appearance.loading')}</NoticeCard> : null}
      {!themeListLoading && !themeListError && !themeList.length ? (
        <NoticeCard tone="default">{t('settings.appearance.noAvailableThemes')}</NoticeCard>
      ) : null}

      {themeList.map(theme => {
        const versionInfo = getThemeVersionInfo(theme.id);
        const versionLabel = versionInfo && versionInfo.pluginId === theme.plugin_id
          ? `v${versionInfo.installedVersion ?? versionInfo.version}`
          : null;
        const isActive = currentTheme.id === theme.id && currentTheme.plugin_id === theme.plugin_id;

        return (
          <ThemeCard
            key={`${theme.plugin_id}:${theme.id}`}
            theme={theme}
            isActive={isActive}
            versionLabel={versionLabel}
            onPress={() => onThemeChange({
              plugin_id: theme.plugin_id,
              theme_id: theme.id,
            })}
          />
        );
      })}
    </RnSection>
  );
}

function LanguageSection({
  locale,
  locales,
  timezone,
  onLocaleChange,
  onTimezoneChange,
  formatLocaleLabel,
  t,
}: {
  locale: string;
  locales: Array<{ id: string; label: string; source: string; nativeLabel: string }>;
  timezone: string;
  onLocaleChange: (locale: string) => void;
  onTimezoneChange: (timezone: string) => void;
  formatLocaleLabel: (locale: { id: string; nativeLabel: string }) => string;
  t: T;
}) {
  return (
    <RnSection title={t('settings.language.title')}>
      <View style={languageStyles.group}>
        <RnText variant="label">{t('settings.language.interface')}</RnText>
        <View style={languageStyles.options}>
          {locales.map(localeOption => (
            <OptionChip
              key={localeOption.id}
              label={formatLocaleLabel(localeOption)}
              active={locale === localeOption.id}
              onPress={() => onLocaleChange(localeOption.id)}
            />
          ))}
        </View>
      </View>

      <View style={languageStyles.group}>
        <RnText variant="label">{t('settings.language.timezone')}</RnText>
        <View style={languageStyles.options}>
          {TIMEZONE_OPTIONS.map(timezoneOption => (
            <OptionChip
              key={timezoneOption.value}
              label={timezoneOption.label}
              active={timezone === timezoneOption.value}
              onPress={() => onTimezoneChange(timezoneOption.value)}
            />
          ))}
        </View>
      </View>
    </RnSection>
  );
}

const languageStyles = StyleSheet.create({
  group: {
    marginBottom: rnFoundationTokens.spacing.md,
  },
  options: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: rnFoundationTokens.spacing.sm,
  },
});

function AboutSection({
  versionInfo,
  loading,
  t,
}: {
  versionInfo: SystemVersionRead | null;
  loading: boolean;
  t: T;
}) {
  const currentVersion = versionInfo?.current_version ?? '-';
  const updateStatus = versionInfo?.update_status ?? 'unknown';

  return (
    <RnSection title={t('settings.versionManagement.title')}>
      <RnCard variant="muted">
        <View style={aboutStyles.center}>
          <RnText style={aboutStyles.emoji}>FC</RnText>
          <RnText variant="title">FamilyClaw</RnText>
          <RnText variant="caption" tone="secondary" style={aboutStyles.version}>
            {t('settings.versionManagement.currentVersionPill', { version: currentVersion })}
          </RnText>
        </View>
      </RnCard>
      {!loading && updateStatus === 'update_available' ? (
        <View style={aboutStyles.updateBadge}>
          <RnText variant="caption" tone="success">
            {t('settings.versionManagement.statusBadge.updateAvailable')}
          </RnText>
        </View>
      ) : null}
    </RnSection>
  );
}

const aboutStyles = StyleSheet.create({
  center: {
    alignItems: 'center',
    paddingVertical: rnFoundationTokens.spacing.lg,
  },
  emoji: {
    fontSize: 40,
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  version: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
  updateBadge: {
    marginTop: rnFoundationTokens.spacing.sm,
  },
});

function SettingsContent() {
  const router = useRouter();
  const { t, locale, locales, setLocale, formatLocaleLabel } = useI18n();
  const {
    theme: currentTheme,
    themeList,
    themeListLoading,
    themeListError,
    themeFallbackNotice,
    setTheme,
    getThemeVersionInfo,
  } = useTheme();
  const {
    currentHouseholdId,
    currentHousehold,
    refreshCurrentHousehold,
    refreshHouseholds,
  } = useHouseholdContext();

  const initialSection = router.params?.section ?? 'appearance';
  const [activeSection, setActiveSection] = useState<SettingsSection>(
    (['language', 'about'] as const).includes(initialSection as 'language' | 'about')
      ? initialSection as SettingsSection
      : 'appearance',
  );
  const [timezone, setTimezone] = useState(currentHousehold?.timezone ?? 'Asia/Shanghai');
  const [versionInfo, setVersionInfo] = useState<SystemVersionRead | null>(null);
  const [versionLoading, setVersionLoading] = useState(true);

  useEffect(() => {
    if (currentHousehold?.timezone) {
      setTimezone(currentHousehold.timezone);
    }
  }, [currentHousehold?.timezone]);

  useEffect(() => {
    let cancelled = false;

    async function loadVersion() {
      setVersionLoading(true);
      try {
        const result = await settingsApi.getSystemVersion();
        if (!cancelled) {
          setVersionInfo(result);
        }
      } catch {
        if (!cancelled) {
          setVersionInfo(null);
        }
      } finally {
        if (!cancelled) {
          setVersionLoading(false);
        }
      }
    }

    void loadVersion();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('nav.settings') }).catch(() => undefined);
  }, [t]);

  async function handleLocaleChange(nextLocale: string) {
    const previousLocale = locale;
    setLocale(nextLocale);
    if (!currentHouseholdId) {
      return;
    }

    try {
      await settingsApi.updateHousehold(currentHouseholdId, { locale: nextLocale });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
    } catch {
      setLocale(previousLocale);
    }
  }

  async function handleTimezoneChange(nextTimezone: string) {
    const previousTimezone = timezone;
    setTimezone(nextTimezone);
    if (!currentHouseholdId) {
      return;
    }

    try {
      await settingsApi.updateHousehold(currentHouseholdId, { timezone: nextTimezone });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
    } catch {
      setTimezone(previousTimezone);
    }
  }

  const sectionOptions = [
    { key: 'appearance', label: t('settings.section.appearance') },
    { key: 'language', label: t('settings.section.language') },
    { key: 'about', label: t('settings.section.about') },
  ];

  const processedLocales = useMemo(
    () => locales.map(item => ({
      ...item,
      label: item.label ?? item.id,
      nativeLabel: item.nativeLabel ?? item.label ?? item.id,
    })),
    [locales],
  );

  return (
    <RnPageShell safeAreaBottom={false}>
      <RnPageHeader title={t('settings.title')} />
      <SegmentedControl
        options={sectionOptions}
        value={activeSection}
        onChange={section => setActiveSection(section as SettingsSection)}
      />

      {activeSection === 'appearance' ? (
        <AppearanceSection
          currentTheme={currentTheme}
          themeList={themeList}
          themeListLoading={themeListLoading}
          themeListError={themeListError}
          themeFallbackNotice={themeFallbackNotice}
          getThemeVersionInfo={getThemeVersionInfo}
          onThemeChange={selection => setTheme(selection)}
          t={t}
        />
      ) : null}

      {activeSection === 'language' ? (
        <LanguageSection
          locale={locale}
          locales={processedLocales}
          timezone={timezone}
          onLocaleChange={handleLocaleChange}
          onTimezoneChange={handleTimezoneChange}
          formatLocaleLabel={item => formatLocaleLabel(item)}
          t={t}
        />
      ) : null}

      {activeSection === 'about' ? (
        <AboutSection versionInfo={versionInfo} loading={versionLoading} t={t} />
      ) : null}

      <RnTabBar />
    </RnPageShell>
  );
}

export default function SettingsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/index">
      <SettingsContent />
    </GuardedPage>
  );
}
