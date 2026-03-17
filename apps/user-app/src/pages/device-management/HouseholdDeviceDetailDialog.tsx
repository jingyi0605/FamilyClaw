import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import Taro from '@tarojs/taro';
import { useAuthContext } from '../../runtime';
import { Card, ToggleSwitch } from '../family/base';
import {
  getDeviceEnabledBadgeTone,
  getDeviceEnabledState,
  getDeviceRuntimeBadgeTone,
  normalizeDeviceDisplayStatus,
} from './deviceStatusDisplay';
import { ApiError, settingsApi } from '../settings/settingsApi';
import { SpeakerVoiceprintTab } from '../settings/components/SpeakerVoiceprintTab';
import { VoiceprintEnrollmentWizard } from '../settings/components/VoiceprintEnrollmentWizard';
import {
  createVoiceprintWaitingWizardState,
  createVoiceprintWizardState,
  getNextWizardStateFromEnrollment,
  type VoiceprintWizardState,
} from '../settings/components/speakerVoiceprintHelpers';
import type {
  DeviceEntity,
  DeviceEntityControl,
  DeviceEntityListRead,
  DeviceActionExecuteRequest,
  DeviceActionLogListRead,
  DeviceDetailPluginTabRead,
  DeviceDetailViewRead,
  HouseholdVoiceprintSummaryRead,
  PluginConfigFormRead,
  PluginManifestConfigField,
  PluginManifestFieldUiSchema,
  Room,
  VoiceprintEnrollmentRead,
} from '../settings/settingsTypes';

export type DevicePageLookup = (
  key: string,
  params?: Record<string, string | number>,
) => string;

type EntityView = 'favorites' | 'all';
type DeviceDetailTabKey = 'controls' | `builtin:${string}` | `plugin:${string}:${string}`;

type Props = {
  open: boolean;
  currentHouseholdId: string | null;
  deviceId: string | null;
  deviceName: string;
  subtitle: string;
  page: DevicePageLookup;
  fallbackStatus?: 'active' | 'offline' | 'inactive' | 'disabled';
  fallbackControllable?: boolean;
  fallbackRoomId?: string | null;
  onClose: () => void;
  onStatus: (message: string) => void;
  onError: (message: string) => void;
  onReload: () => Promise<void>;
  onDeleted?: () => void;
};

const DEVICE_LOG_PAGE_SIZE = 20;

type DeviceEditDraft = {
  name: string;
  roomId: string;
  enabled: boolean;
};

const EMPTY_DEVICE_EDIT_DRAFT: DeviceEditDraft = {
  name: '',
  roomId: '',
  enabled: false,
};

type DevicePluginTabDraft = {
  values: Record<string, unknown>;
  fieldErrors: Record<string, string>;
  error: string;
  saving: boolean;
};

function getPluginTabDraftKey(pluginId: string, tabKey: string) {
  return `${pluginId}:${tabKey}`;
}

function buildPluginTabDraft(form: PluginConfigFormRead): DevicePluginTabDraft {
  return {
    values: { ...form.view.values },
    fieldErrors: { ...form.view.field_errors },
    error: '',
    saving: false,
  };
}

function normalizePluginSubmitValue(field: PluginManifestConfigField, value: unknown): unknown {
  if (field.type === 'boolean') {
    return value === true;
  }
  if (field.type === 'integer') {
    if (typeof value === 'number') return Math.trunc(value);
    if (typeof value === 'string' && value.trim()) return Number.parseInt(value.trim(), 10);
    return value;
  }
  if (field.type === 'number') {
    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.trim()) return Number(value.trim());
    return value;
  }
  if (field.type === 'string' || field.type === 'text' || field.type === 'secret' || field.type === 'enum') {
    return typeof value === 'string' ? value.trim() : value;
  }
  return value;
}

function isPluginFieldVisible(
  fieldKey: string,
  values: Record<string, unknown>,
  widgets: Record<string, PluginManifestFieldUiSchema> | undefined,
) {
  const rules = widgets?.[fieldKey]?.visible_when ?? [];
  if (rules.length === 0) {
    return true;
  }
  return rules.every((rule) => {
    const currentValue = values[rule.field];
    if (rule.operator === 'truthy') {
      return Boolean(currentValue);
    }
    if (rule.operator === 'equals') {
      return currentValue === rule.value;
    }
    if (rule.operator === 'not_equals') {
      return currentValue !== rule.value;
    }
    if (rule.operator === 'in') {
      return Array.isArray(rule.value) && rule.value.includes(currentValue);
    }
    return true;
  });
}

function extractPluginErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const payload = error.payload as { detail?: unknown } | undefined;
    const detail = payload?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const detailRecord = detail as Record<string, unknown>;
      const message = typeof detailRecord.detail === 'string' ? detailRecord.detail : null;
      const fieldErrors = detailRecord.field_errors && typeof detailRecord.field_errors === 'object'
        ? (detailRecord.field_errors as Record<string, string>)
        : null;
      return {
        message: message || error.message || fallback,
        fieldErrors: fieldErrors ?? {},
      };
    }
    return {
      message: error.message || fallback,
      fieldErrors: {},
    };
  }
  return {
    message: error instanceof Error ? error.message : fallback,
    fieldErrors: {},
  };
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

