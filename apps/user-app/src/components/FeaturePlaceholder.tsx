import Taro from '@tarojs/taro';
import { PageSection, StatusCard, UiButton, UiText, userAppFoundationTokens } from '@familyclaw/user-ui';
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
        <UiText tone="secondary">
          {props.blockingReason}
        </UiText>
        <UiButton
          variant="secondary"
          onClick={() => Taro.navigateTo({ url: '/pages/entry/index' })}
          style={{ marginTop: userAppFoundationTokens.spacing.sm }}
        >
          {getPageMessage(locale, 'featurePlaceholder.backToEntry')}
        </UiButton>
      </PageSection>
    </AppShellPage>
  );
}
