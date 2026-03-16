import { useEffect, useMemo, useState } from 'react';
import { GuardedPage, useAuthContext, useHouseholdContext, useI18n } from '../../../runtime';
import { Card, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { SpeakerDeviceDetailDialog } from '../components/SpeakerDeviceDetailDialog';
import { SpeakerVoiceprintTab } from '../components/SpeakerVoiceprintTab';
import { VoiceprintEnrollmentWizard } from '../components/VoiceprintEnrollmentWizard';
import {
  createVoiceprintWaitingWizardState,
  createVoiceprintWizardState,
  getNextWizardStateFromEnrollment,
  type VoiceprintWizardState,
} from '../components/speakerVoiceprintHelpers';
import { settingsApi } from '../settingsApi';
import type {
  ContextOverviewRead,
  Device,
  HomeAssistantConfig,
  HomeAssistantDeviceCandidate,
  HomeAssistantRoomCandidate,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  HouseholdVoiceprintSummaryRead,
  Room,
  VoiceprintEnrollmentRead,
  VoiceDiscoveryTerminal,
} from '../settingsTypes';

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) {
    return values.enUS;
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return values.zhTW;
  }
  return values.zhCN;
}

function resolveDateLocale(locale: string | undefined) {
  if (locale?.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return 'zh-TW';
  }
  return 'zh-CN';
}

