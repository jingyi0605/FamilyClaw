import { useEffect, useMemo, useState } from 'react';
import { GuardedPage, useHouseholdContext } from '../../../runtime';
import { Card, EmptyState, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  PluginRegistryItem,
} from '../settingsTypes';

type PlatformInfo = {
  code: string;
  name: string;
  icon: string;
};

type ChannelPluginOption = {
  pluginId: string;
  platformCode: string;
  name: string;
  icon: string;
};

type ConfigFieldDef = {
  key: string;
  label: string;
  type: 'text' | 'password';
  required: boolean;
  placeholder: string;
  helpText?: string;
};

const PLATFORM_CONFIG_FIELDS: Record<string, ConfigFieldDef[]> = {
  telegram: [
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: true, placeholder: '123456:ABC...', helpText: '从 @BotFather 获取的机器人令牌' },
    { key: 'webhook_secret', label: 'Webhook Secret', type: 'password', required: false, placeholder: '可选安全密钥', helpText: '用于校验 Webhook 来源' },
  ],
  discord: [
    { key: 'application_public_key', label: 'Application Public Key', type: 'text', required: true, placeholder: 'abc123def456...', helpText: 'Discord Developer Portal 的公钥' },
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: false, placeholder: '可选，用于主动发消息', helpText: '没有主动消息需求就别填' },
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
    { key: 'corp_secret', label: '应用 Secret', type: 'password', required: true, placeholder: '应用凭证密钥', helpText: '应用 Secret' },
    { key: 'agent_id', label: 'Agent ID', type: 'text', required: true, placeholder: '1000001', helpText: '企业微信 AgentId' },
    { key: 'callback_token', label: 'Callback Token', type: 'password', required: true, placeholder: '回调 Token', helpText: '接收回调消息时使用' },
    { key: 'encoding_aes_key', label: 'Encoding AES Key', type: 'password', required: true, placeholder: '消息加解密密钥', helpText: '企业微信 AES Key' },
  ],
  wecom_bot: [
    { key: 'webhook_url', label: 'Webhook URL', type: 'text', required: false, placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx', helpText: '与机器人 key 二选一' },
    { key: 'key', label: '机器人 Key', type: 'password', required: false, placeholder: 'Webhook key 参数', helpText: '与 Webhook URL 二选一' },
  ],
};

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', name: 'Telegram', icon: '📮' },
  { code: 'discord', name: 'Discord', icon: '🎮' },
  { code: 'feishu', name: '飞书', icon: '🪽' },
  { code: 'dingtalk', name: '钉钉', icon: '📱' },
  { code: 'wecom_app', name: '企业微信应用', icon: '🏢' },
  { code: 'wecom_bot', name: '企业微信群机器人', icon: '🤖' },
];

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find((item) => item.code === platformCode) ?? { code: platformCode, name: platformCode, icon: '🔌' };
}

