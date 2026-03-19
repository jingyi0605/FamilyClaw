import { RnRoutePlaceholder } from '../../components/RnRoutePlaceholder';
import { USER_GUIDE_ANCHOR_IDS, useI18n } from '../../runtime/index.rn';

export default function MemoriesPage() {
  const { t } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/memories/index"
      title={t('nav.memories')}
      guideAnchorId={USER_GUIDE_ANCHOR_IDS.memoriesOverview}
    />
  );
}
