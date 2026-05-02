import type { ReactNode } from 'react';
import { PageHeader } from '@familyclaw/user-ui';
import { useH5PageLayoutMode, useI18n } from '../../runtime/h5-shell';
import { SettingsNav, type SettingsNavKey } from './SettingsNav';

export function SettingsPageShell(props: {
  activeKey: SettingsNavKey;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const layoutMode = useH5PageLayoutMode('settings');

  return (
    <div
      className="page page--settings"
      data-layout-mode={layoutMode.id}
      data-layout-touch={layoutMode.isTouchLayout ? 'true' : 'false'}
      data-layout-nav={layoutMode.navVariant}
    >
      <PageHeader
        title={t('settings.title')}
        align="end"
        actionsClassName="page-header__actions--tabs"
        actions={<SettingsNav activeKey={props.activeKey} />}
      />
      <div className="settings-content">{props.children}</div>
    </div>
  );
}
