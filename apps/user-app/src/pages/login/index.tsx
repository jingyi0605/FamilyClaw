import { useState } from 'react';
import { Button, Form, Input, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';
import { GuardedPage, useAuthContext } from '../../runtime';

function NativeLoginPageContent() {
  const { login, loginError, loginPending } = useAuthContext();
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
      <PageSection title="登录" description="使用家庭账号进入 FamilyClaw">
        <Form onSubmit={handleSubmit}>
          <View style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
            <Input
              value={username}
              type="text"
              placeholder="请输入用户名"
              onInput={event => setUsername(event.detail.value)}
              style={{
                background: '#ffffff',
                border: '1px solid #d8dee9',
                borderRadius: '12px',
                padding: '14px 16px',
                fontSize: '16px',
              }}
            />
            <Input
              value={password}
              type="text"
              password
              placeholder="请输入密码"
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
              {loginPending ? '登录中...' : '进入家庭空间'}
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
