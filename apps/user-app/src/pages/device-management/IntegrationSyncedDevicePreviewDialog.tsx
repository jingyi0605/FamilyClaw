import { Card } from '../family/base';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type { IntegrationResource } from '../settings/settingsTypes';

type PageLookup = (
  key: Parameters<typeof getPageMessage>[1],
  params?: Record<string, string | number>,
) => string;

type Props = {
  open: boolean;
  instanceName: string;
  devices: IntegrationResource[];
  page: PageLookup;
  onClose: () => void;
};

function getDeviceStatusBadge(status: string): 'success' | 'warning' | 'inactive' | 'danger' | 'secondary' {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'offline') {
    return 'warning';
  }
  if (status === 'disabled') {
    return 'danger';
  }
  if (status === 'inactive') {
    return 'inactive';
  }
  return 'secondary';
}

function formatDeviceStatus(statusValue: string, page: PageLookup) {
  if (statusValue === 'active') {
    return page('settings.integrations.deviceStatus.active');
  }
  if (statusValue === 'offline') {
    return page('settings.integrations.deviceStatus.offline');
  }
  if (statusValue === 'disabled') {
    return page('settings.integrations.deviceStatus.disabled');
  }
  return page('settings.integrations.deviceStatus.inactive');
}

export function IntegrationSyncedDevicePreviewDialog({
  open,
  instanceName,
  devices,
  page,
  onClose,
}: Props) {
  if (!open) {
    return null;
  }

  return (
    <div className="member-modal-overlay" onClick={onClose}>
      <div className="member-modal integration-device-preview-modal" onClick={(event) => event.stopPropagation()}>
        <div className="member-modal__header">
          <div>
            <h3>{page('settings.integrations.preview.title', { name: instanceName })}</h3>
            <p>{page('settings.integrations.preview.desc')}</p>
          </div>
        </div>

        <Card>
          <div className="integration-status__detail">{page('settings.integrations.preview.readOnlyHint')}</div>
          <div className="integration-status__detail">{page('settings.integrations.preview.manageHint')}</div>
        </Card>

        <div className="settings-card-grid">
          {devices.length === 0 ? (
            <Card>
              <div className="settings-empty-state">
                <h3>{page('settings.integrations.preview.emptyTitle')}</h3>
                <p>{page('settings.integrations.preview.emptyDesc')}</p>
              </div>
            </Card>
          ) : devices.map((device) => (
            <Card key={`${device.integration_instance_id}:${device.resource_key}`} className="integration-card">
              <div className="integration-card__header">
                <div className="device-card__info">
                  <span className="device-card__name">{device.name}</span>
                  <span className="device-card__room">{device.room_name || page('settings.integrations.instance.noRoom')}</span>
                </div>
                <span className={`badge badge--${getDeviceStatusBadge(device.status)}`}>
                  {formatDeviceStatus(device.status, page)}
                </span>
              </div>
              <div className="integration-status__detail">{device.category || device.plugin_id}</div>
            </Card>
          ))}
        </div>

        <div className="member-modal__actions">
          <button className="btn btn--outline btn--sm" type="button" onClick={onClose}>
            {page('settings.integrations.action.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
