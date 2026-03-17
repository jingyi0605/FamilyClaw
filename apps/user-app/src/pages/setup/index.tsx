import { Text } from '@tarojs/components';
import { AppShellPage } from '../../components/AppShellPage';
import { GuardedPage } from '../../runtime';

export default function SetupPage() {
  return (
    <GuardedPage mode="setup" path="/pages/setup/index">
      <AppShellPage>
        <Text style={{ display: 'block', fontSize: '24px', lineHeight: '1.8', color: '#5c6b80' }}>
          H5 主线已经迁入统一壳；当前文件只保留给 RN 安全构建使用，不承接网页 DOM 和历史样式。
        </Text>
      </AppShellPage>
    </GuardedPage>
  );
}
