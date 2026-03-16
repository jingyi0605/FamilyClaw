import { FeaturePlaceholder } from '../../components/FeaturePlaceholder';
import { useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';

export default function FamilyPage() {
  const { locale } = useI18n();

  return (
    <FeaturePlaceholder
      title={getPageMessage(locale, 'family.placeholder.title')}
      description={getPageMessage(locale, 'family.placeholder.description')}
      parityStatus="h5_ready"
      blockingReason={getPageMessage(locale, 'family.placeholder.blockingReason')}
    />
  );
}
