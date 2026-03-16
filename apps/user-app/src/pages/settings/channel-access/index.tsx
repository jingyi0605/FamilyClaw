import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import { GuardedPage, useHouseholdContext } from '../../../runtime';
import { Card, EmptyState, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatus,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelConnectionMode,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  PluginRegistryItem,
} from '../settingsTypes';

type PlatformInfo = { code: string; name: string; icon: string };
type ConfigFieldDef = {
  key: string;
  label: string;
  type: 'text' | 'password';
  required: boolean;
  placeholder: string;
  helpText?: string;
};
type AccountFormState = {
  plugin_id: string;
  display_name: string;
  connection_mode: ChannelConnectionMode;
  config: Record<string, unknown>;
  status: ChannelAccountStatus;
};

const PLATFORM_CONFIG_FIELDS: Record<string, ConfigFieldDef[]> = {
  discord: [
    { key: 'application_public_key', label: 'Application Public Key', type: 'text', required: true, placeholder: 'abc123def456...', helpText: 'Discord Developer Portal 的公钥' },
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: false, placeholder: '可选，用于主动发消息', helpText: '没有主动发消息需求就别填' },
  ],
  feishu: [
    { key: 'app_id', label: 'App ID', type: 'text', required: true, placeholder: 'cli_xxx', helpText: '飞书开放平台应用 ID' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: true, placeholder: '应用密钥', helpText: '飞书开放平台应用密钥' },
    { key: 'encrypt_key', label: 'Encrypt Key', type: 'password', required: false, placeholder: '可选，加密密钥', helpText: '用于消息加解密' },
    { key: 'base_url', label: 'Base URL', type: 'text', required: false, placeholder: 'https://open.feishu.cn', helpText: '私有部署时才改' },
  ],
  dingtalk: [
    { key: 'app_key', label: 'App Key', type: 'text', required: true, placeholder: 'dingxxx', helpText: '钉钉开放平台应用 Key' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: false, placeholder: '可选', helpText: '需要 API 调用时才填' },
  ],
  wecom_app: [
    { key: 'corp_id', label: 'Corp ID', type: 'text', required: true, placeholder: 'ww1234567890abcdef', helpText: '企业微信后台的 Corp ID' },
    { key: 'corp_secret', label: 'App Secret', type: 'password', required: true, placeholder: '应用凭证密钥', helpText: '企业微信应用 Secret' },
    { key: 'agent_id', label: 'Agent ID', type: 'text', required: true, placeholder: '1000001', helpText: '企业微信 AgentId' },
    { key: 'callback_token', label: 'Callback Token', type: 'password', required: true, placeholder: '回调 Token', helpText: '接收回调消息时使用' },
    { key: 'encoding_aes_key', label: 'Encoding AES Key', type: 'password', required: true, placeholder: '消息加解密密钥', helpText: '企业微信 AES Key' },
  ],
  wecom_bot: [
    { key: 'webhook_url', label: 'Webhook URL', type: 'text', required: false, placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx', helpText: '与机器人 key 二选一' },
    { key: 'key', label: 'Bot Key', type: 'password', required: false, placeholder: 'Webhook key 参数', helpText: '与 Webhook URL 二选一' },
  ],
};

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', name: 'Telegram', icon: '📮' },
  { code: 'discord', name: 'Discord', icon: '🎮' },
  { code: 'feishu', name: 'Feishu', icon: '🪽' },
  { code: 'dingtalk', name: 'DingTalk', icon: '📱' },
  { code: 'wecom_app', name: 'WeCom App', icon: '🏢' },
  { code: 'wecom_bot', name: 'WeCom Bot', icon: '🤖' },
];

function buildInitialAccountForm(): AccountFormState {
  return { plugin_id: '', display_name: '', connection_mode: 'polling', config: {}, status: 'draft' };
}

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find((item) => item.code === platformCode) ?? { code: platformCode, name: platformCode, icon: '🔌' };
}

