import { useI18n } from '../../runtime/index.rn';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { RnRoutePlaceholder } from '../../components/RnRoutePlaceholder';

export default function SetupPage() {
  const { locale } = useI18n();

  return (
    <RnRoutePlaceholder
      mode="setup"
      path="/pages/setup/index"
      title={getPageMessage(locale, 'setup.page.title')}
    />
  );
}
