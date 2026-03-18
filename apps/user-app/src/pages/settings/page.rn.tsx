/**
 * RN 设置页
 *
 * 分段控制器切换外观/语言/关于三个区块。
 */
import { useState, useEffect, useMemo } from 'react';
import { Pressable, View, StyleSheet } from 'react-native';
import Taro, { useRouter } from '@tarojs/taro';
import { GuardedPage, useHouseholdContext, useI18n } from '../../runtime';
import {
  RnPageShell,
  RnPageHeader,
  RnSection,
  RnCard,
  RnText,
  RnTabBar,
  rnFoundationTokens,
  rnSemanticTokens,
} from '../../runtime/rn-shell';
import { settingsApi } from './settingsApi';
import type { SystemVersionRead } from './settingsTypes';

/* ─── 类型 ─── */

type SettingsSection = 'appearance' | 'language' | 'about';
type T = ReturnType<typeof useI18n>['t'];

interface ThemeInfo { id: string; emoji: string; label: string; description: string }

/* ─── 静态数据 ─── */

const THEME_LIST: ThemeInfo[] = [
  { id: 'chun-he-jing-ming', emoji: '🌸', label: '春和景明', description: '温暖宁静，适合日常使用' },
  { id: 'yue-lang-xing-xi', emoji: '🌙', label: '月朗星稀', description: '柔和深色，减少视觉疲劳' },
  { id: 'ming-cha-qiu-hao', emoji: '🔍', label: '明察秋毫', description: '更大字号、更高对比度' },
  { id: 'wan-zi-qian-hong', emoji: '🌈', label: '万紫千红', description: '鲜艳活泼，色彩绚烂' },
  { id: 'feng-chi-dian-che', emoji: '⚡', label: '风驰电掣', description: '霓虹电网，赛博激光' },
  { id: 'xing-he-wan-li', emoji: '🚀', label: '星河万里', description: '星云流动，宇宙漫游' },
  { id: 'qing-shan-lv-shui', emoji: '🌿', label: '青山绿水', description: '自然清新，森林氧吧' },
  { id: 'jin-xiu-qian-cheng', emoji: '👑', label: '锦绣前程', description: '鎏金尊贵，大气庄重' },
];

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'UTC', label: 'UTC (UTC+0)' },
];

const THEME_PREVIEW_BG: Record<string, string> = {
  'chun-he-jing-ming': '#f7f5f2', 'yue-lang-xing-xi': '#0f1117',
  'ming-cha-qiu-hao': '#f5f5f0', 'wan-zi-qian-hong': '#fef8ff',
  'feng-chi-dian-che': '#160a22', 'xing-he-wan-li': '#0f1228',
  'qing-shan-lv-shui': '#f2f7f3', 'jin-xiu-qian-cheng': '#0e0c08',
};

const THEME_PREVIEW_CARD: Record<string, string> = {
  'chun-he-jing-ming': '#ffffff', 'yue-lang-xing-xi': '#1e2130',
  'ming-cha-qiu-hao': '#ffffff', 'wan-zi-qian-hong': '#ffffff',
  'feng-chi-dian-che': '#251440', 'xing-he-wan-li': '#1c2045',
  'qing-shan-lv-shui': '#ffffff', 'jin-xiu-qian-cheng': '#1e1a0e',
};

/* ─── 分段控制器 ─── */

