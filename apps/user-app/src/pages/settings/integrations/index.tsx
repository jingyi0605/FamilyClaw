import { useEffect, useMemo, useState } from 'react';
import { GuardedPage, useAuthContext, useHouseholdContext } from '../../../runtime';
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

function SettingsIntegrationsContent() {
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

  const getDefaultVoiceDiscoveryDraft = () => ({ terminal_name: '小爱音箱', room_id: rooms[0]?.id ?? '' });
  const mergeVoiceDiscoveryDrafts = (items: VoiceDiscoveryTerminal[], previous: Record<string, { terminal_name: string; room_id: string }>) => Object.fromEntries(items.map((item) => [item.fingerprint, { ...getDefaultVoiceDiscoveryDraft(), ...previous[item.fingerprint] }]));
  const normalizeVoiceDiscoveryErrorMessage = (message: string) => {
    if (message === 'voice discovery not found') return '这台音箱已经不在待添加列表里了。';
    if (message === 'room not found') return '所选房间不存在。';
    if (message === 'room must belong to the same household') return '请选择当前家庭下的房间。';
    if (message === 'voice terminal already claimed by another household') return '这台音箱已经被其他家庭添加。';
    return message;
  };

  async function loadVoiceDiscoveries(householdId: string, options?: { silent?: boolean }) {
    try {
      const result = await settingsApi.listVoiceTerminalDiscoveries(householdId);
      setVoiceDiscoveries(result.items);
      setVoiceDiscoveryDrafts((current) => mergeVoiceDiscoveryDrafts(result.items, current));
      if (!options?.silent) setVoiceDiscoveryError('');
    } catch (loadError) {
      if (!options?.silent) setVoiceDiscoveryError(loadError instanceof Error ? normalizeVoiceDiscoveryErrorMessage(loadError.message) : '新音箱列表加载失败');
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
        setVoiceprintError(loadError instanceof Error ? loadError.message : '声纹状态加载失败');
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
        setError([configResult, devicesResult, roomsResult, overviewResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : '集成数据加载失败').join('；'));
      } else {
        setOverview(null);
        setError([configResult, devicesResult, roomsResult].filter((result) => result.status === 'rejected').map((result) => result.reason instanceof Error ? result.reason.message : '集成数据加载失败').join('；'));
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
        setVoiceprintWizard((current) => current ? { ...current, step: 'failed', error: pollError instanceof Error ? pollError.message : '录入进度加载失败' } : current);
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
    try { await action(); } catch (actionError) { setError(actionError instanceof Error ? actionError.message : '操作失败'); } finally { setLoading(false); }
  }

  async function handleSaveHaConfig(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.updateHomeAssistantConfig(currentHouseholdId, { base_url: haForm.base_url.trim() || null, access_token: haForm.access_token.trim() || undefined, clear_access_token: haForm.clear_access_token, sync_rooms_enabled: haForm.sync_rooms_enabled });
      setHaConfig(result);
      setHaForm({ base_url: result.base_url ?? '', access_token: '', sync_rooms_enabled: result.sync_rooms_enabled, clear_access_token: false });
      setConfigModalOpen(false); setStatus('当前家庭的 Home Assistant 配置已保存');
    });
  }

  async function openDeviceSyncModal() {
    if (!currentHouseholdId) { setError('还没有选中家庭。'); return; }
    setDeviceModalLoading(true); setError('');
    try {
      const result = await settingsApi.listHomeAssistantDeviceCandidates(currentHouseholdId);
      setDeviceCandidates(result.items); setSelectedExternalDeviceIds(result.items.map((item) => item.external_device_id)); setDeviceModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '加载 HA 设备候选项失败');
    } finally { setDeviceModalLoading(false); }
  }

  async function handleConfirmDeviceSync() {
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.syncSelectedHomeAssistantDevices(currentHouseholdId, selectedExternalDeviceIds);
      setSyncSummary(result); setDeviceModalOpen(false); await reloadWorkspace(); setStatus(`已从 Home Assistant 导入 ${result.created_devices + result.updated_devices} 台设备。`);
    });
  }

  async function openRoomSyncModal() {
    if (!currentHouseholdId) { setError('还没有选中家庭。'); return; }
    setRoomModalLoading(true); setError('');
    try {
      const result = await settingsApi.listHomeAssistantRoomCandidates(currentHouseholdId);
      setRoomCandidates(result.items); setSelectedRoomNames(result.items.filter((item) => item.can_sync).map((item) => item.name)); setRoomModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '加载 HA 房间候选项失败');
    } finally { setRoomModalLoading(false); }
  }

  async function handleConfirmRoomSync() {
    if (!currentHouseholdId) return;
    await runAction(async () => {
      const result = await settingsApi.syncSelectedHomeAssistantRooms(currentHouseholdId, selectedRoomNames);
      setRoomSyncSummary(result); setRoomModalOpen(false); await reloadWorkspace(); setStatus(`已从 Home Assistant 导入 ${result.created_rooms} 个房间。`);
    });
  }

  function toggleRoomSelection(roomName: string) { setSelectedRoomNames((current) => current.includes(roomName) ? current.filter((item) => item !== roomName) : [...current, roomName]); }
  function toggleDeviceSelection(externalDeviceId: string) { setSelectedExternalDeviceIds((current) => current.includes(externalDeviceId) ? current.filter((item) => item !== externalDeviceId) : [...current, externalDeviceId]); }
  function toggleDeviceRoomSelection(deviceIds: string[]) { setSelectedExternalDeviceIds((current) => deviceIds.every((id) => current.includes(id)) ? current.filter((id) => !deviceIds.includes(id)) : Array.from(new Set([...current, ...deviceIds]))); }
  async function handleSaveDevice(deviceId: string) { const draft = deviceDrafts[deviceId]; if (!draft) return; await runAction(async () => { await settingsApi.updateDevice(deviceId, draft); await reloadWorkspace(); setStatus('设备设置已保存'); }); }
  function openSpeakerSettings(device: Device) { setSpeakerSettingsError(''); setSpeakerDetailDeviceId(device.id); }
  async function handleSaveSpeakerSettings(payload: { voice_auto_takeover_enabled: boolean; voice_takeover_prefixes: string[] }) {
    if (!speakerDetailDeviceId) return;
    setLoading(true); setStatus(''); setError(''); setSpeakerSettingsError('');
    try {
      await settingsApi.updateDevice(speakerDetailDeviceId, payload);
      await reloadWorkspace();
      setStatus('音箱设置已保存');
    } catch (actionError) {
      setSpeakerSettingsError(actionError instanceof Error ? actionError.message : '音箱设置保存失败');
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
      setVoiceprintError(actionError instanceof Error ? actionError.message : '设备级声纹开关保存失败');
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
        error: actionError instanceof Error ? actionError.message : '录入进度加载失败',
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
        error: actionError instanceof Error ? actionError.message : '建档任务创建失败',
      } : current);
    } finally {
      setVoiceprintWizardBusy(false);
    }
  }

  function updateVoiceDiscoveryDraft(fingerprint: string, patch: Partial<{ terminal_name: string; room_id: string }>) { setVoiceDiscoveryDrafts((current) => ({ ...current, [fingerprint]: { terminal_name: current[fingerprint]?.terminal_name ?? '小爱音箱', room_id: current[fingerprint]?.room_id ?? (rooms[0]?.id ?? ''), ...patch } })); }
  function getVoiceDiscoveryDraft(fingerprint: string) { const draft = voiceDiscoveryDrafts[fingerprint]; return draft ? { terminal_name: draft.terminal_name || '小爱音箱', room_id: draft.room_id || rooms[0]?.id || '' } : getDefaultVoiceDiscoveryDraft(); }
  async function handleClaimVoiceDiscovery(fingerprint: string) {
    const draft = getVoiceDiscoveryDraft(fingerprint);
    if (!currentHouseholdId) { setVoiceDiscoveryError('还没有选中家庭。'); return; }
    if (!draft.terminal_name.trim()) { setVoiceDiscoveryError('请先填写设备名称。'); return; }
    if (!draft.room_id) { setVoiceDiscoveryError('请先选择所在房间。'); return; }
    setVoiceClaimingFingerprint(fingerprint); setVoiceDiscoveryError('');
    try {
      await settingsApi.claimVoiceTerminalDiscovery(fingerprint, { household_id: currentHouseholdId, room_id: draft.room_id, terminal_name: draft.terminal_name.trim() });
      await reloadWorkspace(); setStatus('新音箱已经添加到当前家庭。');
    } catch (claimError) {
      setVoiceDiscoveryError(claimError instanceof Error ? normalizeVoiceDiscoveryErrorMessage(claimError.message) : '添加音箱失败');
    } finally { setVoiceClaimingFingerprint(null); }
  }

  const roomNameMap = useMemo(() => Object.fromEntries(rooms.map((room) => [room.id, room.name])), [rooms]);
  const roomOptions = useMemo(() => [{ id: '', name: '未分配房间' }, ...rooms.map((room) => ({ id: room.id, name: room.name }))], [rooms]);
  const deviceCandidateGroups = useMemo(() => Array.from(deviceCandidates.reduce((map, candidate) => map.set(candidate.room_name || '未分配房间', [...(map.get(candidate.room_name || '未分配房间') ?? []), candidate]), new Map<string, HomeAssistantDeviceCandidate[]>()).entries()).map(([roomName, items]) => ({ roomName, items })).sort((left, right) => left.roomName.localeCompare(right.roomName, 'zh-CN')), [deviceCandidates]);
  const formatDeviceType = (type: Device['device_type']) => ({ light: '灯光', ac: '温控', curtain: '窗帘', speaker: '音箱', camera: '安防', sensor: '传感器', lock: '门锁' }[type] ?? type);
  const formatVoiceDiscoveryStatus = (value: VoiceDiscoveryTerminal['connection_status']) => value === 'online' ? '在线' : '最近在线';
  const formatVoiceDiscoveryTime = (value: string) => Number.isNaN(new Date(value).getTime()) ? value : new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const formatVoiceDiscoverySerial = (sn: string) => sn.trim().length <= 4 ? sn.trim() : sn.trim().slice(-4);
  const formatHaStatus = (config: HomeAssistantConfig | null, statusValue: ContextOverviewRead['home_assistant_status'] | undefined) => !config?.base_url || !config?.token_configured ? { label: '未配置', tone: 'idle' as const } : statusValue === 'healthy' ? { label: '已连接', tone: 'online' as const } : statusValue === 'degraded' ? { label: '部分可用', tone: 'warning' as const } : statusValue === 'offline' ? { label: '暂时连不上', tone: 'offline' as const } : { label: '等待检查', tone: 'warning' as const };
  const haStatus = formatHaStatus(haConfig, overview?.home_assistant_status);
  const lastSyncText = syncSummary ? '刚刚' : haConfig?.last_device_sync_at ?? (overview ? '已加载当前状态' : '暂无记录');
  const haAddressText = haConfig?.base_url ?? '未配置';
  const canOperateHa = Boolean(haConfig?.base_url && haConfig?.token_configured);
  const syncButtonLabel = canOperateHa ? (loading ? '导入中...' : '导入设备') : '请先连接 Home Assistant';
  const syncRoomsButtonLabel = canOperateHa ? '导入房间' : '请先连接 Home Assistant';
  const disabledHaActionTooltip = canOperateHa ? undefined : '先完成 Home Assistant 连接设置';
  const canManageVoiceprint = actor?.member_role === 'admin';
  const speakerDetailDevice = useMemo(
    () => devices.find((device) => device.id === speakerDetailDeviceId) ?? null,
    [devices, speakerDetailDeviceId],
  );

  return (
    <SettingsPageShell activeKey="integrations">
      <div className="settings-page">
        <Section title="Home Assistant 连接">
          <Card className="integration-status-card">
            <div className="integration-status">
              <span className={`integration-status__indicator integration-status__indicator--${haStatus.tone}`} />
              <div className="integration-status__text">
                <span className="integration-status__label">Home Assistant</span>
                <span className="integration-status__detail">连接状态：{haStatus.label} · 最近同步：{lastSyncText}</span>
                <span className="integration-status__detail">连接地址：{haAddressText}</span>
              </div>
              <div className="integration-actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(true)} disabled={loading}>连接设置</button>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openDeviceSyncModal} disabled={loading || deviceModalLoading || !canOperateHa}>{syncButtonLabel}</button></span>
                <span className="integration-action-tooltip" title={disabledHaActionTooltip}><button className="btn btn--outline btn--sm" onClick={openRoomSyncModal} disabled={loading || roomModalLoading || !canOperateHa}>{syncRoomsButtonLabel}</button></span>
              </div>
            </div>
            {syncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>这次导入新增了 {syncSummary.created_devices} 台设备，更新了 {syncSummary.updated_devices} 台设备，为 {syncSummary.assigned_rooms} 台设备补上了房间；另有 {syncSummary.failed_entities} 项没有导入成功。</div> : null}
            {roomSyncSummary ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>这次导入了 {roomSyncSummary.created_rooms} 个房间，识别到 {roomSyncSummary.matched_entities} 项关联内容，跳过了 {roomSyncSummary.skipped_entities} 项重复内容。</div> : null}
            {status ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{status}</div> : null}
            {error ? <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{error}</div> : null}
          </Card>
        </Section>

        <Section title="待添加的音箱">
          <Card className="integration-status-card">
            <div className="integration-status" style={{ alignItems: 'flex-start' }}>
              <div className="integration-status__text">
                <span className="integration-status__label">自动发现</span>
                <span className="integration-status__detail">系统会持续查找同一局域网里的可接入音箱。填好名称和房间后，就能把它加入当前家庭。</span>
                <span className="integration-status__detail">如果这里一直没有结果，先确认音箱和当前服务连的是同一个局域网。</span>
              </div>
            </div>
            {voiceDiscoveryError ? <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>{voiceDiscoveryError}</div> : null}
            <div className="device-list" style={{ marginTop: '1rem' }}>
              {voiceDiscoveries.length === 0 ? (
                <div className="integration-status__detail">暂时还没有发现可添加的音箱。</div>
              ) : voiceDiscoveries.map((item) => {
                const draft = getVoiceDiscoveryDraft(item.fingerprint);
                const isClaiming = voiceClaimingFingerprint === item.fingerprint;
                return (
                  <Card key={item.fingerprint} className="device-card device-card--editor">
                    <div className="device-card__editor-grid">
                      <div className="device-card__info">
                        <span className="device-card__name">{item.model}</span>
                        <span className="device-card__room">设备尾号 {formatVoiceDiscoverySerial(item.sn)} · {formatVoiceDiscoveryStatus(item.connection_status)} · 最近出现于 {formatVoiceDiscoveryTime(item.last_seen_at)}</span>
                      </div>
                      <input className="form-input" value={draft.terminal_name} placeholder="例如：客厅音箱" onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { terminal_name: event.target.value })} />
                      <select className="form-select" value={draft.room_id} onChange={(event) => updateVoiceDiscoveryDraft(item.fingerprint, { room_id: event.target.value })} disabled={rooms.length === 0}>
                        {rooms.length === 0 ? <option value="">请先创建房间</option> : rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
                      </select>
                    </div>
                    <div className="device-card__actions">
                      <span className={`badge badge--${item.connection_status === 'online' ? 'success' : 'secondary'}`}>{formatVoiceDiscoveryStatus(item.connection_status)}</span>
                      <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleClaimVoiceDiscovery(item.fingerprint)} disabled={isClaiming || rooms.length === 0}>{isClaiming ? '添加中...' : '加入家庭'}</button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>
        </Section>

        <Section title="设备列表">
          <div className="device-list">
            {loading && devices.length === 0 ? <div className="text-text-secondary">正在加载设备列表...</div> : devices.map((device) => {
              const draft = deviceDrafts[device.id] ?? { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable };
              const supportsVoiceSettings = device.device_type === 'speaker' && device.vendor === 'xiaomi';
              return (
                <Card key={device.id} className="device-card device-card--editor">
                  <div className="device-card__editor-grid">
                    <div className="device-card__info">
                      <span className="device-card__name">{device.name}</span>
                      <span className="device-card__room">{roomNameMap[device.room_id ?? ''] ?? '未分配房间'} · {formatDeviceType(device.device_type)}</span>
                      {supportsVoiceSettings ? <span className="integration-status__detail">{device.voice_auto_takeover_enabled ? '当前接管方式：默认响应所有语音请求' : `当前接管方式：只响应以 ${device.voice_takeover_prefixes.join('、')} 开头的话`}</span> : null}
                    </div>
                    <input className="form-input" value={draft.name} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, name: event.target.value } }))} />
                    <select className="form-select" value={draft.room_id ?? ''} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, room_id: event.target.value || null } }))}>{roomOptions.map((option) => <option key={option.id || 'unassigned'} value={option.id}>{option.name}</option>)}</select>
                    <select className="form-select" value={draft.status} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, status: event.target.value as Device['status'] } }))}><option value="active">在线</option><option value="offline">离线</option><option value="inactive">未启用</option></select>
                    <select className="form-select" value={draft.controllable ? 'true' : 'false'} onChange={(event) => setDeviceDrafts((current) => ({ ...current, [device.id]: { ...draft, controllable: event.target.value === 'true' } }))}><option value="true">可控制</option><option value="false">只读</option></select>
                  </div>
                  <div className="device-card__actions">
                    <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>{device.status === 'active' ? '在线' : device.status === 'offline' ? '离线' : '未启用'}</span>
                    {supportsVoiceSettings ? <button className="btn btn--outline btn--sm" type="button" onClick={() => openSpeakerSettings(device)} disabled={loading}>更多设置</button> : null}
                    <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSaveDevice(device.id)} disabled={loading}>保存修改</button>
                  </div>
                </Card>
              );
            })}
          </div>
        </Section>
        {speakerDetailDevice ? (
          <SpeakerDeviceDetailDialog
            device={speakerDetailDevice}
            roomName={roomNameMap[speakerDetailDevice.room_id ?? ''] ?? '未分配房间'}
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
              <div className="member-modal__header"><div><h3>选择要导入的房间</h3><p>这里只会导入当前家庭里还没有的房间，已经同名的会自动跳过。</p></div></div>
              <div className="ha-room-modal__list">{roomCandidates.length === 0 ? <div className="integration-status__detail">HA 里没有可识别的房间。</div> : roomCandidates.map((candidate) => (
                <label key={candidate.name} className={`ha-room-option ${candidate.can_sync ? '' : 'ha-room-option--disabled'}`}>
                  <input type="checkbox" checked={selectedRoomNames.includes(candidate.name)} disabled={!candidate.can_sync || loading} onChange={() => toggleRoomSelection(candidate.name)} />
                  <div className="ha-room-option__body"><div className="ha-room-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.can_sync ? 'success' : 'warning'}`}>{candidate.can_sync ? '可导入' : '已存在'}</span></div><div className="integration-status__detail">{candidate.exists_locally ? '当前家庭里已经有同名房间。' : '导入后可直接给设备分配房间。'}</div></div>
                </label>
              ))}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setRoomModalOpen(false)} disabled={loading}>取消</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmRoomSync()} disabled={loading || selectedRoomNames.length === 0}>导入选中房间</button></div>
            </div>
          </div>
        ) : null}
        {deviceModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setDeviceModalOpen(false)}>
            <div className="member-modal ha-device-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>选择要导入的设备</h3><p>设备会按房间分组显示。你可以整组选，也可以逐个挑。</p></div></div>
              <div className="ha-device-modal__list">{deviceCandidateGroups.length === 0 ? <div className="integration-status__detail">暂时没有可导入的设备。</div> : deviceCandidateGroups.map((group) => {
                const deviceIds = group.items.map((item) => item.external_device_id);
                const selectedCount = deviceIds.filter((id) => selectedExternalDeviceIds.includes(id)).length;
                const allSelected = selectedCount === deviceIds.length;
                return (
                  <div key={group.roomName} className="ha-device-group">
                    <label className="ha-device-group__header"><input type="checkbox" checked={allSelected} onChange={() => toggleDeviceRoomSelection(deviceIds)} disabled={loading} /><div className="ha-device-group__meta"><strong>{group.roomName}</strong><span className="integration-status__detail">已选 {selectedCount}/{group.items.length} 台</span></div></label>
                    <div className="ha-device-group__items">{group.items.map((candidate) => (
                      <label key={candidate.external_device_id} className="ha-device-option">
                        <input type="checkbox" checked={selectedExternalDeviceIds.includes(candidate.external_device_id)} onChange={() => toggleDeviceSelection(candidate.external_device_id)} disabled={loading} />
                        <div className="ha-device-option__body"><div className="ha-device-option__title-row"><strong>{candidate.name}</strong><span className={`badge badge--${candidate.already_synced ? 'secondary' : 'success'}`}>{candidate.already_synced ? '已导入过' : '新设备'}</span></div><div className="integration-status__detail">{formatDeviceType(candidate.device_type as Device['device_type'])} · {candidate.already_synced ? '再次导入会更新它的名称和房间信息。' : '导入后会加入当前家庭设备列表。'}</div></div>
                      </label>
                    ))}</div>
                  </div>
                );
              })}</div>
              <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setDeviceModalOpen(false)} disabled={loading}>取消</button><button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmDeviceSync()} disabled={loading || selectedExternalDeviceIds.length === 0}>导入选中设备</button></div>
            </div>
          </div>
        ) : null}
        {configModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setConfigModalOpen(false)}>
            <div className="member-modal ha-config-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header"><div><h3>连接 Home Assistant</h3><p>这里只影响当前家庭，其他家庭不会受影响。</p></div></div>
              <form className="settings-form integration-config-form" onSubmit={handleSaveHaConfig}>
                <div className="form-group"><label>Home Assistant 地址</label><input className="form-input" value={haForm.base_url} onChange={(event) => setHaForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="http://homeassistant.local:8123" /><div className="form-help">这里填写你的 Home Assistant 地址。保存后，这一页会显示连接情况。</div></div>
                <div className="form-group"><label>访问密钥（Long-Lived Token）</label><input className="form-input" type="password" value={haForm.access_token} onChange={(event) => setHaForm((current) => ({ ...current, access_token: event.target.value, clear_access_token: false }))} placeholder={haConfig?.token_configured ? '已配置，留空表示不改' : '请输入当前家庭使用的访问密钥'} /><div className="form-help">如果之前已经填过，留空就是保持不变。当前：{haConfig?.token_configured ? '已保存' : '未填写'}。</div></div>
                <div className="integration-config-grid"><div className="form-group"><label>导入房间时</label><select className="form-select" value={haForm.sync_rooms_enabled ? 'true' : 'false'} onChange={(event) => setHaForm((current) => ({ ...current, sync_rooms_enabled: event.target.value === 'true' }))}><option value="false">只导入设备</option><option value="true">导入设备时，顺便匹配已有房间</option></select></div><div className="form-group"><label>访问密钥处理</label><select className="form-select" value={haForm.clear_access_token ? 'clear' : 'keep'} onChange={(event) => setHaForm((current) => ({ ...current, clear_access_token: event.target.value === 'clear', access_token: event.target.value === 'clear' ? '' : current.access_token }))}><option value="keep">保留现有访问密钥</option><option value="clear">清空现有访问密钥</option></select></div></div>
                <div className="member-modal__actions"><button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(false)} disabled={loading}>取消</button><button className="btn btn--outline btn--sm" type="submit" disabled={loading}>{loading ? '保存中...' : '保存连接设置'}</button></div>
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
