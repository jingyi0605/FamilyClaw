/* ============================================================
 * 设置页 - 二级导航 + 6 个子页面
 * ============================================================ */
import { useEffect, useState } from 'react';
import { Outlet, useMatch, Navigate } from 'react-router-dom';
import { useI18n } from '../i18n';
import { useTheme, themeList, type ThemeId } from '../theme';
import { PageHeader, Card, Section, ToggleSwitch } from '../components/base';
import { SettingsNav } from '../components/SettingsNav';
import { useHouseholdContext } from '../state/household';
import { api } from '../lib/api';
import type { ContextConfigRead, ContextOverviewRead, Device, HomeAssistantSyncResponse, Room } from '../lib/types';

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
export function SettingsAi() {
  const { t } = useI18n();
  const { config, loading, error, status, savePatch } = useContextConfigSettings();

  const privacyValue = config?.privacy_mode ?? 'balanced';

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.ai.assistantName')}</label>
            <input type="text" className="form-input" defaultValue="家庭助手" />
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyTone')}</label>
            <select className="form-select">
              <option>温和友好</option>
              <option>简洁干练</option>
              <option>活泼有趣</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyLength')}</label>
            <select className="form-select">
              <option>适中</option>
              <option>简短</option>
              <option>详细</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.outputLanguage')}</label>
            <select className="form-select">
              <option>中文</option>
              <option>English</option>
            </select>
          </div>

          <div className="settings-toggles">
            <ToggleSwitch checked={true} label={t('settings.ai.useMemory')} description={t('settings.ai.useMemoryDesc')} />
            <ToggleSwitch checked={true} label={t('settings.ai.suggestReminder')} description={t('settings.ai.suggestReminderDesc')} />
            <ToggleSwitch checked={false} label={t('settings.ai.suggestScene')} description={t('settings.ai.suggestSceneDesc')} />
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
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.language')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.language.interfaceLang')}</label>
            <select className="form-select" value={locale} onChange={e => setLocale(e.target.value as 'zh-CN' | 'en-US')}>
              <option value="zh-CN">中文（简体）</option>
              <option value="en-US">English</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.dateFormat')}</label>
            <select className="form-select">
              <option>YYYY-MM-DD</option>
              <option>MM/DD/YYYY</option>
              <option>DD/MM/YYYY</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.timeFormat')}</label>
            <select className="form-select">
              <option>24 小时制</option>
              <option>12 小时制</option>
            </select>
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
            <select className="form-select">
              <option>浏览器通知 + 站内消息</option>
              <option>仅站内消息</option>
              <option>全部关闭</option>
            </select>
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
  const [devices, setDevices] = useState<Device[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [syncSummary, setSyncSummary] = useState<HomeAssistantSyncResponse | null>(null);
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

      const [overviewResult, devicesResult, roomsResult] = await Promise.allSettled([
        api.getContextOverview(currentHouseholdId),
        api.listDevices(currentHouseholdId),
        api.listRooms(currentHouseholdId),
      ]);

      if (cancelled) {
        return;
      }

      setOverview(overviewResult.status === 'fulfilled' ? overviewResult.value : null);
      setDevices(devicesResult.status === 'fulfilled' ? devicesResult.value.items : []);
      setRooms(roomsResult.status === 'fulfilled' ? roomsResult.value.items : []);

      const errors = [overviewResult, devicesResult, roomsResult]
        .filter(result => result.status === 'rejected')
        .map(result => result.reason instanceof Error ? result.reason.message : '集成数据加载失败');

      setError(errors.join('；'));
      setLoading(false);
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  async function handleSync() {
    if (!currentHouseholdId) {
      setError('还没有选中家庭，暂时无法同步。');
      return;
    }

    setLoading(true);
    setStatus('');
    setError('');

    try {
      const result = await api.syncHomeAssistant(currentHouseholdId);
      setSyncSummary(result);
      setDevices(result.devices);
      setStatus('Home Assistant 同步完成，设备列表已刷新。');

      const nextOverview = await api.getContextOverview(currentHouseholdId).catch(() => null);
      if (nextOverview) {
        setOverview(nextOverview);
      }
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : '同步失败');
    } finally {
      setLoading(false);
    }
  }

  const roomNameMap = Object.fromEntries(rooms.map(room => [room.id, room.name]));

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

  function formatHaStatus(statusValue: ContextOverviewRead['home_assistant_status'] | undefined) {
    switch (statusValue) {
      case 'healthy':
        return { label: '已连接', tone: 'online' as const };
      case 'degraded':
        return { label: '部分降级', tone: 'warning' as const };
      case 'offline':
        return { label: '连接离线', tone: 'offline' as const };
      default:
        return { label: '状态未知', tone: 'offline' as const };
    }
  }

  const haStatus = formatHaStatus(overview?.home_assistant_status);
  const lastSyncText = syncSummary ? '刚刚' : overview ? '已加载当前状态' : '暂无记录';

  return (
    <div className="settings-page">
      <Section title={t('settings.integrations.haStatus')}>
        <Card className="integration-status-card">
          <div className="integration-status">
            <span className={`integration-status__indicator integration-status__indicator--${haStatus.tone === 'online' ? 'online' : 'offline'}`} />
            <div className="integration-status__text">
              <span className="integration-status__label">Home Assistant</span>
              <span className="integration-status__detail">{haStatus.label} · {t('settings.integrations.lastSync')}：{lastSyncText}</span>
            </div>
            <button className="btn btn--outline btn--sm" onClick={handleSync} disabled={loading}>{loading ? '同步中...' : t('settings.integrations.syncNow')}</button>
          </div>
          {syncSummary && (
            <div className="integration-status__detail" style={{ marginTop: '0.75rem' }}>
              本次同步新增 {syncSummary.created_devices} 台、更新 {syncSummary.updated_devices} 台、失败 {syncSummary.failed_entities} 项。
            </div>
          )}
          {status && <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{status}</div>}
          {error && <div className="integration-status__detail" style={{ marginTop: '0.5rem' }}>{error}</div>}
        </Card>
      </Section>
      <Section title={t('settings.integrations.devices')}>
        <div className="device-list">
          {loading && devices.length === 0 ? <div className="text-text-secondary">正在加载设备列表...</div> : devices.map(device => (
            <Card key={device.id} className="device-card">
              <div className="device-card__info">
                <span className="device-card__name">{device.name}</span>
                <span className="device-card__room">{roomNameMap[device.room_id ?? ''] ?? '未分配房间'} · {formatDeviceType(device.device_type)}</span>
              </div>
              <span className={`badge badge--${device.status === 'active' ? 'success' : 'secondary'}`}>
                {device.status === 'active' ? '在线' : device.status === 'offline' ? '离线' : '未启用'}
              </span>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}
