import { PropsWithChildren, useEffect } from 'react';
import { Button, ScrollView, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  APP_ROUTES,
  useAppRuntime,
  hasDeferredSetupWork,
  MAIN_NAV_ITEMS,
  MainNavKey,
  needsBlockingSetup,
} from '../runtime';
import { AppShellPage } from './AppShellPage';

type MainShellPageProps = PropsWithChildren<{
  currentNav: MainNavKey;
  title: string;
  description: string;
}>;

export function MainShellPage({ currentNav, title, description, children }: MainShellPageProps) {
  const { bootstrap, error, loading, refreshing, refresh, logout, switchHousehold } = useAppRuntime();

  useEffect(() => {
    if (loading) {
      return;
    }

    if (error && !bootstrap) {
      return;
    }

    if (!bootstrap?.actor?.authenticated) {
      void Taro.reLaunch({ url: APP_ROUTES.login });
      return;
    }

    if (needsBlockingSetup(bootstrap.setupStatus) || !bootstrap.currentHousehold) {
      void Taro.reLaunch({ url: APP_ROUTES.setup });
    }
  }, [bootstrap, error, loading]);

  if (loading || (error && !bootstrap) || !bootstrap?.actor?.authenticated || needsBlockingSetup(bootstrap?.setupStatus ?? null) || !bootstrap.currentHousehold) {
    return (
      <AppShellPage>
        <PageSection title="正在进入主导航壳" description="先校验账号态和 setup 状态，再渲染受保护页面。">
          <Text style={{ color: error && !bootstrap ? userAppTokens.colorWarning : userAppTokens.colorMuted, fontSize: '24px' }}>
            {error && !bootstrap ? error : '正在检查访问条件...'}
          </Text>
          {error && !bootstrap ? (
            <Button
              size="mini"
              onClick={() => void refresh()}
              style={{
                background: userAppTokens.colorSurface,
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusMd,
                color: userAppTokens.colorText,
                marginTop: '12px',
              }}
            >
              重新读取启动摘要
            </Button>
          ) : null}
        </PageSection>
      </AppShellPage>
    );
  }

  async function handleNavigate(url: string) {
    await Taro.reLaunch({ url });
  }

  return (
    <AppShellPage>
      <PageSection title={title} description={description}>
        <StatusCard label="当前账号" value={bootstrap?.actor?.username ?? '未登录'} tone="info" />
        <StatusCard label="当前家庭" value={bootstrap?.currentHousehold?.name ?? '尚未选定'} tone="success" />
        <StatusCard
          label="初始化状态"
          value={hasDeferredSetupWork(bootstrap?.setupStatus ?? null) ? 'AI 配置与管家步骤待补' : '已满足高频链路进入条件'}
          tone={hasDeferredSetupWork(bootstrap?.setupStatus ?? null) ? 'warning' : 'success'}
        />
        <StatusCard
          label="平台能力"
          value={bootstrap ? `${bootstrap.platformTarget.supports_share ? '支持' : '不支持'} 分享 / ${bootstrap.platformTarget.supports_deeplink ? '支持' : '不支持'} 深链` : '加载中'}
          tone="info"
        />
        {error ? <Text style={{ color: userAppTokens.colorWarning, fontSize: '24px' }}>{error}</Text> : null}
        {refreshing ? <Text style={{ color: userAppTokens.colorMuted, fontSize: '24px' }}>正在刷新数据...</Text> : null}
        <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '12px' }}>
          <Button
            size="mini"
            onClick={() => void refresh()}
            style={{
              background: userAppTokens.colorSurface,
              border: `1px solid ${userAppTokens.colorBorder}`,
              borderRadius: userAppTokens.radiusMd,
              color: userAppTokens.colorText,
            }}
          >
            刷新启动摘要
          </Button>
          <Button
            size="mini"
            onClick={() => void logout().then(() => Taro.reLaunch({ url: '/pages/login/index' }))}
            style={{
              background: '#fff5f2',
              border: `1px solid ${userAppTokens.colorWarning}`,
              borderRadius: userAppTokens.radiusMd,
              color: userAppTokens.colorWarning,
            }}
          >
            退出登录
          </Button>
        </View>
      </PageSection>

      {bootstrap?.households?.length ? (
        <PageSection title="家庭切换" description="家庭上下文已经抽到共享层，这里直接消费，不再重写一套浏览器状态。">
          <ScrollView scrollX>
            <View style={{ display: 'flex', flexDirection: 'row', gap: '12px' }}>
              {bootstrap.households.map(household => {
                const active = household.id === bootstrap.currentHousehold?.id;
                return (
                  <Button
                    key={household.id}
                    size="mini"
                    onClick={() => void switchHousehold(household.id)}
                    style={{
                      background: active ? userAppTokens.colorPrimary : userAppTokens.colorSurface,
                      border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusMd,
                      color: active ? '#ffffff' : userAppTokens.colorText,
                      minWidth: '140px',
                    }}
                  >
                    {household.name}
                  </Button>
                );
              })}
            </View>
          </ScrollView>
        </PageSection>
      ) : null}

      <PageSection title="主导航壳" description="这里就是阶段 3.1 的主壳。以后高频页面都挂在这层，不再各跑各的。">
        <ScrollView scrollX>
          <View style={{ display: 'flex', flexDirection: 'row', gap: '12px' }}>
            {MAIN_NAV_ITEMS.map(item => {
              const active = item.key === currentNav;
              return (
                <Button
                  key={item.key}
                  size="mini"
                  onClick={() => void handleNavigate(item.url)}
                  style={{
                    background: active ? userAppTokens.colorPrimary : '#f9fbff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusMd,
                    color: active ? '#ffffff' : userAppTokens.colorText,
                    minWidth: '120px',
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </View>
        </ScrollView>
      </PageSection>

      {hasDeferredSetupWork(bootstrap?.setupStatus ?? null) ? (
        <View
          style={{
            background: '#fff8ec',
            border: `1px solid ${userAppTokens.colorWarning}`,
            borderRadius: userAppTokens.radiusLg,
            padding: userAppTokens.spacingMd,
          }}
        >
          <Text style={{ color: userAppTokens.colorWarning, display: 'block', fontSize: '28px', fontWeight: '600' }}>
            初始化还有后续步骤
          </Text>
          <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', lineHeight: '1.6', marginTop: '8px' }}>
            当前高频页面已经允许进入，但 AI 配置和首位管家创建还没迁到共享主线。这个不再阻塞 3.2，高频链路先走通。
          </Text>
        </View>
      ) : null}

      {children}
    </AppShellPage>
  );
}
