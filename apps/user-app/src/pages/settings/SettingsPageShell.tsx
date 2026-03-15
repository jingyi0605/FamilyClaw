import type { ReactNode } from 'react';
import { PageHeader } from '../family/base';
import { SettingsNav, type SettingsNavKey } from './SettingsNav';

export function SettingsPageShell(props: {
  activeKey: SettingsNavKey;
  children: ReactNode;
}) {
  return (
    <div className="page page--settings">
      <PageHeader title="设置" />
      <div className="settings-layout">
        <SettingsNav activeKey={props.activeKey} />
        <div className="settings-content">{props.children}</div>
      </div>
    </div>
  );
}
