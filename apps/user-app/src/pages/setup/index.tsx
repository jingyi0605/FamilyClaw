import { Text } from '@tarojs/components';
import { AppShellPage } from '../../components/AppShellPage';

export default function SetupPage() {
  return (
    <AppShellPage>
      <Text style={{ display: 'block', fontSize: '24px', lineHeight: '1.8', color: '#5c6b80' }}>
        初始化向导的旧页正式迁移先落在 H5，RN 这里先保留安全占位，避免多端构建被网页表单和浏览器实时连接卡死。
      </Text>
    </AppShellPage>
  );
}
