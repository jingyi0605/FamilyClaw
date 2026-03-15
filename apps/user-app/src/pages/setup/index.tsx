import { Text } from '@tarojs/components';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';

export default function SetupPage() {
  return (
    <AppShellPage>
      <PageSection title="初始化向导壳" description="先接共享 setup 状态入口，再迁具体步骤。">
        <StatusCard label="当前状态" value="只建立壳和路由" tone="warning" />
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px' }}>
          真正的向导步骤和提交逻辑还没迁，这里只先把页面边界和入口固定下来。
        </Text>
      </PageSection>
    </AppShellPage>
  );
}
