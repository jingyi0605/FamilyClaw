import { useEffect, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { BootstrapSnapshot } from '@familyclaw/user-core';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { countParityItems, userWebParityRegistry } from '@familyclaw/user-testing';
import { AppShellPage } from '../../components/AppShellPage';
import { loadUserAppBootstrap } from '../../runtime';

export default function EntryPage() {
  const [snapshot, setSnapshot] = useState<BootstrapSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const paritySummary = countParityItems(userWebParityRegistry);

  useEffect(() => {
    let cancelled = false;

    void loadUserAppBootstrap()
      .then(result => {
        if (cancelled) {
          return;
        }

        setSnapshot(result);
        setError('');
      })
      .catch(fetchError => {
        if (cancelled) {
          return;
        }

        setError(fetchError instanceof Error ? fetchError.message : '启动信息加载失败');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShellPage>
      <PageSection
        title="spec011 已落地起步"
        description="这里先把统一主线入口、共享层和多端构建入口接起来，再逐步迁业务页面。"
      >
        <StatusCard
          label="当前平台"
          value={snapshot ? `${snapshot.platformTarget.platform} / ${snapshot.platformTarget.runtime}` : '尚未读取'}
          tone="info"
        />
        <StatusCard label="登录状态" value={snapshot?.actor?.authenticated ? '已识别账号态' : '未登录或会话未恢复'} tone="success" />
        <StatusCard label="家庭上下文" value={snapshot?.currentHousehold?.name ?? '尚未选中家庭'} tone="info" />
        <StatusCard label="迁移对齐项" value={`进行中 ${paritySummary.in_progress} / 未开始 ${paritySummary.not_started}`} tone="warning" />
        {loading ? (
          <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px' }}>正在读取共享层启动摘要...</Text>
        ) : null}
        {error ? (
          <Text style={{ color: '#c47900', display: 'block', fontSize: '24px', marginTop: '8px' }}>{error}</Text>
        ) : null}
      </PageSection>

      <PageSection title="阶段 1 已接入的入口" description="先建主线壳，不急着把 user-web 整坨搬过来。">
        <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/login/index' })}>登录入口壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/setup/index' })}>初始化向导壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/home/index' })}>首页壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/family/index' })}>家庭壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/assistant/index' })}>助手壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/memories/index' })}>记忆壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/settings/index' })}>设置壳</Button>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/plugins/index' })}>插件壳</Button>
        </View>
      </PageSection>
    </AppShellPage>
  );
}
