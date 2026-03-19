import { RnRoutePlaceholder } from '../../components/RnRoutePlaceholder';
import { USER_GUIDE_ANCHOR_IDS, useI18n } from '../../runtime/index.rn';

export default function AssistantPage() {
  const { t } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/assistant/index"
      title={t('nav.assistant')}
      guideAnchorId={USER_GUIDE_ANCHOR_IDS.assistantOverview}
    />
  );
}
