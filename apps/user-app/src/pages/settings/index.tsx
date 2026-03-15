import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Text, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  BootstrapSnapshot,
  ContextConfigRead,
  LocaleDefinition,
  ThemeId,
  buildLocaleDefinitions,
  formatLocaleOptionLabel,
  getLocaleSourceLabel,
  getStoredLocaleId,
  getStoredThemeId,
  listThemeOptions,
  persistLocaleId,
  persistThemeId,
  resolveSupportedLocale,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  FormField,
  OptionPills,
  PrimaryButton,
  SectionNote,
  TextInput,
} from '../../components/AppUi';
import { MainShellPage } from '../../components/MainShellPage';
import { APP_ROUTES, coreApiClient, needsBlockingSetup, taroStorage, useAppRuntime } from '../../runtime';

const themeOptions = listThemeOptions();

const homeModeOptions: Array<{ value: ContextConfigRead['home_mode']; label: string }> = [
  { value: 'home', label: '居家' },
  { value: 'away', label: '离家' },
  { value: 'night', label: '夜间' },
  { value: 'sleep', label: '睡眠' },
  { value: 'custom', label: '自定义' },
];

const privacyOptions: Array<{ value: ContextConfigRead['privacy_mode']; label: string }> = [
  { value: 'balanced', label: '平衡' },
  { value: 'strict', label: '严格' },
  { value: 'care', label: '关怀' },
];

const automationOptions: Array<{ value: ContextConfigRead['automation_level']; label: string }> = [
  { value: 'manual', label: '手动' },
  { value: 'assisted', label: '辅助自动' },
  { value: 'automatic', label: '自动' },
];

function buildDefaultConfig(): ContextConfigRead {
  return {
    household_id: '',
    home_mode: 'home',
    privacy_mode: 'balanced',
    automation_level: 'assisted',
    home_assistant_status: 'offline',
    active_member_id: null,
    voice_fast_path_enabled: false,
    guest_mode_enabled: false,
    child_protection_enabled: false,
    elder_care_watch_enabled: false,
    quiet_hours_enabled: false,
    quiet_hours_start: '22:00',
    quiet_hours_end: '07:00',
    member_states: [],
    room_settings: [],
    version: 0,
    updated_by: null,
    updated_at: '',
  };
}

