import { Text } from '@tarojs/components';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { AppShellPage } from '../../components/AppShellPage';

export default function LoginPage() {
  return (
    <AppShellPage>
      <PageSection title="登录壳" description="这里只先立登录页边界，后面再迁表单、错误态和鉴权跳转。">
        <StatusCard label="迁移策略" value="先共用 API client，再替换页面 UI" tone="info" />
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px' }}>
          当前没有把 user-web 的登录页整坨复制过来，先保留壳和共享依赖入口。
        </Text>
      </PageSection>
    </AppShellPage>
  );
}
