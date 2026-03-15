import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import { useDidShow } from '@tarojs/taro';
import {
  ContextOverviewRead,
  Device,
  HomeAssistantConfig,
  HomeAssistantDeviceCandidate,
  HomeAssistantRoomCandidate,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  Room,
  VoiceDiscoveryTerminal,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  FormField,
  OptionPills,
  PrimaryButton,
  SecondaryButton,
  SectionNote,
  TextInput,
} from '../../../components/AppUi';
import { MainShellPage } from '../../../components/MainShellPage';
import { coreApiClient, useAppRuntime } from '../../../runtime';

const BOOLEAN_OPTIONS = [
  { value: 'true', label: '开启' },
  { value: 'false', label: '关闭' },
] as const;

type HaConfigForm = {
  baseUrl: string;
  accessToken: string;
  syncRoomsEnabled: boolean;
  clearAccessToken: boolean;
};

function buildHaConfigForm(config?: HomeAssistantConfig | null): HaConfigForm {
  return {
    baseUrl: config?.base_url ?? '',
    accessToken: '',
    syncRoomsEnabled: config?.sync_rooms_enabled ?? false,
    clearAccessToken: false,
  };
}

function formatHaStatus(config: HomeAssistantConfig | null, statusValue: ContextOverviewRead['home_assistant_status'] | undefined) {
  if (!config?.base_url || !config.token_configured) {
    return { label: '未配置', tone: 'warning' as const };
  }

  switch (statusValue) {
    case 'healthy':
      return { label: '已连接', tone: 'success' as const };
    case 'degraded':
      return { label: '部分降级', tone: 'warning' as const };
    case 'offline':
      return { label: '连接离线', tone: 'warning' as const };
    default:
      return { label: '待检测', tone: 'info' as const };
  }
}

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '暂无';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('zh-CN');
}

function formatVoiceDiscoveryStatus(status: VoiceDiscoveryTerminal['connection_status']) {
  switch (status) {
    case 'online':
      return '在线';
    case 'offline':
      return '离线';
    default:
      return '未知';
  }
}

function formatVoiceDiscoverySerial(sn: string) {
  const normalized = sn.trim();
  if (normalized.length <= 4) {
    return normalized;
  }
  return normalized.slice(-4);
}

function mergeVoiceDiscoveryDrafts(
  items: VoiceDiscoveryTerminal[],
  rooms: Room[],
  previous: Record<string, { terminalName: string; roomId: string }>,
) {
  const fallbackRoomId = rooms[0]?.id ?? '';
  return Object.fromEntries(
    items.map(item => {
      const nextDraft = normalizeVoiceDiscoveryDraft(previous[item.fingerprint], rooms);
      return [
        item.fingerprint,
        nextDraft ?? {
          terminalName: '家庭音箱',
          roomId: fallbackRoomId,
        },
      ];
    }),
  );
}

function normalizeVoiceDiscoveryDraft(
  draft: { terminalName: string; roomId: string } | undefined,
  rooms: Room[],
) {
  if (!draft) {
    return null;
  }
  const fallbackRoomId = rooms[0]?.id ?? '';
  const hasRoom = rooms.some(room => room.id === draft.roomId);
  return {
    terminalName: draft.terminalName || '家庭音箱',
    roomId: hasRoom ? draft.roomId : fallbackRoomId,
  };
}

