/* ============================================================
 * 设置页 - 二级导航 + 6 个子页面
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { Outlet, useMatch, Navigate } from 'react-router-dom';
import { formatLocaleOptionLabel, getLocaleSourceLabel, useI18n } from '../i18n';
import { useTheme, themeList, type ThemeId } from '../theme';
import { PageHeader, Card, Section, ToggleSwitch } from '../components/base';
import { SettingsNav } from '../components/SettingsNav';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import type {
  ContextConfigRead,
  ContextOverviewRead,
  Device,
  HomeAssistantConfig,
  HomeAssistantDeviceCandidate,
  HomeAssistantRoomCandidate,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  Room,
} from '../lib/types';
export { SettingsAiPage as SettingsAi } from './SettingsAiPage';

function useContextConfigSettings() {
  const { currentHouseholdId } = useHouseholdContext();
  const [config, setConfig] = useState<ContextConfigRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    if (!currentHouseholdId) {
      setConfig(null);
      return;
    }

    let cancelled = false;

    const loadConfig = async () => {
      setLoading(true);
      setError('');
      setStatus('');
      try {
        const result = await api.getContextConfig(currentHouseholdId);
        if (!cancelled) {
          setConfig(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载设置失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadConfig();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  async function savePatch(patch: Partial<Omit<ContextConfigRead, 'household_id' | 'version' | 'updated_by' | 'updated_at'>>) {
    if (!currentHouseholdId || !config) {
      return;
    }

    setLoading(true);
    setError('');
    setStatus('');
    try {
      const result = await api.updateContextConfig(currentHouseholdId, {
        home_mode: config.home_mode,
        privacy_mode: config.privacy_mode,
        automation_level: config.automation_level,
        home_assistant_status: config.home_assistant_status,
        active_member_id: config.active_member_id,
        voice_fast_path_enabled: config.voice_fast_path_enabled,
        guest_mode_enabled: config.guest_mode_enabled,
        child_protection_enabled: config.child_protection_enabled,
        elder_care_watch_enabled: config.elder_care_watch_enabled,
        quiet_hours_enabled: config.quiet_hours_enabled,
        quiet_hours_start: config.quiet_hours_start,
        quiet_hours_end: config.quiet_hours_end,
        member_states: config.member_states,
        room_settings: config.room_settings,
        ...patch,
      });
      setConfig(result);
      setStatus('设置已保存。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存设置失败');
    } finally {
      setLoading(false);
    }
  }

  return { config, loading, error, status, savePatch };
}

/* ---- 设置布局 ---- */
export function SettingsLayout() {
  const { t } = useI18n();
  const isRoot = useMatch('/settings');

  if (isRoot) {
    return <Navigate to="/settings/appearance" replace />;
  }

  return (
    <div className="page page--settings">
      <PageHeader title={t('settings.title')} />
      <div className="settings-layout">
        <SettingsNav />
        <div className="settings-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/* ---- 外观主题 ---- */
export function SettingsAppearance() {
  const { t } = useI18n();
  const { themeId, setTheme } = useTheme();

  return (
    <div className="settings-page">
      <Section title={t('settings.appearance.theme')}>
        <div className="theme-grid">
          {themeList.map(th => (
            <div
              key={th.id}
              className={`theme-card ${themeId === th.id ? 'theme-card--active' : ''}`}
              onClick={() => setTheme(th.id)}
              style={{
                '--preview-bg': th.bgApp,
                '--preview-card': th.bgCard,
                '--preview-brand': th.brandPrimary,
                '--preview-text': th.textPrimary,
                '--preview-glow': th.glowColor,
              } as React.CSSProperties}
            >
              {/* 主题预览色块 */}
              <div className="theme-card__preview">
                <div className="theme-card__preview-bg">
                  <div className="theme-card__preview-sidebar" />
                  <div className="theme-card__preview-content">
                    <div className="theme-card__preview-bar" />
                    <div className="theme-card__preview-cards">
                      <div className="theme-card__preview-mini" />
                      <div className="theme-card__preview-mini" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="theme-card__info">
                <span className="theme-card__emoji">{th.emoji}</span>
                <div className="theme-card__text">
                  <span className="theme-card__label">{th.label}</span>
                  <span className="theme-card__desc">{th.description}</span>
                </div>
                {themeId === th.id && <span className="theme-card__check">✓</span>}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

/* ---- AI 配置 ---- */
export function LegacySettingsAi() {
  const { t } = useI18n();
  const { config, loading, error, status, savePatch } = useContextConfigSettings();

  const privacyValue = config?.privacy_mode ?? 'balanced';

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.ai.assistantName')}</label>
            <input type="text" className="form-input" value="家庭助手" disabled readOnly />
            <div className="form-help">这个字段后端还没有稳定的用户态配置，先展示默认值，不支持保存。</div>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyTone')}</label>
            <select className="form-select" value="温和友好" disabled>
              <option>温和友好</option>
              <option>简洁干练</option>
              <option>活泼有趣</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyLength')}</label>
            <select className="form-select" value="适中" disabled>
              <option>适中</option>
              <option>简短</option>
              <option>详细</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.outputLanguage')}</label>
            <select className="form-select" value="中文" disabled>
              <option>中文</option>
              <option>English</option>
            </select>
            <div className="form-help">回复语气、长度和输出语言当前都是产品预留项，先不做假保存。</div>
          </div>

          <div className="settings-toggles">
            <ToggleSwitch checked={true} label={t('settings.ai.useMemory')} description={`${t('settings.ai.useMemoryDesc')} 当前按系统默认策略运行，暂不支持单独保存。`} disabled />
            <ToggleSwitch checked={true} label={t('settings.ai.suggestReminder')} description={`${t('settings.ai.suggestReminderDesc')} 当前按系统默认策略运行，暂不支持单独保存。`} disabled />
            <ToggleSwitch checked={false} label={t('settings.ai.suggestScene')} description={`${t('settings.ai.suggestSceneDesc')} 场景策略还没有稳定的用户态配置字段。`} disabled />
          </div>

          <Section title="家庭服务开关" className="section--embedded">
            <div className="settings-toggles">
              <ToggleSwitch checked={config?.voice_fast_path_enabled ?? false} label="语音快通道" description="开启后，系统会优先走更快的语音响应链路。" onChange={value => void savePatch({ voice_fast_path_enabled: value })} />
              <ToggleSwitch checked={config?.guest_mode_enabled ?? false} label="访客模式" description="开启后，访客相关提示和家庭上下文会用更保守的展示方式。" onChange={value => void savePatch({ guest_mode_enabled: value })} />
              <ToggleSwitch checked={config?.child_protection_enabled ?? false} label="儿童保护" description="开启后，系统会对儿童相关提醒和内容给出更严格的边界。" onChange={value => void savePatch({ child_protection_enabled: value })} />
              <ToggleSwitch checked={config?.elder_care_watch_enabled ?? false} label="长辈关怀" description="开启后，系统会更关注长辈提醒和异常状态。" onChange={value => void savePatch({ elder_care_watch_enabled: value })} />
            </div>
          </Section>

          <div className="form-group">
            <label>{t('settings.ai.privacyLevel')}</label>
            <select className="form-select" value={privacyValue} onChange={event => void savePatch({ privacy_mode: event.target.value as ContextConfigRead['privacy_mode'] })} disabled={loading || !config}>
              <option value="balanced">标准</option>
              <option value="strict">严格</option>
              <option value="care">关怀优先</option>
            </select>
          </div>
        </div>
        <div className="settings-note">
          <span>🧩</span> 当前已接入真实字段：隐私级别。助手称呼、回复语气、长度和记忆策略，后端还没有稳定的用户态配置字段，先保留产品骨架。
        </div>
        {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
        {status && <div className="settings-note"><span>✅</span> {status}</div>}
        <div className="settings-note">
          <span>ℹ️</span> {t('settings.ai.advancedNote')}
        </div>
      </Section>
    </div>
  );
}

/* ---- 语言与地区 ---- */
export function SettingsLanguage() {
  const { t, locale, setLocale, locales } = useI18n();

  function renderLocaleSource(localeItem: typeof locales[number]) {
    switch (getLocaleSourceLabel(localeItem)) {
      case 'builtin':
        return t('settings.language.sourceBuiltin');
      case 'official':
        return t('settings.language.sourceOfficial');
      default:
        return t('settings.language.sourceThirdParty');
    }
  }

  return (
    <div className="settings-page">
      <Section title={t('settings.language')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.language.interfaceLang')}</label>
            <select className="form-select" value={locale} onChange={e => setLocale(e.target.value)}>
              {locales.map(item => (
                <option key={item.id} value={item.id}>{formatLocaleOptionLabel(item)}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.dateFormat')}</label>
            <select className="form-select" value="YYYY-MM-DD" disabled>
              <option>YYYY-MM-DD</option>
              <option>MM/DD/YYYY</option>
              <option>DD/MM/YYYY</option>
            </select>
            <div className="form-help">日期格式当前跟随系统默认规则展示，暂不支持单独保存。</div>
          </div>
          <div className="form-group">
            <label>{t('settings.language.timeFormat')}</label>
            <select className="form-select" value="24 小时制" disabled>
              <option>24 小时制</option>
              <option>12 小时制</option>
            </select>
            <div className="form-help">时间格式当前跟随系统默认规则展示，暂不支持单独保存。</div>
          </div>
          <div className="form-group">
            <label>{t('settings.language.localeCatalog')}</label>
            <div className="settings-note">
              <span>🧩</span> 语言是否可选、谁覆盖谁，当前都以家庭语言接口返回的结果为准。
            </div>
            <div className="settings-note">
              {locales.map(item => (
                <div key={item.id}>
                  {formatLocaleOptionLabel(item)} / {renderLocaleSource(item)} / {t('settings.language.pluginId')}: {item.pluginId ?? t('settings.language.none')} / {t('settings.language.fallback')}: {item.fallback ?? t('settings.language.none')} / {t('settings.language.overrides')}: {item.overriddenPluginIds?.join(', ') || t('settings.language.none')}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>
    </div>
  );
}

/* ---- 通知偏好 ---- */
export function SettingsNotifications() {
  const { t } = useI18n();
  const { config, loading, error, status, savePatch } = useContextConfigSettings();

  return (
    <div className="settings-page">
      <Section title={t('settings.notifications')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.notifications.method')}</label>
            <select className="form-select" value="浏览器通知 + 站内消息" disabled>
              <option>浏览器通知 + 站内消息</option>
              <option>仅站内消息</option>
              <option>全部关闭</option>
            </select>
            <div className="form-help">通知方式还没有对应的稳定后端字段，先展示默认推荐方案。</div>
          </div>
          <div className="settings-toggles">
            <ToggleSwitch checked={config?.quiet_hours_enabled ?? false} label={t('settings.notifications.dnd')} description={`开启后在 ${config?.quiet_hours_start ?? '22:00'}-${config?.quiet_hours_end ?? '07:00'} 不会收到通知`} onChange={value => void savePatch({ quiet_hours_enabled: value })} />
          </div>
          <div className="form-group">
            <label>{t('settings.notifications.scope')}</label>
            <select className="form-select" disabled>
              <option>全部通知</option>
              <option>仅紧急通知</option>
              <option>仅与我相关</option>
            </select>
          </div>
        </div>
        <div className="settings-note">
          <span>🧩</span> 当前已接入真实字段：免打扰开关和时段。通知方式、通知范围还没有对应的后端产品字段，先保留说明，不乱写映射。
        </div>
        {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
        {status && <div className="settings-note"><span>✅</span> {status}</div>}
      </Section>
    </div>
  );
}

/* ---- 长辈友好模式 ---- */
export function SettingsAccessibility() {
  const { t } = useI18n();
  const { themeId, setTheme } = useTheme();
  const isElder = themeId === 'ming-cha-qiu-hao';

  return (
    <div className="settings-page">
      <Section title={t('settings.accessibility')}>
        <div className="settings-toggles">
          <ToggleSwitch
            checked={isElder}
            label={t('settings.accessibility.enable')}
            description={t('settings.accessibility.enableDesc')}
            onChange={v => setTheme(v ? 'ming-cha-qiu-hao' : 'chun-he-jing-ming')}
          />
        </div>
        <div className="elder-preview">
          <Card className="elder-preview-card">
            <h3>预览效果</h3>
            <p style={{ fontSize: isElder ? '1.125rem' : '0.9375rem' }}>
              {isElder
                ? '长辈友好模式已开启。界面使用更大的字号和更高的对比度。'
                : '当前为标准模式。开启长辈友好模式后，界面会更适合年长用户使用。'}
            </p>
          </Card>
        </div>
      </Section>
    </div>
  );
}

/* ---- 设备与集成 ---- */
export function SettingsIntegrations() {
  const { t } = useI18n();
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
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!currentHouseholdId) {
      setOverview(null);
      setDevices([]);
      setRooms([]);
      return;
    }

    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError('');

      const [configResult, devicesResult, roomsResult] = await Promise.allSettled([
        api.getHomeAssistantConfig(currentHouseholdId),
        api.listDevices(currentHouseholdId),
        api.listRooms(currentHouseholdId),
      ]);

      if (cancelled) {
        return;
      }

      const nextConfig = configResult.status === 'fulfilled' ? configResult.value : null;
      setDevices(devicesResult.status === 'fulfilled' ? devicesResult.value.items : []);
      setRooms(roomsResult.status === 'fulfilled' ? roomsResult.value.items : []);
      setHaConfig(nextConfig);
      setHaForm({
        base_url: nextConfig?.base_url ?? '',
        access_token: '',
        sync_rooms_enabled: nextConfig?.sync_rooms_enabled ?? false,
        clear_access_token: false,
      });
      setDeviceDrafts(Object.fromEntries((devicesResult.status === 'fulfilled' ? devicesResult.value.items : []).map(device => [device.id, { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable }])));

      const hasHaConfig = Boolean(nextConfig?.base_url && nextConfig?.token_configured);
      if (hasHaConfig) {
        const overviewResult = await api.getContextOverview(currentHouseholdId).then(
          value => ({ status: 'fulfilled' as const, value }),
          reason => ({ status: 'rejected' as const, reason }),
        );

        if (cancelled) {
          return;
        }

        setOverview(overviewResult.status === 'fulfilled' ? overviewResult.value : null);
        const errors = [configResult, devicesResult, roomsResult, overviewResult]
          .filter(result => result.status === 'rejected')
          .map(result => result.reason instanceof Error ? result.reason.message : '集成数据加载失败');
        setError(errors.join('；'));
      } else {
        setOverview(null);
        const errors = [configResult, devicesResult, roomsResult]
          .filter(result => result.status === 'rejected')
          .map(result => result.reason instanceof Error ? result.reason.message : '集成数据加载失败');
        setError(errors.join('；'));
      }
      setLoading(false);
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  async function reloadWorkspace() {
    if (!currentHouseholdId) {
      return;
    }
    const [config, nextDevices, nextRooms] = await Promise.all([
      api.getHomeAssistantConfig(currentHouseholdId),
      api.listDevices(currentHouseholdId),
      api.listRooms(currentHouseholdId),
    ]);
    setHaConfig(config);
    setHaForm({
      base_url: config.base_url ?? '',
      access_token: '',
      sync_rooms_enabled: config.sync_rooms_enabled,
      clear_access_token: false,
    });
    const hasHaConfig = Boolean(config.base_url && config.token_configured);
    setOverview(hasHaConfig ? await api.getContextOverview(currentHouseholdId).catch(() => null) : null);
    setDevices(nextDevices.items);
    setRooms(nextRooms.items);
    setDeviceDrafts(Object.fromEntries(nextDevices.items.map(device => [device.id, { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable }])));
  }

  async function runAction(action: () => Promise<void>) {
    setLoading(true);
    setStatus('');
    setError('');
    try {
      await action();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveHaConfig(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      return;
    }

    await runAction(async () => {
      const result = await api.updateHomeAssistantConfig(currentHouseholdId, {
        base_url: haForm.base_url.trim() || null,
        access_token: haForm.access_token.trim() || undefined,
        clear_access_token: haForm.clear_access_token,
        sync_rooms_enabled: haForm.sync_rooms_enabled,
      });
      setHaConfig(result);
      setHaForm({
        base_url: result.base_url ?? '',
        access_token: '',
        sync_rooms_enabled: result.sync_rooms_enabled,
        clear_access_token: false,
      });
      setConfigModalOpen(false);
      setStatus('当前家庭的 Home Assistant 配置已保存。');
    });
  }

  async function openDeviceSyncModal() {
    if (!currentHouseholdId) {
      setError('还没有选中家庭，暂时无法同步。');
      return;
    }

    setDeviceModalLoading(true);
    setError('');
    try {
      const result = await api.listHomeAssistantDeviceCandidates(currentHouseholdId);
      setDeviceCandidates(result.items);
      setSelectedExternalDeviceIds(result.items.map(item => item.external_device_id));
      setDeviceModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '加载 HA 设备候选项失败');
    } finally {
      setDeviceModalLoading(false);
    }
  }

  async function handleConfirmDeviceSync() {
    if (!currentHouseholdId) {
      return;
    }

    await runAction(async () => {
      const result = await api.syncSelectedHomeAssistantDevices(currentHouseholdId, selectedExternalDeviceIds);
      setSyncSummary(result);
      setDeviceModalOpen(false);
      await reloadWorkspace();
      setStatus(`Home Assistant 同步完成，本次处理 ${result.created_devices + result.updated_devices} 台设备。`);
    });
  }

  async function openRoomSyncModal() {
    if (!currentHouseholdId) {
      setError('还没有选中家庭，暂时无法同步房间。');
      return;
    }
    setRoomModalLoading(true);
    setError('');
    try {
      const result = await api.listHomeAssistantRoomCandidates(currentHouseholdId);
      setRoomCandidates(result.items);
      setSelectedRoomNames(result.items.filter(item => item.can_sync).map(item => item.name));
      setRoomModalOpen(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '加载 HA 房间候选项失败');
    } finally {
      setRoomModalLoading(false);
    }
  }

  async function handleConfirmRoomSync() {
    if (!currentHouseholdId) {
      return;
    }

    await runAction(async () => {
      const result = await api.syncSelectedHomeAssistantRooms(currentHouseholdId, selectedRoomNames);
      setRoomSyncSummary(result);
      setRoomModalOpen(false);
      await reloadWorkspace();
      setStatus(`已从 HA 同步 ${result.created_rooms} 个房间。`);
    });
  }

  function toggleRoomSelection(roomName: string) {
    setSelectedRoomNames(current => current.includes(roomName)
      ? current.filter(name => name !== roomName)
      : [...current, roomName]);
  }

  function toggleDeviceSelection(externalDeviceId: string) {
    setSelectedExternalDeviceIds(current => current.includes(externalDeviceId)
      ? current.filter(id => id !== externalDeviceId)
      : [...current, externalDeviceId]);
  }

  function toggleDeviceRoomSelection(deviceIds: string[]) {
    setSelectedExternalDeviceIds(current => {
      const allSelected = deviceIds.every(id => current.includes(id));
      if (allSelected) {
        return current.filter(id => !deviceIds.includes(id));
      }
      return Array.from(new Set([...current, ...deviceIds]));
    });
  }

  async function handleSaveDevice(deviceId: string) {
    const draft = deviceDrafts[deviceId];
    if (!draft) {
      return;
    }

    await runAction(async () => {
      await api.updateDevice(deviceId, draft);
      await reloadWorkspace();
      setStatus('设备信息已更新。');
    });
  }

  const roomNameMap = useMemo(() => Object.fromEntries(rooms.map(room => [room.id, room.name])), [rooms]);
  const roomOptions = useMemo(() => [{ id: '', name: '未分配房间' }, ...rooms.map(room => ({ id: room.id, name: room.name }))], [rooms]);
  const deviceCandidateGroups = useMemo(() => {
    const groups = new Map<string, HomeAssistantDeviceCandidate[]>();
    deviceCandidates.forEach(candidate => {
      const roomName = candidate.room_name || '未分配房间';
      groups.set(roomName, [...(groups.get(roomName) ?? []), candidate]);
    });
    return Array.from(groups.entries())
      .map(([roomName, items]) => ({ roomName, items }))
      .sort((a, b) => a.roomName.localeCompare(b.roomName, 'zh-CN'));
  }, [deviceCandidates]);

  function formatDeviceType(type: Device['device_type']) {
    switch (type) {
      case 'light': return '灯光';
      case 'ac': return '温控';
      case 'curtain': return '窗帘';
      case 'speaker': return '音箱';
      case 'camera': return '安防';
      case 'sensor': return '传感器';
      case 'lock': return '门锁';
    }
  }

  function formatHaStatus(config: HomeAssistantConfig | null, statusValue: ContextOverviewRead['home_assistant_status'] | undefined) {
    if (!config?.base_url || !config.token_configured) {
      return { label: '未配置', tone: 'idle' as const };
    }
    switch (statusValue) {
      case 'healthy':
        return { label: '已连接', tone: 'online' as const };
      case 'degraded':
        return { label: '部分降级', tone: 'warning' as const };
      case 'offline':
        return { label: '连接离线', tone: 'offline' as const };
      default:
        return { label: '待检测', tone: 'warning' as const };
    }
  }

  const haStatus = formatHaStatus(haConfig, overview?.home_assistant_status);
  const lastSyncText = syncSummary ? '刚刚' : haConfig?.last_device_sync_at ?? (overview ? '已加载当前状态' : '暂无记录');
  const haAddressText = haConfig?.base_url ?? '未配置';
  const canOperateHa = Boolean(haConfig?.base_url && haConfig?.token_configured);
  const syncButtonLabel = canOperateHa ? (loading ? '同步中...' : t('settings.integrations.syncNow')) : '请先配置 HA 连接';
  const syncRoomsButtonLabel = canOperateHa ? '从 HA 同步房间' : '请先配置 HA 连接';
  const disabledHaActionTooltip = canOperateHa ? undefined : '请先在“配置连接”里填写 HA 地址和 Token';

  return (
    <div className="settings-page">
      <Section title={t('settings.integrations.haStatus')}>
        <Card className="integration-status-card">
          <div className="integration-status">
            <span className={`integration-status__indicator integration-status__indicator--${haStatus.tone}`} />
            <div className="integration-status__text">
              <span className="integration-status__label">Home Assistant</span>
              <span className="integration-status__detail">{haStatus.label} · {t('settings.integrations.lastSync')}：{lastSyncText}</span>
              <span className="integration-status__detail">HA 地址：{haAddressText}</span>
            </div>
            <div className="integration-actions">
              <button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(true)} disabled={loading}>配置连接</button>
              <span className="integration-action-tooltip" title={disabledHaActionTooltip}>
                <button className="btn btn--outline btn--sm" onClick={openDeviceSyncModal} disabled={loading || deviceModalLoading || !canOperateHa}>
                  {syncButtonLabel}
                </button>
              </span>
              <span className="integration-action-tooltip" title={disabledHaActionTooltip}>
                <button className="btn btn--outline btn--sm" onClick={openRoomSyncModal} disabled={loading || roomModalLoading || !canOperateHa}>
                  {syncRoomsButtonLabel}
                </button>
              </span>
            </div>
          </div>
          {syncSummary && (
            <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>
              本次同步新增 {syncSummary.created_devices} 台、更新 {syncSummary.updated_devices} 台、新增房间 {syncSummary.created_rooms} 个、自动分配房间 {syncSummary.assigned_rooms} 台、失败 {syncSummary.failed_entities} 项。
            </div>
          )}
          {roomSyncSummary && (
            <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>
              房间同步已创建 {roomSyncSummary.created_rooms} 个房间，匹配实体 {roomSyncSummary.matched_entities} 项，跳过 {roomSyncSummary.skipped_entities} 项。
            </div>
          )}
          {status && <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{status}</div>}
          {error && <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{error}</div>}
        </Card>
      </Section>
      <Section title={t('settings.integrations.devices')}>
        <div className="device-list">
          {loading && devices.length === 0 ? <div className="text-text-secondary">正在加载设备列表...</div> : devices.map(device => {
            const draft = deviceDrafts[device.id] ?? { name: device.name, room_id: device.room_id, status: device.status, controllable: device.controllable };
            return (
              <Card key={device.id} className="device-card device-card--editor">
                <div className="device-card__editor-grid">
                  <div className="device-card__info">
                    <span className="device-card__name">{device.name}</span>
                    <span className="device-card__room">{roomNameMap[device.room_id ?? ''] ?? '未分配房间'} · {formatDeviceType(device.device_type)}</span>
                  </div>
                  <input className="form-input" value={draft.name} onChange={event => setDeviceDrafts(current => ({ ...current, [device.id]: { ...draft, name: event.target.value } }))} />
                  <select className="form-select" value={draft.room_id ?? ''} onChange={event => setDeviceDrafts(current => ({ ...current, [device.id]: { ...draft, room_id: event.target.value || null } }))}>
                    {roomOptions.map(option => <option key={option.id || 'unassigned'} value={option.id}>{option.name}</option>)}
                  </select>
                  <select className="form-select" value={draft.status} onChange={event => setDeviceDrafts(current => ({ ...current, [device.id]: { ...draft, status: event.target.value as Device['status'] } }))}>
                    <option value="active">在线</option>
                    <option value="offline">离线</option>
                    <option value="inactive">未启用</option>
                  </select>
                  <select className="form-select" value={draft.controllable ? 'true' : 'false'} onChange={event => setDeviceDrafts(current => ({ ...current, [device.id]: { ...draft, controllable: event.target.value === 'true' } }))}>
                    <option value="true">可控制</option>
                    <option value="false">只读</option>
                  </select>
                </div>
                <div className="device-card__actions">
                  <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>
                    {device.status === 'active' ? '在线' : device.status === 'offline' ? '离线' : '未启用'}
                  </span>
                  <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleSaveDevice(device.id)} disabled={loading}>保存设备</button>
                </div>
              </Card>
            );
          })}
        </div>
      </Section>
      {roomModalOpen && (
        <div className="member-modal-overlay" onClick={() => setRoomModalOpen(false)}>
          <div className="member-modal ha-room-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>选择要同步的 HA 房间</h3>
                <p>这里只做从 HA 导入房间。已经在家庭里存在同名房间的项会直接禁用，不能重复导入。</p>
              </div>
            </div>
            <div className="ha-room-modal__list">
              {roomCandidates.length === 0 ? <div className="integration-status__detail">HA 里没有可识别的房间。</div> : roomCandidates.map(candidate => (
                <label key={candidate.name} className={`ha-room-option ${candidate.can_sync ? '' : 'ha-room-option--disabled'}`}>
                  <input
                    type="checkbox"
                    checked={selectedRoomNames.includes(candidate.name)}
                    disabled={!candidate.can_sync || loading}
                    onChange={() => toggleRoomSelection(candidate.name)}
                  />
                  <div className="ha-room-option__body">
                    <div className="ha-room-option__title-row">
                      <strong>{candidate.name}</strong>
                      <span className={`badge badge--${candidate.can_sync ? 'success' : 'warning'}`}>{candidate.can_sync ? '可同步' : '本地重名'}</span>
                    </div>
                    <div className="integration-status__detail">HA 关联实体 {candidate.entity_count} 个{candidate.exists_locally ? ' · 本地已经有同名房间' : ''}</div>
                  </div>
                </label>
              ))}
            </div>
            <div className="member-modal__actions">
              <button className="btn btn--outline btn--sm" type="button" onClick={() => setRoomModalOpen(false)} disabled={loading}>取消</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmRoomSync()} disabled={loading || selectedRoomNames.length === 0}>同步选中房间</button>
            </div>
          </div>
        </div>
      )}
      {deviceModalOpen && (
        <div className="member-modal-overlay" onClick={() => setDeviceModalOpen(false)}>
          <div className="member-modal ha-device-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>选择要同步的 HA 设备</h3>
                <p>设备按房间分组展示。你可以按房间整组选，也可以单独勾选设备。</p>
              </div>
            </div>
            <div className="ha-device-modal__list">
              {deviceCandidateGroups.length === 0 ? <div className="integration-status__detail">HA 里没有可同步的设备。</div> : deviceCandidateGroups.map(group => {
                const deviceIds = group.items.map(item => item.external_device_id);
                const selectedCount = deviceIds.filter(id => selectedExternalDeviceIds.includes(id)).length;
                const allSelected = selectedCount === deviceIds.length;
                return (
                  <div key={group.roomName} className="ha-device-group">
                    <label className="ha-device-group__header">
                      <input type="checkbox" checked={allSelected} onChange={() => toggleDeviceRoomSelection(deviceIds)} disabled={loading} />
                      <div className="ha-device-group__meta">
                        <strong>{group.roomName}</strong>
                        <span className="integration-status__detail">已选 {selectedCount}/{group.items.length} 台</span>
                      </div>
                    </label>
                    <div className="ha-device-group__items">
                      {group.items.map(candidate => (
                        <label key={candidate.external_device_id} className="ha-device-option">
                          <input
                            type="checkbox"
                            checked={selectedExternalDeviceIds.includes(candidate.external_device_id)}
                            onChange={() => toggleDeviceSelection(candidate.external_device_id)}
                            disabled={loading}
                          />
                          <div className="ha-device-option__body">
                            <div className="ha-device-option__title-row">
                              <strong>{candidate.name}</strong>
                              <span className={`badge badge--${candidate.already_synced ? 'secondary' : 'success'}`}>{candidate.already_synced ? '已同步过' : '新设备'}</span>
                            </div>
                            <div className="integration-status__detail">{candidate.device_type} · 主实体 {candidate.primary_entity_id} · 关联实体 {candidate.entity_count} 个</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="member-modal__actions">
              <button className="btn btn--outline btn--sm" type="button" onClick={() => setDeviceModalOpen(false)} disabled={loading}>取消</button>
              <button className="btn btn--outline btn--sm" type="button" onClick={() => void handleConfirmDeviceSync()} disabled={loading || selectedExternalDeviceIds.length === 0}>同步选中设备</button>
            </div>
          </div>
        </div>
      )}
      {configModalOpen && (
        <div className="member-modal-overlay" onClick={() => setConfigModalOpen(false)}>
          <div className="member-modal ha-config-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <div>
                <h3>配置 Home Assistant 连接</h3>
                <p>这里保存的是当前家庭专属配置，不会影响别的家庭。</p>
              </div>
            </div>
            <form className="settings-form integration-config-form" onSubmit={handleSaveHaConfig}>
              <div className="form-group">
                <label>HA 地址</label>
                <input className="form-input" value={haForm.base_url} onChange={event => setHaForm(current => ({ ...current, base_url: event.target.value }))} placeholder="http://homeassistant.local:8123" />
                <div className="form-help">主页面只展示地址和状态，具体编辑放到这个弹窗里。</div>
              </div>
              <div className="form-group">
                <label>Long-Lived Token</label>
                <input className="form-input" type="password" value={haForm.access_token} onChange={event => setHaForm(current => ({ ...current, access_token: event.target.value, clear_access_token: false }))} placeholder={haConfig?.token_configured ? '已配置，留空表示不改' : '请输入当前家庭专用 Token'} />
                <div className="form-help">当前状态：{haConfig?.token_configured ? '已保存 Token' : '还没有 Token'}。</div>
              </div>
              <div className="integration-config-grid">
                <div className="form-group">
                  <label>房间同步策略</label>
                  <select className="form-select" value={haForm.sync_rooms_enabled ? 'true' : 'false'} onChange={event => setHaForm(current => ({ ...current, sync_rooms_enabled: event.target.value === 'true' }))}>
                    <option value="false">只同步设备</option>
                    <option value="true">同步设备时尝试自动关联已有房间</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Token 操作</label>
                  <select className="form-select" value={haForm.clear_access_token ? 'clear' : 'keep'} onChange={event => setHaForm(current => ({ ...current, clear_access_token: event.target.value === 'clear', access_token: event.target.value === 'clear' ? '' : current.access_token }))}>
                    <option value="keep">保留现有 Token</option>
                    <option value="clear">清空现有 Token</option>
                  </select>
                </div>
              </div>
              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setConfigModalOpen(false)} disabled={loading}>取消</button>
                <button className="btn btn--outline btn--sm" type="submit" disabled={loading}>{loading ? '保存中...' : '保存连接配置'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
