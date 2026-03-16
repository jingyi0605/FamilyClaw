import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';
import { GuardedPage, useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';

export default function AssistantPage() {
  const { locale } = useI18n();

  return (
    <GuardedPage mode="protected" path="/pages/assistant/index">
      <FeaturePlaceholder
        title={getPageMessage(locale, 'assistant.placeholder.title')}
        description={getPageMessage(locale, 'assistant.placeholder.description')}
        parityStatus="h5_ready"
        blockingReason={getPageMessage(locale, 'assistant.placeholder.blockingReason')}
      />
    </GuardedPage>
  );
}
