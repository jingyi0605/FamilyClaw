import { useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import { getLocaleSourceLabel } from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n, useTheme } from '../../runtime/h5-shell';

export default function SettingsPage() {
  const { currentHousehold } = useHouseholdContext();
  const { themeId, themeList, setTheme } = useTheme();
  const { locale, locales, setLocale, formatLocaleLabel } = useI18n();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const currentTheme = themeList.find(item => item.id === themeId) ?? themeList[0];
  const currentLocale = locales.find(item => item.id === locale) ?? locales[0];

  async function handleThemeChange(nextThemeId: typeof themeId) {
    setSaving(true);
    setError('');
    setStatus('');

    try {
      setTheme(nextThemeId);
      setStatus('主题偏好已经写回统一 H5 壳，登录页和业务页现在共用同一套主题状态。');
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
      setLocale(nextLocaleId);
      setStatus('语言偏好已经写回统一 H5 壳，登录页和业务页现在共用同一套语言状态。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '语言偏好保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <GuardedPage mode="protected" path="/pages/settings/index">
      <div className="page">
        <PageSection
          title="统一壳状态"
          description="这里不再自己读一遍 bootstrap，而是直接消费统一 H5 壳里的主题、语言和家庭上下文。"
        >
          <StatusCard label="当前主题" value={currentTheme?.label ?? '未读取'} tone="info" />
          <StatusCard
            label="当前语言"
            value={currentLocale ? formatLocaleLabel(currentLocale) : '未读取'}
            tone="success"
          />
          <StatusCard
            label="当前家庭"
            value={currentHousehold?.name ?? '尚未选中家庭'}
            tone="info"
          />
          <StatusCard
            label="家庭时区"
            value={currentHousehold?.timezone ?? '尚未读取'}
            tone="warning"
          />
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
          title="主题切换"
          description="正式主题系统已经挂到顶层，后续页面不该再各自灌 CSS 变量。"
        >
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {themeList.map(option => (
              <Button
                key={option.id}
                disabled={saving}
                onClick={() => void handleThemeChange(option.id)}
                style={{
                  background: option.id === themeId ? option.brandPrimary : option.bgCard,
                  borderRadius: userAppTokens.radiusMd,
                  border: `1px solid ${option.brandPrimary}`,
                  color: option.id === themeId ? '#ffffff' : userAppTokens.colorText,
                }}
              >
                {option.label} 路 {option.description}
              </Button>
            ))}
          </View>
        </PageSection>

        <PageSection
          title="语言切换"
          description="正式国际化状态已经挂到顶层，并且会随着家庭 locale 列表同步插件语言。"
        >
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {locales.map(option => (
              <Button
                key={option.id}
                disabled={saving}
                onClick={() => void handleLocaleChange(option.id)}
                style={{
                  background: option.id === locale ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
                  borderRadius: userAppTokens.radiusMd,
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  color: option.id === locale ? '#ffffff' : userAppTokens.colorText,
                }}
              >
                {formatLocaleLabel(option)} 路 {getLocaleSourceLabel(option)}
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
            当前家庭默认语言：{currentHousehold?.locale ?? '未读取'}。页面语言偏好和插件 locale 注入现在都由同一个顶层 provider 管。
          </Text>
        </PageSection>
      </div>
    </GuardedPage>
  );
}
