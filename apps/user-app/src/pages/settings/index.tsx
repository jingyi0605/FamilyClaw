import { useEffect, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import {
  buildLocaleDefinitions,
  formatLocaleOptionLabel,
  getLocaleSourceLabel,
  getStoredLocaleId,
  getStoredThemeId,
  listThemeOptions,
  persistLocaleId,
  persistThemeId,
  resolveSupportedLocale,
  type BootstrapSnapshot,
  type LocaleDefinition,
  type ThemeId,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';
import { loadUserAppBootstrap, taroStorage } from '../../runtime';

const themeOptions = listThemeOptions();

export default function SettingsPage() {
  const [snapshot, setSnapshot] = useState<BootstrapSnapshot | null>(null);
  const [localeOptions, setLocaleOptions] = useState<LocaleDefinition[]>(buildLocaleDefinitions());
  const [themeId, setThemeId] = useState<ThemeId>('chun-he-jing-ming');
  const [localeId, setLocaleId] = useState('zh-CN');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    let cancelled = false;

    const loadSettings = async () => {
      setLoading(true);
      setError('');

      try {
        const bootstrap = await loadUserAppBootstrap();
        const definitions = buildLocaleDefinitions(bootstrap.locales);
        const householdLocale = resolveSupportedLocale(
          bootstrap.currentHousehold?.locale,
          definitions,
        );
        const [storedThemeId, storedLocaleId] = await Promise.all([
          getStoredThemeId(taroStorage),
          getStoredLocaleId(taroStorage, definitions, householdLocale),
        ]);

        if (cancelled) {
          return;
        }

        setSnapshot(bootstrap);
        setLocaleOptions(definitions);
        setThemeId(storedThemeId);
        setLocaleId(storedLocaleId);
      } catch (loadError) {
        if (cancelled) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : '设置页加载失败');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  const currentTheme = themeOptions.find(item => item.id === themeId) ?? themeOptions[0];
  const currentLocale = localeOptions.find(item => item.id === localeId) ?? localeOptions[0];

  async function handleThemeChange(nextThemeId: ThemeId) {
    setSaving(true);
    setError('');
    setStatus('');

    try {
      const resolvedThemeId = await persistThemeId(taroStorage, nextThemeId);
      setThemeId(resolvedThemeId);
      setStatus('主题偏好已写入共享存储，新旧前端都可以复用这份选择。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '主题偏好保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function handleLocaleChange(nextLocaleId: string) {
    setSaving(true);
    setError('');
    setStatus('');

    try {
      const fallbackLocale = resolveSupportedLocale(snapshot?.currentHousehold?.locale, localeOptions);
      const resolvedLocaleId = await persistLocaleId(taroStorage, nextLocaleId, localeOptions, fallbackLocale);
      setLocaleId(resolvedLocaleId);
      setStatus('语言偏好已写入共享存储，后面迁移设置子页时不需要再重写一套浏览器逻辑。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '语言偏好保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShellPage>
      <PageSection
        title="设置入口已接共享状态"
        description="这一页不再是空壳，主题和语言偏好已经从 user-web 的浏览器实现里抽到共享层。"
      >
        <StatusCard label="当前主题" value={currentTheme?.label ?? '未读取'} tone="info" />
        <StatusCard
          label="当前语言"
          value={currentLocale ? formatLocaleOptionLabel(currentLocale) : '未读取'}
          tone="success"
        />
        <StatusCard
          label="当前家庭"
          value={snapshot?.currentHousehold?.name ?? '尚未选中家庭'}
          tone="info"
        />
        <StatusCard
          label="家庭时区"
          value={snapshot?.currentHousehold?.timezone ?? '尚未读取'}
          tone="warning"
        />
        {loading ? (
          <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '24px' }}>
            正在读取共享设置偏好...
          </Text>
        ) : null}
        {error ? (
          <Text style={{ color: userAppTokens.colorWarning, display: 'block', fontSize: '24px', marginTop: '8px' }}>
            {error}
          </Text>
        ) : null}
        {status ? (
          <Text style={{ color: userAppTokens.colorSuccess, display: 'block', fontSize: '24px', marginTop: '8px' }}>
            {status}
          </Text>
        ) : null}
      </PageSection>

      <PageSection
        title="主题偏好"
        description="先把主题选择落到共享存储。真正的跨端视觉切换后面再接 UI token，不做假动作。"
      >
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {themeOptions.map(option => (
            <Button
              key={option.id}
              disabled={saving}
              onClick={() => void handleThemeChange(option.id)}
              style={{
                background: option.id === themeId ? option.accentColor : option.previewSurface,
                borderRadius: userAppTokens.radiusMd,
                border: `1px solid ${option.accentColor}`,
                color: option.id === themeId ? '#ffffff' : userAppTokens.colorText,
              }}
            >
              {option.label} · {option.description}
            </Button>
          ))}
        </View>
      </PageSection>

      <PageSection
        title="语言偏好"
        description="这里先复用共享 locale 目录和持久化逻辑。家庭级语言写回接口后面再补，不现在乱糊一层。"
      >
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {localeOptions.map(option => (
            <Button
              key={option.id}
              disabled={saving}
              onClick={() => void handleLocaleChange(option.id)}
              style={{
                background: option.id === localeId ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
                borderRadius: userAppTokens.radiusMd,
                border: `1px solid ${userAppTokens.colorBorder}`,
                color: option.id === localeId ? '#ffffff' : userAppTokens.colorText,
              }}
            >
              {formatLocaleOptionLabel(option)} · {getLocaleSourceLabel(option)}
            </Button>
          ))}
        </View>
        <Text
          style={{
            color: userAppTokens.colorMuted,
            display: 'block',
            fontSize: '22px',
            lineHeight: '1.6',
            marginTop: '12px',
          }}
        >
          当前家庭默认语言：{snapshot?.currentHousehold?.locale ?? '未读取'}。现在先保证本地共享偏好可复用，家庭级持久化等 2.1 里的剩余 API client 一起补。
        </Text>
      </PageSection>
    </AppShellPage>
  );
}