export default function SettingsIntegrationsPage() {
  const { bootstrap, refresh } = useAppRuntime();
  const [overview, setOverview] = useState<ContextOverviewRead | null>(null);
  const [haConfig, setHaConfig] = useState<HomeAssistantConfig | null>(null);
  const [haForm, setHaForm] = useState<HaConfigForm>(buildHaConfigForm());
  const [devices, setDevices] = useState<Device[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [deviceCandidates, setDeviceCandidates] = useState<HomeAssistantDeviceCandidate[]>([]);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [roomCandidates, setRoomCandidates] = useState<HomeAssistantRoomCandidate[]>([]);
  const [selectedRoomNames, setSelectedRoomNames] = useState<string[]>([]);
  const [voiceDiscoveries, setVoiceDiscoveries] = useState<VoiceDiscoveryTerminal[]>([]);
  const [voiceDrafts, setVoiceDrafts] = useState<Record<string, { terminalName: string; roomId: string }>>({});
  const [syncSummary, setSyncSummary] = useState<HomeAssistantSyncResponse | null>(null);
  const [roomSyncSummary, setRoomSyncSummary] = useState<HomeAssistantRoomSyncResponse | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [busyKey, setBusyKey] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [voiceError, setVoiceError] = useState('');
  const activeHouseholdIdRef = useRef('');
  const loadRequestIdRef = useRef(0);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';
  const haStatus = formatHaStatus(haConfig, overview?.home_assistant_status);
  const roomNameMap = useMemo(() => new Map(rooms.map(room => [room.id, room.name])), [rooms]);
  const canOperateHa = Boolean(haConfig?.base_url && haConfig?.token_configured);

  const loadWorkspace = useCallback(async () => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      activeHouseholdIdRef.current = householdId;
      setOverview(null);
      setHaConfig(null);
      setHaForm(buildHaConfigForm());
      setDevices([]);
      setRooms([]);
      setDeviceCandidates([]);
      setSelectedDeviceIds([]);
      setRoomCandidates([]);
      setSelectedRoomNames([]);
      setVoiceDiscoveries([]);
      setVoiceDrafts({});
      setSyncSummary(null);
      setRoomSyncSummary(null);
      setStatus('');
      setError('');
      setVoiceError('');
    }

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');
    setVoiceError('');

    try {
      const [
        overviewResult,
        haConfigResult,
        devicesResult,
        roomsResult,
        voiceResult,
      ] = await Promise.all([
        coreApiClient.getContextOverview(householdId).catch(() => null),
        coreApiClient.getHomeAssistantConfig(householdId).catch(() => null),
        coreApiClient.listDevices(householdId).catch(() => ({ items: [] as Device[] })),
        coreApiClient.listRooms(householdId).catch(() => ({ items: [] as Room[] })),
        coreApiClient.listVoiceTerminalDiscoveries(householdId).catch(loadError => {
          if (requestId === loadRequestIdRef.current) {
            setVoiceError(loadError instanceof Error ? loadError.message : '语音终端发现列表读取失败');
          }
          return null;
        }),
      ]);

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      setOverview(overviewResult);
      setHaConfig(haConfigResult);
      setHaForm(buildHaConfigForm(haConfigResult));
      setDevices(devicesResult.items);
      setRooms(roomsResult.items);

      const voiceItems = voiceResult?.items ?? [];
      setVoiceDiscoveries(voiceItems);
      setVoiceDrafts(current => mergeVoiceDiscoveryDrafts(voiceItems, roomsResult.items, current));

      if (!overviewResult || !haConfigResult) {
        setError('部分集成状态读取失败，当前页会保留可运行边界，不会假装一切正常。');
      }
    } catch (loadError) {
      if (requestId === loadRequestIdRef.current) {
        setError(loadError instanceof Error ? loadError.message : '集成页加载失败');
      }
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [currentHouseholdId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useDidShow(() => {
    if (currentHouseholdId) {
      void loadWorkspace();
    }
  });

  async function reloadWorkspace(successMessage?: string) {
    await Promise.all([
      loadWorkspace(),
      refresh(),
    ]);
    if (successMessage) {
      setStatus(successMessage);
    }
  }

  function toggleDeviceSelection(externalDeviceId: string) {
    setSelectedDeviceIds(current => (
      current.includes(externalDeviceId)
        ? current.filter(item => item !== externalDeviceId)
        : [...current, externalDeviceId]
    ));
  }

  function toggleRoomSelection(roomName: string) {
    setSelectedRoomNames(current => (
      current.includes(roomName)
        ? current.filter(item => item !== roomName)
        : [...current, roomName]
    ));
  }

  async function handleSaveHaConfig() {
    if (!currentHouseholdId) {
      setError('当前没有可用的家庭上下文');
      return;
    }

    setBusyKey('ha-config');
    setStatus('');
    setError('');

    try {
      const result = await coreApiClient.updateHomeAssistantConfig(currentHouseholdId, {
        base_url: haForm.baseUrl.trim() || null,
        access_token: haForm.accessToken.trim() || undefined,
        clear_access_token: haForm.clearAccessToken,
        sync_rooms_enabled: haForm.syncRoomsEnabled,
      });
      setHaConfig(result);
      setHaForm(buildHaConfigForm(result));
      await reloadWorkspace('Home Assistant 连接配置已保存。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存 HA 配置失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleLoadDeviceCandidates() {
    if (!currentHouseholdId || !canOperateHa) {
      return;
    }

    setBusyKey('device-candidates');
    setStatus('');
    setError('');

    try {
      const result = await coreApiClient.listHomeAssistantDeviceCandidates(currentHouseholdId);
      setDeviceCandidates(result.items);
      setSelectedDeviceIds([]);
      setStatus('已刷新 Home Assistant 设备候选列表。');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '读取 HA 设备候选失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSyncDevices(syncAll: boolean) {
    if (!currentHouseholdId || !canOperateHa) {
      return;
    }

    const targetIds = syncAll ? [] : selectedDeviceIds;
    if (!syncAll && targetIds.length === 0) {
      setError('请先选中至少一个 HA 设备');
      return;
    }

    setBusyKey(syncAll ? 'device-sync-all' : 'device-sync-selected');
    setStatus('');
    setError('');

    try {
      const result = syncAll
        ? await coreApiClient.syncHomeAssistant(currentHouseholdId)
        : await coreApiClient.syncSelectedHomeAssistantDevices(currentHouseholdId, targetIds);
      setSyncSummary(result);
      await reloadWorkspace(syncAll ? 'HA 设备已全部同步。' : '选中的 HA 设备已同步。');
      setSelectedDeviceIds([]);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : '同步 HA 设备失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleLoadRoomCandidates() {
    if (!currentHouseholdId || !canOperateHa) {
      return;
    }

    setBusyKey('room-candidates');
    setStatus('');
    setError('');

    try {
      const result = await coreApiClient.listHomeAssistantRoomCandidates(currentHouseholdId);
      setRoomCandidates(result.items);
      setSelectedRoomNames([]);
      setStatus('已刷新 Home Assistant 房间候选列表。');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '读取 HA 房间候选失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleSyncRooms(syncAll: boolean) {
    if (!currentHouseholdId || !canOperateHa) {
      return;
    }

    const targetNames = syncAll ? [] : selectedRoomNames;
    if (!syncAll && targetNames.length === 0) {
      setError('请先选中至少一个 HA 房间');
      return;
    }

    setBusyKey(syncAll ? 'room-sync-all' : 'room-sync-selected');
    setStatus('');
    setError('');

    try {
      const result = syncAll
        ? await coreApiClient.syncHomeAssistantRooms(currentHouseholdId)
        : await coreApiClient.syncSelectedHomeAssistantRooms(currentHouseholdId, targetNames);
      setRoomSyncSummary(result);
      await reloadWorkspace(syncAll ? 'HA 房间已全部同步。' : '选中的 HA 房间已同步。');
      setSelectedRoomNames([]);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : '同步 HA 房间失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleClaimVoiceDiscovery(fingerprint: string) {
    if (!currentHouseholdId) {
      return;
    }

    const draft = normalizeVoiceDiscoveryDraft(voiceDrafts[fingerprint], rooms);
    if (!draft?.roomId || !draft.terminalName.trim()) {
      setVoiceError('请先为待认领音箱填写名称并选择房间。');
      return;
    }

    setBusyKey(`voice-${fingerprint}`);
    setStatus('');
    setVoiceError('');

    try {
      await coreApiClient.claimVoiceTerminalDiscovery(fingerprint, {
        household_id: currentHouseholdId,
        room_id: draft.roomId,
        terminal_name: draft.terminalName.trim(),
      });
      await reloadWorkspace('语音终端已认领到当前家庭。');
    } catch (claimError) {
      setVoiceError(claimError instanceof Error ? claimError.message : '认领语音终端失败');
    } finally {
      setBusyKey('');
    }
  }

  return (
    <MainShellPage
      currentNav="settings"
      title="设备与集成页已经进入 user-app"
      description="这里先只接旧页里真实可用的 HA、设备同步、房间同步和语音终端认领能力，不碰被禁改的后端模块。"
    >
      <PageSection title="集成总览" description="先看清当前家庭的集成状态，再动配置。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="Home Assistant" value={haStatus.label} tone={haStatus.tone} />
        <StatusCard label="本地设备" value={`${devices.length}`} tone="info" />
        <StatusCard label="房间数量" value={`${rooms.length}`} tone="success" />
        <StatusCard label="待认领音箱" value={`${voiceDiscoveries.length}`} tone={voiceDiscoveries.length > 0 ? 'warning' : 'success'} />
        {pageLoading ? <SectionNote>正在读取集成状态...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
        {voiceError ? <SectionNote tone="warning">{voiceError}</SectionNote> : null}
      </PageSection>

      <PageSection title="Home Assistant 连接配置" description="这里保存的是当前家庭专属配置，不影响别的家庭。">
        <FormField label="HA 地址">
          <TextInput value={haForm.baseUrl} placeholder="http://homeassistant.local:8123" onInput={value => setHaForm(current => ({ ...current, baseUrl: value }))} />
        </FormField>
        <FormField label="Long-Lived Token" hint={haConfig?.token_configured ? '当前已保存 Token；留空表示不改。' : '当前还没有可用 Token。'}>
          <TextInput value={haForm.accessToken} password placeholder="请输入当前家庭专用 Token" onInput={value => setHaForm(current => ({ ...current, accessToken: value, clearAccessToken: false }))} />
        </FormField>
        <FormField label="同步设备时自动关联已有房间">
          <OptionPills value={haForm.syncRoomsEnabled ? 'true' : 'false'} options={BOOLEAN_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setHaForm(current => ({ ...current, syncRoomsEnabled: value === 'true' }))} />
        </FormField>
        <FormField label="Token 操作">
          <OptionPills value={haForm.clearAccessToken ? 'true' : 'false'} options={[{ value: 'false', label: '保留现有 Token' }, { value: 'true', label: '清空现有 Token' }]} onChange={value => setHaForm(current => ({ ...current, clearAccessToken: value === 'true', accessToken: value === 'true' ? '' : current.accessToken }))} />
        </FormField>
        <ActionRow>
          <PrimaryButton disabled={busyKey === 'ha-config'} onClick={() => void handleSaveHaConfig()}>
            {busyKey === 'ha-config' ? '保存中...' : '保存 HA 配置'}
          </PrimaryButton>
          <SecondaryButton onClick={() => void loadWorkspace()}>
            重新读取集成状态
          </SecondaryButton>
        </ActionRow>
        <SectionNote>
          当前状态：{haStatus.label}。最近设备同步时间：{formatRelativeTime(haConfig?.last_device_sync_at)}。
        </SectionNote>
      </PageSection>

      <PageSection title="HA 设备同步" description="这里只接已经存在的设备候选与同步 API，不去碰别的后端模块。">
        {!canOperateHa ? (
          <EmptyStateCard title="还不能同步 HA 设备" description="先把 HA 地址和 Token 配好，不要指望页面替你猜。" />
        ) : (
          <>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'device-candidates'} onClick={() => void handleLoadDeviceCandidates()}>
                {busyKey === 'device-candidates' ? '刷新中...' : '刷新设备候选'}
              </PrimaryButton>
              <SecondaryButton disabled={busyKey === 'device-sync-all'} onClick={() => void handleSyncDevices(true)}>
                {busyKey === 'device-sync-all' ? '同步中...' : '同步全部设备'}
              </SecondaryButton>
              <SecondaryButton disabled={busyKey === 'device-sync-selected'} onClick={() => void handleSyncDevices(false)}>
                {busyKey === 'device-sync-selected' ? '同步中...' : `同步选中设备 (${selectedDeviceIds.length})`}
              </SecondaryButton>
            </ActionRow>
            {syncSummary ? (
              <SectionNote tone="success">
                本次设备同步新增 {syncSummary.created_devices} 台、更新 {syncSummary.updated_devices} 台、自动分配房间 {syncSummary.assigned_rooms} 台、失败 {syncSummary.failed_entities} 项。
              </SectionNote>
            ) : null}
            {deviceCandidates.length === 0 ? (
              <EmptyStateCard title="当前还没有设备候选" description="先点“刷新设备候选”从 HA 拉一次候选列表。" />
            ) : (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {deviceCandidates.map(candidate => {
                  const selected = selectedDeviceIds.includes(candidate.external_device_id);
                  return (
                    <View
                      key={candidate.external_device_id}
                      style={{
                        background: selected ? '#eef5ff' : '#ffffff',
                        border: `1px solid ${selected ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                        borderRadius: userAppTokens.radiusLg,
                        padding: userAppTokens.spacingMd,
                      }}
                    >
                      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                        {candidate.name}
                      </Text>
                      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                        {candidate.device_type} · 主实体 {candidate.primary_entity_id} · 关联实体 {candidate.entity_count} 个
                      </Text>
                      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                        房间：{candidate.room_name ?? 'HA 未提供房间'}
                      </Text>
                      <ActionRow>
                        <SecondaryButton onClick={() => toggleDeviceSelection(candidate.external_device_id)}>
                          {selected ? '取消选择' : candidate.already_synced ? '重新同步这台' : '选择这台'}
                        </SecondaryButton>
                      </ActionRow>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        )}
      </PageSection>

      <PageSection title="HA 房间同步" description="房间同步只做当前后端已经支持的事情：读候选、选中、同步。">
        {!canOperateHa ? (
          <EmptyStateCard title="还不能同步 HA 房间" description="先把 HA 连接配置补全，再谈房间同步。" />
        ) : (
          <>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'room-candidates'} onClick={() => void handleLoadRoomCandidates()}>
                {busyKey === 'room-candidates' ? '刷新中...' : '刷新房间候选'}
              </PrimaryButton>
              <SecondaryButton disabled={busyKey === 'room-sync-all'} onClick={() => void handleSyncRooms(true)}>
                {busyKey === 'room-sync-all' ? '同步中...' : '同步全部房间'}
              </SecondaryButton>
              <SecondaryButton disabled={busyKey === 'room-sync-selected'} onClick={() => void handleSyncRooms(false)}>
                {busyKey === 'room-sync-selected' ? '同步中...' : `同步选中房间 (${selectedRoomNames.length})`}
              </SecondaryButton>
            </ActionRow>
            {roomSyncSummary ? (
              <SectionNote tone="success">
                本次房间同步创建了 {roomSyncSummary.created_rooms} 个房间，匹配实体 {roomSyncSummary.matched_entities} 项，跳过 {roomSyncSummary.skipped_entities} 项。
              </SectionNote>
            ) : null}
            {roomCandidates.length === 0 ? (
              <EmptyStateCard title="当前还没有房间候选" description="先点“刷新房间候选”从 HA 拉一次。" />
            ) : (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {roomCandidates.map(candidate => {
                  const selected = selectedRoomNames.includes(candidate.name);
                  return (
                    <View
                      key={candidate.name}
                      style={{
                        background: selected ? '#eef5ff' : '#ffffff',
                        border: `1px solid ${selected ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                        borderRadius: userAppTokens.radiusLg,
                        padding: userAppTokens.spacingMd,
                      }}
                    >
                      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                        {candidate.name}
                      </Text>
                      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                        关联实体 {candidate.entity_count} 个 · {candidate.exists_locally ? '本地已存在同名房间' : '本地尚未存在'}
                      </Text>
                      <ActionRow>
                        <SecondaryButton disabled={!candidate.can_sync} onClick={() => toggleRoomSelection(candidate.name)}>
                          {!candidate.can_sync ? '本地重名，不能同步' : selected ? '取消选择' : '选择这个房间'}
                        </SecondaryButton>
                      </ActionRow>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        )}
      </PageSection>

      <PageSection title="语音终端发现与认领" description="这块只接现有发现与认领接口，不会擅自改你禁止触碰的后端模块。">
        {voiceDiscoveries.length === 0 ? (
          <EmptyStateCard title="当前没有待认领音箱" description="如果局域网里暂时没发现新终端，这里就应该是空，不要伪造数据。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {voiceDiscoveries.map(item => {
              const draft = normalizeVoiceDiscoveryDraft(voiceDrafts[item.fingerprint], rooms) ?? {
                terminalName: '家庭音箱',
                roomId: rooms[0]?.id ?? '',
              };
              return (
                <View
                  key={item.fingerprint}
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                    {item.model}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                    设备编号尾号 {formatVoiceDiscoverySerial(item.sn)} · {formatVoiceDiscoveryStatus(item.connection_status)} · 最近发现于 {formatRelativeTime(item.last_seen_at)}
                  </Text>
                  <FormField label="终端名称">
                    <TextInput
                      value={draft.terminalName}
                      onInput={value => setVoiceDrafts(current => {
                        const currentDraft = normalizeVoiceDiscoveryDraft(current[item.fingerprint], rooms) ?? draft;
                        return {
                          ...current,
                          [item.fingerprint]: {
                            ...currentDraft,
                            terminalName: value,
                          },
                        };
                      })}
                    />
                  </FormField>
                  <FormField label="归属房间">
                    {rooms.length === 0 ? (
                      <SectionNote tone="warning">当前家庭还没有房间，先去家庭页建房间，否则这里没法认领。</SectionNote>
                    ) : (
                      <OptionPills
                        value={draft.roomId}
                        options={rooms.map(room => ({ value: room.id, label: room.name }))}
                        onChange={value => setVoiceDrafts(current => {
                          const currentDraft = normalizeVoiceDiscoveryDraft(current[item.fingerprint], rooms) ?? draft;
                          return {
                            ...current,
                            [item.fingerprint]: {
                              ...currentDraft,
                              roomId: value,
                            },
                          };
                        })}
                      />
                    )}
                  </FormField>
                  <ActionRow>
                    <PrimaryButton disabled={busyKey === `voice-${item.fingerprint}` || rooms.length === 0} onClick={() => void handleClaimVoiceDiscovery(item.fingerprint)}>
                      {busyKey === `voice-${item.fingerprint}` ? '认领中...' : '认领到当前家庭'}
                    </PrimaryButton>
                  </ActionRow>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="当前本地设备" description="这轮先把设备清单可见化，确认同步结果不是黑盒。">
        {devices.length === 0 ? (
          <EmptyStateCard title="当前还没有本地设备" description="要么还没同步，要么这个家庭本来就没有设备数据。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {devices.map(device => (
              <View
                key={device.id}
                style={{
                  background: '#ffffff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  padding: userAppTokens.spacingMd,
                }}
              >
                <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '26px', fontWeight: '600' }}>
                  {device.name}
                </Text>
                <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                  {device.device_type} · {device.status} · {device.controllable ? '可控制' : '只读'}
                </Text>
                <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                  房间：{device.room_id ? roomNameMap.get(device.room_id) ?? device.room_id : '未分配'}
                </Text>
              </View>
            ))}
          </View>
        )}
      </PageSection>
    </MainShellPage>
  );
}
