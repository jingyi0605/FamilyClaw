import { useEffect, useState } from 'react';
import { Text } from '@tarojs/components';
import { BootstrapSnapshot } from '@familyclaw/user-core';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';
import { loadUserAppBootstrap } from '../../runtime';

export default function HomePage() {
  const [snapshot, setSnapshot] = useState<BootstrapSnapshot | null>(null);

  useEffect(() => {
    void loadUserAppBootstrap().then(setSnapshot).catch(() => {
      setSnapshot(null);
    });
  }, []);

  return (
    <AppShellPage>
      <PageSection title="首页壳" description="首页先接共享启动摘要，暂时不迁 user-web 的业务大卡片。">
        <StatusCard label="当前账号" value={snapshot?.actor?.username ?? '未读取'} tone="info" />
        <StatusCard label="当前家庭" value={snapshot?.currentHousehold?.name ?? '未选定'} tone="success" />
        <StatusCard label="平台能力" value={snapshot ? `${snapshot.platformTarget.supports_share ? '支持' : '暂不支持'}分享` : '未探测'} tone="info" />
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px' }}>
          共享启动数据已经走 `user-core + user-platform`，这就是后面迁页面的落点。
        </Text>
      </PageSection>
    </AppShellPage>
  );
}
