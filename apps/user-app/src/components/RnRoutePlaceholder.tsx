import { useEffect } from 'react';
import Taro from '@tarojs/taro';
import { RnButton, RnCard, RnPageShell, RnText, rnFoundationTokens } from '../runtime/rn-shell';
import { GuardedPage, useI18n } from '../runtime/index.rn';
import { getPageMessage } from '../runtime/h5-shell/i18n/pageMessageUtils';

type RnRoutePlaceholderProps = {
  mode: 'protected' | 'setup';
  path: string;
  title: string;
};

export function RnRoutePlaceholder(props: RnRoutePlaceholderProps) {
  const { locale } = useI18n();

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: props.title }).catch(() => undefined);
  }, [props.title]);

  return (
    <GuardedPage mode={props.mode} path={props.path}>
      <RnPageShell safeAreaBottom scrollable={false}>
        <RnCard>
          <RnText variant="title" style={{ marginBottom: rnFoundationTokens.spacing.sm }}>
            {props.title}
          </RnText>
          <RnText variant="body" tone="secondary" style={{ marginBottom: rnFoundationTokens.spacing.sm }}>
            {getPageMessage(locale, 'rn.placeholder.description')}
          </RnText>
          <RnButton variant="secondary" onPress={() => void Taro.reLaunch({ url: '/pages/entry/index' })}>
            {getPageMessage(locale, 'featurePlaceholder.backToEntry')}
          </RnButton>
        </RnCard>
      </RnPageShell>
    </GuardedPage>
  );
}
