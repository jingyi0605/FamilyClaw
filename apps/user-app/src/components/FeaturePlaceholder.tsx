import { Button, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { AppShellPage } from './AppShellPage';

type FeaturePlaceholderProps = {
  title: string;
  description: string;
  parityStatus: string;
  blockingReason: string;
};

export function FeaturePlaceholder(props: FeaturePlaceholderProps) {
  return (
    <AppShellPage>
      <PageSection title={props.title} description={props.description}>
        <StatusCard label="当前迁移状态" value={props.parityStatus} tone="warning" />
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px', lineHeight: '1.6' }}>
          {props.blockingReason}
        </Text>
        <View style={{ marginTop: '16px' }}>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/entry/index' })}>返回迁移主线入口</Button>
        </View>
      </PageSection>
    </AppShellPage>
  );
}
