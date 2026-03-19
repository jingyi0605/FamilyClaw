import { RnRoutePlaceholder } from '../../../components/RnRoutePlaceholder';
import { useI18n } from '../../../runtime/index.rn';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';

export default function SettingsAccountsPage() {
  const { locale } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="protected"
      path="/pages/settings/accounts/index"
      title={getPageMessage(locale, 'settings.accounts.title')}
    />
  );
}
