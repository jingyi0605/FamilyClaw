import { Button, Text, View } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { PageSection, StatusCard } from '@familyclaw/user-ui';
import { AppShellPage } from './AppShellPage';
import { useI18n } from '../runtime';
import { getPageMessage } from '../runtime/h5-shell/i18n/pageMessageUtils';

type FeaturePlaceholderProps = {
  title: string;
  description: string;
  parityStatus: string;
  blockingReason: string;
};

export function FeaturePlaceholder(props: FeaturePlaceholderProps) {
  const { locale } = useI18n();

  return (
    <AppShellPage>
      <PageSection title={props.title} description={props.description}>
        <StatusCard label={getPageMessage(locale, 'featurePlaceholder.migrationStatusLabel')} value={props.parityStatus} tone="warning" />
        <Text style={{ color: '#5c6b80', display: 'block', fontSize: '24px', lineHeight: '1.6' }}>
          {props.blockingReason}
        </Text>
        <View style={{ marginTop: '16px' }}>
          <Button onClick={() => Taro.navigateTo({ url: '/pages/entry/index' })}>{getPageMessage(locale, 'featurePlaceholder.backToEntry')}</Button>
        </View>
      </PageSection>
    </AppShellPage>
  );
}