function SegmentedControl({
  options, value, onChange,
}: {
  options: { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <View style={segStyles.container}>
      {options.map(opt => {
        const active = opt.key === value;
        return (
          <Pressable key={opt.key} style={[segStyles.item, active && segStyles.itemActive]} onPress={() => onChange(opt.key)}>
            <RnText variant="caption" tone={active ? 'primary' : 'secondary'} style={{ fontWeight: active ? '600' : '400' }}>
              {opt.label}
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

/* ─── 主题卡片 ─── */

function ThemeCard({ theme, isActive, onPress }: { theme: ThemeInfo; isActive: boolean; onPress: () => void }) {
  return (
    <Pressable style={[tcStyles.container, isActive && tcStyles.containerActive]} onPress={onPress}>
      <View style={tcStyles.preview}>
        <View style={[tcStyles.previewBg, { backgroundColor: THEME_PREVIEW_BG[theme.id] ?? '#f7f5f2' }]}>
          <View style={[tcStyles.previewCard, { backgroundColor: THEME_PREVIEW_CARD[theme.id] ?? '#fff' }]} />
        </View>
      </View>
      <View style={tcStyles.info}>
        <RnText variant="label" style={tcStyles.flex1}>{theme.emoji} {theme.label}</RnText>
        {isActive ? <RnText variant="caption" tone="primary">✓</RnText> : null}
      </View>
      <RnText variant="caption" tone="tertiary" numberOfLines={1}>{theme.description}</RnText>
    </Pressable>
  );
}

const tcStyles = StyleSheet.create({
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
  previewBg: { flex: 1, padding: 6 },
  previewCard: { flex: 1, borderRadius: 4 },
  info: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  flex1: { flex: 1 },
});

/* ─── 选项标签（语言/时区） ─── */

function OptionChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[chipStyles.chip, active && chipStyles.chipActive]} onPress={onPress}>
      <RnText variant="caption" tone={active ? 'primary' : 'secondary'}>{label}</RnText>
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

/* ─── 区块组件 ─── */

function AppearanceSection({ themeId, onThemeChange, t }: { themeId: string; onThemeChange: (id: string) => void; t: T }) {
  return (
    <RnSection title={t('settings.appearance.title')}>
      <RnText variant="body" tone="secondary" style={{ marginBottom: rnFoundationTokens.spacing.md }}>
        {t('settings.appearance.desc')}
      </RnText>
      {THEME_LIST.map(theme => (
        <ThemeCard key={theme.id} theme={theme} isActive={themeId === theme.id} onPress={() => onThemeChange(theme.id)} />
      ))}
    </RnSection>
  );
}

function LanguageSection({
  locale, locales, timezone, onLocaleChange, onTimezoneChange, formatLocaleLabel, t,
}: {
  locale: string;
  locales: Array<{ id: string; label: string; source: string; nativeLabel: string }>;
  timezone: string;
  onLocaleChange: (locale: string) => void;
  onTimezoneChange: (tz: string) => void;
  formatLocaleLabel: (locale: { id: string; nativeLabel: string }) => string;
  t: T;
}) {
  return (
    <RnSection title={t('settings.language.title')}>
      <View style={langStyles.group}>
        <RnText variant="label">{t('settings.language.interface')}</RnText>
        <View style={langStyles.options}>
          {locales.map(loc => (
            <OptionChip key={loc.id} label={formatLocaleLabel(loc)} active={locale === loc.id} onPress={() => onLocaleChange(loc.id)} />
          ))}
        </View>
      </View>
      <View style={langStyles.group}>
        <RnText variant="label">{t('settings.language.timezone')}</RnText>
        <View style={langStyles.options}>
          {TIMEZONE_OPTIONS.map(tz => (
            <OptionChip key={tz.value} label={tz.label} active={timezone === tz.value} onPress={() => onTimezoneChange(tz.value)} />
          ))}
        </View>
      </View>
    </RnSection>
  );
}

const langStyles = StyleSheet.create({
  group: { marginBottom: rnFoundationTokens.spacing.md },
  options: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: rnFoundationTokens.spacing.sm,
  },
});

function AboutSection({ versionInfo, loading, t }: { versionInfo: SystemVersionRead | null; loading: boolean; t: T }) {
  const currentVersion = versionInfo?.current_version ?? '-';
  const updateStatus = versionInfo?.update_status ?? 'unknown';

  return (
    <RnSection title={t('settings.versionManagement.title')}>
      <RnCard variant="muted">
        <View style={aboutStyles.center}>
          <RnText style={aboutStyles.emoji}>🐾</RnText>
          <RnText variant="title">FamilyClaw</RnText>
          <RnText variant="caption" tone="secondary" style={aboutStyles.version}>
            {t('settings.versionManagement.currentVersionPill', { version: currentVersion })}
          </RnText>
        </View>
      </RnCard>
      {!loading && updateStatus === 'update_available' ? (
        <View style={aboutStyles.updateBadge}>
          <RnText variant="caption" tone="success">{t('settings.versionManagement.statusBadge.updateAvailable')}</RnText>
        </View>
      ) : null}
    </RnSection>
  );
}

const aboutStyles = StyleSheet.create({
  center: { alignItems: 'center', paddingVertical: rnFoundationTokens.spacing.lg },
  emoji: { fontSize: 40, marginBottom: rnFoundationTokens.spacing.sm },
  version: { marginTop: rnFoundationTokens.spacing.xs },
  updateBadge: { marginTop: rnFoundationTokens.spacing.sm },
});

/* ─── 页面主体 ─── */

function SettingsContent() {
  const router = useRouter();
  const { t, locale, locales, setLocale, formatLocaleLabel } = useI18n();
  const { currentHouseholdId, currentHousehold, refreshCurrentHousehold, refreshHouseholds } = useHouseholdContext();

  const initialSection = router.params?.section ?? 'appearance';
  const [activeSection, setActiveSection] = useState<SettingsSection>(
    (['language', 'about'] as const).includes(initialSection as 'language' | 'about')
      ? initialSection as SettingsSection
      : 'appearance',
  );

  const [themeId, setThemeId] = useState('chun-he-jing-ming');
  const [timezone, setTimezone] = useState(currentHousehold?.timezone ?? 'Asia/Shanghai');
  const [versionInfo, setVersionInfo] = useState<SystemVersionRead | null>(null);
  const [versionLoading, setVersionLoading] = useState(true);

  useEffect(() => {
    if (currentHousehold?.timezone) setTimezone(currentHousehold.timezone);
  }, [currentHousehold?.timezone]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setVersionLoading(true);
      try {
        const r = await settingsApi.getSystemVersion();
        if (!cancelled) setVersionInfo(r);
      } catch {
        if (!cancelled) setVersionInfo(null);
      } finally {
        if (!cancelled) setVersionLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('nav.settings') }).catch(() => undefined);
  }, [t]);

  async function handleLocaleChange(next: string) {
    const prev = locale;
    setLocale(next);
    if (!currentHouseholdId) return;
    try {
      await settingsApi.updateHousehold(currentHouseholdId, { locale: next });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
    } catch {
      setLocale(prev);
    }
  }

  async function handleTimezoneChange(next: string) {
    const prev = timezone;
    setTimezone(next);
    if (!currentHouseholdId) return;
    try {
      await settingsApi.updateHousehold(currentHouseholdId, { timezone: next });
      await refreshCurrentHousehold(currentHouseholdId);
      await refreshHouseholds();
    } catch {
      setTimezone(prev);
    }
  }

  const sectionOptions = [
    { key: 'appearance', label: t('settings.section.appearance') },
    { key: 'language', label: t('settings.section.language') },
    { key: 'about', label: t('settings.section.about') },
  ];

  const processedLocales = useMemo(() =>
    locales.map(loc => ({ ...loc, label: loc.label ?? loc.id, nativeLabel: loc.nativeLabel ?? loc.label ?? loc.id })),
    [locales],
  );

  return (
    <RnPageShell safeAreaBottom={false}>
      <RnPageHeader title={t('settings.title')} />
      <SegmentedControl options={sectionOptions} value={activeSection} onChange={k => setActiveSection(k as SettingsSection)} />

      {activeSection === 'appearance' ? (
        <AppearanceSection themeId={themeId} onThemeChange={setThemeId} t={t} />
      ) : null}

      {activeSection === 'language' ? (
        <LanguageSection
          locale={locale}
          locales={processedLocales}
          timezone={timezone}
          onLocaleChange={handleLocaleChange}
          onTimezoneChange={handleTimezoneChange}
          formatLocaleLabel={loc => formatLocaleLabel(loc)}
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
