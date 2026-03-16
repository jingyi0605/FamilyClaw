import { useState } from 'react';
import { Button, Form, Input, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection } from '@familyclaw/user-ui';
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
          <View style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
            <Text style={{ color: '#1f2937', fontSize: '14px', fontWeight: '600' }}>
              {t('login.username')}
            </Text>
            <Input
              value={username}
              type="text"
              placeholder={t('login.usernamePlaceholder')}
              onInput={event => setUsername(event.detail.value)}
              style={{
                background: '#ffffff',
                border: '1px solid #d8dee9',
                borderRadius: '12px',
                padding: '14px 16px',
                fontSize: '16px',
              }}
            />
            <Text style={{ color: '#1f2937', fontSize: '14px', fontWeight: '600' }}>
              {t('login.password')}
            </Text>
            <Input
              value={password}
              type="text"
              password
              placeholder={t('login.passwordPlaceholder')}
              onInput={event => setPassword(event.detail.value)}
              style={{
                background: '#ffffff',
                border: '1px solid #d8dee9',
                borderRadius: '12px',
                padding: '14px 16px',
                fontSize: '16px',
              }}
            />
            {loginError ? (
              <Text style={{ color: '#c2410c', display: 'block', fontSize: '24px' }}>
                {loginError}
              </Text>
            ) : null}
            <Button formType="submit" loading={loginPending} disabled={loginPending || !username.trim() || !password}>
              {loginPending ? t('login.loggingIn') : t('login.submit')}
            </Button>
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
