import { RnRoutePlaceholder } from '../../components/RnRoutePlaceholder';
import { USER_GUIDE_ANCHOR_IDS, useI18n } from '../../runtime/index.rn';
import { useRnPageLayoutMode } from '../../runtime/rn-shell';

export default function AssistantPage() {
  const { t } = useI18n();
  const layoutMode = useRnPageLayoutMode('assistant');

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/assistant/index"
      title={t('nav.assistant')}
      guideAnchorId={USER_GUIDE_ANCHOR_IDS.assistantOverview}
      description={layoutMode.isTouchLayout ? t('assistant.welcomeHint') : undefined}
    />
  );
}