function SettingsIntegrationsContent() {
  const { locale } = useI18n();
  const { actor } = useAuthContext();
  const { currentHouseholdId } = useHouseholdContext();
  const [overview, setOverview] = useState<ContextOverviewRead | null>(null);
  const [haConfig, setHaConfig] = useState<HomeAssistantConfig | null>(null);
  const [haForm, setHaForm] = useState({ base_url: '', access_token: '', sync_rooms_enabled: false, clear_access_token: false });
  const [devices, setDevices] = useState<Device[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [deviceDrafts, setDeviceDrafts] = useState<Record<string, Pick<Device, 'name' | 'room_id' | 'status' | 'controllable'>>>({});
  const [deviceCandidates, setDeviceCandidates] = useState<HomeAssistantDeviceCandidate[]>([]);
  const [selectedExternalDeviceIds, setSelectedExternalDeviceIds] = useState<string[]>([]);
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [deviceModalLoading, setDeviceModalLoading] = useState(false);
  const [syncSummary, setSyncSummary] = useState<HomeAssistantSyncResponse | null>(null);
  const [roomSyncSummary, setRoomSyncSummary] = useState<HomeAssistantRoomSyncResponse | null>(null);
  const [roomCandidates, setRoomCandidates] = useState<HomeAssistantRoomCandidate[]>([]);
  const [selectedRoomNames, setSelectedRoomNames] = useState<string[]>([]);
  const [roomModalOpen, setRoomModalOpen] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [roomModalLoading, setRoomModalLoading] = useState(false);
  const [voiceDiscoveries, setVoiceDiscoveries] = useState<VoiceDiscoveryTerminal[]>([]);
  const [voiceDiscoveryDrafts, setVoiceDiscoveryDrafts] = useState<Record<string, { terminal_name: string; room_id: string }>>({});
  const [voiceDiscoveryError, setVoiceDiscoveryError] = useState('');
  const [voiceClaimingFingerprint, setVoiceClaimingFingerprint] = useState<string | null>(null);
  const [speakerDetailDeviceId, setSpeakerDetailDeviceId] = useState<string | null>(null);
  const [speakerSettingsError, setSpeakerSettingsError] = useState('');
  const [voiceprintSummary, setVoiceprintSummary] = useState<HouseholdVoiceprintSummaryRead | null>(null);
  const [voiceprintLoading, setVoiceprintLoading] = useState(false);
  const [voiceprintError, setVoiceprintError] = useState('');
  const [voiceprintSwitchSaving, setVoiceprintSwitchSaving] = useState(false);
  const [voiceprintWizard, setVoiceprintWizard] = useState<VoiceprintWizardState | null>(null);
  const [voiceprintWizardEnrollment, setVoiceprintWizardEnrollment] = useState<VoiceprintEnrollmentRead | null>(null);
  const [voiceprintWizardBusy, setVoiceprintWizardBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const copy = {
    defaultSpeakerName: pickLocaleText(locale, { zhCN: '小爱音箱', zhTW: '小愛音箱', enUS: 'Xiaomi speaker' }),
    roomUnassigned: pickLocaleText(locale, { zhCN: '未分配房间', zhTW: '未分配房間', enUS: 'Unassigned room' }),
    discoveryNotFound: pickLocaleText(locale, { zhCN: '这台音箱已经不在待添加列表里了。', zhTW: '這台音箱已不在待新增列表裡。', enUS: 'This speaker is no longer in the pending list.' }),
    roomNotFound: pickLocaleText(locale, { zhCN: '所选房间不存在。', zhTW: '所選房間不存在。', enUS: 'The selected room does not exist.' }),
    roomMismatch: pickLocaleText(locale, { zhCN: '请选择当前家庭下的房间。', zhTW: '請選擇目前家庭下的房間。', enUS: 'Select a room that belongs to the current household.' }),
    discoveryClaimed: pickLocaleText(locale, { zhCN: '这台音箱已经被其他家庭添加。', zhTW: '這台音箱已被其他家庭加入。', enUS: 'This speaker has already been claimed by another household.' }),
    loadDiscoveryFailed: pickLocaleText(locale, { zhCN: '新音箱列表加载失败', zhTW: '新音箱列表載入失敗', enUS: 'Failed to load new speaker discoveries' }),
    loadVoiceprintFailed: pickLocaleText(locale, { zhCN: '声纹状态加载失败', zhTW: '聲紋狀態載入失敗', enUS: 'Failed to load voiceprint status' }),
    loadIntegrationFailed: pickLocaleText(locale, { zhCN: '集成数据加载失败', zhTW: '整合資料載入失敗', enUS: 'Failed to load integration data' }),
    loadEnrollmentFailed: pickLocaleText(locale, { zhCN: '录入进度加载失败', zhTW: '錄入進度載入失敗', enUS: 'Failed to load enrollment progress' }),
    actionFailed: pickLocaleText(locale, { zhCN: '操作失败', zhTW: '操作失敗', enUS: 'Action failed' }),
    saveHaSuccess: pickLocaleText(locale, { zhCN: '当前家庭的 Home Assistant 配置已保存', zhTW: '目前家庭的 Home Assistant 設定已儲存', enUS: 'Home Assistant settings for this household have been saved' }),
    selectHousehold: pickLocaleText(locale, { zhCN: '还没有选中家庭。', zhTW: '尚未選取家庭。', enUS: 'No household is selected yet.' }),
    loadHaDevicesFailed: pickLocaleText(locale, { zhCN: '加载 HA 设备候选项失败', zhTW: '載入 HA 裝置候選項失敗', enUS: 'Failed to load HA device candidates' }),
    importHaDevicesSuccess: (count: number) => pickLocaleText(locale, {
      zhCN: `已从 Home Assistant 导入 ${count} 台设备。`,
      zhTW: `已從 Home Assistant 匯入 ${count} 台裝置。`,
      enUS: `Imported ${count} devices from Home Assistant.`,
    }),
    loadHaRoomsFailed: pickLocaleText(locale, { zhCN: '加载 HA 房间候选项失败', zhTW: '載入 HA 房間候選項失敗', enUS: 'Failed to load HA room candidates' }),
    importHaRoomsSuccess: (count: number) => pickLocaleText(locale, {
      zhCN: `已从 Home Assistant 导入 ${count} 个房间。`,
      zhTW: `已從 Home Assistant 匯入 ${count} 個房間。`,
      enUS: `Imported ${count} rooms from Home Assistant.`,
    }),
    saveDeviceSuccess: pickLocaleText(locale, { zhCN: '设备设置已保存', zhTW: '裝置設定已儲存', enUS: 'Device settings saved' }),
    saveSpeakerSuccess: pickLocaleText(locale, { zhCN: '音箱设置已保存', zhTW: '音箱設定已儲存', enUS: 'Speaker settings saved' }),
    saveSpeakerFailed: pickLocaleText(locale, { zhCN: '音箱设置保存失败', zhTW: '音箱設定儲存失敗', enUS: 'Failed to save speaker settings' }),
    saveVoiceprintSwitchFailed: pickLocaleText(locale, { zhCN: '设备级声纹开关保存失败', zhTW: '裝置層級聲紋開關儲存失敗', enUS: 'Failed to save the device voiceprint switch' }),
    createEnrollmentFailed: pickLocaleText(locale, { zhCN: '建档任务创建失败', zhTW: '建檔任務建立失敗', enUS: 'Failed to create the enrollment task' }),
    deviceNameRequired: pickLocaleText(locale, { zhCN: '请先填写设备名称。', zhTW: '請先填寫裝置名稱。', enUS: 'Enter a device name first.' }),
    roomRequired: pickLocaleText(locale, { zhCN: '请先选择所在房间。', zhTW: '請先選擇所在房間。', enUS: 'Select a room first.' }),
    claimSpeakerSuccess: pickLocaleText(locale, { zhCN: '新音箱已经添加到当前家庭。', zhTW: '新音箱已加入目前家庭。', enUS: 'The new speaker has been added to the current household.' }),
    claimSpeakerFailed: pickLocaleText(locale, { zhCN: '添加音箱失败', zhTW: '新增音箱失敗', enUS: 'Failed to add the speaker' }),
    deviceTypeLight: pickLocaleText(locale, { zhCN: '灯光', zhTW: '燈光', enUS: 'Light' }),
    deviceTypeAc: pickLocaleText(locale, { zhCN: '温控', zhTW: '溫控', enUS: 'Climate' }),
    deviceTypeCurtain: pickLocaleText(locale, { zhCN: '窗帘', zhTW: '窗簾', enUS: 'Curtain' }),
    deviceTypeSpeaker: pickLocaleText(locale, { zhCN: '音箱', zhTW: '音箱', enUS: 'Speaker' }),
    deviceTypeCamera: pickLocaleText(locale, { zhCN: '安防', zhTW: '安防', enUS: 'Security' }),
    deviceTypeSensor: pickLocaleText(locale, { zhCN: '传感器', zhTW: '感測器', enUS: 'Sensor' }),
    deviceTypeLock: pickLocaleText(locale, { zhCN: '门锁', zhTW: '門鎖', enUS: 'Lock' }),
    online: pickLocaleText(locale, { zhCN: '在线', zhTW: '在線', enUS: 'Online' }),
    recentlyOnline: pickLocaleText(locale, { zhCN: '最近在线', zhTW: '最近在線', enUS: 'Recently online' }),
    haUnconfigured: pickLocaleText(locale, { zhCN: '未配置', zhTW: '未設定', enUS: 'Not configured' }),
    haHealthy: pickLocaleText(locale, { zhCN: '已连接', zhTW: '已連線', enUS: 'Connected' }),
    haDegraded: pickLocaleText(locale, { zhCN: '部分可用', zhTW: '部分可用', enUS: 'Partially available' }),
    haOffline: pickLocaleText(locale, { zhCN: '暂时连不上', zhTW: '暫時無法連線', enUS: 'Currently unreachable' }),
    haChecking: pickLocaleText(locale, { zhCN: '等待检查', zhTW: '等待檢查', enUS: 'Waiting for check' }),
    justNow: pickLocaleText(locale, { zhCN: '刚刚', zhTW: '剛剛', enUS: 'Just now' }),
    currentStatusLoaded: pickLocaleText(locale, { zhCN: '已加载当前状态', zhTW: '已載入目前狀態', enUS: 'Current status loaded' }),
    noRecord: pickLocaleText(locale, { zhCN: '暂无记录', zhTW: '暫無紀錄', enUS: 'No records yet' }),
    connectHaFirst: pickLocaleText(locale, { zhCN: '请先连接 Home Assistant', zhTW: '請先連接 Home Assistant', enUS: 'Connect Home Assistant first' }),
    importing: pickLocaleText(locale, { zhCN: '导入中...', zhTW: '匯入中...', enUS: 'Importing...' }),
    importDevices: pickLocaleText(locale, { zhCN: '导入设备', zhTW: '匯入裝置', enUS: 'Import devices' }),
    importRooms: pickLocaleText(locale, { zhCN: '导入房间', zhTW: '匯入房間', enUS: 'Import rooms' }),
    finishHaConnectionFirst: pickLocaleText(locale, { zhCN: '先完成 Home Assistant 连接设置', zhTW: '請先完成 Home Assistant 連線設定', enUS: 'Finish the Home Assistant connection setup first' }),
  };

  const getDefaultVoiceDiscoveryDraft = () => ({ terminal_name: copy.defaultSpeakerName, room_id: rooms[0]?.id ?? '' });
  const mergeVoiceDiscoveryDrafts = (items: VoiceDiscoveryTerminal[], previous: Record<string, { terminal_name: string; room_id: string }>) => Object.fromEntries(items.map((item) => [item.fingerprint, { ...getDefaultVoiceDiscoveryDraft(), ...previous[item.fingerprint] }]));
  const normalizeVoiceDiscoveryErrorMessage = (message: string) => {
    if (message === 'voice discovery not found') return copy.discoveryNotFound;
    if (message === 'room not found') return copy.roomNotFound;
    if (message === 'room must belong to the same household') return copy.roomMismatch;
    if (message === 'voice terminal already claimed by another household') return copy.discoveryClaimed;
    return message;
  };

  async function loadVoiceDiscoveries(householdId: string, options?: { silent?: boolean }) {
    try {
      const result = await settingsApi.listVoiceTerminalDiscoveries(householdId);
      setVoiceDiscoveries(result.items);
      setVoiceDiscoveryDrafts((current) => mergeVoiceDiscoveryDrafts(result.items, current));
      if (!options?.silent) setVoiceDiscoveryError('');
    } catch (loadError) {
      if (!options?.silent) setVoiceDiscoveryError(loadError instanceof Error ? normalizeVoiceDiscoveryErrorMessage(loadError.message) : copy.loadDiscoveryFailed);
    }
  }

  async function loadVoiceprintSummary(terminalId: string, options?: { silent?: boolean }) {
    if (!currentHouseholdId) return;
    try {
      setVoiceprintLoading(true);
      const result = await settingsApi.getHouseholdVoiceprintSummary(currentHouseholdId, terminalId);
      setVoiceprintSummary(result);
      if (!options?.silent) setVoiceprintError('');
    } catch (loadError) {
      if (!options?.silent) {
        setVoiceprintError(loadError instanceof Error ? loadError.message : copy.loadVoiceprintFailed);
      }
    } finally {
      setVoiceprintLoading(false);
    }
  }

  function closeSpeakerDetail() {
    setSpeakerDetailDeviceId(null);
    setSpeakerSettingsError('');
    setVoiceprintSummary(null);
    setVoiceprintError('');
    setVoiceprintWizard(null);
    setVoiceprintWizardEnrollment(null);
    setVoiceprintWizardBusy(false);
  }

  useEffect(() => {
    if (!currentHouseholdId) {
      setOverview(null); setDevices([]); setRooms([]); setVoiceDiscoveries([]); setVoiceDiscoveryDrafts({}); setVoiceDiscoveryError('');
      setVoiceprintSummary(null); setVoiceprintError(''); setVoiceprintWizard(null); setVoiceprintWizardEnrollment(null);
      return;
    }
    let cancelled = false;
    async function loadData() {
      setLoading(true); setError('');
      const [configResult, devicesResult, roomsResult] = await Promise.allSettled([
        settingsApi.getHomeAssistantConfig(currentHouseholdId),
        settingsApi.listDevices(currentHouseholdId),
        settingsApi.listRooms(currentHouseholdId),
      ]);
      if (cancelled) return;
      const nextConfig = configResult.status === 'fulfilled' ? configResult.value : null;
      const nextDevices = devicesResult.status === 'fulfilled' ? devicesResult.value.items : [];
      const nextRooms = roomsResult.status === 'fulfilled' ? roomsResult.value.items : [];
      setDevices(nextDevices); setRooms(nextRooms); setHaConfig(nextConfig);
      setHaForm({ base_url: nextConfig?.base_url ?? '', access_token: '', sync_rooms_enabled: nextConfig?.sync_rooms_enabled ?? false, clear_access_token: false });
      setDeviceDrafts(Object.fromEntries(nextDevices.map((device) => [device.id, { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable }])));
      await loadVoiceDiscoveries(currentHouseholdId);
      const hasHaConfig = Boolean(nextConfig?.base_url && nextConfig?.token_configured);
      if (hasHaConfig) {
        const overviewResult = await settingsApi.getContextOverview(currentHouseholdId).then((value) => ({ status: 'fulfilled' as const, value }), (reason) => ({ status: 'rejected' as const, reason }));
        if (cancelled) return;
        setOverview(overviewResult.status === 'fulfilled' ? overviewResult.value : null);
        setError([configResult, devicesResult, roomsResult, overviewResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : copy.loadIntegrationFailed).join('；'));
      } else {
        setOverview(null);
        setError([configResult, devicesResult, roomsResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : copy.loadIntegrationFailed).join('；'));
      }
      setLoading(false);
    }
    void loadData();
    return () => { cancelled = true; };
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId) return;
    const timer = window.setInterval(() => { void loadVoiceDiscoveries(currentHouseholdId, { silent: true }); }, 5000);
    return () => window.clearInterval(timer);
  }, [currentHouseholdId]);

  useEffect(() => {
    if (rooms.length === 0) return;
    setVoiceDiscoveryDrafts((current) => Object.fromEntries(Object.entries(current).map(([fingerprint, draft]) => [fingerprint, { ...draft, room_id: draft.room_id || rooms[0].id }])));
  }, [rooms]);

  useEffect(() => {
    if (!currentHouseholdId || !speakerDetailDeviceId) {
      setVoiceprintSummary(null);
      setVoiceprintError('');
      return;
    }
    void loadVoiceprintSummary(speakerDetailDeviceId);
  }, [currentHouseholdId, speakerDetailDeviceId]);

  useEffect(() => {
    if (!voiceprintWizard || voiceprintWizard.step !== 'waiting' || !voiceprintWizard.enrollmentId || !speakerDetailDeviceId) {
      return;
    }
    const activeEnrollmentId = voiceprintWizard.enrollmentId;
    const activeDeviceId = speakerDetailDeviceId;
    let cancelled = false;
    let timerId: number | undefined;

    async function pollEnrollment() {
      try {
        const enrollment = await settingsApi.getVoiceprintEnrollment(activeEnrollmentId);
        if (cancelled) return;
        setVoiceprintWizardEnrollment(enrollment);
        setVoiceprintWizard((current) => current ? getNextWizardStateFromEnrollment(current, enrollment) : current);
        if (enrollment.status === 'completed' || enrollment.status === 'failed' || enrollment.status === 'cancelled') {
          await reloadWorkspace();
          await loadVoiceprintSummary(activeDeviceId, { silent: true });
          return;
        }
      } catch (pollError) {
        if (cancelled) return;
        setVoiceprintWizard((current) => current ? { ...current, step: 'failed', error: pollError instanceof Error ? pollError.message : copy.loadEnrollmentFailed } : current);
        return;
      }
      if (!cancelled) {
        timerId = window.setTimeout(() => { void pollEnrollment(); }, 3000);
      }
    }

    void pollEnrollment();
    return () => {
      cancelled = true;
      if (typeof timerId === 'number') {
        window.clearTimeout(timerId);
      }
    };
  }, [speakerDetailDeviceId, voiceprintWizard?.enrollmentId, voiceprintWizard?.step]);

  async function reloadWorkspace() {
    if (!currentHouseholdId) return;
    const [config, nextDevices, nextRooms] = await Promise.all([settingsApi.getHomeAssistantConfig(currentHouseholdId), settingsApi.listDevices(currentHouseholdId), settingsApi.listRooms(currentHouseholdId)]);
    setHaConfig(config);
    setHaForm({ base_url: config.base_url ?? '', access_token: '', sync_rooms_enabled: config.sync_rooms_enabled, clear_access_token: false });
    setOverview(config.base_url && config.token_configured ? await settingsApi.getContextOverview(currentHouseholdId).catch(() => null) : null);
    setDevices(nextDevices.items); setRooms(nextRooms.items);
    setDeviceDrafts(Object.fromEntries(nextDevices.items.map((device) => [device.id, { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable }])));
    await loadVoiceDiscoveries(currentHouseholdId, { silent: true });
  }

  async function runAction(action: () => Promise<void>) {
    setLoading(true); setStatus(''); setError('');
    try { await action(); } catch (actionError) { setError(actionError instanceof Error ? actionError.message : copy.actionFailed); } finally { setLoading(false); }
  }

  async function handleSaveHaConfig(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.updateHomeAssistantConfig(currentHouseholdId, { base_url: haForm.base_url.trim() || null, access_token: haForm.access_token.trim() || undefined, clear_access_token: haForm.clear_access_token, sync_rooms_enabled: haForm.sync_rooms_enabled });
      setHaConfig(result);
      setHaForm({ base_url: result.base_url ?? '', access_token: '', sync_rooms_enabled: result.sync_rooms_enabled, clear_access_token: false });
      setConfigModalOpen(false); setStatus(copy.saveHaSuccess);
    });
  }

  async function openDeviceSyncModal() {
    if (!currentHouseholdId) { setError(copy.selectHousehold); return; }
    setDeviceModalLoading(true); setError('');
    try {
      const result = await settingsApi.listHomeAssistantDeviceCandidates(currentHouseholdId);
      setDeviceCandidates(result.items); setSelectedExternalDeviceIds(result.items.map((item) => item.external_device_id)); setDeviceModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : copy.loadHaDevicesFailed);
    } finally { setDeviceModalLoading(false); }
  }

  async function handleConfirmDeviceSync() {
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.syncSelectedHomeAssistantDevices(currentHouseholdId, selectedExternalDeviceIds);
      setSyncSummary(result); setDeviceModalOpen(false); await reloadWorkspace(); setStatus(copy.importHaDevicesSuccess(result.created_devices + result.updated_devices));
    });
  }

  async function openRoomSyncModal() {
    if (!currentHouseholdId) { setError(copy.selectHousehold); return; }
    setRoomModalLoading(true); setError('');
    try {
      const result = await settingsApi.listHomeAssistantRoomCandidates(currentHouseholdId);
      setRoomCandidates(result.items); setSelectedRoomNames(result.items.filter((item) => item.can_sync).map((item) => item.name)); setRoomModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : copy.loadHaRoomsFailed);
    } finally { setRoomModalLoading(false); }
  }

  async function handleConfirmRoomSync() {
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.syncSelectedHomeAssistantRooms(currentHouseholdId, selectedRoomNames);
      setRoomSyncSummary(result); setRoomModalOpen(false); await reloadWorkspace(); setStatus(copy.importHaRoomsSuccess(result.created_rooms));
    });
  }

  function toggleRoomSelection(roomName: string) { setSelectedRoomNames((current) => current.includes(roomName) ? current.filter((item) => item !== roomName) : [...current, roomName]); }
  function toggleDeviceSelection(externalDeviceId: string) { setSelectedExternalDeviceIds((current) => current.includes(externalDeviceId) ? current.filter((item) => item !== externalDeviceId) : [...current, externalDeviceId]); }
  function toggleDeviceRoomSelection(deviceIds: string[]) { setSelectedExternalDeviceIds((current) => deviceIds.every((id) => current.includes(id)) ? current.filter((id) => !deviceIds.includes(id)) : Array.from(new Set([...current, ...deviceIds]))); }
  async function handleSaveDevice(deviceId: string) { const draft = deviceDrafts[deviceId]; if (!draft) return; await runAction(async () => { await settingsApi.updateDevice(deviceId, draft); await reloadWorkspace(); setStatus(copy.saveDeviceSuccess); }); }
  function openSpeakerSettings(device: Device) { setSpeakerSettingsError(''); setSpeakerDetailDeviceId(device.id); }
  async function handleSaveSpeakerSettings(payload: { voice_auto_takeover_enabled: boolean; voice_takeover_prefixes: string[] }) {
    if (!speakerDetailDeviceId) return;
    setLoading(true); setStatus(''); setError(''); setSpeakerSettingsError('');
    try {
      await settingsApi.updateDevice(speakerDetailDeviceId, payload);
      await reloadWorkspace();
      setStatus(copy.saveSpeakerSuccess);
    } catch (actionError) {
      setSpeakerSettingsError(actionError instanceof Error ? actionError.message : copy.saveSpeakerFailed);
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleVoiceprintEnabled(nextValue: boolean) {
    if (!speakerDetailDeviceId) return;
    const previousSummary = voiceprintSummary;
    setVoiceprintSwitchSaving(true);
    setVoiceprintError('');
    setVoiceprintSummary((current) => current ? {
      ...current,
      voiceprint_identity_enabled: nextValue,
      conversation_mode: nextValue ? 'voiceprint_member' : 'public',
    } : current);
    try {
      await settingsApi.updateDevice(speakerDetailDeviceId, { voiceprint_identity_enabled: nextValue });
      await reloadWorkspace();
      await loadVoiceprintSummary(speakerDetailDeviceId, { silent: true });
    } catch (actionError) {
      setVoiceprintSummary(previousSummary);
      setVoiceprintError(actionError instanceof Error ? actionError.message : copy.saveVoiceprintSwitchFailed);
    } finally {
      setVoiceprintSwitchSaving(false);
    }
  }

  function handleOpenVoiceprintWizard(memberId?: string) {
    if (actor?.member_role !== 'admin' || !voiceprintSummary || voiceprintSummary.members.length === 0) return;
    setVoiceprintWizardEnrollment(null);
    setVoiceprintWizard(createVoiceprintWizardState('create', memberId ?? null));
  }

  function handleOpenVoiceprintUpdateWizard(memberId: string) {
    if (actor?.member_role !== 'admin' || !voiceprintSummary) return;
    setVoiceprintWizardEnrollment(null);
    setVoiceprintWizard(createVoiceprintWizardState('update', memberId));
  }

  async function handleResumeVoiceprintEnrollment(enrollmentId: string, memberId: string) {
    if (actor?.member_role !== 'admin') return;
    setVoiceprintWizardBusy(true);
    setVoiceprintWizard(createVoiceprintWaitingWizardState(memberId, enrollmentId));
    try {
      const enrollment = await settingsApi.getVoiceprintEnrollment(enrollmentId);
      setVoiceprintWizardEnrollment(enrollment);
      setVoiceprintWizard((current) => current ? getNextWizardStateFromEnrollment(current, enrollment) : current);
    } catch (actionError) {
      setVoiceprintWizard((current) => current ? {
        ...current,
        step: 'failed',
        error: actionError instanceof Error ? actionError.message : copy.loadEnrollmentFailed,
      } : current);
    } finally {
      setVoiceprintWizardBusy(false);
    }
  }

  function handleVoiceprintWizardContinue() {
    setVoiceprintWizard((current) => current && current.memberId ? { ...current, step: 'confirm', error: '' } : current);
  }

  function handleVoiceprintWizardBack() {
    setVoiceprintWizard((current) => {
      if (!current || current.lockedMemberId) return current;
      return { ...current, step: 'select_member', error: '' };
    });
  }

  async function handleSubmitVoiceprintWizard() {
    if (!voiceprintWizard?.memberId || !speakerDetailDeviceId || !currentHouseholdId) return;
    setVoiceprintWizardBusy(true);
    setVoiceprintWizard((current) => current ? { ...current, step: 'creating', error: '' } : current);
    try {
      const enrollment = await settingsApi.createVoiceprintEnrollment({
        household_id: currentHouseholdId,
        member_id: voiceprintWizard.memberId,
        terminal_id: speakerDetailDeviceId,
        sample_goal: 3,
      });
      setVoiceprintWizardEnrollment(enrollment);
      setVoiceprintWizard((current) => current ? getNextWizardStateFromEnrollment({ ...current, enrollmentId: enrollment.id }, enrollment) : current);
      await loadVoiceprintSummary(speakerDetailDeviceId, { silent: true });
    } catch (actionError) {
      setVoiceprintWizard((current) => current ? {
        ...current,
        step: 'failed',
        error: actionError instanceof Error ? actionError.message : copy.createEnrollmentFailed,
      } : current);
    } finally {
      setVoiceprintWizardBusy(false);
    }
  }

  function updateVoiceDiscoveryDraft(fingerprint: string, patch: Partial<{ terminal_name: string; room_id: string }>) { setVoiceDiscoveryDrafts((current) => ({ ...current, [fingerprint]: { terminal_name: current[fingerprint]?.terminal_name ?? copy.defaultSpeakerName, room_id: current[fingerprint]?.room_id ?? (rooms[0]?.id ?? ''), ...patch } })); }
  function getVoiceDiscoveryDraft(fingerprint: string) { const draft = voiceDiscoveryDrafts[fingerprint]; return draft ? { terminal_name: draft.terminal_name || copy.defaultSpeakerName, room_id: draft.room_id || rooms[0]?.id || '' } : getDefaultVoiceDiscoveryDraft(); }
  async function handleClaimVoiceDiscovery(fingerprint: string) {
    const draft = getVoiceDiscoveryDraft(fingerprint);
    if (!currentHouseholdId) { setVoiceDiscoveryError(copy.selectHousehold); return; }
    if (!draft.terminal_name.trim()) { setVoiceDiscoveryError(copy.deviceNameRequired); return; }
    if (!draft.room_id) { setVoiceDiscoveryError(copy.roomRequired); return; }
    setVoiceClaimingFingerprint(fingerprint); setVoiceDiscoveryError('');
    try {
      await settingsApi.claimVoiceTerminalDiscovery(fingerprint, { household_id: currentHouseholdId, room_id: draft.room_id, terminal_name: draft.terminal_name.trim() });
      await reloadWorkspace(); setStatus(copy.claimSpeakerSuccess);
    } catch (claimError) {
      setVoiceDiscoveryError(claimError instanceof Error ? normalizeVoiceDiscoveryErrorMessage(claimError.message) : copy.claimSpeakerFailed);
    } finally { setVoiceClaimingFingerprint(null); }
  }

  const roomNameMap = useMemo(() => Object.fromEntries(rooms.map((room) => [room.id, room.name])), [rooms]);
  const roomOptions = useMemo(() => [{ id: '', name: copy.roomUnassigned }, ...rooms.map((room) => ({ id: room.id, name: room.name }))], [copy.roomUnassigned, rooms]);
  const deviceCandidateGroups = useMemo(() => Array.from(deviceCandidates.reduce((map, candidate) => map.set(candidate.room_name || copy.roomUnassigned, [...(map.get(candidate.room_name || copy.roomUnassigned) ?? []), candidate]), new Map<string, HomeAssistantDeviceCandidate[]>()).entries()).map(([roomName, items]) => ({ roomName, items })).sort((left, right) => left.roomName.localeCompare(right.roomName, resolveDateLocale(locale))), [copy.roomUnassigned, deviceCandidates, locale]);
  const formatDeviceType = (type: Device['device_type']) => ({ light: copy.deviceTypeLight, ac: copy.deviceTypeAc, curtain: copy.deviceTypeCurtain, speaker: copy.deviceTypeSpeaker, camera: copy.deviceTypeCamera, sensor: copy.deviceTypeSensor, lock: copy.deviceTypeLock }[type] ?? type);
  const formatVoiceDiscoveryStatus = (value: VoiceDiscoveryTerminal['connection_status']) => value === 'online' ? copy.online : copy.recentlyOnline;
  const formatVoiceDiscoveryTime = (value: string) => Number.isNaN(new Date(value).getTime()) ? value : new Date(value).toLocaleString(resolveDateLocale(locale), { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const formatVoiceDiscoverySerial = (sn: string) => sn.trim().length <= 4 ? sn.trim() : sn.trim().slice(-4);
  const formatHaStatus = (config: HomeAssistantConfig | null, statusValue: ContextOverviewRead['home_assistant_status'] | undefined) => !config?.base_url || !config?.token_configured ? { label: copy.haUnconfigured, tone: 'idle' as const } : statusValue === 'healthy' ? { label: copy.haHealthy, tone: 'online' as const } : statusValue === 'degraded' ? { label: copy.haDegraded, tone: 'warning' as const } : statusValue === 'offline' ? { label: copy.haOffline, tone: 'offline' as const } : { label: copy.haChecking, tone: 'warning' as const };
  const haStatus = formatHaStatus(haConfig, overview?.home_assistant_status);
  const lastSyncText = syncSummary ? copy.justNow : haConfig?.last_device_sync_at ?? (overview ? copy.currentStatusLoaded : copy.noRecord);
  const haAddressText = haConfig?.base_url ?? copy.haUnconfigured;
  const canOperateHa = Boolean(haConfig?.base_url && haConfig?.token_configured);
  const syncButtonLabel = canOperateHa ? (loading ? copy.importing : copy.importDevices) : copy.connectHaFirst;
  const syncRoomsButtonLabel = canOperateHa ? copy.importRooms : copy.connectHaFirst;
  const disabledHaActionTooltip = canOperateHa ? undefined : copy.finishHaConnectionFirst;
  const canManageVoiceprint = actor?.member_role === 'admin';
  const speakerDetailDevice = useMemo(
    () => devices.find((device) => device.id === speakerDetailDeviceId) ?? null,
    [devices, speakerDetailDeviceId],
  );

  return (
    <SettingsPageShell activeKey="integrations">
      <div className="settings-page">
        <Section title={pickLocaleText(locale, { zhCN: 'Home Assistant 连接', zhTW: 'Home Assistant 連線', enUS: 'Home Assistant connection' })}>
          <Card className="integration-status-card">
            <div className="integration-status">
              <span className={`integration-status__indicator integration-status__indicator--${haStatus.tone}`} />
              <div className="integration-status__text">
                <span className="integration-status__label">Home Assistant</span>
                <span className="integration-status__detail">{pickLocaleText(locale, {
                  zhCN: `连接状态：${haStatus.label} · 最近同步：${lastSyncText}`,
                  zhTW: `連線狀態：${haStatus.label} · 最近同步：${lastSyncText}`,
                  enUS: `Status: ${haStatus.label} · Last sync: ${lastSyncText}`,
                })}</span>
                <span className="integration-status__detail">{pickLocaleText(locale, {
                  zhCN: `连接地址：${haAddressText}`,
                  zhTW: `連線位址：${haAddressText}`,
                  enUS: `Address: ${haAddressText}`,
                })}</span>
              </div>
              <div className="integration-actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(true)} disabled={loading}>{pickLocaleText(locale, { zhCN: '连接设置', zhTW: '連線設定', enUS: 'Connection settings' })}</button>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openDeviceSyncModal} disabled={loading || deviceModalLoading || !canOperateHa}>{syncButtonLabel}</button></span>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openRoomSyncModal} disabled={loading || roomModalLoading || !canOperateHa}>{syncRoomsButtonLabel}</button></span>
              </div>
            </div>
            {syncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>{pickLocaleText(locale, {
              zhCN: `这次导入新增了 ${syncSummary.created_devices} 台设备，更新了 ${syncSummary.updated_devices} 台设备，为 ${syncSummary.assigned_rooms} 台设备补上了房间；另有 ${syncSummary.failed_entities} 项没有导入成功。`,
              zhTW: `這次匯入新增了 ${syncSummary.created_devices} 台裝置，更新了 ${syncSummary.updated_devices} 台裝置，為 ${syncSummary.assigned_rooms} 台裝置補上了房間；另有 ${syncSummary.failed_entities} 項沒有匯入成功。`,
              enUS: `This import added ${syncSummary.created_devices} devices, updated ${syncSummary.updated_devices} devices, filled room assignments for ${syncSummary.assigned_rooms} devices, and left ${syncSummary.failed_entities} entities not imported.`,
            })}</div> : null}
            {roomSyncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{pickLocaleText(locale, {
              zhCN: `这次导入了 ${roomSyncSummary.created_rooms} 个房间，识别到 ${roomSyncSummary.matched_entities} 项关联内容，跳过了 ${roomSyncSummary.skipped_entities} 项重复内容。`,
              zhTW: `這次匯入了 ${roomSyncSummary.created_rooms} 個房間，識別到 ${roomSyncSummary.matched_entities} 項關聯內容，跳過了 ${roomSyncSummary.skipped_entities} 項重複內容。`,
              enUS: `This import added ${roomSyncSummary.created_rooms} rooms, matched ${roomSyncSummary.matched_entities} related items, and skipped ${roomSyncSummary.skipped_entities} duplicates.`,
            })}</div> : null}
            {status ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{status}</div> : null}
            {error ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{error}</div> : null}
          </Card>
        </Section>

        <Section title={pickLocaleText(locale, { zhCN: '待添加的音箱', zhTW: '待新增的音箱', enUS: 'Pending speakers' })}>
          <Card className="integration-status-card">
            <div className="integration-status" style={{ alignItems: 'flex-start' }}>
              <div className="integration-status__text">
                <span className="integration-status__label">{pickLocaleText(locale, { zhCN: '自动发现', zhTW: '自動發現', enUS: 'Auto discovery' })}</span>
                <span className="integration-status__detail">{pickLocaleText(locale, {
                  zhCN: '系统会持续查找同一局域网里的可接入音箱。填好名称和房间后，就能把它加入当前家庭。',
                  zhTW: '系統會持續查找同一區域網路裡可接入的音箱。填好名稱和房間後，就能把它加入目前家庭。',
                  enUS: 'The system continuously looks for speakers on the same local network. Fill in the name and room to add one to the current household.',
                })}</span>
                <span className="integration-status__detail">{pickLocaleText(locale, {
                  zhCN: '如果这里一直没有结果，先确认音箱和当前服务连的是同一个局域网。',
                  zhTW: '如果這裡一直沒有結果，先確認音箱和目前服務連的是同一個區域網路。',
                  enUS: 'If nothing appears here, first make sure the speaker and this service are on the same local network.',
                })}</span>
              </div>
            </div>
            {voiceDiscoveryError ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>{voiceDiscoveryError}</div> : null}
            <div className="device-list" style={{ marginTop: '1rem' }}>
              {voiceDiscoveries.length === 0 ? (
                <div className="integration-status__detail">{pickLocaleText(locale, { zhCN: '暂时还没有发现可添加的音箱。', zhTW: '暫時還沒有發現可新增的音箱。', enUS: 'No addable speakers have been discovered yet.' })}</div>
              ) : voiceDiscoveries.map((item) => {
                const draft = getVoiceDiscoveryDraft(item.fingerprint);
                const isClaiming = voiceClaimingFingerprint === item.fingerprint;
                return (
                  <Card key={item.fingerprint} className="device-card device-card--editor">
                    <div className="device-card__editor-grid">
                      <div className="device-card__info">
                        <span className="device-card__name">{item.model}</span>
                        <span className="device-card__room">{pickLocaleText(locale, {
                          zhCN: `设备尾号 ${formatVoiceDiscoverySerial(item.sn)} · ${formatVoiceDiscoveryStatus(item.connection_status)} · 最近出现于 ${formatVoiceDiscoveryTime(item.last_seen_at)}`,
                          zhTW: `裝置尾號 ${formatVoiceDiscoverySerial(item.sn)} · ${formatVoiceDiscoveryStatus(item.connection_status)} · 最近出現於 ${formatVoiceDiscoveryTime(item.last_seen_at)}`,
                          enUS: `Serial ending ${formatVoiceDiscoverySerial(item.sn)} · ${formatVoiceDiscoveryStatus(item.connection_status)} · Last seen at ${formatVoiceDiscoveryTime(item.last_seen_at)}`,
                        })}</span>
                      </div>
                      <input className="form-input" value={draft.terminal_name} placeholder={pickLocaleText(locale, { zhCN: '例如：客厅音箱', zhTW: '例如：客廳音箱', enUS: 'For example: living room speaker' })} onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { terminal_name: event.target.value })} />
                      <select className="form-select" value={draft.room_id} onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { room_id: event.target.value })} disabled={rooms.length === 0}>
                        {rooms.length === 0 ? <option value="">{pickLocaleText(locale, { zhCN: '请先创建房间', zhTW: '請先建立房間', enUS: 'Create a room first' })}</option> : rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
                      </select>
                    </div>
                    <div className="device-card__actions">
                      <span className={`badge badge--${item.connection_status === 'online' ? 'success' : 'secondary'}`}>{formatVoiceDiscoveryStatus(item.connection_status)}</span>
                      <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleClaimVoiceDiscovery(item.fingerprint)} disabled={isClaiming || rooms.length === 0}>{isClaiming ? pickLocaleText(locale, { zhCN: '添加中...', zhTW: '新增中...', enUS: 'Adding...' }) : pickLocaleText(locale, { zhCN: '加入家庭', zhTW: '加入家庭', enUS: 'Add to household' })}</button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>
        </Section>

        <Section title={pickLocaleText(locale, { zhCN: '设备列表', zhTW: '裝置列表', enUS: 'Devices' })}>
          <div className="device-list">
            {loading && devices.length === 0 ? <div className="text-text-secondary">{pickLocaleText(locale, { zhCN: '正在加载设备列表...', zhTW: '正在載入裝置列表...', enUS: 'Loading devices...' })}</div> : devices.map((device) => {
              const draft = deviceDrafts[device.id] ?? { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable };
              const supportsVoiceSettings = device.device_type === 'speaker' && device.vendor === 'xiaomi';
              return (
                <Card key={device.id} className="device-card device-card--editor">
                  <div className="device-card__editor-grid">
                    <div className="device-card__info">
                      <span className="device-card__name">{device.name}</span>
                      <span className="device-card__room">{roomNameMap[device.room_id ?? ''] ?? copy.roomUnassigned} · {formatDeviceType(device.device_type)}</span>
                      {supportsVoiceSettings ? <span className="integration-status__detail">{device.voice_auto_takeover_enabled ? pickLocaleText(locale, { zhCN: '当前接管方式：默认响应所有语音请求', zhTW: '目前接管方式：預設回應所有語音請求', enUS: 'Current takeover mode: respond to all voice requests by default' }) : pickLocaleText(locale, {
                        zhCN: `当前接管方式：只响应以 ${device.voice_takeover_prefixes.join('、')} 开头的话`,
                        zhTW: `目前接管方式：只回應以 ${device.voice_takeover_prefixes.join('、')} 開頭的話`,
                        enUS: `Current takeover mode: only respond to phrases starting with ${device.voice_takeover_prefixes.join(', ')}`,
                      })}</span> : null}
                    </div>
                    <input className="form-input" value={draft.name} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, name: event.target.value } }))} />
                    <select className="form-select" value={draft.room_id ?? ''} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, room_id: event.target.value || null } }))}>{roomOptions.map((option) => <option key={option.id || 'unassigned'} value={option.id}>{option.name}</option>)}</select>
                    <select className="form-select" value={draft.status} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, status: event.target.value as Device['status'] } }))}><option value="active">{copy.online}</option><option value="offline">{pickLocaleText(locale, { zhCN: '离线', zhTW: '離線', enUS: 'Offline' })}</option><option value="inactive">{pickLocaleText(locale, { zhCN: '未启用', zhTW: '未啟用', enUS: 'Inactive' })}</option></select>
                    <select className="form-select" value={draft.controllable ? 'true' : 'false'} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, controllable: event.target.value === 'true' } }))}><option value="true">{pickLocaleText(locale, { zhCN: '可控制', zhTW: '可控制', enUS: 'Controllable' })}</option><option value="false">{pickLocaleText(locale, { zhCN: '只读', zhTW: '唯讀', enUS: 'Read-only' })}</option></select>
                  </div>
                  <div className="device-card__actions">
                    <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>{device.status === 'active' ? copy.online : device.status === 'offline' ? pickLocaleText(locale, { zhCN: '离线', zhTW: '離線', enUS: 'Offline' }) : pickLocaleText(locale, { zhCN: '未启用', zhTW: '未啟用', enUS: 'Inactive' })}</span>
                    {supportsVoiceSettings ? <button className="btn btn--outline btn--sm" type="button" onClick={() => openSpeakerSettings(device)} disabled={loading}>{pickLocaleText(locale, { zhCN: '更多设置', zhTW: '更多設定', enUS: 'More settings' })}</button> : null}
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSaveDevice(device.id)} disabled={loading}>{pickLocaleText(locale, { zhCN: '保存修改', zhTW: '儲存修改', enUS: 'Save changes' })}</button>
                  </div>
                </Card>
              );
            })}
          </div>
        </Section>
        {speakerDetailDevice ? (
          <SpeakerDeviceDetailDialog
            device={speakerDetailDevice}
            roomName={roomNameMap[speakerDetailDevice.room_id ?? ''] ?? copy.roomUnassigned}
            saving={loading}
            error={speakerSettingsError}
            voiceprintTab={(
              <SpeakerVoiceprintTab
                device={speakerDetailDevice}
                canManage={canManageVoiceprint}
                summary={voiceprintSummary}
                loading={voiceprintLoading}
                error={voiceprintError}
                switchSaving={voiceprintSwitchSaving}
                onRetry={() => void loadVoiceprintSummary(speakerDetailDevice.id)}
                onToggleVoiceprintEnabled={handleToggleVoiceprintEnabled}
                onStartEnrollment={handleOpenVoiceprintWizard}
                onUpdateVoiceprint={handleOpenVoiceprintUpdateWizard}
                onResumeEnrollment={(enrollmentId, memberId) => void handleResumeVoiceprintEnrollment(enrollmentId, memberId)}
              />
            )}
            onClose={closeSpeakerDetail}
            onSaveTakeover={handleSaveSpeakerSettings}
          />
        ) : null}
        {speakerDetailDevice && voiceprintWizard ? (
          <VoiceprintEnrollmentWizard
            wizard={voiceprintWizard}
            members={voiceprintSummary?.members ?? []}
            deviceName={speakerDetailDevice.name}
            enrollment={voiceprintWizardEnrollment}
            busy={voiceprintWizardBusy}
            onClose={() => { setVoiceprintWizard(null); setVoiceprintWizardEnrollment(null); }}
            onBack={handleVoiceprintWizardBack}
            onSelectMember={(memberId) => setVoiceprintWizard((current) => current ? { ...current, memberId, error: '' } : current)}
            onContinue={handleVoiceprintWizardContinue}
            onStart={handleSubmitVoiceprintWizard}
          />
        ) : null}
        {roomModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setRoomModalOpen(false)}>
            <div className="member-modal ha-room-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>{pickLocaleText(locale, { zhCN: '选择要导入的房间', zhTW: '選擇要匯入的房間', enUS: 'Choose rooms to import' })}</h3><p>{pickLocaleText(locale, {
                zhCN: '这里只会导入当前家庭里还没有的房间，已经同名的会自动跳过。',
                zhTW: '這裡只會匯入目前家庭裡還沒有的房間，已經同名的會自動跳過。',
                enUS: 'Only rooms that do not already exist in the current household will be imported. Rooms with the same name are skipped automatically.',
              })}</p></div></div>
              <div className="ha-room-modal__list">{roomCandidates.length === 0 ? <div className="integration-status__detail">{pickLocaleText(locale, { zhCN: 'HA 里没有可识别的房间。', zhTW: 'HA 裡沒有可識別的房間。', enUS: 'No recognizable rooms were found in HA.' })}</div> : roomCandidates.map((candidate) => (
                <label key={candidate.name} className={`ha-room-option ${candidate.can_sync ? '' : 'ha-room-option--disabled'}`}>
                  <input type="checkbox" checked={selectedRoomNames.includes(candidate.name)} disabled={!candidate.can_sync || loading} onChange={() => toggleRoomSelection(candidate.name)} />
                  <div className="ha-room-option__body"><div className="ha-room-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.can_sync ? 'success' : 'warning'}`}>{candidate.can_sync ? pickLocaleText(locale, { zhCN: '可导入', zhTW: '可匯入', enUS: 'Importable' }) : pickLocaleText(locale, { zhCN: '已存在', zhTW: '已存在', enUS: 'Already exists' })}</span></div><div className="integration-status__detail">{candidate.exists_locally ? pickLocaleText(locale, { zhCN: '当前家庭里已经有同名房间。', zhTW: '目前家庭裡已經有同名房間。', enUS: 'A room with the same name already exists in this household.' }) : pickLocaleText(locale, { zhCN: '导入后可直接给设备分配房间。', zhTW: '匯入後可直接替裝置分配房間。', enUS: 'Once imported, devices can be assigned to this room directly.' })}</div></div>
                </label>
              ))}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setRoomModalOpen(false)} disabled={loading}>{pickLocaleText(locale, { zhCN: '取消', zhTW: '取消', enUS: 'Cancel' })}</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmRoomSync()} disabled={loading || selectedRoomNames.length === 0}>{pickLocaleText(locale, { zhCN: '导入选中房间', zhTW: '匯入選中房間', enUS: 'Import selected rooms' })}</button></div>
            </div>
          </div>
        ) : null}
        {deviceModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setDeviceModalOpen(false)}>
            <div className="member-modal ha-device-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>{pickLocaleText(locale, { zhCN: '选择要导入的设备', zhTW: '選擇要匯入的裝置', enUS: 'Choose devices to import' })}</h3><p>{pickLocaleText(locale, {
                zhCN: '设备会按房间分组显示。你可以整组选，也可以逐个挑。',
                zhTW: '裝置會依房間分組顯示。您可以整組選，也可以逐個挑。',
                enUS: 'Devices are grouped by room. You can select a whole group or pick them one by one.',
              })}</p></div></div>
              <div className="ha-device-modal__list">{deviceCandidateGroups.length === 0 ? <div className="integration-status__detail">{pickLocaleText(locale, { zhCN: '暂时没有可导入的设备。', zhTW: '暫時沒有可匯入的裝置。', enUS: 'There are no importable devices right now.' })}</div> : deviceCandidateGroups.map((group) => {
                const deviceIds = group.items.map((item) => item.external_device_id);
                const selectedCount = deviceIds.filter((id) => selectedExternalDeviceIds.includes(id)).length;
                const allSelected = selectedCount === deviceIds.length;
                return (
                  <div key={group.roomName} className="ha-device-group">
                    <label className="ha-device-group__header"><input type="checkbox" checked={allSelected} onChange={() => toggleDeviceRoomSelection(deviceIds)} disabled={loading} /><div className="ha-device-group__meta"><strong>{group.roomName}</strong><span className="integration-status__detail">{pickLocaleText(locale, { zhCN: `已选 ${selectedCount}/${group.items.length} 台`, zhTW: `已選 ${selectedCount}/${group.items.length} 台`, enUS: `Selected ${selectedCount}/${group.items.length}` })}</span></div></label>
                    <div className="ha-device-group__items">{group.items.map((candidate) => (
                      <label key={candidate.external_device_id} className="ha-device-option">
                        <input type="checkbox" checked={selectedExternalDeviceIds.includes(candidate.external_device_id)} onChange={() => toggleDeviceSelection(candidate.external_device_id)} disabled={loading} />
                        <div className="ha-device-option__body"><div className="ha-device-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.already_synced ? 'secondary' : 'success'}`}>{candidate.already_synced ? pickLocaleText(locale, { zhCN: '已导入过', zhTW: '已匯入過', enUS: 'Imported before' }) : pickLocaleText(locale, { zhCN: '新设备', zhTW: '新裝置', enUS: 'New device' })}</span></div><div className="integration-status__detail">{formatDeviceType(candidate.device_type as Device['device_type'])} · {candidate.already_synced ? pickLocaleText(locale, { zhCN: '再次导入会更新它的名称和房间信息。', zhTW: '再次匯入會更新它的名稱和房間資訊。', enUS: 'Re-importing will update its name and room information.' }) : pickLocaleText(locale, { zhCN: '导入后会加入当前家庭设备列表。', zhTW: '匯入後會加入目前家庭裝置列表。', enUS: 'After import, it will be added to the current household device list.' })}</div></div>
                      </label>
                    ))}</div>
                  </div>
                );
              })}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setDeviceModalOpen(false)} disabled={loading}>{pickLocaleText(locale, { zhCN: '取消', zhTW: '取消', enUS: 'Cancel' })}</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmDeviceSync()} disabled={loading || selectedExternalDeviceIds.length === 0}>{pickLocaleText(locale, { zhCN: '导入选中设备', zhTW: '匯入選中裝置', enUS: 'Import selected devices' })}</button></div>
            </div>
          </div>
        ) : null}
        {configModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setConfigModalOpen(false)}>
            <div className="member-modal ha-config-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>{pickLocaleText(locale, { zhCN: '连接 Home Assistant', zhTW: '連線 Home Assistant', enUS: 'Connect Home Assistant' })}</h3><p>{pickLocaleText(locale, {
                zhCN: '这里只影响当前家庭，其他家庭不会受影响。',
                zhTW: '這裡只影響目前家庭，其他家庭不會受影響。',
                enUS: 'Changes here only affect the current household.',
              })}</p></div></div>
              <form className="settings-form integration-config-form" onSubmit={handleSaveHaConfig}>
                <div className="form-group"><label>{pickLocaleText(locale, { zhCN: 'Home Assistant 地址', zhTW: 'Home Assistant 位址', enUS: 'Home Assistant URL' })}</label><input className="form-input" value={haForm.base_url} onChange={(event) => setHaForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="http://homeassistant.local:8123" /><div className="form-help">{pickLocaleText(locale, {
                  zhCN: '这里填写你的 Home Assistant 地址。保存后，这一页会显示连接情况。',
                  zhTW: '這裡填寫您的 Home Assistant 位址。儲存後，這一頁會顯示連線情況。',
                  enUS: 'Enter your Home Assistant URL here. After saving, this page will show the connection status.',
                })}</div></div>
                <div className="form-group"><label>{pickLocaleText(locale, { zhCN: '访问密钥（Long-Lived Token）', zhTW: '存取金鑰（Long-Lived Token）', enUS: 'Access token (Long-Lived Token)' })}</label><input className="form-input" type="password" value={haForm.access_token} onChange={(event) => setHaForm((current) => ({ ...current, access_token: event.target.value, clear_access_token: false }))} placeholder={haConfig?.token_configured ? pickLocaleText(locale, { zhCN: '已配置，留空表示不改', zhTW: '已設定，留空表示不變更', enUS: 'Configured already. Leave blank to keep it unchanged.' }) : pickLocaleText(locale, { zhCN: '请输入当前家庭使用的访问密钥', zhTW: '請輸入目前家庭使用的存取金鑰', enUS: 'Enter the access token used by the current household' })} /><div className="form-help">{pickLocaleText(locale, {
                  zhCN: `如果之前已经填过，留空就是保持不变。当前：${haConfig?.token_configured ? '已保存' : '未填写'}。`,
                  zhTW: `如果之前已經填過，留空就是保持不變。目前：${haConfig?.token_configured ? '已儲存' : '未填寫'}。`,
                  enUS: `If a token was entered before, leaving this blank keeps it unchanged. Current state: ${haConfig?.token_configured ? 'saved' : 'not provided'}.`,
                })}</div></div>
                <div className="integration-config-grid"><div className="form-group"><label>{pickLocaleText(locale, { zhCN: '导入房间时', zhTW: '匯入房間時', enUS: 'When importing rooms' })}</label><select className="form-select" value={haForm.sync_rooms_enabled ? 'true' : 'false'} onChange={(event) => setHaForm((current) => ({ ...current, sync_rooms_enabled: event.target.value === 'true' }))}><option value="false">{pickLocaleText(locale, { zhCN: '只导入设备', zhTW: '只匯入裝置', enUS: 'Import devices only' })}</option><option value="true">{pickLocaleText(locale, { zhCN: '导入设备时，顺便匹配已有房间', zhTW: '匯入裝置時，順便匹配已有房間', enUS: 'When importing devices, also match existing rooms' })}</option></select></div><div className="form-group"><label>{pickLocaleText(locale, { zhCN: '访问密钥处理', zhTW: '存取金鑰處理', enUS: 'Access token handling' })}</label><select className="form-select" value={haForm.clear_access_token ? 'clear' : 'keep'} onChange={(event) => setHaForm((current) => ({ ...current, clear_access_token: event.target.value === 'clear', access_token: event.target.value === 'clear' ? '' : current.access_token }))}><option value="keep">{pickLocaleText(locale, { zhCN: '保留现有访问密钥', zhTW: '保留現有存取金鑰', enUS: 'Keep the current token' })}</option><option value="clear">{pickLocaleText(locale, { zhCN: '清空现有访问密钥', zhTW: '清空現有存取金鑰', enUS: 'Clear the current token' })}</option></select></div></div>
                <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(false)} disabled={loading}>{pickLocaleText(locale, { zhCN: '取消', zhTW: '取消', enUS: 'Cancel' })}</button><button className="btn btn--outline btn--sm" type="submit" disabled={loading}>{loading ? pickLocaleText(locale, { zhCN: '保存中...', zhTW: '儲存中...', enUS: 'Saving...' }) : pickLocaleText(locale, { zhCN: '保存连接设置', zhTW: '儲存連線設定', enUS: 'Save connection settings' })}</button></div>
              </form>
            </div>
          </div>
        ) : null}
      </div>
    </SettingsPageShell>
  );
}

export default function SettingsIntegrationsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/integrations/index">
      <SettingsIntegrationsContent />
    </GuardedPage>
  );
}