function formatStatus(status: string): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  switch (status) {
    case 'active':
      return { label: '已启用', tone: 'success' };
    case 'draft':
      return { label: '待启用', tone: 'secondary' };
    case 'degraded':
      return { label: '连接异常', tone: 'warning' };
    case 'disabled':
      return { label: '已停用', tone: 'secondary' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatProbeStatus(status: string | null): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (!status) return { label: '未检查', tone: 'secondary' };
  switch (status) {
    case 'ok':
      return { label: '连接正常', tone: 'success' };
    case 'failed':
      return { label: '检查失败', tone: 'danger' };
    case 'pending':
      return { label: '检查中', tone: 'warning' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatConnectionMode(mode: 'webhook' | 'polling' | 'websocket') {
  switch (mode) {
    case 'webhook':
      return '自动接收消息';
    case 'polling':
      return '定时拉取消息';
    case 'websocket':
      return '长连接';
    default:
      return mode;
  }
}

function getProbeMessageClassName(account: ChannelAccountRead): string {
  return account.last_probe_status === 'ok'
    ? 'channel-account-card__success'
    : 'channel-account-card__error';
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
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const message = 'msg' in item && typeof item.msg === 'string' ? item.msg : null;
        const location = 'loc' in item && Array.isArray(item.loc)
          ? item.loc
            .filter((part: unknown): part is string | number => typeof part === 'string' || typeof part === 'number')
            .join('.')
          : '';
        if (message && location) {
          return `${location}: ${message}`;
        }
        return message;
      })
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) {
      return messages.join('；');
    }
  }
  return error.message || '保存失败';
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
  const [accountForm, setAccountForm] = useState({
    plugin_id: '',
    display_name: '',
    connection_mode: 'webhook' as 'webhook' | 'polling' | 'websocket',
    config: {} as Record<string, unknown>,
    status: 'draft' as 'draft' | 'active' | 'degraded' | 'disabled',
  });
  const [modalLoading, setModalLoading] = useState(false);

  useEffect(() => {
    if (!currentHouseholdId) {
      setAccounts([]);
      setMembers([]);
      setChannelPlugins([]);
      return;
    }

    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError('');
      try {
        const [pluginsResult, accountsResult, membersResult] = await Promise.all([
          settingsApi.listRegisteredPlugins(currentHouseholdId),
          settingsApi.listChannelAccounts(currentHouseholdId),
          settingsApi.listMembers(currentHouseholdId),
        ]);
        if (!cancelled) {
          setChannelPlugins(pluginsResult.items.filter((plugin) => plugin.types.includes('channel')));
          setAccounts(accountsResult);
          setMembers(membersResult.items);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  const channelPluginMap = useMemo(() => new Map(channelPlugins.map((plugin) => [plugin.id, plugin])), [channelPlugins]);
  const availableChannelPlugins = useMemo<ChannelPluginOption[]>(() => (
    channelPlugins
      .filter((plugin) => plugin.enabled && !!plugin.capabilities.channel?.platform_code)
      .map((plugin) => {
        const platformCode = plugin.capabilities.channel?.platform_code ?? plugin.id.replace(/^channel-/, '');
        const platform = getPlatformInfo(platformCode);
        return {
          pluginId: plugin.id,
          platformCode,
          name: plugin.name,
          icon: platform.icon,
        };
      })
      .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
  ), [channelPlugins]);

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

  function toggleAccountExpand(accountId: string) {
    if (expandedAccountId === accountId) {
      setExpandedAccountId(null);
      setAccountStatus(null);
      setFailedDeliveries([]);
      setFailedInboundEvents([]);
      return;
    }
    setExpandedAccountId(accountId);
    void loadAccountDetail(accountId);
  }

  function openCreateModal() {
    setEditingAccount(null);
    setAccountForm({
      plugin_id: '',
      display_name: '',
      connection_mode: 'webhook',
      config: {},
      status: 'draft',
    });
    setAccountModalOpen(true);
  }

  function openEditModal(account: ChannelAccountRead) {
    setEditingAccount(account);
    setAccountForm({
      plugin_id: account.plugin_id,
      display_name: account.display_name,
      connection_mode: account.connection_mode,
      config: account.config,
      status: account.status,
    });
    setAccountModalOpen(true);
  }

  async function handleSaveAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;

    setModalLoading(true);
    setError('');
    setStatus('');

    try {
      if (editingAccount) {
        const payload: ChannelAccountUpdate = {
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          config: accountForm.config,
          status: accountForm.status,
        };
        const result = await settingsApi.updateChannelAccount(currentHouseholdId, editingAccount.id, payload);
        setAccounts((current) => current.map((item) => item.id === result.id ? result : item));
        setStatus('聊天平台已更新');
      } else {
        const payload: ChannelAccountCreate = {
          plugin_id: accountForm.plugin_id,
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          config: accountForm.config,
          status: accountForm.status,
        };
        const result = await settingsApi.createChannelAccount(currentHouseholdId, payload);
        setAccounts((current) => [result, ...current]);
        setStatus('聊天平台已添加');
      }
      setAccountModalOpen(false);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? formatApiErrorMessage(saveError)
          : saveError instanceof Error
            ? saveError.message
            : '保存失败',
      );
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
      if (expandedAccountId === accountId) {
        setAccountStatus(result);
      }
      setStatus('连接检查已完成');
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : '连接检查失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleAccountStatus(account: ChannelAccountRead) {
    if (!currentHouseholdId) return;

    const nextStatus = account.status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      const result = await settingsApi.updateChannelAccount(currentHouseholdId, account.id, { status: nextStatus });
      setAccounts((current) => current.map((item) => item.id === result.id ? result : item));
      setStatus(nextStatus === 'active' ? '账号已启用' : '账号已停用');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SettingsPageShell activeKey="channel-access">
      <div className="settings-page">
        <Section title="聊天平台">
          <Card className="channel-access-notice">
            <div className="channel-access-notice__content">
              <h3>把常用聊天工具接进来</h3>
              <p>把 Telegram、Discord、飞书这类聊天工具接进来后，家庭成员就能直接在熟悉的聊天窗口里和系统沟通。</p>
              <ul>
                <li><strong>聊天平台</strong>：每个平台各有一套接入信息。</li>
                <li><strong>成员关联</strong>：把平台账号和家庭成员对应起来，系统才知道是谁在发消息。</li>
                <li><strong>连接情况</strong>：这里可以查看是否连通，以及最近有没有收发失败。</li>
              </ul>
            </div>
          </Card>

          {error ? <div className="settings-note"><span>⚠️</span> {error}</div> : null}
          {status ? <div className="settings-note"><span>✓</span> {status}</div> : null}

          <div className="channel-account-list">
            {loading && accounts.length === 0 ? (
              <div className="text-text-secondary">正在加载聊天平台...</div>
            ) : accounts.length === 0 ? (
              <EmptyState
                icon="🔌"
                title="还没有接入聊天平台"
                description="先添加一个家里常用的聊天工具。"
                action={<button className="btn btn--primary" onClick={openCreateModal} disabled={availableChannelPlugins.length === 0}>添加平台</button>}
              />
            ) : (
              <>
                <div className="channel-account-list__header">
                  <span>已接入 {accounts.length} 个聊天平台</span>
                  <button className="btn btn--primary btn--sm" onClick={openCreateModal} disabled={availableChannelPlugins.length === 0}>添加平台</button>
                </div>

                {accounts.map((account) => {
                  const platform = getPlatformInfo(account.platform_code);
                  const statusInfo = formatStatus(account.status);
                  const probeInfo = formatProbeStatus(account.last_probe_status);
                  const isExpanded = expandedAccountId === account.id;
                  const pluginState = getAccountPluginState(account);
                  const pluginDisabled = isAccountPluginDisabled(account);
                  const pluginDisabledReason = pluginState?.disabled_reason ?? '当前家庭已经停用了这个聊天平台能力';

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
                            {pluginDisabled ? <span className="channel-account-card__error"> · 当前不可用</span> : null}
                            {account.last_error_message ? (
                              <span className={getProbeMessageClassName(account)}> · {account.last_error_message}</span>
                            ) : null}
                          </div>
                          {pluginDisabled ? <div className="channel-account-card__times">{pluginDisabledReason}</div> : null}
                          <div className="channel-account-card__times">
                            最近收到消息：{formatTimestamp(account.last_inbound_at)} · 最近发送消息：{formatTimestamp(account.last_outbound_at)}
                          </div>
                        </div>
                        <div className="channel-account-card__actions">
                          <button className="btn btn--outline btn--sm" onClick={() => openEditModal(account)} disabled={loading || pluginDisabled}>修改</button>
                          <button className="btn btn--outline btn--sm" onClick={() => void handleProbeAccount(account.id)} disabled={loading || pluginDisabled}>检查连接</button>
                          <button className="btn btn--outline btn--sm" onClick={() => void handleToggleAccountStatus(account)} disabled={loading || pluginDisabled}>
                            {account.status === 'disabled' ? '启用' : '停用'}
                          </button>
                          <button className="btn btn--outline btn--sm" onClick={() => toggleAccountExpand(account.id)}>
                            {isExpanded ? '收起详情' : '查看详情'}
                          </button>
                        </div>
                      </div>

                      {isExpanded ? (
                        <div className="channel-account-card__detail">
                          {detailLoading ? (
                            <div className="text-text-secondary">加载详情中...</div>
                          ) : (
                            <>
                              {accountStatus ? (
                                <div className="channel-detail-section">
                                  <h4>连接情况</h4>
                                  <div className="channel-detail-stats">
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">{accountStatus.recent_failure_summary.recent_failure_count}</span>
                                      <span className="channel-detail-stat__label">最近失败次数</span>
                                    </div>
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">{accountStatus.recent_delivery_count}</span>
                                      <span className="channel-detail-stat__label">最近发送消息</span>
                                    </div>
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">{accountStatus.recent_inbound_count}</span>
                                      <span className="channel-detail-stat__label">最近收到消息</span>
                                    </div>
                                  </div>
                                  {accountStatus.recent_failure_summary.last_error_message ? (
                                    <div className="channel-detail-error">
                                      <strong>最近一次失败：</strong>
                                      {accountStatus.recent_failure_summary.last_error_message}
                                      <span className="channel-detail-error__time">（{formatTimestamp(accountStatus.recent_failure_summary.last_failed_at)}）</span>
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}

                              <div className="channel-detail-section">
                                <h4>成员绑定</h4>
                                <ChannelAccountBindingsPanel householdId={currentHouseholdId ?? ''} accountId={account.id} members={activeMembers} />
                              </div>

                              {failedDeliveries.length > 0 || failedInboundEvents.length > 0 ? (
                                <div className="channel-detail-section">
                                  <h4>最近未成功处理的消息</h4>
                                  {failedDeliveries.length > 0 ? (
                                    <div className="channel-failure-list">
                                      <h5>发送失败（最近 5 条）</h5>
                                      {failedDeliveries.map((item) => (
                                        <div key={item.id} className="channel-failure-item">
                                          <span className="channel-failure-item__type">{item.delivery_type}</span>
                                          <span className="channel-failure-item__error">{item.last_error_message ?? '未知错误'}</span>
                                          <span className="channel-failure-item__time">{formatTimestamp(item.created_at)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                  {failedInboundEvents.length > 0 ? (
                                    <div className="channel-failure-list">
                                      <h5>接收失败（最近 5 条）</h5>
                                      {failedInboundEvents.map((item) => (
                                        <div key={item.id} className="channel-failure-item">
                                          <span className="channel-failure-item__type">{item.event_type}</span>
                                          <span className="channel-failure-item__error">{item.error_message ?? '未知错误'}</span>
                                          <span className="channel-failure-item__time">{formatTimestamp(item.received_at)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
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
            )}
          </div>
        </Section>

        {accountModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setAccountModalOpen(false)}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <h3>{editingAccount ? '修改平台接入' : '添加平台接入'}</h3>
                <p>填好对应平台提供的信息后，家庭成员就能在这个聊天工具里联系系统，账号标识由系统自动生成。</p>
              </div>
              <form className="settings-form" onSubmit={handleSaveAccount}>
                <div className="form-group">
                  <label>平台</label>
                  <select
                    className="form-select"
                    value={accountForm.plugin_id}
                    onChange={(event) => setAccountForm((current) => ({ ...current, plugin_id: event.target.value }))}
                    disabled={Boolean(editingAccount)}
                    required
                  >
                    <option value="">请选择平台</option>
                    {availableChannelPlugins.map((plugin) => (
                      <option key={plugin.pluginId} value={plugin.pluginId}>{plugin.icon} {plugin.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>显示名称</label>
                  <input
                    className="form-input"
                    value={accountForm.display_name}
                    onChange={(event) => setAccountForm((current) => ({ ...current, display_name: event.target.value }))}
                    placeholder="例如：家庭 Telegram 助手"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>接入方式</label>
                  <select
                    className="form-select"
                    value={accountForm.connection_mode}
                    onChange={(event) => setAccountForm((current) => ({ ...current, connection_mode: event.target.value as 'webhook' | 'polling' | 'websocket' }))}
                  >
                    <option value="webhook">Webhook（推荐）</option>
                    <option value="polling">Polling</option>
                    <option value="websocket">WebSocket</option>
                  </select>
                  <div className="form-help">大多数平台直接用 Webhook 就够了，只有你明确知道要改时再换。</div>
                </div>
                <div className="form-group">
                  <label>状态</label>
                  <select
                    className="form-select"
                    value={accountForm.status}
                    onChange={(event) => setAccountForm((current) => ({ ...current, status: event.target.value as 'draft' | 'active' | 'degraded' | 'disabled' }))}
                  >
                    <option value="draft">先保存，暂不启用</option>
                    <option value="active">启用</option>
                    <option value="disabled">停用</option>
                  </select>
                  <div className="form-help">建议先保存，确认能正常收发消息后再启用。</div>
                </div>

                {(() => {
                  const platformCode = editingAccount?.platform_code ?? availableChannelPlugins.find((plugin) => plugin.pluginId === accountForm.plugin_id)?.platformCode;
                  const configFields = platformCode ? PLATFORM_CONFIG_FIELDS[platformCode] : null;
                  if (!configFields || configFields.length === 0) {
                    return null;
                  }
                  return (
                    <div className="form-group channel-config-section">
                      <label>接入信息</label>
                      <div className="channel-config-fields">
                        {configFields.map((field) => (
                          <div key={field.key} className="channel-config-field">
                            <label className="channel-config-field__label">
                              {field.label}
                              {field.required ? <span className="required-mark">*</span> : null}
                            </label>
                            <input
                              type={field.type}
                              className="form-input"
                              value={(accountForm.config[field.key] as string) ?? ''}
                              onChange={(event) => setAccountForm((current) => ({
                                ...current,
                                config: { ...current.config, [field.key]: event.target.value },
                              }))}
                              placeholder={field.placeholder}
                              required={field.required}
                            />
                            {field.helpText ? <div className="form-help">{field.helpText}</div> : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

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