function formatStatus(status: string): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (status === 'active') return { label: '已启用', tone: 'success' };
  if (status === 'draft') return { label: '草稿', tone: 'secondary' };
  if (status === 'degraded') return { label: '降级', tone: 'warning' };
  if (status === 'disabled') return { label: '已停用', tone: 'secondary' };
  return { label: status, tone: 'secondary' };
}

function formatProbeStatus(status: string | null): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (!status) return { label: '未检查', tone: 'secondary' };
  if (status === 'ok') return { label: '连接正常', tone: 'success' };
  if (status === 'failed') return { label: '检查失败', tone: 'danger' };
  if (status === 'pending') return { label: '检查中', tone: 'warning' };
  return { label: status, tone: 'secondary' };
}

function formatConnectionMode(mode: ChannelConnectionMode) {
  if (mode === 'webhook') return '自动接收消息';
  if (mode === 'polling') return '定时拉取消息';
  if (mode === 'websocket') return '长连接';
  return mode;
}

function formatTimestamp(value: string | null) {
  if (!value) return '暂无';
  try {
    return new Date(value).toLocaleString('zh-CN');
  } catch {
    return value;
  }
}

function formatApiErrorMessage(error: ApiError): string {
  const payload = error.payload as { detail?: unknown } | undefined;
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const message = 'msg' in item && typeof item.msg === 'string' ? item.msg : null;
        const location = 'loc' in item && Array.isArray(item.loc)
          ? item.loc.filter((part: unknown): part is string | number => typeof part === 'string' || typeof part === 'number').join('.')
          : '';
        if (message && location) return `${location}: ${message}`;
        return message;
      })
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) return messages.join('; ');
  }
  return error.message || '保存失败';
}

function getConfigFields(plugin: PluginRegistryItem | null, platformCode: string | null): ConfigFieldDef[] {
  const configSpec = plugin?.config_specs?.find((item) => item.scope_type === 'channel_account');
  if (configSpec) {
    const fieldMap = new Map(configSpec.config_schema.fields.map((field) => [field.key, field]));
    const widgets = configSpec.ui_schema.widgets ?? {};
    const orderedKeys = configSpec.ui_schema.field_order?.filter((key) => fieldMap.has(key))
      ?? configSpec.config_schema.fields.map((field) => field.key);
    return orderedKeys.flatMap((key) => {
      const field = fieldMap.get(key);
      if (!field) return [];
      const widget = widgets[key];
      return [{
        key: field.key,
        label: field.label,
        type: field.type === 'secret' || widget?.widget === 'password' ? 'password' : 'text',
        required: field.required,
        placeholder: widget?.placeholder ?? '',
        helpText: widget?.help_text ?? field.description ?? undefined,
      }];
    });
  }
  const legacyFields = plugin?.capabilities.channel?.ui?.account_config_fields;
  if (legacyFields?.length) {
    return legacyFields.map((field) => ({
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      placeholder: field.placeholder ?? '',
      helpText: field.help_text ?? undefined,
    }));
  }
  return platformCode ? (PLATFORM_CONFIG_FIELDS[platformCode] ?? []) : [];
}

function getSupportedConnectionModes(plugin: PluginRegistryItem | null): ChannelConnectionMode[] {
  return (plugin?.capabilities.channel?.inbound_modes ?? []).filter((mode): mode is ChannelConnectionMode => (
    mode === 'webhook' || mode === 'polling' || mode === 'websocket'
  ));
}

function resolveDefaultConnectionMode(plugin: PluginRegistryItem | null): ChannelConnectionMode {
  return getSupportedConnectionModes(plugin)[0] ?? 'polling';
}