export function HouseholdDeviceDetailDialog({
  open,
  currentHouseholdId,
  deviceId,
  deviceName,
  subtitle,
  page,
  fallbackStatus = 'inactive',
  fallbackControllable = false,
  fallbackRoomId = null,
  onClose,
  onStatus,
  onError,
  onReload,
  onDeleted,
}: Props) {
  const { actor } = useAuthContext();
  const [entityView, setEntityView] = useState<EntityView>('favorites');
  const [activeDetailTab, setActiveDetailTab] = useState<DeviceDetailTabKey>('controls');
  const [detailView, setDetailView] = useState<DeviceDetailViewRead | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [entityResponse, setEntityResponse] = useState<DeviceEntityListRead | null>(null);
  const [deviceLogs, setDeviceLogs] = useState<DeviceActionLogListRead | null>(null);
  const [rangeDrafts, setRangeDrafts] = useState<Record<string, number>>({});
  const [rooms, setRooms] = useState<Room[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [roomsLoading, setRoomsLoading] = useState(false);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editDraft, setEditDraft] = useState<DeviceEditDraft>(EMPTY_DEVICE_EDIT_DRAFT);
  const [editError, setEditError] = useState('');
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [loadedEditSourceKey, setLoadedEditSourceKey] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState<Record<string, boolean>>({});
  const [logsModalOpen, setLogsModalOpen] = useState(false);
  const [voiceprintSummary, setVoiceprintSummary] = useState<HouseholdVoiceprintSummaryRead | null>(null);
  const [voiceprintLoading, setVoiceprintLoading] = useState(false);
  const [voiceprintError, setVoiceprintError] = useState('');
  const [voiceprintSwitchSaving, setVoiceprintSwitchSaving] = useState(false);
  const [voiceprintWizard, setVoiceprintWizard] = useState<VoiceprintWizardState | null>(null);
  const [voiceprintEnrollment, setVoiceprintEnrollment] = useState<VoiceprintEnrollmentRead | null>(null);
  const [voiceprintBusy, setVoiceprintBusy] = useState(false);
  const [pluginTabDrafts, setPluginTabDrafts] = useState<Record<string, DevicePluginTabDraft>>({});

  const selectedDevice = detailView?.device ?? entityResponse?.device ?? null;
  const selectedEntities = entityResponse?.items ?? [];
  const selectedDeviceStatus = selectedDevice?.status ?? fallbackStatus;
  const selectedDeviceName = selectedDevice?.name ?? deviceName;
  const selectedDeviceDisabled = normalizeDeviceDisplayStatus(selectedDeviceStatus) === 'disabled';
  const selectedDeviceControllable = selectedDevice?.controllable ?? fallbackControllable;
  const canManageVoiceprint = actor?.member_role === 'admin';
  const detailTabs = useMemo(() => {
    const items: Array<{
      key: DeviceDetailTabKey;
      label: string;
      description?: string | null;
      pluginTab?: DeviceDetailPluginTabRead;
    }> = [
      {
        key: 'controls',
        label: page('settings.integrations.deviceDetail.tabs.controls'),
      },
    ];
    if (detailView?.builtin_tabs.some((tab) => tab.key === 'voiceprint')) {
      items.push({
        key: 'builtin:voiceprint',
        label: page('settings.integrations.deviceDetail.tabs.voiceprint'),
      });
    }
    for (const tab of detailView?.plugin_tabs ?? []) {
      items.push({
        key: `plugin:${tab.plugin_id}:${tab.tab_key}`,
        label: tab.title,
        description: tab.description,
        pluginTab: tab,
      });
    }
    return items;
  }, [detailView?.builtin_tabs, detailView?.plugin_tabs, page]);
  const activePluginTab = useMemo(
    () => detailTabs.find((item) => item.key === activeDetailTab)?.pluginTab ?? null,
    [activeDetailTab, detailTabs],
  );
  const sourceDraft = useMemo<DeviceEditDraft>(() => ({
    name: selectedDevice?.name ?? deviceName,
    roomId: selectedDevice?.room_id ?? fallbackRoomId ?? '',
    enabled: getDeviceEnabledState(selectedDeviceStatus) === 'enabled',
  }), [deviceName, fallbackRoomId, selectedDevice?.name, selectedDevice?.room_id, selectedDeviceStatus]);
  const sourceDraftKey = useMemo(
    () => JSON.stringify(sourceDraft),
    [sourceDraft],
  );
  const sortedRooms = useMemo(
    () => [...rooms].sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')),
    [rooms],
  );
  const isEditDirty = editDraft.name.trim() !== sourceDraft.name.trim()
    || editDraft.roomId !== sourceDraft.roomId
    || editDraft.enabled !== sourceDraft.enabled;

  useEffect(() => {
    if (!open || !deviceId) {
      setActiveDetailTab('controls');
      setDetailView(null);
      setEntityView('favorites');
      setEntityResponse(null);
      setDeviceLogs(null);
      setEditModalOpen(false);
      setLogsModalOpen(false);
      setEditDraft(EMPTY_DEVICE_EDIT_DRAFT);
      setEditError('');
      setLoadedEditSourceKey(null);
      setVoiceprintSummary(null);
      setVoiceprintError('');
      setVoiceprintWizard(null);
      setVoiceprintEnrollment(null);
      setPluginTabDrafts({});
      return;
    }
    setActiveDetailTab('controls');
    setEntityView('favorites');
    setDeviceLogs(null);
    setEditModalOpen(false);
    setLogsModalOpen(false);
  }, [deviceId, open]);

  useEffect(() => {
    if (!open || !deviceId) {
      return;
    }
    if (loadedEditSourceKey === sourceDraftKey && !editError) {
      return;
    }
    if (loadedEditSourceKey === null || !isEditDirty) {
      setEditDraft(sourceDraft);
      setEditError('');
      setLoadedEditSourceKey(sourceDraftKey);
    }
  }, [deviceId, editError, isEditDirty, loadedEditSourceKey, open, sourceDraft, sourceDraftKey]);

  useEffect(() => {
    if (!open || !deviceId) {
      return;
    }
    void loadDeviceDetail(deviceId);
  }, [deviceId, open]);

  useEffect(() => {
    if (!open || !deviceId) {
      return;
    }
    void loadDeviceEntities(deviceId, entityView);
  }, [deviceId, entityView, open]);

  useEffect(() => {
    if (!open || !deviceId || !detailView?.capabilities.supports_voiceprint) {
      return;
    }
    void loadVoiceprintSummary(deviceId);
  }, [detailView?.capabilities.supports_voiceprint, deviceId, open]);

  useEffect(() => {
    const activeKeys = new Set(detailTabs.map((item) => item.key));
    if (!activeKeys.has(activeDetailTab)) {
      setActiveDetailTab('controls');
    }
  }, [activeDetailTab, detailTabs]);

  useEffect(() => {
    if (!open || !currentHouseholdId) {
      setRooms([]);
      setRoomsLoading(false);
      return;
    }

    const householdId = currentHouseholdId;
    let cancelled = false;

    async function loadRooms() {
      setRoomsLoading(true);
      try {
        const response = await settingsApi.listRooms(householdId);
        if (cancelled) {
          return;
        }
        setRooms(response.items);
      } catch (error) {
        if (cancelled) {
          return;
        }
        onError(error instanceof Error ? error.message : page('settings.integrations.error.loadRoomsFailed'));
      } finally {
        if (!cancelled) {
          setRoomsLoading(false);
        }
      }
    }

    void loadRooms();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, onError, open, page]);

  useEffect(() => {
    if (!voiceprintWizard || voiceprintWizard.step !== 'waiting' || !voiceprintWizard.enrollmentId) {
      return undefined;
    }

    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const enrollment = await settingsApi.getVoiceprintEnrollment(voiceprintWizard.enrollmentId!);
        if (cancelled) {
          return;
        }
        setVoiceprintEnrollment(enrollment);
        setVoiceprintWizard((current) => (
          current ? getNextWizardStateFromEnrollment(current, enrollment) : current
        ));
        if (enrollment.status === 'completed' || enrollment.status === 'failed' || enrollment.status === 'cancelled') {
          void (deviceId ? loadVoiceprintSummary(deviceId) : Promise.resolve());
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setVoiceprintWizard((current) => current ? {
          ...current,
          step: 'failed',
          error: error instanceof Error ? error.message : page('settings.integrations.error.loadVoiceprintEnrollmentFailed'),
        } : current);
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [deviceId, page, voiceprintWizard]);

  useEffect(() => {
    if (!open || !voiceprintWizard || voiceprintWizard.step !== 'waiting' || !voiceprintWizard.enrollmentId) {
      return undefined;
    }

    let cancelled = false;
    const timer = setInterval(() => {
      void settingsApi.getVoiceprintEnrollment(voiceprintWizard.enrollmentId!)
        .then((enrollment) => {
          if (cancelled) {
            return;
          }
          setVoiceprintEnrollment(enrollment);
          setVoiceprintWizard((current) => current ? getNextWizardStateFromEnrollment(current, enrollment) : current);
          if (enrollment.status === 'completed' || enrollment.status === 'failed' || enrollment.status === 'cancelled') {
            if (deviceId) {
              void loadVoiceprintSummary(deviceId);
            }
          }
        })
        .catch((error) => {
          if (cancelled) {
            return;
          }
          setVoiceprintWizard((current) => current ? {
            ...current,
            step: 'failed',
            error: error instanceof Error ? error.message : page('settings.integrations.error.loadVoiceprintEnrollmentFailed'),
          } : current);
        });
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [deviceId, open, page, voiceprintWizard]);

  async function loadDeviceEntities(currentDeviceId: string, view: EntityView) {
    setEntitiesLoading(true);
    try {
      const response = await settingsApi.listDeviceEntities(currentDeviceId, view);
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

  async function loadDeviceDetail(currentDeviceId: string) {
    setDetailLoading(true);
    try {
      const response = await settingsApi.getDeviceDetailView(currentDeviceId);
      setDetailView(response);
      setPluginTabDrafts((current) => {
        const next = { ...current };
        for (const tab of response.plugin_tabs) {
          const draftKey = getPluginTabDraftKey(tab.plugin_id, tab.tab_key);
          next[draftKey] = buildPluginTabDraft(tab.config_form);
        }
        return next;
      });
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.loadDeviceDetailFailed'));
    } finally {
      setDetailLoading(false);
    }
  }

  async function loadDeviceLogs(currentDeviceId: string) {
    setLogsLoading(true);
    try {
      const response = await settingsApi.listDeviceActionLogs(currentDeviceId, {
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

  async function loadVoiceprintSummary(currentDeviceId: string) {
    if (!currentHouseholdId) {
      return;
    }
    setVoiceprintLoading(true);
    try {
      const response = await settingsApi.getHouseholdVoiceprintSummary(currentHouseholdId, currentDeviceId);
      setVoiceprintSummary(response);
      setVoiceprintError('');
    } catch (error) {
      const message = error instanceof Error ? error.message : page('settings.integrations.error.loadVoiceprintFailed');
      setVoiceprintError(message);
    } finally {
      setVoiceprintLoading(false);
    }
  }

  function formatDeviceStatus(statusValue: string) {
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

  function formatDeviceEnabledStatus(statusValue: string) {
    return getDeviceEnabledState(statusValue) === 'disabled'
      ? page('settings.integrations.deviceEnabled.disabled')
      : page('settings.integrations.deviceEnabled.enabled');
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
    if (!deviceId) {
      return;
    }
    await loadDeviceDetail(deviceId);
    await loadDeviceEntities(deviceId, entityView);
    if (detailView?.capabilities.supports_voiceprint) {
      await loadVoiceprintSummary(deviceId);
    }
    if (logsModalOpen) {
      await loadDeviceLogs(deviceId);
    }
    await onReload();
  }

  async function handleFavoriteToggle(entity: DeviceEntity) {
    if (!deviceId) {
      return;
    }
    setActionSubmitting((current) => ({ ...current, [`favorite:${entity.entity_id}`]: true }));
    try {
      const response = await settingsApi.updateDeviceEntityFavorite(deviceId, entity.entity_id, !entity.favorite);
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
    if (!currentHouseholdId || !deviceId) {
      return;
    }
    const payload: DeviceActionExecuteRequest = {
      household_id: currentHouseholdId,
      device_id: deviceId,
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
      if (logsModalOpen && deviceId) {
        await loadDeviceLogs(deviceId);
      }
    } finally {
      setActionSubmitting((current) => ({ ...current, [`control:${entity.entity_id}:${action}`]: false }));
    }
  }

  async function handleDeleteDevice() {
    if (!deviceId) {
      return;
    }
    const confirmResult = await Taro.showModal({
      title: page('settings.integrations.deviceDetail.deleteTitle'),
      content: page('settings.integrations.deviceDetail.deleteConfirm', { name: selectedDeviceName }),
      confirmText: page('settings.integrations.action.deleteDevice'),
      cancelText: page('settings.integrations.action.cancel'),
      confirmColor: '#d14343',
    });
    if (!confirmResult.confirm) {
      return;
    }
    setDeleteSubmitting(true);
    try {
      await settingsApi.deleteDevice(deviceId);
      onStatus(page('settings.integrations.status.deviceDeleted', { name: selectedDeviceName }));
      onDeleted?.();
      onClose();
      await onReload();
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.deleteDeviceFailed'));
    } finally {
      setDeleteSubmitting(false);
    }
  }

  async function openLogsModal() {
    if (!deviceId) {
      return;
    }
    setLogsModalOpen(true);
    await loadDeviceLogs(deviceId);
  }

  function resetEditForm() {
    setEditDraft(sourceDraft);
    setEditError('');
    setLoadedEditSourceKey(sourceDraftKey);
  }

  function openEditModal() {
    resetEditForm();
    setEditModalOpen(true);
  }

  function closeEditModal() {
    resetEditForm();
    setEditModalOpen(false);
  }

  async function handleSaveDevice() {
    if (!deviceId) {
      return;
    }

    const trimmedName = editDraft.name.trim();
    if (!trimmedName) {
      setEditError(page('settings.integrations.deviceDetail.aliasRequired'));
      return;
    }

    const payload: Parameters<typeof settingsApi.updateDevice>[1] = {};
    if (trimmedName !== sourceDraft.name.trim()) {
      payload.name = trimmedName;
    }

    const nextRoomId = editDraft.roomId || null;
    const currentRoomId = sourceDraft.roomId || null;
    if (nextRoomId !== currentRoomId) {
      payload.room_id = nextRoomId;
    }

    if (editDraft.enabled !== sourceDraft.enabled) {
      payload.status = editDraft.enabled ? 'inactive' : 'disabled';
    }

    if (Object.keys(payload).length === 0) {
      setEditError('');
      return;
    }

    setEditSubmitting(true);
    setEditError('');
    try {
      const updatedDevice = await settingsApi.updateDevice(deviceId, payload);
      setEntityResponse((current) => current ? {
        ...current,
        device: updatedDevice,
      } : current);
      setEditDraft({
        name: updatedDevice.name,
        roomId: updatedDevice.room_id ?? '',
        enabled: getDeviceEnabledState(updatedDevice.status) === 'enabled',
      });
      setLoadedEditSourceKey(JSON.stringify({
        name: updatedDevice.name,
        roomId: updatedDevice.room_id ?? '',
        enabled: getDeviceEnabledState(updatedDevice.status) === 'enabled',
      }));
      setEditModalOpen(false);
      onStatus(page('settings.integrations.status.deviceUpdated', { name: updatedDevice.name }));
      await refreshCurrentDevice();
    } catch (error) {
      const message = error instanceof Error ? error.message : page('settings.integrations.error.updateDeviceFailed');
      setEditError(message);
      onError(message);
    } finally {
      setEditSubmitting(false);
    }
  }

  function updatePluginDraft(tab: DeviceDetailPluginTabRead, updater: (current: DevicePluginTabDraft) => DevicePluginTabDraft) {
    const draftKey = getPluginTabDraftKey(tab.plugin_id, tab.tab_key);
    setPluginTabDrafts((current) => ({
      ...current,
      [draftKey]: updater(current[draftKey] ?? buildPluginTabDraft(tab.config_form)),
    }));
  }

  async function handleSavePluginTab(tab: DeviceDetailPluginTabRead) {
    if (!currentHouseholdId || !deviceId) {
      return;
    }
    const draftKey = getPluginTabDraftKey(tab.plugin_id, tab.tab_key);
    const draft = pluginTabDrafts[draftKey] ?? buildPluginTabDraft(tab.config_form);
    const fieldMap = new Map(tab.config_form.config_spec.config_schema.fields.map((field) => [field.key, field]));
    const values = Object.fromEntries(
      Object.entries(draft.values).map(([key, value]) => {
        const field = fieldMap.get(key);
        return [key, field ? normalizePluginSubmitValue(field, value) : value];
      }),
    );

    updatePluginDraft(tab, (current) => ({ ...current, saving: true, error: '' }));
    try {
      const response = await settingsApi.saveHouseholdPluginConfigForm(currentHouseholdId, tab.plugin_id, {
        scope_type: tab.config_form.view.scope_type,
        scope_key: deviceId,
        values,
        clear_secret_fields: [],
      });
      setDetailView((current) => current ? {
        ...current,
        device: {
          ...current.device,
          voice_auto_takeover_enabled: Boolean(response.view.values.voice_auto_takeover_enabled ?? current.device.voice_auto_takeover_enabled),
          voice_takeover_prefixes: typeof response.view.values.voice_takeover_prefixes === 'string'
            ? response.view.values.voice_takeover_prefixes
              .split(/\r?\n|,/)
              .map((item) => item.trim())
              .filter(Boolean)
            : current.device.voice_takeover_prefixes,
        },
        plugin_tabs: current.plugin_tabs.map((item) => (
          item.plugin_id === tab.plugin_id && item.tab_key === tab.tab_key
            ? { ...item, config_form: response }
            : item
        )),
      } : current);
      updatePluginDraft(tab, () => buildPluginTabDraft(response));
      onStatus(page('settings.integrations.status.pluginDeviceConfigSaved', { name: tab.title }));
      await onReload();
    } catch (error) {
      const resolved = extractPluginErrorMessage(error, page('settings.integrations.error.savePluginDeviceConfigFailed'));
      updatePluginDraft(tab, (current) => ({
        ...current,
        saving: false,
        error: resolved.message,
        fieldErrors: resolved.fieldErrors,
      }));
      onError(resolved.message);
      return;
    }
    updatePluginDraft(tab, (current) => ({ ...current, saving: false }));
  }

  async function handleToggleVoiceprintEnabled(nextValue: boolean) {
    if (!deviceId) {
      return;
    }
    setVoiceprintSwitchSaving(true);
    try {
      await settingsApi.updateDevice(deviceId, {
        voiceprint_identity_enabled: nextValue,
      });
      await refreshCurrentDevice();
      onStatus(page('settings.integrations.status.voiceprintUpdated', { name: selectedDeviceName }));
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.updateVoiceprintFailed'));
    } finally {
      setVoiceprintSwitchSaving(false);
    }
  }

  function handleOpenVoiceprintCreate(memberId?: string) {
    setVoiceprintEnrollment(null);
    setVoiceprintWizard(createVoiceprintWizardState('create', memberId ?? null));
  }

  function handleOpenVoiceprintUpdate(memberId: string) {
    setVoiceprintEnrollment(null);
    setVoiceprintWizard(createVoiceprintWizardState('update', memberId));
  }

  async function handleResumeVoiceprintEnrollment(enrollmentId: string, memberId: string) {
    setVoiceprintBusy(true);
    try {
      const enrollment = await settingsApi.getVoiceprintEnrollment(enrollmentId);
      setVoiceprintEnrollment(enrollment);
      setVoiceprintWizard(getNextWizardStateFromEnrollment(
        createVoiceprintWaitingWizardState(memberId, enrollmentId, enrollment.sample_count > 0 ? 'update' : 'create'),
        enrollment,
      ));
    } catch (error) {
      onError(error instanceof Error ? error.message : page('settings.integrations.error.loadVoiceprintEnrollmentFailed'));
    } finally {
      setVoiceprintBusy(false);
    }
  }

  async function handleStartVoiceprintEnrollment() {
    if (!currentHouseholdId || !deviceId || !voiceprintWizard?.memberId) {
      return;
    }
    setVoiceprintBusy(true);
    setVoiceprintWizard((current) => current ? { ...current, step: 'creating', error: '' } : current);
    try {
      const enrollment = await settingsApi.createVoiceprintEnrollment({
        household_id: currentHouseholdId,
        member_id: voiceprintWizard.memberId,
        terminal_id: deviceId,
      });
      setVoiceprintEnrollment(enrollment);
      setVoiceprintWizard((current) => current ? getNextWizardStateFromEnrollment(current, enrollment) : current);
      await loadVoiceprintSummary(deviceId);
    } catch (error) {
      setVoiceprintWizard((current) => current ? {
        ...current,
        step: 'failed',
        error: error instanceof Error ? error.message : page('settings.integrations.error.createVoiceprintEnrollmentFailed'),
      } : current);
    } finally {
      setVoiceprintBusy(false);
    }
  }

  function renderPluginField(
    tab: DeviceDetailPluginTabRead,
    field: PluginManifestConfigField,
    widget?: PluginManifestFieldUiSchema,
  ) {
    const draftKey = getPluginTabDraftKey(tab.plugin_id, tab.tab_key);
    const draft = pluginTabDrafts[draftKey] ?? buildPluginTabDraft(tab.config_form);
    const value = draft.values[field.key];
    const fieldError = draft.fieldErrors[field.key];

    if (!isPluginFieldVisible(field.key, draft.values, tab.config_form.config_spec.ui_schema.widgets)) {
      return null;
    }

    if (field.type === 'boolean') {
      return (
        <div key={field.key} className="integration-device-detail__toggle-card">
          <ToggleSwitch
            checked={value === true}
            label={field.label}
            description={widget?.help_text ?? field.description ?? ''}
            disabled={draft.saving}
            onChange={(nextValue) => updatePluginDraft(tab, (current) => ({
              ...current,
              values: { ...current.values, [field.key]: nextValue },
              fieldErrors: { ...current.fieldErrors, [field.key]: '' },
            }))}
          />
          {fieldError ? <div className="form-error">{fieldError}</div> : null}
        </div>
      );
    }

    if (field.type === 'enum') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <select
            className="form-select"
            value={typeof value === 'string' ? value : ''}
            disabled={draft.saving}
            onChange={(event) => updatePluginDraft(tab, (current) => ({
              ...current,
              values: { ...current.values, [field.key]: event.currentTarget.value },
              fieldErrors: { ...current.fieldErrors, [field.key]: '' },
            }))}
          >
            <option value="">{page('settings.integrations.pluginConfig.selectPlaceholder')}</option>
            {(field.enum_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-error">{fieldError}</div> : null}
        </div>
      );
    }

    if (field.type === 'text') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <textarea
            className="form-input"
            value={typeof value === 'string' ? value : ''}
            placeholder={widget?.placeholder ?? undefined}
            disabled={draft.saving}
            onChange={(event) => updatePluginDraft(tab, (current) => ({
              ...current,
              values: { ...current.values, [field.key]: event.currentTarget.value },
              fieldErrors: { ...current.fieldErrors, [field.key]: '' },
            }))}
          />
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-error">{fieldError}</div> : null}
        </div>
      );
    }

    return (
      <div key={field.key} className="form-group">
        <label>{field.label}</label>
        <input
          className="form-input"
          type={field.type === 'secret' ? 'password' : (field.type === 'integer' || field.type === 'number' ? 'number' : 'text')}
          value={typeof value === 'string' || typeof value === 'number' ? String(value) : ''}
          placeholder={widget?.placeholder ?? undefined}
          disabled={draft.saving}
          onChange={(event) => updatePluginDraft(tab, (current) => ({
            ...current,
            values: { ...current.values, [field.key]: event.currentTarget.value },
            fieldErrors: { ...current.fieldErrors, [field.key]: '' },
          }))}
        />
        <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
        {fieldError ? <div className="form-error">{fieldError}</div> : null}
      </div>
    );
  }

  function renderPluginTab(tab: DeviceDetailPluginTabRead) {
    const draftKey = getPluginTabDraftKey(tab.plugin_id, tab.tab_key);
    const draft = pluginTabDrafts[draftKey] ?? buildPluginTabDraft(tab.config_form);
    const fieldMap = new Map(tab.config_form.config_spec.config_schema.fields.map((field) => [field.key, field]));
    const orderedKeys = tab.config_form.config_spec.ui_schema.field_order?.filter((key) => fieldMap.has(key))
      ?? tab.config_form.config_spec.config_schema.fields.map((field) => field.key);

    return (
      <div className="speaker-device-detail-dialog__panel">
        <div className="speaker-device-detail-dialog__panel-header">
          <h4>{tab.title}</h4>
          <p>{tab.description || tab.config_form.config_spec.description || page('settings.integrations.pluginConfig.desc')}</p>
        </div>
        <div className="settings-form">
          {draft.error ? <div className="form-error">{draft.error}</div> : null}
          {tab.config_form.config_spec.ui_schema.sections.length > 0
            ? tab.config_form.config_spec.ui_schema.sections.map((section) => (
              <div key={section.id} className="integration-device-detail__plugin-section">
                <h4>{section.title}</h4>
                {section.description ? <p className="integration-status__detail">{section.description}</p> : null}
                {section.fields.map((fieldKey) => {
                  const field = fieldMap.get(fieldKey);
                  if (!field) {
                    return null;
                  }
                  return renderPluginField(tab, field, tab.config_form.config_spec.ui_schema.widgets?.[field.key]);
                })}
              </div>
            ))
            : orderedKeys.map((fieldKey) => {
              const field = fieldMap.get(fieldKey);
              if (!field) {
                return null;
              }
              return renderPluginField(tab, field, tab.config_form.config_spec.ui_schema.widgets?.[field.key]);
            })}
          <div className="member-modal__actions">
            <button
              className="btn btn--primary btn--sm"
              type="button"
              onClick={() => void handleSavePluginTab(tab)}
              disabled={draft.saving}
            >
              {draft.saving
                ? page('settings.integrations.action.saving')
                : (tab.config_form.config_spec.ui_schema.submit_text || page('settings.integrations.action.savePluginDeviceConfig'))}
            </button>
          </div>
        </div>
      </div>
    );
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
            onChange={(event) => {
              const nextValue = Number(event.currentTarget.value);
              setRangeDrafts((current) => ({
                ...current,
                [entity.entity_id]: nextValue,
              }));
            }}
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

  if (!open || !deviceId) {
    return null;
  }

  const editFormContent = (
    <>
      {editError ? <div className="form-error">{editError}</div> : null}
      <div className="settings-form integration-device-detail__edit-form">
        <div className="form-group">
          <label htmlFor="integration-device-alias">{page('settings.integrations.deviceDetail.aliasLabel')}</label>
          <input
            id="integration-device-alias"
            className="form-input"
            type="text"
            value={editDraft.name}
            placeholder={page('settings.integrations.deviceDetail.aliasPlaceholder')}
            disabled={editSubmitting || deleteSubmitting}
            onChange={(event) => {
              const nextName = event.currentTarget.value;
              setEditError('');
              setEditDraft((current) => ({ ...current, name: nextName }));
            }}
          />
          <div className="form-help">{page('settings.integrations.deviceDetail.aliasHelp')}</div>
        </div>

        <div className="form-group">
          <label htmlFor="integration-device-room">{page('settings.integrations.deviceDetail.roomLabel')}</label>
          <select
            id="integration-device-room"
            className="form-select"
            value={editDraft.roomId}
            disabled={editSubmitting || deleteSubmitting || roomsLoading}
            onChange={(event) => {
              const nextRoomId = event.currentTarget.value;
              setEditError('');
              setEditDraft((current) => ({ ...current, roomId: nextRoomId }));
            }}
          >
            <option value="">{page('settings.integrations.deviceDetail.roomUnassigned')}</option>
            {sortedRooms.map((room) => (
              <option key={room.id} value={room.id}>{room.name}</option>
            ))}
          </select>
          <div className="form-help">
            {roomsLoading
              ? page('settings.integrations.deviceDetail.roomLoading')
              : page('settings.integrations.deviceDetail.roomHelp')}
          </div>
        </div>

        <div className="integration-device-detail__toggle-card">
          <ToggleSwitch
            checked={editDraft.enabled}
            label={page('settings.integrations.deviceDetail.enabledLabel')}
            description={editDraft.enabled
              ? page('settings.integrations.deviceDetail.enabledDescEnabled')
              : page('settings.integrations.deviceDetail.enabledDescDisabled')}
            disabled={editSubmitting || deleteSubmitting}
            onChange={(value) => {
              setEditError('');
              setEditDraft((current) => ({ ...current, enabled: value }));
            }}
          />
        </div>
      </div>
    </>
  );

  const controlsPanel = (
    <>
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
                <div className="integration-entity__summary">
                  <div className="integration-entity__title-row">
                    <strong>{entity.name}</strong>
                    <span className="badge badge--secondary">{entity.domain}</span>
                  </div>
                  <div className="integration-status__detail">
                    {page('settings.integrations.deviceDetail.entityState', { state: entity.state_display })}
                    {entity.unit ? ` ${entity.unit}` : ''}
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
    </>
  );

  const voiceprintPanel = detailView?.capabilities.supports_voiceprint ? (
    <SpeakerVoiceprintTab
      device={selectedDevice ?? {
        id: deviceId,
        household_id: currentHouseholdId ?? '',
        room_id: fallbackRoomId,
        name: selectedDeviceName,
        device_type: 'speaker',
        vendor: 'xiaomi',
        status: selectedDeviceStatus,
        controllable: selectedDeviceControllable,
        voice_auto_takeover_enabled: false,
        voiceprint_identity_enabled: false,
        voice_takeover_prefixes: [],
        created_at: '',
        updated_at: '',
      }}
      canManage={canManageVoiceprint}
      summary={voiceprintSummary}
      loading={voiceprintLoading}
      error={voiceprintError}
      switchSaving={voiceprintSwitchSaving}
      onRetry={() => {
        if (deviceId) {
          void loadVoiceprintSummary(deviceId);
        }
      }}
      onToggleVoiceprintEnabled={(nextValue) => void handleToggleVoiceprintEnabled(nextValue)}
      onStartEnrollment={(memberId) => handleOpenVoiceprintCreate(memberId)}
      onUpdateVoiceprint={(memberId) => handleOpenVoiceprintUpdate(memberId)}
      onResumeEnrollment={(enrollmentId, memberId) => void handleResumeVoiceprintEnrollment(enrollmentId, memberId)}
    />
  ) : null;

  const dialogContent = (
    <>
      <div className="member-modal-overlay" onClick={onClose}>
        <div className="member-modal integration-device-detail-modal" onClick={(event) => event.stopPropagation()}>
          <div className="integration-device-detail">
            <div className="member-modal__header integration-device-detail-modal__header">
              <div>
                <h3>{selectedDeviceName}</h3>
                <p>{subtitle}</p>
              </div>
              <button className="btn btn--outline btn--sm" type="button" onClick={onClose}>
                {page('settings.integrations.action.close')}
              </button>
            </div>

            <div className="integration-device-detail__tabs integration-device-detail__tabs--primary">
              {detailTabs.map((tab) => (
                <button
                  key={tab.key}
                  className={activeDetailTab === tab.key ? 'integration-device-detail__tab integration-device-detail__tab--active' : 'integration-device-detail__tab'}
                  type="button"
                  onClick={() => setActiveDetailTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="integration-device-detail__header">
              <div>
                <div className="integration-device-detail__title-row">
                  <span className={`badge badge--${getDeviceEnabledBadgeTone(selectedDeviceStatus)}`}>
                    {formatDeviceEnabledStatus(selectedDeviceStatus)}
                  </span>
                  {!selectedDeviceDisabled ? (
                    <span className={`badge badge--${getDeviceRuntimeBadgeTone(selectedDeviceStatus)}`}>
                      {formatDeviceStatus(selectedDeviceStatus)}
                    </span>
                  ) : null}
                  <span className={`badge badge--${selectedDeviceDisabled ? 'danger' : (selectedDeviceControllable ? 'success' : 'secondary')}`}>
                    {selectedDeviceControllable
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
                  className="btn btn--outline btn--sm btn--danger"
                  type="button"
                  onClick={() => void handleDeleteDevice()}
                  disabled={deleteSubmitting || editSubmitting}
                >
                  {page('settings.integrations.action.deleteDevice')}
                </button>
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={openEditModal}
                  disabled={deleteSubmitting || editSubmitting}
                >
                  {page('settings.integrations.action.editDevice')}
                </button>
              </div>
            </div>

            {selectedDeviceDisabled ? (
              <div className="integration-device-detail__notice">
                {page('settings.integrations.deviceDetail.deviceDisabledHint')}
              </div>
            ) : null}

            {detailLoading ? (
              <Card>
                <div className="integration-status__detail">{page('settings.integrations.deviceDetail.loadingDetail')}</div>
              </Card>
            ) : activeDetailTab === 'controls' ? (
              controlsPanel
            ) : activeDetailTab === 'builtin:voiceprint' ? (
              voiceprintPanel
            ) : activePluginTab ? (
              renderPluginTab(activePluginTab)
            ) : (
              <Card>
                <div className="settings-empty-state integration-device-detail__empty">
                  <h3>{page('settings.integrations.deviceDetail.emptyTabTitle')}</h3>
                  <p>{page('settings.integrations.deviceDetail.emptyTabDesc')}</p>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>

      {editModalOpen ? (
        <div className="member-modal-overlay" onClick={closeEditModal}>
          <div className="member-modal integration-device-edit-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{page('settings.integrations.deviceDetail.editTitle')}</h3>
                <p>{page('settings.integrations.deviceDetail.editDesc')}</p>
              </div>
              <button className="btn btn--outline btn--sm" type="button" onClick={closeEditModal}>
                {page('settings.integrations.action.close')}
              </button>
            </div>
            <div className="integration-device-edit-modal__body">
              {editFormContent}
            </div>
            <div className="member-modal__actions">
              <button className="btn btn--outline btn--sm" type="button" onClick={closeEditModal}>
                {page('settings.integrations.action.close')}
              </button>
              <button
                className="btn btn--primary btn--sm"
                type="button"
                onClick={() => void handleSaveDevice()}
                disabled={!isEditDirty || editSubmitting || deleteSubmitting}
              >
                {editSubmitting
                  ? page('settings.integrations.action.saving')
                  : page('settings.integrations.action.saveDevice')}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {voiceprintWizard && voiceprintSummary ? (
        <VoiceprintEnrollmentWizard
          wizard={voiceprintWizard}
          members={voiceprintSummary.members}
          deviceName={selectedDeviceName}
          enrollment={voiceprintEnrollment}
          busy={voiceprintBusy}
          onClose={() => {
            if (voiceprintWizard.step === 'waiting') {
              return;
            }
            setVoiceprintWizard(null);
            setVoiceprintEnrollment(null);
          }}
          onBack={() => setVoiceprintWizard((current) => (
            current
              ? {
                ...current,
                step: 'select_member',
                enrollmentId: null,
                error: '',
              }
              : current
          ))}
          onSelectMember={(memberId) => setVoiceprintWizard((current) => (
            current
              ? {
                ...current,
                memberId,
                lockedMemberId: current.lockedMemberId ?? memberId,
              }
              : current
          ))}
          onContinue={() => setVoiceprintWizard((current) => (
            current && current.memberId
              ? { ...current, step: 'confirm', lockedMemberId: current.lockedMemberId ?? current.memberId }
              : current
          ))}
          onStart={() => void handleStartVoiceprintEnrollment()}
        />
      ) : null}

      {logsModalOpen ? (
        <div className="member-modal-overlay" onClick={() => setLogsModalOpen(false)}>
          <div className="member-modal integration-device-logs-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>{page('settings.integrations.deviceLogs.title')}</h3>
                <p>{page('settings.integrations.deviceLogs.desc', { name: selectedDeviceName })}</p>
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

  if (typeof document === 'undefined') {
    return dialogContent;
  }

  return createPortal(dialogContent, document.body);
}
