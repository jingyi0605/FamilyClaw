import { PropsWithChildren } from 'react';
import { Text, View } from '@tarojs/components';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import { AppShellPage } from './AppShellPage';
import { useAppRuntime } from '../runtime';

type AuthShellPageProps = PropsWithChildren<{
  title: string;
  description: string;
}>;

export function AuthShellPage({ title, description, children }: AuthShellPageProps) {
  const { bootstrap, error, refreshing } = useAppRuntime();

  return (
    <AppShellPage>
      <View
        style={{
          background: `linear-gradient(160deg, ${userAppTokens.colorPrimary} 0%, #0f9d6c 100%)`,
          borderRadius: userAppTokens.radiusLg,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          padding: userAppTokens.spacingMd,
        }}
      >
        <Text style={{ color: '#ffffff', fontSize: '40px', fontWeight: '700' }}>
          FamilyClaw
        </Text>
        <Text style={{ color: 'rgba(255,255,255,0.88)', fontSize: '26px', lineHeight: '1.6' }}>
          先把认证链路和初始化壳跑通，再继续迁主页面。现在不搞花架子，先让新应用真的能进得去。
        </Text>
      </View>

      <PageSection title={title} description={description}>
        <StatusCard
          label="当前平台"
          value={bootstrap ? `${bootstrap.platformTarget.platform} / ${bootstrap.platformTarget.runtime}` : '加载中'}
          tone="info"
        />
        <StatusCard
          label="账号状态"
          value={bootstrap?.actor?.authenticated ? `已登录：${bootstrap.actor.username}` : '未登录'}
          tone={bootstrap?.actor?.authenticated ? 'success' : 'warning'}
        />
        {refreshing ? <Text style={{ color: userAppTokens.colorMuted, fontSize: '24px' }}>正在刷新启动状态...</Text> : null}
        {error ? <Text style={{ color: userAppTokens.colorWarning, fontSize: '24px' }}>{error}</Text> : null}
      </PageSection>

      {children}
    </AppShellPage>
  );
}
