import { PropsWithChildren, useEffect } from 'react';
import { ScrollView, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection, StatusCard, UiButton, UiCard, UiText, userAppFoundationTokens } from '@familyclaw/user-ui';
import {
  APP_ROUTES,
  useAppRuntime,
  hasDeferredSetupWork,
  MAIN_NAV_ITEMS,
  MainNavKey,
  needsBlockingSetup,
  useI18n,
} from '../runtime';
import { AppShellPage } from './AppShellPage';

type MainShellPageProps = PropsWithChildren<{
  currentNav: MainNavKey;
  title: string;
  description: string;
}>;

export function MainShellPage({ currentNav, title, description, children }: MainShellPageProps) {
  const { bootstrap, error, loading, refreshing, refresh, logout, switchHousehold } = useAppRuntime();
  const { t } = useI18n();

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
          <UiText variant="body" tone={error && !bootstrap ? 'warning' : 'secondary'}>
            {error && !bootstrap ? error : '正在检查访问条件...'}
          </UiText>
          {error && !bootstrap ? (
            <UiButton size="sm" variant="secondary" onClick={() => void refresh()} style={{ marginTop: userAppFoundationTokens.spacing.sm }}>
              重新读取启动摘要
            </UiButton>
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
        {error ? <UiText variant="body" tone="warning">{error}</UiText> : null}
        {refreshing ? <UiText variant="body" tone="secondary">正在刷新数据...</UiText> : null}
        <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: userAppFoundationTokens.spacing.sm }}>
          <UiButton size="sm" variant="secondary" onClick={() => void refresh()}>
            刷新启动摘要
          </UiButton>
          <UiButton
            size="sm"
            variant="warning"
            onClick={() => void logout().then(() => Taro.reLaunch({ url: '/pages/login/index' }))}
          >
            退出登录
          </UiButton>
        </View>
      </PageSection>

      {bootstrap?.households?.length ? (
        <PageSection title="家庭切换" description="家庭上下文已经抽到共享层，这里直接消费，不再重写一套浏览器状态。">
          <ScrollView scrollX>
            <View style={{ display: 'flex', flexDirection: 'row', gap: userAppFoundationTokens.spacing.sm }}>
              {bootstrap.households.map(household => {
                const active = household.id === bootstrap.currentHousehold?.id;
                return (
                  <UiButton
                    key={household.id}
                    size="sm"
                    variant={active ? 'primary' : 'secondary'}
                    onClick={() => void switchHousehold(household.id)}
                  >
                    {household.name}
                  </UiButton>
                );
              })}
            </View>
          </ScrollView>
        </PageSection>
      ) : null}

      <PageSection title="主导航壳" description="这里就是阶段 3.1 的主壳。以后高频页面都挂在这层，不再各跑各的。">
        <ScrollView scrollX>
          <View style={{ display: 'flex', flexDirection: 'row', gap: userAppFoundationTokens.spacing.sm }}>
            {MAIN_NAV_ITEMS.map(item => {
              const active = item.key === currentNav;
              return (
                <UiButton
                  key={item.key}
                  size="sm"
                  variant={active ? 'primary' : 'secondary'}
                  onClick={() => void handleNavigate(item.url)}
                >
                  {item.label}
                </UiButton>
              );
            })}
          </View>
        </ScrollView>
      </PageSection>

      {hasDeferredSetupWork(bootstrap?.setupStatus ?? null) ? (
        <UiCard variant="warning">
          <UiText variant="label" tone="warning">
            初始化还有后续步骤
          </UiText>
          <UiText variant="body" style={{ marginTop: userAppFoundationTokens.spacing.xs }}>
            当前高频页面已经允许进入，但 AI 配置和首位管家创建还没迁到共享主线。这个不再阻塞 3.2，高频链路先走通。
          </UiText>
        </UiCard>
      ) : null}

      {children}
    </AppShellPage>
  );
}
