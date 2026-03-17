import { useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card } from '../../family/base';
import { settingsApi } from '../settingsApi';
import type {
  DeviceActionExecuteRequest,
  DeviceActionLogListRead,
  DeviceEntity,
  DeviceEntityControl,
  DeviceEntityListRead,
  IntegrationInstance,
  IntegrationResource,
} from '../settingsTypes';

type EntityView = 'favorites' | 'all';

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

const DEVICE_LOG_PAGE_SIZE = 20;

function getResourceDeviceId(resource: IntegrationResource): string | null {
  if (resource.device_id && resource.device_id.trim()) {
    return resource.device_id;
  }
  if (resource.resource_type === 'device' && resource.id.trim()) {
    return resource.id;
  }
  return null;
}

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

function getLogResultBadge(result: string): 'success' | 'danger' | 'warning' | 'secondary' {
  if (result === 'success') {
    return 'success';
  }
  if (result === 'failed' || result === 'error') {
    return 'danger';
  }
  if (result === 'blocked') {
    return 'warning';
  }
  return 'secondary';
}

function isControlOn(control: DeviceEntityControl): boolean {
  return control.value === true || control.value === 'on' || control.value === 'open' || control.value === 'unlocked';
}

function getRangeDraftValue(control: DeviceEntityControl, draft: number | undefined): number {
  if (typeof draft === 'number' && Number.isFinite(draft)) {
    return draft;
  }
  if (typeof control.value === 'number' && Number.isFinite(control.value)) {
    return control.value;
  }
  return control.min_value ?? 0;
}

