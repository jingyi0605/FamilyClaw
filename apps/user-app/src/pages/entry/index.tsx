import { useEffect } from 'react';
import { Text } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';
import { resolveBootstrapRoute, useAppRuntime } from '../../runtime';

export default function EntryPage() {
  const { bootstrap, error, loading, refresh } = useAppRuntime();

  useEffect(() => {
    if (loading) {
      return;
    }

    if (error && !bootstrap) {
      return;
    }

    void Taro.reLaunch({ url: resolveBootstrapRoute(bootstrap) });
  }, [bootstrap, error, loading]);

  return (
    <AppShellPage>
      <PageSection
        title="正在进入统一前端主线"
        description="入口页现在只负责一件事：读取共享启动摘要，然后把你送去登录、初始化向导或主壳。"
      >
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px', lineHeight: '1.6' }}>
          {loading
            ? '正在读取共享层启动摘要...'
            : error && !bootstrap
              ? '启动摘要读取失败，请先重试。'
              : '启动摘要已读取，正在跳转。'}
        </Text>
        {error ? <Text style={{ color: '#c47900', display: 'block', fontSize: '24px', marginTop: '8px' }}>{error}</Text> : null}
        {!loading ? (
          <Text
            onClick={() => void refresh()}
            style={{ color: '#1d6fd6', display: 'block', fontSize: '24px', marginTop: '8px' }}
          >
            重新读取启动状态
          </Text>
        ) : null}
      </PageSection>
    </AppShellPage>
  );
}
