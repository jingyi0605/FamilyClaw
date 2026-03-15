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
          setError(loadError instanceof Error ? loadError.message : '加载设置失败');
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
  }, [currentHouseholdId]);

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
      setStatus('设置已保存。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存设置失败');
    } finally {
      setLoading(false);
    }
  }

  return { config, loading, error, status, savePatch };
}

function SettingsAppearanceSection() {
  const { themeId, themeList, setTheme } = useTheme();

  return (
    <div className="settings-page">
      <Section title="主题模式">
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
  const { locale, locales, setLocale, formatLocaleLabel } = useI18n();
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
      setError('请先选择家庭');
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
      setError(saveError instanceof Error ? saveError.message : '保存语言设置失败');
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
      '界面语言已更新。',
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
      '时区已更新。',
    );

    if (!saved) {
      setTimezone(previousTimezone);
    }
  }

  return (
    <div className="settings-page">
      <Section title="语言与地区">
        <div className="settings-form">
          <div className="form-group">
            <label>界面语言</label>
            <select
              className="form-select"
              value={locale}
              onChange={(event) => void handleLocaleChange(event.target.value)}
              disabled={saving}
            >
              {locales.map((item) => (
                <option key={item.id} value={item.id}>
                  {formatLocaleLabel(item)} · {getLocaleSourceLabel(item)}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>时区</label>
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

  return (
    <div className="settings-page">
      <Section title="通知偏好">
        <div className="settings-form">
          <div className="form-group">
            <label>通知方式</label>
            <select className="form-select" value="浏览器通知 + 站内消息" disabled>
              <option>浏览器通知 + 站内消息</option>
              <option>仅站内消息</option>
              <option>全部关闭</option>
            </select>
            <div className="form-help">
              通知方式还没有稳定后端字段，先展示默认方案，不乱写假映射。
            </div>
          </div>

          <div className="settings-toggles">
            <ToggleSwitch
              checked={config?.quiet_hours_enabled ?? false}
              label="免打扰"
              description={`开启后在 ${config?.quiet_hours_start ?? '22:00'}-${config?.quiet_hours_end ?? '07:00'} 不发送通知`}
              onChange={(value) => void savePatch({ quiet_hours_enabled: value })}
            />
          </div>

          <div className="form-group">
            <label>通知范围</label>
            <select className="form-select" disabled>
              <option>全部通知</option>
              <option>仅紧急通知</option>
              <option>仅与我相关</option>
            </select>
          </div>
        </div>

        <SettingsNotice icon="ℹ️">
          当前真正接入的只有免打扰开关和时段。其他字段后端还没稳定，先别自作聪明编状态。
        </SettingsNotice>
        {error ? <SettingsNotice tone="error" icon="⚠️">{error}</SettingsNotice> : null}
        {status ? <SettingsNotice tone="success" icon="✓">{status}</SettingsNotice> : null}
        {loading ? <SettingsNotice icon="⏳">正在保存...</SettingsNotice> : null}
      </Section>
    </div>
  );
}

function SettingsAccessibilitySection() {
  const { themeId, setTheme } = useTheme();
  const isElder = themeId === 'ming-cha-qiu-hao';

  return (
    <div className="settings-page">
      <Section title="长辈友好">
        <div className="settings-toggles">
          <ToggleSwitch
            checked={isElder}
            label="启用长辈友好模式"
            description="切换到更大字号和更高对比度"
            onChange={(value) => setTheme(value ? 'ming-cha-qiu-hao' : 'chun-he-jing-ming')}
          />
        </div>

        <div className="elder-preview">
          <Card className="elder-preview-card">
            <h3>预览效果</h3>
            <p style={{ fontSize: isElder ? '1.125rem' : '0.9375rem' }}>
              {isElder
                ? '长辈友好模式已开启，界面会使用更大的字号和更高的对比度。'
                : '当前是标准模式。开启后会更适合年长用户阅读和操作。'}
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
