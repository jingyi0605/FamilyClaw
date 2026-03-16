import { useState } from 'react';
import { Form, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { FormField, PageSection, UiButton, UiInput, UiText, userAppFoundationTokens } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';
import { GuardedPage, useAuthContext, useI18n } from '../../runtime';

function NativeLoginPageContent() {
  const { login, loginError, loginPending } = useAuthContext();
  const { t } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(event: { preventDefault?: () => void }) {
    event.preventDefault?.();

    try {
      await login(username.trim(), password);
      await Taro.reLaunch({ url: '/pages/entry/index' });
    } catch {
      return;
    }
  }

  return (
    <AppShellPage>
      <PageSection title={t('login.title')} description={t('login.formSubtitle')}>
        <Form onSubmit={handleSubmit}>
          <View style={{ display: 'flex', flexDirection: 'column', gap: userAppFoundationTokens.spacing.md }}>
            <FormField label={t('login.username')}>
              <UiInput
                value={username}
                placeholder={t('login.usernamePlaceholder')}
                onInput={setUsername}
              />
            </FormField>
            <FormField label={t('login.password')}>
              <UiInput
                value={password}
                password
                placeholder={t('login.passwordPlaceholder')}
                onInput={setPassword}
              />
            </FormField>
            {loginError ? (
              <UiText tone="warning">
                {loginError}
              </UiText>
            ) : null}
            <UiButton formType="submit" loading={loginPending} disabled={loginPending || !username.trim() || !password}>
              {loginPending ? t('login.loggingIn') : t('login.submit')}
            </UiButton>
          </View>
        </Form>
      </PageSection>
    </AppShellPage>
  );
}

export default function LoginPage() {
  return (
    <GuardedPage mode="login" path="/pages/login/index">
      <NativeLoginPageContent />
    </GuardedPage>
  );
}