export default function SettingsPage() {
  const { bootstrap, loading } = useAppRuntime();
  const [config, setConfig] = useState<ContextConfigRead>(buildDefaultConfig());
  const [themeId, setThemeId] = useState<ThemeId>('chun-he-jing-ming');
  const [localeId, setLocaleId] = useState('zh-CN');
  const [localeOptions, setLocaleOptions] = useState<LocaleDefinition[]>(buildLocaleDefinitions());
  const [pageLoading, setPageLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [savingKey, setSavingKey] = useState('');
  const loadRequestIdRef = useRef(0);
  const activeHouseholdIdRef = useRef('');

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';

  const loadSettings = useCallback(async (snapshot: BootstrapSnapshot | null = bootstrap) => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;
    const definitions = buildLocaleDefinitions(snapshot?.locales ?? []);
    const householdLocale = resolveSupportedLocale(snapshot?.currentHousehold?.locale, definitions);

    if (householdChanged) {
      setConfig(buildDefaultConfig());
      setStatus('');
      setError('');
    }

    activeHouseholdIdRef.current = householdId;

    setPageLoading(true);
    setError('');

    try {
      const [storedTheme, storedLocale, configResult] = await Promise.all([
        getStoredThemeId(taroStorage),
        getStoredLocaleId(taroStorage, definitions, householdLocale),
        householdId ? coreApiClient.getContextConfig(householdId) : Promise.resolve(buildDefaultConfig()),
      ]);

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      setLocaleOptions(definitions);
      setThemeId(storedTheme);
      setLocaleId(storedLocale);
      setConfig(configResult);
    } catch (loadError) {
      if (requestId !== loadRequestIdRef.current) {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : '设置页加载失败');
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [bootstrap, currentHouseholdId]);

  useEffect(() => {
    if (loading || !bootstrap?.actor?.authenticated || needsBlockingSetup(bootstrap.setupStatus)) {
      return;
    }

    void loadSettings();
  }, [bootstrap, loadSettings, loading]);

  useDidShow(() => {
    if (!loading && bootstrap?.actor?.authenticated && !needsBlockingSetup(bootstrap.setupStatus)) {
      void loadSettings();
    }
  });

  async function runConfigSave(key: string, nextConfig: ContextConfigRead, successMessage: string) {
    if (!currentHouseholdId) {
      setError('当前没有可用的家庭上下文');
      return;
    }

    setSavingKey(key);
    setStatus('');
    setError('');

    try {
      const result = await coreApiClient.updateContextConfig(currentHouseholdId, {
        home_mode: nextConfig.home_mode,
        privacy_mode: nextConfig.privacy_mode,
        automation_level: nextConfig.automation_level,
        home_assistant_status: nextConfig.home_assistant_status,
        active_member_id: nextConfig.active_member_id,
        voice_fast_path_enabled: nextConfig.voice_fast_path_enabled,
        guest_mode_enabled: nextConfig.guest_mode_enabled,
        child_protection_enabled: nextConfig.child_protection_enabled,
        elder_care_watch_enabled: nextConfig.elder_care_watch_enabled,
        quiet_hours_enabled: nextConfig.quiet_hours_enabled,
        quiet_hours_start: nextConfig.quiet_hours_start,
        quiet_hours_end: nextConfig.quiet_hours_end,
        member_states: nextConfig.member_states,
        room_settings: nextConfig.room_settings,
      });
      setConfig(result);
      setStatus(successMessage);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '设置保存失败');
    } finally {
      setSavingKey('');
    }
  }

  async function handleThemeSave(nextThemeId: ThemeId) {
    setSavingKey('theme');
    setStatus('');
    setError('');

    try {
      const savedThemeId = await persistThemeId(taroStorage, nextThemeId);
      setThemeId(savedThemeId);
      setStatus('主题偏好已写入共享存储。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '主题保存失败');
    } finally {
      setSavingKey('');
    }
  }

  async function handleLocaleSave(nextLocaleId: string) {
    setSavingKey('locale');
    setStatus('');
    setError('');

    try {
      const fallbackLocale = resolveSupportedLocale(bootstrap?.currentHousehold?.locale, localeOptions);
      const savedLocaleId = await persistLocaleId(taroStorage, nextLocaleId, localeOptions, fallbackLocale);
      setLocaleId(savedLocaleId);
      setStatus('语言偏好已写入共享存储。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '语言保存失败');
    } finally {
      setSavingKey('');
    }
  }

  const currentTheme = themeOptions.find(item => item.id === themeId) ?? themeOptions[0];
  const currentLocale = localeOptions.find(item => item.id === localeId) ?? localeOptions[0];

  const toggleOptions = useMemo(() => ([
    { value: 'true', label: '开启' },
    { value: 'false', label: '关闭' },
  ]), []);

  return (
    <MainShellPage currentNav="settings" title="设置链路已接入真实偏好和运行配置" description="设置页现在不只会存主题和语言，还能改家庭运行模式、服务开关和免打扰时段。">
      <PageSection title="当前设置摘要" description="用户最常看的几个设置状态先在这一屏收口。">
        <StatusCard label="当前主题" value={currentTheme.label} tone="info" />
        <StatusCard label="当前语言" value={currentLocale ? formatLocaleOptionLabel(currentLocale) : '未读取'} tone="success" />
        <StatusCard label="家庭时区" value={bootstrap?.currentHousehold?.timezone ?? '未读取'} tone="info" />
        <StatusCard label="家庭模式" value={config.home_mode} tone="warning" />
        {pageLoading ? <SectionNote>正在加载设置页...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
      </PageSection>

      <PageSection title="正式设置子页" description="这三块是真缺口，现在已经在 user-app 里有正式入口，不再让设置首页把问题藏起来。">
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[
            {
              title: 'AI 设置中心',
              description: '管理 AI provider、能力路由、首位管家补建和 Agent 配置中心。',
              url: APP_ROUTES.settingsAi,
            },
            {
              title: '设备与集成',
              description: '管理 Home Assistant 配置、设备同步、房间同步和语音终端认领。',
              url: APP_ROUTES.settingsIntegrations,
            },
            {
              title: '通讯平台接入',
              description: '管理平台账号、状态探测、失败记录和成员绑定。',
              url: APP_ROUTES.settingsChannelAccess,
            },
          ].map(item => (
            <View
              key={item.url}
              style={{
                background: '#ffffff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                {item.title}
              </Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px', lineHeight: '1.6' }}>
                {item.description}
              </Text>
              <ActionRow>
                <PrimaryButton onClick={() => void Taro.navigateTo({ url: item.url })}>
                  进入设置页
                </PrimaryButton>
              </ActionRow>
            </View>
          ))}
        </View>
      </PageSection>

      <PageSection title="主题偏好" description="先把主题偏好继续放在共享存储，保证新旧前端一致。">
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {themeOptions.map(option => (
            <View
              key={option.id}
              style={{
                background: option.id === themeId ? option.previewSurface : '#f9fbff',
                border: `1px solid ${option.accentColor}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                {option.label}
              </Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '24px', lineHeight: '1.6' }}>
                {option.description}
              </Text>
              <ActionRow>
                <PrimaryButton disabled={savingKey === 'theme'} onClick={() => void handleThemeSave(option.id)}>
                  {themeId === option.id ? '当前已启用' : savingKey === 'theme' ? '保存中...' : '启用主题'}
                </PrimaryButton>
              </ActionRow>
            </View>
          ))}
        </View>
      </PageSection>

      <PageSection title="语言偏好" description="这里直接复用共享 locale 目录和持久化逻辑。">
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {localeOptions.map(option => (
            <View
              key={option.id}
              style={{
                background: option.id === localeId ? '#eef5ff' : '#f9fbff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                {formatLocaleOptionLabel(option)}
              </Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '24px', lineHeight: '1.6' }}>
                来源：{getLocaleSourceLabel(option)}
              </Text>
              <ActionRow>
                <PrimaryButton disabled={savingKey === 'locale'} onClick={() => void handleLocaleSave(option.id)}>
                  {localeId === option.id ? '当前已启用' : savingKey === 'locale' ? '保存中...' : '启用语言'}
                </PrimaryButton>
              </ActionRow>
            </View>
          ))}
        </View>
      </PageSection>

      <PageSection title="家庭运行模式" description="这些就是设置页真正该管的核心运行配置，不是摆几个不能保存的假控件。">
        <FormField label="家庭模式">
          <OptionPills value={config.home_mode} options={homeModeOptions} onChange={value => setConfig(current => ({ ...current, home_mode: value }))} />
        </FormField>
        <FormField label="隐私模式">
          <OptionPills value={config.privacy_mode} options={privacyOptions} onChange={value => setConfig(current => ({ ...current, privacy_mode: value }))} />
        </FormField>
        <FormField label="自动化等级">
          <OptionPills value={config.automation_level} options={automationOptions} onChange={value => setConfig(current => ({ ...current, automation_level: value }))} />
        </FormField>
        <ActionRow>
          <PrimaryButton
            disabled={!currentHouseholdId || Boolean(savingKey)}
            onClick={() => void runConfigSave('runtime-mode', config, '运行模式配置已保存。')}
          >
            {savingKey === 'runtime-mode' ? '保存中...' : '保存运行模式'}
          </PrimaryButton>
        </ActionRow>
      </PageSection>

      <PageSection title="家庭服务开关" description="高频服务开关和免打扰时段先做到真能保存。">
        <FormField label="语音快通道">
          <OptionPills value={String(config.voice_fast_path_enabled)} options={toggleOptions} onChange={value => setConfig(current => ({ ...current, voice_fast_path_enabled: value === 'true' }))} />
        </FormField>
        <FormField label="访客模式">
          <OptionPills value={String(config.guest_mode_enabled)} options={toggleOptions} onChange={value => setConfig(current => ({ ...current, guest_mode_enabled: value === 'true' }))} />
        </FormField>
        <FormField label="儿童保护">
          <OptionPills value={String(config.child_protection_enabled)} options={toggleOptions} onChange={value => setConfig(current => ({ ...current, child_protection_enabled: value === 'true' }))} />
        </FormField>
        <FormField label="长辈关怀">
          <OptionPills value={String(config.elder_care_watch_enabled)} options={toggleOptions} onChange={value => setConfig(current => ({ ...current, elder_care_watch_enabled: value === 'true' }))} />
        </FormField>
        <FormField label="免打扰开关">
          <OptionPills value={String(config.quiet_hours_enabled)} options={toggleOptions} onChange={value => setConfig(current => ({ ...current, quiet_hours_enabled: value === 'true' }))} />
        </FormField>
        <FormField label="免打扰开始时间">
          <TextInput value={config.quiet_hours_start} onInput={value => setConfig(current => ({ ...current, quiet_hours_start: value }))} />
        </FormField>
        <FormField label="免打扰结束时间">
          <TextInput value={config.quiet_hours_end} onInput={value => setConfig(current => ({ ...current, quiet_hours_end: value }))} />
        </FormField>
        <ActionRow>
          <PrimaryButton
            disabled={!currentHouseholdId || Boolean(savingKey)}
            onClick={() => void runConfigSave('runtime-switches', config, '服务开关和免打扰时段已保存。')}
          >
            {savingKey === 'runtime-switches' ? '保存中...' : '保存服务开关'}
          </PrimaryButton>
        </ActionRow>
      </PageSection>

      <PageSection title="长辈友好快速切换" description="低频子页先不搬完，但最常用的可读性切换直接放到这里。">
        <FormField label="是否切换到长辈友好主题">
          <OptionPills
            value={themeId === 'ming-cha-qiu-hao' ? 'true' : 'false'}
            options={toggleOptions}
            onChange={value => void handleThemeSave(value === 'true' ? 'ming-cha-qiu-hao' : 'chun-he-jing-ming')}
          />
        </FormField>
        <SectionNote>
          这轮先把真正常用的切换做实。通知、插件、HA 集成这些低频子页后面再按优先级单独迁，不在当前阶段把页面堆肿。
        </SectionNote>
      </PageSection>

      {!currentHouseholdId && !pageLoading ? (
        <EmptyStateCard title="当前没有家庭上下文" description="设置页依赖已选中的家庭，先回首页或向导补上下文。" />
      ) : null}
    </MainShellPage>
  );
}