function buildRangeActionParams(action: string, value: number): Record<string, unknown> {
  if (action === 'set_volume') {
    return { volume_pct: value };
  }
  if (action === 'set_temperature') {
    return { temperature_c: value };
  }
  if (action === 'set_brightness') {
    return { brightness_pct: value };
  }
  return { value };
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
  const [entityView, setEntityView] = useState<EntityView>('favorites');
  const [entityResponse, setEntityResponse] = useState<DeviceEntityListRead | null>(null);
  const [deviceLogs, setDeviceLogs] = useState<DeviceActionLogListRead | null>(null);
  const [rangeDrafts, setRangeDrafts] = useState<Record<string, number>>({});
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState<Record<string, boolean>>({});
  const [logsModalOpen, setLogsModalOpen] = useState(false);

  const selectedDeviceResource = useMemo(
    () => selectedDevices.find((item) => getResourceDeviceId(item) === selectedDeviceId) ?? null,
    [selectedDeviceId, selectedDevices],
  );

  const selectedDevice = entityResponse?.device ?? null;
  const selectedEntities = entityResponse?.items ?? [];
  const selectedDeviceStatus = selectedDevice?.status ?? selectedDeviceResource?.status ?? 'inactive';
  const selectedDeviceDisabled = selectedDeviceStatus === 'disabled';

  useEffect(() => {
    if (!selectedDeviceId) {
      return;
    }
    if (selectedDevices.some((item) => getResourceDeviceId(item) === selectedDeviceId)) {
      return;
    }
    setSelectedDeviceId(null);
    setDetailModalOpen(false);
    setLogsModalOpen(false);
    setEntityResponse(null);
  }, [selectedDeviceId, selectedDevices]);

  useEffect(() => {
    if (!selectedDeviceId || !detailModalOpen) {
      setEntityResponse(null);
      return;
    }
    void loadDeviceEntities(selectedDeviceId, entityView);
  }, [detailModalOpen, selectedDeviceId, entityView]);

  async function loadDeviceEntities(deviceId: string, view: EntityView) {
    setEntitiesLoading(true);
    try {
      const response = await settingsApi.listDeviceEntities(deviceId, view);
      setEntityResponse(response);
      setRangeDrafts((current) => {
        const next = { ...current };
        for (const entity of response.items) {
          if (entity.control.kind !== 'range') {
            continue;
          }
          next[entity.entity_id] = getRangeDraftValue(entity.control, current[entity.entity_id]);
        }
        return next;
      });
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.loadDeviceEntitiesFailed'));
    } finally {
      setEntitiesLoading(false);
    }
  }

  async function loadDeviceLogs(deviceId: string) {
    setLogsLoading(true);
    try {
      const response = await settingsApi.listDeviceActionLogs(deviceId, {
        page: 1,
        page_size: DEVICE_LOG_PAGE_SIZE,
      });
      setDeviceLogs(response);
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.loadDeviceLogsFailed'));
    } finally {
      setLogsLoading(false);
    }
  }

  function formatDeviceStatus(statusValue: string) {
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

  function formatLogResult(resultValue: string) {
    if (resultValue === 'success') {
      return page('settings.integrations.deviceLogs.result.success');
    }
    if (resultValue === 'failed' || resultValue === 'error') {
      return page('settings.integrations.deviceLogs.result.failed');
    }
    if (resultValue === 'blocked') {
      return page('settings.integrations.deviceLogs.result.blocked');
    }
    return resultValue;
  }

  async function refreshCurrentDevice() {
    if (!selectedDeviceId) {
      return;
    }
    await loadDeviceEntities(selectedDeviceId, entityView);
    if (logsModalOpen) {
      await loadDeviceLogs(selectedDeviceId);
    }
    await onReload(selectedDeviceId);
  }

  async function handleFavoriteToggle(entity: DeviceEntity) {
    if (!selectedDeviceId) {
      return;
    }
    setActionSubmitting((current) => ({ ...current, [`favorite:${entity.entity_id}`]: true }));
    try {
      const response = await settingsApi.updateDeviceEntityFavorite(selectedDeviceId, entity.entity_id, !entity.favorite);
      setEntityResponse(response);
      onStatus(entity.favorite
        ? page('settings.integrations.status.favoriteRemoved', { name: entity.name })
        : page('settings.integrations.status.favoriteAdded', { name: entity.name }));
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.updateFavoriteFailed'));
    } finally {
      setActionSubmitting((current) => ({ ...current, [`favorite:${entity.entity_id}`]: false }));
    }
  }

  async function handleExecuteEntityAction(entity: DeviceEntity, action: string, params: Record<string, unknown>) {
    if (!currentHouseholdId || !selectedDeviceId) {
      return;
    }
    const payload: DeviceActionExecuteRequest = {
      household_id: currentHouseholdId,
      device_id: selectedDeviceId,
      entity_id: entity.entity_id,
      action,
      params,
      reason: 'settings_device_page',
    };
    setActionSubmitting((current) => ({ ...current, [`control:${entity.entity_id}:${action}`]: true }));
    try {
      await settingsApi.executeDeviceAction(payload);
      onStatus(page('settings.integrations.status.deviceActionExecuted', { name: entity.name }));
      await refreshCurrentDevice();
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.deviceControlFailed'));
      if (logsModalOpen) {
        await loadDeviceLogs(selectedDeviceId);
      }
    } finally {
      setActionSubmitting((current) => ({ ...current, [`control:${entity.entity_id}:${action}`]: false }));
    }
  }

  async function handleDisableDevice() {
    if (!selectedDeviceId || !selectedDevice) {
      return;
    }
    const confirmResult = await Taro.showModal({
      title: page('settings.integrations.deviceDetail.disableTitle'),
      content: page('settings.integrations.deviceDetail.disableConfirm', { name: selectedDevice.name }),
      confirmText: page('settings.integrations.action.disableDevice'),
      cancelText: page('settings.integrations.action.cancel'),
    });
    if (!confirmResult.confirm) {
      return;
    }
    setSubmitting(true);
    try {
      await settingsApi.disableDevice(selectedDeviceId);
      onStatus(page('settings.integrations.status.deviceDisabled', { name: selectedDevice.name }));
      await refreshCurrentDevice();
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.disableDeviceFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteDevice() {
    if (!selectedDeviceId || !selectedDevice) {
      return;
    }
    const confirmResult = await Taro.showModal({
      title: page('settings.integrations.deviceDetail.deleteTitle'),
      content: page('settings.integrations.deviceDetail.deleteConfirm', { name: selectedDevice.name }),
      confirmText: page('settings.integrations.action.deleteDevice'),
      cancelText: page('settings.integrations.action.cancel'),
      confirmColor: '#d14343',
    });
    if (!confirmResult.confirm) {
      return;
    }
    setSubmitting(true);
    try {
      await settingsApi.deleteDevice(selectedDeviceId);
      onStatus(page('settings.integrations.status.deviceDeleted', { name: selectedDevice.name }));
      setDetailModalOpen(false);
      setLogsModalOpen(false);
      setDeviceLogs(null);
      setEntityResponse(null);
      setSelectedDeviceId(null);
      await onReload();
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.deleteDeviceFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function openLogsModal() {
    if (!selectedDeviceId) {
      return;
    }
    setLogsModalOpen(true);
    await loadDeviceLogs(selectedDeviceId);
  }

  function openDeviceDetail(deviceId: string | null) {
    if (!deviceId) {
      return;
    }
    setSelectedDeviceId(deviceId);
    setEntityView('favorites');
    setLogsModalOpen(false);
    setDetailModalOpen(true);
  }

  function closeDeviceDetail() {
    setDetailModalOpen(false);
    setLogsModalOpen(false);
  }

  function renderEntityControls(entity: DeviceEntity) {
    const actionDisabled = selectedDeviceDisabled || entity.read_only || entity.control.disabled;
    if (entity.read_only || entity.control.kind === 'none') {
      return (
        <div className="integration-entity__readonly">
          {selectedDeviceDisabled
            ? page('settings.integrations.deviceDetail.deviceDisabledHint')
            : page('settings.integrations.deviceDetail.readOnlyHint')}
        </div>
      );
    }

    if (entity.control.kind === 'toggle') {
      const nextAction = isControlOn(entity.control) ? entity.control.action_off : entity.control.action_on;
      return (
        <div className="integration-entity__controls">
          <button
            className="btn btn--outline btn--sm"
            type="button"
            disabled={actionDisabled || !nextAction || actionSubmitting[`control:${entity.entity_id}:${nextAction ?? 'toggle'}`]}
            onClick={() => nextAction ? void handleExecuteEntityAction(entity, nextAction, {}) : undefined}
          >
            {isControlOn(entity.control)
              ? page('settings.integrations.action.turnOff')
              : page('settings.integrations.action.turnOn')}
          </button>
        </div>
      );
    }

    if (entity.control.kind === 'range' && entity.control.action) {
      const draftValue = getRangeDraftValue(entity.control, rangeDrafts[entity.entity_id]);
      return (
        <div className="integration-entity__controls integration-entity__controls--range">
          <div className="integration-entity__range-value">
            {page('settings.integrations.deviceDetail.currentValue', { value: draftValue })}
            {entity.control.unit ? ` ${entity.control.unit}` : ''}
          </div>
          <input
            className="integration-entity__range"
            type="range"
            min={entity.control.min_value ?? 0}
            max={entity.control.max_value ?? 100}
            step={entity.control.step ?? 1}
            value={draftValue}
            disabled={actionDisabled}
            onChange={(event) => setRangeDrafts((current) => ({
              ...current,
              [entity.entity_id]: Number(event.currentTarget.value),
            }))}
          />
          <button
            className="btn btn--outline btn--sm"
            type="button"
            disabled={actionDisabled || actionSubmitting[`control:${entity.entity_id}:${entity.control.action}`]}
            onClick={() => void handleExecuteEntityAction(
              entity,
              entity.control.action!,
              buildRangeActionParams(entity.control.action!, draftValue),
            )}
          >
            {page('settings.integrations.action.apply')}
          </button>
        </div>
      );
    }

    return (
      <div className="integration-entity__controls integration-entity__controls--actions">
        {entity.control.options.map((option) => (
          <button
            key={`${entity.entity_id}:${option.action}:${option.value}`}
            className="btn btn--outline btn--sm"
            type="button"
            disabled={actionDisabled || actionSubmitting[`control:${entity.entity_id}:${option.action}`]}
            onClick={() => void handleExecuteEntityAction(entity, option.action, option.params)}
          >
            {option.label}
          </button>
        ))}
      </div>
    );
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
                  <span className={`badge badge--${getDeviceStatusBadge(device.status)}`}>
                    {formatDeviceStatus(device.status)}
                  </span>
                </div>
                <div className="integration-status__detail">{device.category || selectedInstance.plugin_id}</div>
              </button>
            </Card>
          );
        })}
      </div>
      {detailModalOpen && selectedDeviceResource ? (
        <div className="member-modal-overlay" onClick={closeDeviceDetail}>
          <div className="member-modal integration-device-detail-modal" onClick={(event) => event.stopPropagation()}>
            <div className="integration-device-detail">
              <div className="member-modal__header integration-device-detail-modal__header">
                <div>
                  <h3>{selectedDevice?.name || selectedDeviceResource.name}</h3>
                  <p>
                    {page('settings.integrations.deviceDetail.summary', {
                      room: selectedDeviceResource.room_name || page('settings.integrations.instance.noRoom'),
                      plugin: selectedInstance.display_name,
                    })}
                  </p>
                </div>
                <button className="btn btn--outline btn--sm" type="button" onClick={closeDeviceDetail}>
                  {page('settings.integrations.action.close')}
                </button>
              </div>

              <div className="integration-device-detail__header">
                <div>
                  <div className="integration-device-detail__title-row">
                    <span className={`badge badge--${getDeviceStatusBadge(selectedDeviceStatus)}`}>
                      {formatDeviceStatus(selectedDeviceStatus)}
                    </span>
                    <span className={`badge badge--${selectedDeviceDisabled ? 'danger' : (selectedDevice?.controllable ? 'success' : 'secondary')}`}>
                      {selectedDevice?.controllable
                        ? page('settings.integrations.deviceDetail.controllable')
                        : page('settings.integrations.deviceDetail.readOnly')}
                    </span>
                  </div>
                </div>
                <div className="device-card__actions">
                  <button className="btn btn--outline btn--sm" type="button" onClick={() => void openLogsModal()}>
                    {page('settings.integrations.action.viewLogs')}
                  </button>
                  <button
                    className="btn btn--outline btn--sm"
                    type="button"
                    onClick={() => void handleDisableDevice()}
                    disabled={submitting || selectedDeviceDisabled}
                  >
                    {page('settings.integrations.action.disableDevice')}
                  </button>
                  <button
                    className="btn btn--outline btn--sm btn--danger"
                    type="button"
                    onClick={() => void handleDeleteDevice()}
                    disabled={submitting}
                  >
                    {page('settings.integrations.action.deleteDevice')}
                  </button>
                </div>
              </div>

              {selectedDeviceDisabled ? (
                <div className="integration-device-detail__notice">
                  {page('settings.integrations.deviceDetail.deviceDisabledHint')}
                </div>
              ) : null}

              <div className="integration-device-detail__tabs">
                <button
                  className={entityView === 'favorites' ? 'integration-device-detail__tab integration-device-detail__tab--active' : 'integration-device-detail__tab'}
                  type="button"
                  onClick={() => setEntityView('favorites')}
                >
                  {page('settings.integrations.deviceDetail.tabs.favorites')}
                </button>
                <button
                  className={entityView === 'all' ? 'integration-device-detail__tab integration-device-detail__tab--active' : 'integration-device-detail__tab'}
                  type="button"
                  onClick={() => setEntityView('all')}
                >
                  {page('settings.integrations.deviceDetail.tabs.all')}
                </button>
              </div>

              {entitiesLoading ? (
                <Card>
                  <div className="integration-status__detail">{page('settings.integrations.deviceDetail.loadingEntities')}</div>
                </Card>
              ) : selectedEntities.length === 0 && entityView === 'favorites' ? (
                <Card>
                  <div className="settings-empty-state integration-device-detail__empty">
                    <h3>{page('settings.integrations.deviceDetail.favoritesEmptyTitle')}</h3>
                    <p>{page('settings.integrations.deviceDetail.favoritesEmptyDesc')}</p>
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => setEntityView('all')}>
                      {page('settings.integrations.action.goToAllEntities')}
                    </button>
                  </div>
                </Card>
              ) : selectedEntities.length === 0 ? (
                <Card>
                  <div className="settings-empty-state integration-device-detail__empty">
                    <h3>{page('settings.integrations.deviceDetail.allEntitiesEmptyTitle')}</h3>
                    <p>{page('settings.integrations.deviceDetail.allEntitiesEmptyDesc')}</p>
                  </div>
                </Card>
              ) : (
                <div className="integration-entity-list">
                  {selectedEntities.map((entity) => (
                    <Card key={entity.entity_id} className="integration-entity-card">
                      <div className="integration-entity__header">
                        <div>
                          <div className="integration-entity__title-row">
                            <strong>{entity.name}</strong>
                            <span className="badge badge--secondary">{entity.domain}</span>
                          </div>
                          <div className="integration-status__detail">
                            {page('settings.integrations.deviceDetail.entityState', { state: entity.state_display })}
                            {entity.unit ? ` · ${entity.unit}` : ''}
                          </div>
                        </div>
                        <button
                          className={entity.favorite ? 'btn btn--outline btn--sm integration-entity__favorite integration-entity__favorite--active' : 'btn btn--outline btn--sm integration-entity__favorite'}
                          type="button"
                          onClick={() => void handleFavoriteToggle(entity)}
                          disabled={actionSubmitting[`favorite:${entity.entity_id}`]}
                        >
                          {entity.favorite
                            ? page('settings.integrations.action.unfavorite')
                            : page('settings.integrations.action.favorite')}
                        </button>
                      </div>
                      {entity.control.disabled_reason ? (
                        <div className="integration-entity__readonly">{entity.control.disabled_reason}</div>
                      ) : null}
                      {renderEntityControls(entity)}
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {logsModalOpen ? (
        <div className="member-modal-overlay" onClick={() => setLogsModalOpen(false)}>
          <div className="member-modal integration-device-logs-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{page('settings.integrations.deviceLogs.title')}</h3>
                <p>{page('settings.integrations.deviceLogs.desc', { name: selectedDevice?.name || selectedDeviceResource?.name || '' })}</p>
              </div>
            </div>
            {logsLoading ? (
              <div className="integration-status__detail">{page('settings.integrations.deviceLogs.loading')}</div>
            ) : !deviceLogs || deviceLogs.items.length === 0 ? (
              <div className="settings-empty-state integration-device-detail__empty">
                <h3>{page('settings.integrations.deviceLogs.emptyTitle')}</h3>
                <p>{page('settings.integrations.deviceLogs.emptyDesc')}</p>
              </div>
            ) : (
              <div className="integration-device-logs">
                {deviceLogs.items.map((item) => (
                  <div key={item.id} className="integration-device-logs__item">
                    <div className="integration-device-logs__header">
                      <strong>{item.entity_name || item.entity_id || item.action}</strong>
                      <span className={`badge badge--${getLogResultBadge(item.result)}`}>
                        {formatLogResult(item.result)}
                      </span>
                    </div>
                    <div className="integration-status__detail">{item.action}</div>
                    <div className="integration-status__detail">{item.created_at}</div>
                    {item.message ? <div className="integration-device-logs__message">{item.message}</div> : null}
                  </div>
                ))}
              </div>
            )}
            <div className="member-modal__actions">
              <button className="btn btn--outline btn--sm" type="button" onClick={() => setLogsModalOpen(false)}>
                {page('settings.integrations.action.close')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
