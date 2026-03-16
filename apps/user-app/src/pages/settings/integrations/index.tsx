import { useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { GuardedPage, useAuthContext, useHouseholdContext, useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
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
  const page = (
    key: Parameters<typeof getPageMessage>[1],
    params?: Record<string, string | number>,
  ) => getPageMessage(locale, key, params);
  const listSeparator = locale.toLowerCase().startsWith('en') ? ', ' : '、';
  const errorJoiner = locale.toLowerCase().startsWith('en') ? '; ' : '；';
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

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: page('settings.integrations.title') }).catch(() => undefined);
  }, [locale]);

  const copy = {
    defaultSpeakerName: page('settings.integrations.defaultSpeakerName'),
    roomUnassigned: page('settings.integrations.roomUnassigned'),
    discoveryNotFound: page('settings.integrations.error.discoveryNotFound'),
    roomNotFound: page('settings.integrations.error.roomNotFound'),
    roomMismatch: page('settings.integrations.error.roomMismatch'),
    discoveryClaimed: page('settings.integrations.error.discoveryClaimed'),
    loadDiscoveryFailed: page('settings.integrations.error.loadDiscoveryFailed'),
    loadVoiceprintFailed: page('settings.integrations.error.loadVoiceprintFailed'),
    loadIntegrationFailed: page('settings.integrations.error.loadIntegrationFailed'),
    loadEnrollmentFailed: page('settings.integrations.error.loadEnrollmentFailed'),
    actionFailed: page('settings.integrations.error.actionFailed'),
    saveHaSuccess: page('settings.integrations.status.saveHaSuccess'),
    selectHousehold: page('settings.integrations.error.selectHousehold'),
    loadHaDevicesFailed: page('settings.integrations.error.loadHaDevicesFailed'),
    importHaDevicesSuccess: (count: number) => page('settings.integrations.status.importHaDevicesSuccess', { count }),
    loadHaRoomsFailed: page('settings.integrations.error.loadHaRoomsFailed'),
    importHaRoomsSuccess: (count: number) => page('settings.integrations.status.importHaRoomsSuccess', { count }),
    saveDeviceSuccess: page('settings.integrations.status.saveDeviceSuccess'),
    saveSpeakerSuccess: page('settings.integrations.status.saveSpeakerSuccess'),
    saveSpeakerFailed: page('settings.integrations.error.saveSpeakerFailed'),
    saveVoiceprintSwitchFailed: page('settings.integrations.error.saveVoiceprintSwitchFailed'),
    createEnrollmentFailed: page('settings.integrations.error.createEnrollmentFailed'),
    deviceNameRequired: page('settings.integrations.error.deviceNameRequired'),
    roomRequired: page('settings.integrations.error.roomRequired'),
    claimSpeakerSuccess: page('settings.integrations.status.claimSpeakerSuccess'),
    claimSpeakerFailed: page('settings.integrations.error.claimSpeakerFailed'),
    deviceTypeLight: page('settings.integrations.deviceType.light'),
    deviceTypeAc: page('settings.integrations.deviceType.ac'),
    deviceTypeCurtain: page('settings.integrations.deviceType.curtain'),
    deviceTypeSpeaker: page('settings.integrations.deviceType.speaker'),
    deviceTypeCamera: page('settings.integrations.deviceType.camera'),
    deviceTypeSensor: page('settings.integrations.deviceType.sensor'),
    deviceTypeLock: page('settings.integrations.deviceType.lock'),
    online: page('settings.integrations.deviceStatus.online'),
    recentlyOnline: page('settings.integrations.deviceStatus.recentlyOnline'),
    offline: page('settings.integrations.deviceStatus.offline'),
    inactive: page('settings.integrations.deviceStatus.inactive'),
    controllable: page('settings.integrations.deviceControllable.true'),
    readOnly: page('settings.integrations.deviceControllable.false'),
    haUnconfigured: page('settings.integrations.ha.unconfigured'),
    haHealthy: page('settings.integrations.ha.healthy'),
    haDegraded: page('settings.integrations.ha.degraded'),
    haOffline: page('settings.integrations.ha.offline'),
    haChecking: page('settings.integrations.ha.checking'),
    justNow: page('settings.integrations.ha.justNow'),
    currentStatusLoaded: page('settings.integrations.ha.currentStatusLoaded'),
    noRecord: page('settings.integrations.ha.noRecord'),
    connectHaFirst: page('settings.integrations.action.connectHaFirst'),
    importing: page('settings.integrations.action.importing'),
    importDevices: page('settings.integrations.action.importDevices'),
    importRooms: page('settings.integrations.action.importRooms'),
    finishHaConnectionFirst: page('settings.integrations.action.finishHaConnectionFirst'),
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
        setError([configResult, devicesResult, roomsResult, overviewResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : copy.loadIntegrationFailed).join(errorJoiner));
      } else {
        setOverview(null);
        setError([configResult, devicesResult, roomsResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : copy.loadIntegrationFailed).join(errorJoiner));
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
  const formatVoiceTakeoverPrefixes = (prefixes: string[]) => prefixes.join(listSeparator);
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
        <Section title={page('settings.integrations.section.haConnection')}>
          <Card className="integration-status-card">
            <div className="integration-status">
              <span className={`integration-status__indicator integration-status__indicator--${haStatus.tone}`} />
              <div className="integration-status__text">
                <span className="integration-status__label">Home Assistant</span>
                <span className="integration-status__detail">{page('settings.integrations.ha.statusDetail', { status: haStatus.label, time: lastSyncText })}</span>
                <span className="integration-status__detail">{page('settings.integrations.ha.addressDetail', { address: haAddressText })}</span>
              </div>
              <div className="integration-actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(true)} disabled={loading}>{page('settings.integrations.action.connectionSettings')}</button>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openDeviceSyncModal} disabled={loading || deviceModalLoading || !canOperateHa}>{syncButtonLabel}</button></span>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openRoomSyncModal} disabled={loading || roomModalLoading || !canOperateHa}>{syncRoomsButtonLabel}</button></span>
              </div>
            </div>
            {syncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>{page('settings.integrations.summary.deviceSync', { created: syncSummary.created_devices, updated: syncSummary.updated_devices, assigned: syncSummary.assigned_rooms, failed: syncSummary.failed_entities })}</div> : null}
            {roomSyncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{page('settings.integrations.summary.roomSync', { created: roomSyncSummary.created_rooms, matched: roomSyncSummary.matched_entities, skipped: roomSyncSummary.skipped_entities })}</div> : null}
            {status ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{status}</div> : null}
            {error ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{error}</div> : null}
          </Card>
        </Section>

        <Section title={page('settings.integrations.section.pendingSpeakers')}>
          <Card className="integration-status-card">
            <div className="integration-status" style={{ alignItems: 'flex-start' }}>
              <div className="integration-status__text">
                <span className="integration-status__label">{page('settings.integrations.discovery.title')}</span>
                <span className="integration-status__detail">{page('settings.integrations.discovery.desc')}</span>
                <span className="integration-status__detail">{page('settings.integrations.discovery.hint')}</span>
              </div>
            </div>
            {voiceDiscoveryError ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>{voiceDiscoveryError}</div> : null}
            <div className="device-list" style={{ marginTop: '1rem' }}>
              {voiceDiscoveries.length === 0 ? (
                <div className="integration-status__detail">{page('settings.integrations.discovery.empty')}</div>
              ) : voiceDiscoveries.map((item) => {
                const draft = getVoiceDiscoveryDraft(item.fingerprint);
                const isClaiming = voiceClaimingFingerprint === item.fingerprint;
                return (
                  <Card key={item.fingerprint} className="device-card device-card--editor">
                    <div className="device-card__editor-grid">
                      <div className="device-card__info">
                        <span className="device-card__name">{item.model}</span>
                        <span className="device-card__room">{page('settings.integrations.discovery.deviceMeta', { serial: formatVoiceDiscoverySerial(item.sn), status: formatVoiceDiscoveryStatus(item.connection_status), time: formatVoiceDiscoveryTime(item.last_seen_at) })}</span>
                      </div>
                      <input className="form-input" value={draft.terminal_name} placeholder={page('settings.integrations.discovery.namePlaceholder')} onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { terminal_name: event.target.value })} />
                      <select className="form-select" value={draft.room_id} onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { room_id: event.target.value })} disabled={rooms.length === 0}>
                        {rooms.length === 0 ? <option value="">{page('settings.integrations.discovery.createRoomFirst')}</option> : rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
                      </select>
                    </div>
                    <div className="device-card__actions">
                      <span className={`badge badge--${item.connection_status === 'online' ? 'success' : 'secondary'}`}>{formatVoiceDiscoveryStatus(item.connection_status)}</span>
                      <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleClaimVoiceDiscovery(item.fingerprint)} disabled={isClaiming || rooms.length === 0}>{isClaiming ? page('settings.integrations.discovery.adding') : page('settings.integrations.discovery.addToHousehold')}</button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>
        </Section>

        <Section title={page('settings.integrations.section.devices')}>
          <div className="device-list">
            {loading && devices.length === 0 ? <div className="text-text-secondary">{page('settings.integrations.devices.loading')}</div> : devices.map((device) => {
              const draft = deviceDrafts[device.id] ?? { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable };
              const supportsVoiceSettings = device.device_type === 'speaker' && device.vendor === 'xiaomi';
              return (
                <Card key={device.id} className="device-card device-card--editor">
                  <div className="device-card__editor-grid">
                    <div className="device-card__info">
                      <span className="device-card__name">{device.name}</span>
                      <span className="device-card__room">{roomNameMap[device.room_id ?? ''] ?? copy.roomUnassigned} · {formatDeviceType(device.device_type)}</span>
                      {supportsVoiceSettings ? <span className="integration-status__detail">{device.voice_auto_takeover_enabled ? page('settings.integrations.devices.takeoverAll') : page('settings.integrations.devices.takeoverWithPrefixes', { prefixes: formatVoiceTakeoverPrefixes(device.voice_takeover_prefixes) })}</span> : null}
                    </div>
                    <input className="form-input" value={draft.name} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, name: event.target.value } }))} />
                    <select className="form-select" value={draft.room_id ?? ''} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, room_id: event.target.value || null } }))}>{roomOptions.map((option) => <option key={option.id || 'unassigned'} value={option.id}>{option.name}</option>)}</select>
                    <select className="form-select" value={draft.status} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, status: event.target.value as Device['status'] } }))}><option value="active">{copy.online}</option><option value="offline">{copy.offline}</option><option value="inactive">{copy.inactive}</option></select>
                    <select className="form-select" value={draft.controllable ? 'true' : 'false'} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, controllable: event.target.value === 'true' } }))}><option value="true">{copy.controllable}</option><option value="false">{copy.readOnly}</option></select>
                  </div>
                  <div className="device-card__actions">
                    <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>{device.status === 'active' ? copy.online : device.status === 'offline' ? copy.offline : copy.inactive}</span>
                    {supportsVoiceSettings ? <button className="btn btn--outline btn--sm" type="button" onClick={() => openSpeakerSettings(device)} disabled={loading}>{page('settings.integrations.action.moreSettings')}</button> : null}
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSaveDevice(device.id)} disabled={loading}>{page('settings.integrations.action.saveChanges')}</button>
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
              <div className="member-modal__header"><div><h3>{page('settings.integrations.modal.rooms.title')}</h3><p>{page('settings.integrations.modal.rooms.desc')}</p></div></div>
              <div className="ha-room-modal__list">{roomCandidates.length === 0 ? <div className="integration-status__detail">{page('settings.integrations.modal.rooms.empty')}</div> : roomCandidates.map((candidate) => (
                <label key={candidate.name} className={`ha-room-option ${candidate.can_sync ? '' : 'ha-room-option--disabled'}`}>
                  <input type="checkbox" checked={selectedRoomNames.includes(candidate.name)} disabled={!candidate.can_sync || loading} onChange={() => toggleRoomSelection(candidate.name)} />
                  <div className="ha-room-option__body"><div className="ha-room-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.can_sync ? 'success' : 'warning'}`}>{candidate.can_sync ? page('settings.integrations.modal.rooms.importable') : page('settings.integrations.modal.rooms.alreadyExists')}</span></div><div className="integration-status__detail">{candidate.exists_locally ? page('settings.integrations.modal.rooms.existsHint') : page('settings.integrations.modal.rooms.importHint')}</div></div>
                </label>
              ))}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setRoomModalOpen(false)} disabled={loading}>{page('settings.integrations.action.cancel')}</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmRoomSync()} disabled={loading || selectedRoomNames.length === 0}>{page('settings.integrations.action.importSelectedRooms')}</button></div>
            </div>
          </div>
        ) : null}
        {deviceModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setDeviceModalOpen(false)}>
            <div className="member-modal ha-device-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>{page('settings.integrations.modal.devices.title')}</h3><p>{page('settings.integrations.modal.devices.desc')}</p></div></div>
              <div className="ha-device-modal__list">{deviceCandidateGroups.length === 0 ? <div className="integration-status__detail">{page('settings.integrations.modal.devices.empty')}</div> : deviceCandidateGroups.map((group) => {
                const deviceIds = group.items.map((item) => item.external_device_id);
                const selectedCount = deviceIds.filter((id) => selectedExternalDeviceIds.includes(id)).length;
                const allSelected = selectedCount === deviceIds.length;
                return (
                  <div key={group.roomName} className="ha-device-group">
                    <label className="ha-device-group__header"><input type="checkbox" checked={allSelected} onChange={() => toggleDeviceRoomSelection(deviceIds)} disabled={loading} /><div className="ha-device-group__meta"><strong>{group.roomName}</strong><span className="integration-status__detail">{page('settings.integrations.modal.devices.selectedCount', { selected: selectedCount, total: group.items.length })}</span></div></label>
                    <div className="ha-device-group__items">{group.items.map((candidate) => (
                      <label key={candidate.external_device_id} className="ha-device-option">
                        <input type="checkbox" checked={selectedExternalDeviceIds.includes(candidate.external_device_id)} onChange={() => toggleDeviceSelection(candidate.external_device_id)} disabled={loading} />
                        <div className="ha-device-option__body"><div className="ha-device-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.already_synced ? 'secondary' : 'success'}`}>{candidate.already_synced ? page('settings.integrations.modal.devices.importedBefore') : page('settings.integrations.modal.devices.newDevice')}</span></div><div className="integration-status__detail">{formatDeviceType(candidate.device_type as Device['device_type'])} · {candidate.already_synced ? page('settings.integrations.modal.devices.reimportHint') : page('settings.integrations.modal.devices.importHint')}</div></div>
                      </label>
                    ))}</div>
                  </div>
                );
              })}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setDeviceModalOpen(false)} disabled={loading}>{page('settings.integrations.action.cancel')}</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmDeviceSync()} disabled={loading || selectedExternalDeviceIds.length === 0}>{page('settings.integrations.action.importSelectedDevices')}</button></div>
            </div>
          </div>
        ) : null}
        {configModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setConfigModalOpen(false)}>
            <div className="member-modal ha-config-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>{page('settings.integrations.modal.config.title')}</h3><p>{page('settings.integrations.modal.config.desc')}</p></div></div>
              <form className="settings-form integration-config-form" onSubmit={handleSaveHaConfig}>
                <div className="form-group"><label>{page('settings.integrations.modal.config.baseUrlLabel')}</label><input className="form-input" value={haForm.base_url} onChange={(event) => setHaForm((current) => ({ ...current, base_url: event.target.value }))} placeholder={page('settings.integrations.modal.config.baseUrlPlaceholder')} /><div className="form-help">{page('settings.integrations.modal.config.baseUrlHelp')}</div></div>
                <div className="form-group"><label>{page('settings.integrations.modal.config.accessTokenLabel')}</label><input className="form-input" type="password" value={haForm.access_token} onChange={(event) => setHaForm((current) => ({ ...current, access_token: event.target.value, clear_access_token: false }))} placeholder={haConfig?.token_configured ? page('settings.integrations.modal.config.accessTokenPlaceholderConfigured') : page('settings.integrations.modal.config.accessTokenPlaceholderEmpty')} /><div className="form-help">{page('settings.integrations.modal.config.accessTokenHelp', { state: haConfig?.token_configured ? page('settings.integrations.modal.config.tokenStateSaved') : page('settings.integrations.modal.config.tokenStateEmpty') })}</div></div>
                <div className="integration-config-grid"><div className="form-group"><label>{page('settings.integrations.modal.config.syncRoomsLabel')}</label><select className="form-select" value={haForm.sync_rooms_enabled ? 'true' : 'false'} onChange={(event) => setHaForm((current) => ({ ...current, sync_rooms_enabled: event.target.value === 'true' }))}><option value="false">{page('settings.integrations.modal.config.syncRoomsDevicesOnly')}</option><option value="true">{page('settings.integrations.modal.config.syncRoomsMatchExisting')}</option></select></div><div className="form-group"><label>{page('settings.integrations.modal.config.accessTokenHandlingLabel')}</label><select className="form-select" value={haForm.clear_access_token ? 'clear' : 'keep'} onChange={(event) => setHaForm((current) => ({ ...current, clear_access_token: event.target.value === 'clear', access_token: event.target.value === 'clear' ? '' : current.access_token }))}><option value="keep">{page('settings.integrations.modal.config.accessTokenKeep')}</option><option value="clear">{page('settings.integrations.modal.config.accessTokenClear')}</option></select></div></div>
                <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(false)} disabled={loading}>{page('settings.integrations.action.cancel')}</button><button className="btn btn--outline btn--sm" type="submit" disabled={loading}>{loading ? page('settings.integrations.action.saving') : page('settings.integrations.action.saveConnectionSettings')}</button></div>
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
