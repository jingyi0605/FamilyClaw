import type { ReactNode } from 'react';
import { PageHeader } from '@familyclaw/user-ui';
import { useI18n } from '../../runtime/h5-shell';
import { SettingsNav, type SettingsNavKey } from './SettingsNav';

export function SettingsPageShell(props: {
  activeKey: SettingsNavKey;
  children: ReactNode;
}) {
  const { t } = useI18n();

  return (
    <div className="page page--settings">
      <PageHeader title={t('settings.title')} />
      <div className="settings-layout">
        <SettingsNav activeKey={props.activeKey} />
        <div className="settings-content">{props.children}</div>
      </div>
    </div>
  );
}
