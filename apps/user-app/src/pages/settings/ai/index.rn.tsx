import { RnRoutePlaceholder } from '../../../components/RnRoutePlaceholder';
import { useI18n } from '../../../runtime/index.rn';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';

export default function SettingsAiPage() {
  const { locale } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/settings/ai/index"
      title={getPageMessage(locale, 'settings.ai.title')}
    />
  );
}
