import { useMemo, useState } from 'react';
import {
  getDeviceEnabledBadgeTone,
  getDeviceEnabledState,
  getDeviceRuntimeBadgeTone,
  normalizeDeviceDisplayStatus,
} from '../../device-management/deviceStatusDisplay';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { HouseholdDeviceDetailDialog, type DevicePageLookup } from '../../device-management/HouseholdDeviceDetailDialog';
import { Card } from '../../family/base';
import type {
  IntegrationInstance,
  IntegrationResource,
} from '../settingsTypes';

type PageLookup = (
  key: Parameters<typeof getPageMessage>[1],
  params?: Record<string, string | number>,
) => string;

type Props = {
  currentHouseholdId: string | null;
  page: PageLookup;
  selectedInstance: IntegrationInstance;
  selectedDevices: IntegrationResource[];
  onStatus: (message: string) => void;
  onError: (message: string) => void;
  onReload: (preferredDeviceId?: string | null) => Promise<void>;
};

function getResourceDeviceId(resource: IntegrationResource): string | null {
  if (resource.device_id && resource.device_id.trim()) {
    return resource.device_id;
  }
  if (resource.resource_type === 'device' && resource.id.trim()) {
    return resource.id;
  }
  return null;
}

export function IntegrationDevicePanel({
  currentHouseholdId,
  page,
  selectedInstance,
  selectedDevices,
  onStatus,
  onError,
  onReload,
}: Props) {
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  const selectedDeviceResource = useMemo(
    () => selectedDevices.find((item) => getResourceDeviceId(item) === selectedDeviceId) ?? null,
    [selectedDeviceId, selectedDevices],
  );

  function formatDeviceEnabledStatus(statusValue: string) {
    return getDeviceEnabledState(statusValue) === 'disabled'
      ? page('settings.integrations.deviceEnabled.disabled')
      : page('settings.integrations.deviceEnabled.enabled');
  }

  function formatDeviceRuntimeStatus(statusValue: string) {
    switch (normalizeDeviceDisplayStatus(statusValue)) {
      case 'active':
        return page('settings.integrations.deviceRuntime.active');
      case 'offline':
        return page('settings.integrations.deviceRuntime.offline');
      case 'disabled':
        return page('settings.integrations.deviceRuntime.disabled');
      default:
        return page('settings.integrations.deviceRuntime.inactive');
    }
  }

  function openDeviceDetail(deviceId: string | null) {
    if (!deviceId) {
      return;
    }
    setSelectedDeviceId(deviceId);
    setDetailModalOpen(true);
  }

  function closeDeviceDetail() {
    setDetailModalOpen(false);
  }

  const detailPageLookup: DevicePageLookup = (key, params) => page(key as Parameters<PageLookup>[0], params);

  const selectedDeviceSubtitle = selectedDeviceResource
    ? page('settings.integrations.deviceDetail.summary', {
      room: selectedDeviceResource.room_name || page('settings.integrations.instance.noRoom'),
      plugin: selectedInstance.display_name,
    })
    : '';

  const selectedDeviceName = selectedDeviceResource?.name ?? '';
  const selectedDeviceStatus = (selectedDeviceResource?.status ?? 'inactive') as 'active' | 'offline' | 'inactive' | 'disabled';

  function handleDeleted() {
    setSelectedDeviceId(null);
    setDetailModalOpen(false);
  }

  return (
    <>
      <div className="settings-card-grid">
        {selectedDevices.length === 0 ? (
          <Card>
            <div className="integration-status__detail">{page('settings.integrations.instance.devicesEmpty')}</div>
          </Card>
        ) : selectedDevices.map((device) => {
          const deviceId = getResourceDeviceId(device);
          const isActive = detailModalOpen && deviceId !== null && selectedDeviceId === deviceId;
          return (
            <Card key={`${device.integration_instance_id}:${device.resource_key}`} className={isActive ? 'integration-card integration-card--active' : 'integration-card'}>
              <button
                className="integration-card__main"
                type="button"
                onClick={() => openDeviceDetail(deviceId)}
                disabled={!deviceId}
              >
                <div className="integration-card__header">
                  <div className="device-card__info">
                    <span className="device-card__name">{device.name}</span>
                    <span className="device-card__room">{device.room_name || page('settings.integrations.instance.noRoom')}</span>
                  </div>
                  <span className={`badge badge--${getDeviceEnabledBadgeTone(device.status)}`}>
                    {formatDeviceEnabledStatus(device.status)}
                  </span>
                </div>
                <div className="integration-status__detail">
                  {getDeviceEnabledState(device.status) === 'enabled' ? (
                    <span className={`badge badge--${getDeviceRuntimeBadgeTone(device.status)}`}>
                      {formatDeviceRuntimeStatus(device.status)}
                    </span>
                  ) : null}
                  {getDeviceEnabledState(device.status) === 'enabled' ? ' / ' : ''}
                  {device.category || selectedInstance.plugin_id}
                </div>
              </button>
            </Card>
          );
        })}
      </div>
      <HouseholdDeviceDetailDialog
        open={detailModalOpen && selectedDeviceResource !== null}
        currentHouseholdId={currentHouseholdId}
        deviceId={selectedDeviceId}
        deviceName={selectedDeviceName}
        subtitle={selectedDeviceSubtitle}
        page={detailPageLookup}
        fallbackStatus={selectedDeviceStatus}
        fallbackControllable={false}
        onClose={closeDeviceDetail}
        onStatus={onStatus}
        onError={onError}
        onReload={async () => {
          await onReload(selectedDeviceId);
        }}
        onDeleted={handleDeleted}
      />
    </>
  );
}
