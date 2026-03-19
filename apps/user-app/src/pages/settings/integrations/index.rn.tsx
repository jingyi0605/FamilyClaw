import { RnRoutePlaceholder } from '../../../components/RnRoutePlaceholder';
import { useI18n } from '../../../runtime/index.rn';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';

export default function SettingsIntegrationsPage() {
  const { locale } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/settings/integrations/index"
      title={getPageMessage(locale, 'settings.integrations.title')}
    />
  );
}