function SettingsChannelAccessContent() {
  const { currentHouseholdId } = useHouseholdContext();
  const [accounts, setAccounts] = useState<ChannelAccountRead[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [channelPlugins, setChannelPlugins] = useState<PluginRegistryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [expandedAccountId, setExpandedAccountId] = useState<string | null>(null);
  const [accountStatus, setAccountStatus] = useState<ChannelAccountStatusRead | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<ChannelDeliveryRead[]>([]);
  const [failedInboundEvents, setFailedInboundEvents] = useState<ChannelInboundEventRead[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<ChannelAccountRead | null>(null);
  const [accountForm, setAccountForm] = useState<AccountFormState>(buildInitialAccountForm);
  const [modalLoading, setModalLoading] = useState(false);

  async function loadAccounts(cancelled?: () => boolean) {
    if (!currentHouseholdId) {
      setAccounts([]);
      setMembers([]);
      setChannelPlugins([]);
      return false;
    }
    setLoading(true);
    setError('');
    try {
      const [pluginsResult, accountsResult, membersResult] = await Promise.all([
        settingsApi.listRegisteredPlugins(currentHouseholdId),
        settingsApi.listChannelAccounts(currentHouseholdId),
        settingsApi.listMembers(currentHouseholdId),
      ]);
      if (cancelled?.()) return false;
      setChannelPlugins(pluginsResult.items.filter((plugin) => plugin.types.includes('channel')));
      setAccounts(accountsResult);
      setMembers(membersResult.items);
      return true;
    } catch (loadError) {
      if (!cancelled?.()) setError(loadError instanceof Error ? loadError.message : '加载平台账号失败');
      return false;
    } finally {
      if (!cancelled?.()) setLoading(false);
    }
  }

  useEffect(() => {
    if (!currentHouseholdId) return;
    let cancelled = false;
    void loadAccounts(() => cancelled);
    return () => { cancelled = true; };
  }, [currentHouseholdId]);

  const channelPluginMap = useMemo(() => new Map(channelPlugins.map((plugin) => [plugin.id, plugin])), [channelPlugins]);
  const availableChannelPlugins = useMemo(() => channelPlugins
    .filter((plugin) => plugin.enabled && !!plugin.capabilities.channel?.platform_code)
    .map((plugin) => {
      const platformCode = plugin.capabilities.channel?.platform_code ?? plugin.id.replace(/^channel-/, '');
      return { pluginId: plugin.id, platformCode, name: plugin.name, icon: getPlatformInfo(platformCode).icon };
    }), [channelPlugins]);
  const activeMembers = useMemo(() => members.filter((member) => member.status === 'active'), [members]);

  async function loadAccountDetail(accountId: string) {
    if (!currentHouseholdId) return;
    setDetailLoading(true);
    try {
      const [statusResult, deliveriesResult, inboundResult] = await Promise.all([
        settingsApi.getChannelAccountStatus(currentHouseholdId, accountId),
        settingsApi.listChannelDeliveries(currentHouseholdId, { channel_account_id: accountId, status: 'failed' }),
        settingsApi.listChannelInboundEvents(currentHouseholdId, { channel_account_id: accountId, status: 'failed' }),
      ]);
      setAccountStatus(statusResult);
      setFailedDeliveries(deliveriesResult.slice(0, 5));
      setFailedInboundEvents(inboundResult.slice(0, 5));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载详情失败');
    } finally {
      setDetailLoading(false);
    }
  }

  function getAccountPluginState(account: ChannelAccountRead) {
    return channelPluginMap.get(account.plugin_id) ?? null;
  }

  function isAccountPluginDisabled(account: ChannelAccountRead) {
    return getAccountPluginState(account)?.enabled === false;
  }

  function resetExpandedState() {
    setExpandedAccountId(null);
    setAccountStatus(null);
    setFailedDeliveries([]);
    setFailedInboundEvents([]);
  }

  function toggleAccountExpand(accountId: string) {
    if (expandedAccountId === accountId) {
      resetExpandedState();
      return;
    }
    setExpandedAccountId(accountId);
    void loadAccountDetail(accountId);
  }

  function openCreateModal() {
    setEditingAccount(null);
    setAccountForm(buildInitialAccountForm());
    setAccountModalOpen(true);
  }

  function openEditModal(account: ChannelAccountRead) {
    setEditingAccount(account);
    setAccountForm({ plugin_id: account.plugin_id, display_name: account.display_name, connection_mode: account.connection_mode, config: account.config, status: account.status });
    setAccountModalOpen(true);
  }

  async function handleRefreshAccounts() {
    setStatus('');
    const loaded = await loadAccounts();
    if (!loaded) return;
    if (expandedAccountId) await loadAccountDetail(expandedAccountId);
    setStatus('平台账号列表已刷新。');
  }

  async function handleSaveAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;
    setModalLoading(true);
    setError('');
    setStatus('');
    try {
      if (editingAccount) {
        const payload: ChannelAccountUpdate = { display_name: accountForm.display_name, connection_mode: accountForm.connection_mode, config: accountForm.config, status: accountForm.status };
        const result = await settingsApi.updateChannelAccount(currentHouseholdId, editingAccount.id, payload);
        setAccounts((current) => current.map((item) => item.id === result.id ? result : item));
        setStatus('平台账号已更新。');
      } else {
        const payload: ChannelAccountCreate = { plugin_id: accountForm.plugin_id, display_name: accountForm.display_name, connection_mode: accountForm.connection_mode, config: accountForm.config, status: accountForm.status };
        const result = await settingsApi.createChannelAccount(currentHouseholdId, payload);
        setAccounts((current) => [result, ...current]);
        setStatus('平台账号已创建。');
      }
      setAccountModalOpen(false);
    } catch (saveError) {
      setError(saveError instanceof ApiError ? formatApiErrorMessage(saveError) : saveError instanceof Error ? saveError.message : '保存失败');
    } finally {
      setModalLoading(false);
    }
  }

  async function handleProbeAccount(accountId: string) {
    if (!currentHouseholdId) return;
    setLoading(true);
    setError('');
    try {
      const result = await settingsApi.probeChannelAccount(currentHouseholdId, accountId);
      setAccounts((current) => current.map((item) => item.id === result.account.id ? result.account : item));
      if (expandedAccountId === accountId) setAccountStatus(result);
      setStatus('连接检查已完成。');
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : '连接检查失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleAccountStatus(account: ChannelAccountRead) {
    if (!currentHouseholdId) return;
    const nextStatus: ChannelAccountStatus = account.status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      const result = await settingsApi.updateChannelAccount(currentHouseholdId, account.id, { status: nextStatus });
      setAccounts((current) => current.map((item) => item.id === result.id ? result : item));
      setStatus(nextStatus === 'active' ? '账号已启用。' : '账号已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteAccount(account: ChannelAccountRead) {
    if (!currentHouseholdId) return;
    const result = await Taro.showModal({
      title: '删除平台账号',
      content: `确定要彻底删除“${account.display_name}”吗？该账号下的成员绑定、入站记录和发送记录都会一起删除，这一步不能撤销。`,
      confirmText: '确认删除',
      cancelText: '取消',
    });
    if (!result.confirm) return;
    setLoading(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.deleteChannelAccount(currentHouseholdId, account.id);
      setAccounts((current) => current.filter((item) => item.id !== account.id));
      if (expandedAccountId === account.id) resetExpandedState();
      setStatus('平台账号已删除。');
    } catch (deleteError) {
      setError(deleteError instanceof ApiError ? formatApiErrorMessage(deleteError) : deleteError instanceof Error ? deleteError.message : '删除失败');
    } finally {
      setLoading(false);
    }
  }

  const selectedPlugin = editingAccount?.plugin_id ? channelPluginMap.get(editingAccount.plugin_id) ?? null : accountForm.plugin_id ? channelPluginMap.get(accountForm.plugin_id) ?? null : null;
  const selectedPlatformCode = editingAccount?.platform_code ?? availableChannelPlugins.find((plugin) => plugin.pluginId === accountForm.plugin_id)?.platformCode ?? null;
  const configFields = getConfigFields(selectedPlugin, selectedPlatformCode);
  const supportedConnectionModes = useMemo(() => getSupportedConnectionModes(selectedPlugin), [selectedPlugin]);

  useEffect(() => {
    if (!selectedPlugin || supportedConnectionModes.length === 0) return;
    const defaultMode = resolveDefaultConnectionMode(selectedPlugin);
    if (!supportedConnectionModes.includes(accountForm.connection_mode)) {
      setAccountForm((current) => ({ ...current, connection_mode: defaultMode }));
    }
  }, [accountForm.connection_mode, selectedPlugin, supportedConnectionModes]);

  const headerActions = (
    <div className="channel-account-card__actions">
      <button className="btn btn--outline btn--sm" onClick={() => void handleRefreshAccounts()} disabled={loading}>刷新</button>
      <button className="btn btn--primary btn--sm" onClick={openCreateModal} disabled={availableChannelPlugins.length === 0 || loading}>新增平台账号</button>
    </div>
  );

  return (
    <SettingsPageShell activeKey="channel-access">
      <div className="settings-page">
        <Section title="通讯平台接入">
          <Card className="channel-access-notice">
            <div className="channel-access-notice__content">
              <h3>把常用聊天工具接进来</h3>
              <p>配置 Telegram、Discord、飞书这类平台后，家庭成员就能直接在熟悉的聊天窗口里和系统沟通。</p>
            </div>
          </Card>
          {error ? <div className="settings-note settings-note--error"><span>⚠️</span> {error}</div> : null}
          {status ? <div className="settings-note settings-note--success"><span>✓</span> {status}</div> : null}
          <div className="channel-account-list">
            {loading && accounts.length === 0 ? <div className="text-text-secondary">正在加载平台账号...</div> : null}
            {!loading && accounts.length === 0 ? (
              <EmptyState icon="🔌" title="还没有接入聊天平台" description="先把第一个家庭常用聊天工具接进来。" action={headerActions} />
            ) : null}
            {accounts.length > 0 ? (
              <>
                <div className="channel-account-list__header">
                  <span>已配置 {accounts.length} 个平台账号</span>
                  {headerActions}
                </div>
                {accounts.map((account) => {
                  const platform = getPlatformInfo(account.platform_code);
                  const statusInfo = formatStatus(account.status);
                  const probeInfo = formatProbeStatus(account.last_probe_status);
                  const isExpanded = expandedAccountId === account.id;
                  const pluginState = getAccountPluginState(account);
                  const pluginDisabled = isAccountPluginDisabled(account);
                  const pluginDisabledReason = pluginState?.disabled_reason ?? '当前家庭已经停用了这个通道插件。';
                  const supportsMemberBinding = pluginState?.capabilities.channel?.supports_member_binding !== false;
                  const accountMessageClassName = account.last_probe_status === 'ok' ? 'channel-account-card__success' : 'channel-account-card__error';

                  return (
                    <Card key={account.id} className="channel-account-card">
                      <div className="channel-account-card__header">
                        <div className="channel-account-card__icon">{platform.icon}</div>
                        <div className="channel-account-card__info">
                          <div className="channel-account-card__title">
                            <span className="channel-account-card__name">{account.display_name}</span>
                            <span className={`badge badge--${statusInfo.tone}`}>{statusInfo.label}</span>
                            <span className={`badge badge--${probeInfo.tone}`}>{probeInfo.label}</span>
                          </div>
                          <div className="channel-account-card__meta">
                            {platform.name} · {formatConnectionMode(account.connection_mode)}
                            {pluginDisabled ? <span className="channel-account-card__error"> · 插件已停用</span> : null}
                            {account.last_error_message ? <span className={accountMessageClassName}> · {account.last_error_message}</span> : null}
                          </div>
                          {pluginDisabled ? <div className="channel-account-card__times">{pluginDisabledReason}</div> : null}
                          <div className="channel-account-card__times">最近收到消息：{formatTimestamp(account.last_inbound_at)} · 最近发送消息：{formatTimestamp(account.last_outbound_at)}</div>
                        </div>
                        <div className="channel-account-card__actions">
                          <button className="btn btn--outline btn--sm" onClick={() => openEditModal(account)} disabled={loading || pluginDisabled}>编辑</button>
                          <button className="btn btn--outline btn--sm" onClick={() => void handleProbeAccount(account.id)} disabled={loading || pluginDisabled}>检查连接</button>
                          <button className="btn btn--outline btn--sm" onClick={() => void handleToggleAccountStatus(account)} disabled={loading || pluginDisabled}>{account.status === 'disabled' ? '启用' : '停用'}</button>
                          <button className="btn btn--outline btn--sm" onClick={() => void handleDeleteAccount(account)} disabled={loading}>删除</button>
                          <button className="btn btn--outline btn--sm" onClick={() => toggleAccountExpand(account.id)}>{isExpanded ? '收起详情' : '查看详情'}</button>
                        </div>
                      </div>
                      {isExpanded ? (
                        <div className="channel-account-card__detail">
                          {detailLoading ? <div className="text-text-secondary">加载详情中...</div> : (
                            <>
                              {accountStatus ? (
                                <div className="channel-detail-section">
                                  <h4>连接情况</h4>
                                  <div className="channel-detail-stats">
                                    <div className="channel-detail-stat"><span className="channel-detail-stat__value">{accountStatus.recent_failure_summary.recent_failure_count}</span><span className="channel-detail-stat__label">最近失败次数</span></div>
                                    <div className="channel-detail-stat"><span className="channel-detail-stat__value">{accountStatus.recent_delivery_count}</span><span className="channel-detail-stat__label">最近发送消息</span></div>
                                    <div className="channel-detail-stat"><span className="channel-detail-stat__value">{accountStatus.recent_inbound_count}</span><span className="channel-detail-stat__label">最近收到消息</span></div>
                                  </div>
                                  {accountStatus.recent_failure_summary.last_error_message ? <div className="channel-detail-error"><strong>最近一次失败：</strong>{accountStatus.recent_failure_summary.last_error_message}<span className="channel-detail-error__time">（{formatTimestamp(accountStatus.recent_failure_summary.last_failed_at)}）</span></div> : null}
                                </div>
                              ) : null}
                              <div className="channel-detail-section">
                                <h4>成员绑定</h4>
                                <ChannelAccountBindingsPanel householdId={currentHouseholdId ?? ''} accountId={account.id} members={activeMembers} plugin={pluginState} supportsMemberBinding={supportsMemberBinding} />
                              </div>
                              {failedDeliveries.length > 0 || failedInboundEvents.length > 0 ? (
                                <div className="channel-detail-section">
                                  <h4>最近失败记录</h4>
                                  {failedDeliveries.length > 0 ? <div className="channel-failure-list"><h5>发送失败（最近 5 条）</h5>{failedDeliveries.map((item) => <div key={item.id} className="channel-failure-item"><span className="channel-failure-item__type">{item.delivery_type}</span><span className="channel-failure-item__error">{item.last_error_message ?? '未知错误'}</span><span className="channel-failure-item__time">{formatTimestamp(item.created_at)}</span></div>)}</div> : null}
                                  {failedInboundEvents.length > 0 ? <div className="channel-failure-list"><h5>接收失败（最近 5 条）</h5>{failedInboundEvents.map((item) => <div key={item.id} className="channel-failure-item"><span className="channel-failure-item__type">{item.event_type}</span><span className="channel-failure-item__error">{item.error_message ?? '未知错误'}</span><span className="channel-failure-item__time">{formatTimestamp(item.received_at)}</span></div>)}</div> : null}
                                </div>
                              ) : null}
                            </>
                          )}
                        </div>
                      ) : null}
                    </Card>
                  );
                })}
              </>
            ) : null}
          </div>
        </Section>
        {accountModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setAccountModalOpen(false)}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <h3>{editingAccount ? '编辑平台账号' : '新增平台账号'}</h3>
                <p>配置外部聊天平台的接入信息，账号代码由系统自动生成，不需要手填。</p>
              </div>
              <form className="settings-form" onSubmit={handleSaveAccount}>
                <div className="form-group">
                  <label>平台类型</label>
                  <select className="form-select" value={accountForm.plugin_id} onChange={(event) => {
                    const nextPlugin = channelPluginMap.get(event.target.value) ?? null;
                    setAccountForm((current) => ({ ...current, plugin_id: event.target.value, connection_mode: resolveDefaultConnectionMode(nextPlugin) }));
                  }} disabled={Boolean(editingAccount)} required>
                    <option value="">请选择平台</option>
                    {availableChannelPlugins.map((plugin) => <option key={plugin.pluginId} value={plugin.pluginId}>{plugin.icon} {plugin.name}</option>)}
                  </select>
                </div>
                <div className="form-group"><label>显示名称</label><input className="form-input" value={accountForm.display_name} onChange={(event) => setAccountForm((current) => ({ ...current, display_name: event.target.value }))} placeholder="例如：家庭 Telegram 助手" required /></div>
                <div className="form-group">
                  <label>连接方式</label>
                  {supportedConnectionModes.length > 1 ? <select className="form-select" value={accountForm.connection_mode} onChange={(event) => setAccountForm((current) => ({ ...current, connection_mode: event.target.value as ChannelConnectionMode }))}>{supportedConnectionModes.map((mode) => <option key={mode} value={mode}>{formatConnectionMode(mode)}</option>)}</select> : <div className="form-input form-input--readonly">{formatConnectionMode(accountForm.connection_mode)}</div>}
                  <div className="form-help">{supportedConnectionModes.length <= 1 ? '当前平台只支持这一种接入方式，系统会自动使用它。' : '按平台声明选择接入方式，不再手工猜。'}</div>
                </div>
                <div className="form-group">
                  <label>状态</label>
                  <select className="form-select" value={accountForm.status} onChange={(event) => setAccountForm((current) => ({ ...current, status: event.target.value as ChannelAccountStatus }))}>
                    <option value="draft">草稿</option>
                    <option value="active">启用</option>
                    <option value="disabled">停用</option>
                  </select>
                </div>
                {configFields.length > 0 ? <div className="form-group channel-config-section"><label>平台配置</label><div className="channel-config-fields">{configFields.map((field) => <div key={field.key} className="channel-config-field"><label className="channel-config-field__label">{field.label}{field.required ? <span className="required-mark">*</span> : null}</label><input type={field.type} className="form-input" value={String(accountForm.config[field.key] ?? '')} onChange={(event) => setAccountForm((current) => ({ ...current, config: { ...current.config, [field.key]: event.target.value } }))} placeholder={field.placeholder} required={field.required} />{field.helpText ? <div className="form-help">{field.helpText}</div> : null}</div>)}</div></div> : null}
                <div className="member-modal__actions">
                  <button className="btn btn--outline btn--sm" type="button" onClick={() => setAccountModalOpen(false)} disabled={modalLoading}>取消</button>
                  <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>{modalLoading ? '保存中...' : '保存'}</button>
                </div>
              </form>
            </div>
          </div>
        ) : null}
      </div>
    </SettingsPageShell>
  );
}

export default function SettingsChannelAccessPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/channel-access/index">
      <SettingsChannelAccessContent />
    </GuardedPage>
  );
}
