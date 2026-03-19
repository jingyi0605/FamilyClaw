import { RnRoutePlaceholder } from '../../components/RnRoutePlaceholder';
import { USER_GUIDE_ANCHOR_IDS, useI18n } from '../../runtime/index.rn';

export default function FamilyPage() {
  const { t } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/family/index"
      title={t('nav.family')}
      guideAnchorId={USER_GUIDE_ANCHOR_IDS.familyOverview}
    />
  );
}
