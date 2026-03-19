import { RnRoutePlaceholder } from '../../../components/RnRoutePlaceholder';
import { useI18n } from '../../../runtime/index.rn';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';

export default function SettingsChannelAccessPage() {
  const { locale } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/settings/channel-access/index"
      title={getPageMessage(locale, 'settings.channelAccess.sectionTitle')}
    />
  );
}
