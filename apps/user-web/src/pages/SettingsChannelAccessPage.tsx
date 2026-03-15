/* ============================================================
 * 通讯平台接入设置页
 * ============================================================ */
import { useEffect, useState, useMemo } from 'react';
import { useI18n } from '../i18n';
import { PageHeader, Card, Section, EmptyState } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api, ApiError } from '../lib/api';
import type {
  ChannelAccountRead,
  ChannelAccountCreate,
  ChannelAccountUpdate,
  ChannelAccountStatusRead,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  PluginRegistryItem,
} from '../lib/types';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';

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
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: true, placeholder: '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11', helpText: '从 @BotFather 获取的机器人令牌' },
    { key: 'webhook_secret', label: 'Webhook Secret', type: 'password', required: false, placeholder: '可选的安全验证密钥', helpText: '可选，用于验证 Webhook 请求来源' },
  ],
  discord: [
    { key: 'application_public_key', label: 'Application Public Key', type: 'text', required: true, placeholder: 'abc123def456...', helpText: '从 Discord Developer Portal 获取的公钥' },
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: false, placeholder: '可选，主动发消息需要', helpText: '可选，用于主动发送消息' },
  ],
  feishu: [
    { key: 'app_id', label: 'App ID', type: 'text', required: true, placeholder: 'cli_xxx', helpText: '飞书开放平台应用 ID' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: true, placeholder: '应用密钥', helpText: '飞书开放平台应用密钥' },
    { key: 'encrypt_key', label: 'Encrypt Key', type: 'password', required: false, placeholder: '可选，消息加密密钥', helpText: '可选，用于消息加解密' },
    { key: 'base_url', label: 'Base URL', type: 'text', required: false, placeholder: 'https://open.feishu.cn', helpText: '可选，私有部署时修改' },
  ],
  dingtalk: [
    { key: 'app_key', label: 'App Key', type: 'text', required: true, placeholder: 'dingxxx', helpText: '钉钉开放平台应用 Key' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: false, placeholder: '可选，用于获取 Access Token', helpText: '可选，用于 API 调用' },
  ],
  wecom_app: [
    { key: 'corp_id', label: '企业 ID (Corp ID)', type: 'text', required: true, placeholder: 'ww1234567890abcdef', helpText: '企业微信后台的企业 ID' },
    { key: 'corp_secret', label: '应用 Secret', type: 'password', required: true, placeholder: '应用凭证密钥', helpText: '应用的 Secret' },
    { key: 'agent_id', label: 'Agent ID', type: 'text', required: true, placeholder: '1000001', helpText: '应用的 AgentId' },
    { key: 'callback_token', label: 'Callback Token', type: 'password', required: true, placeholder: '回调 Token', helpText: '接收消息的 Token' },
    { key: 'encoding_aes_key', label: 'Encoding AES Key', type: 'password', required: true, placeholder: '消息加解密密钥', helpText: '消息加解密的 AES Key' },
  ],
  wecom_bot: [
    { key: 'webhook_url', label: 'Webhook URL', type: 'text', required: false, placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx', helpText: '群机器人 Webhook 地址，与 Key 二选一' },
    { key: 'key', label: '机器人 Key', type: 'password', required: false, placeholder: '群机器人的 key 参数', helpText: '机器人 Key，与 Webhook URL 二选一' },
  ],
};

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', name: 'Telegram', icon: '📱' },
  { code: 'discord', name: 'Discord', icon: '💬' },
  { code: 'feishu', name: '飞书', icon: '🐦' },
  { code: 'dingtalk', name: '钉钉', icon: '📌' },
  { code: 'wecom_app', name: '企业微信应用', icon: '🏢' },
  { code: 'wecom_bot', name: '企业微信群机器人', icon: '🤖' },
];

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find(p => p.code === platformCode) ?? { code: platformCode, name: platformCode, icon: '🔌' };
}

function formatStatus(status: string): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  switch (status) {
    case 'active':
      return { label: '已启用', tone: 'success' };
    case 'draft':
      return { label: '草稿', tone: 'secondary' };
    case 'degraded':
      return { label: '降级', tone: 'warning' };
    case 'disabled':
      return { label: '已停用', tone: 'secondary' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatProbeStatus(status: string | null): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (!status) return { label: '未探测', tone: 'secondary' };
  switch (status) {
    case 'ok':
      return { label: '正常', tone: 'success' };
    case 'failed':
      return { label: '失败', tone: 'danger' };
    case 'pending':
      return { label: '探测中', tone: 'warning' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '暂无';
  try {
    return new Date(ts).toLocaleString('zh-CN');
  } catch {
    return ts;
  }
}

export function SettingsChannelAccess() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();

  const [accounts, setAccounts] = useState<ChannelAccountRead[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [channelPlugins, setChannelPlugins] = useState<PluginRegistryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  // 详情相关状态
  const [expandedAccountId, setExpandedAccountId] = useState<string | null>(null);
  const [accountStatus, setAccountStatus] = useState<ChannelAccountStatusRead | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<ChannelDeliveryRead[]>([]);
  const [failedInboundEvents, setFailedInboundEvents] = useState<ChannelInboundEventRead[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // 弹窗状态
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<ChannelAccountRead | null>(null);
  const [accountForm, setAccountForm] = useState<{
    plugin_id: string;
    account_code: string;
    display_name: string;
    connection_mode: 'webhook' | 'polling' | 'websocket';
    config: Record<string, unknown>;
    status: 'draft' | 'active' | 'degraded' | 'disabled';
  }>({
    plugin_id: '',
    account_code: '',
    display_name: '',
    connection_mode: 'webhook',
    config: {},
    status: 'draft',
  });
  const [modalLoading, setModalLoading] = useState(false);

  // 加载平台账号列表
  useEffect(() => {
    if (!currentHouseholdId) {
      setAccounts([]);
      setMembers([]);
      setChannelPlugins([]);
      return;
    }

    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const [pluginsResult, accountsResult, membersResult] = await Promise.all([
          api.listRegisteredPlugins(currentHouseholdId),
          api.listChannelAccounts(currentHouseholdId),
          api.listMembers(currentHouseholdId),
        ]);
        if (!cancelled) {
          setChannelPlugins(pluginsResult.items.filter(plugin => plugin.types.includes('channel')));
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
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  const channelPluginMap = useMemo(() => {
    return new Map(channelPlugins.map(plugin => [plugin.id, plugin]));
  }, [channelPlugins]);

  const availableChannelPlugins = useMemo<ChannelPluginOption[]>(() => {
    return channelPlugins
      .filter(plugin => plugin.enabled && !!plugin.capabilities.channel?.platform_code)
      .map(plugin => {
        const platformCode = plugin.capabilities.channel?.platform_code ?? plugin.id.replace(/^channel-/, '');
        const platform = getPlatformInfo(platformCode);
        return {
          pluginId: plugin.id,
          platformCode,
          name: plugin.name,
          icon: platform.icon,
        };
      })
      .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'));
  }, [channelPlugins]);

  // 加载账号详情
  async function loadAccountDetail(accountId: string) {
    if (!currentHouseholdId) return;

    setDetailLoading(true);
    try {
      const [statusResult, deliveriesResult, inboundResult] = await Promise.all([
        api.getChannelAccountStatus(currentHouseholdId, accountId),
        api.listChannelDeliveries(currentHouseholdId, { channel_account_id: accountId, status: 'failed' }),
        api.listChannelInboundEvents(currentHouseholdId, { channel_account_id: accountId, status: 'failed' }),
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

  function getAccountPluginState(account: ChannelAccountRead): PluginRegistryItem | null {
    return channelPluginMap.get(account.plugin_id) ?? null;
  }

  function isAccountPluginDisabled(account: ChannelAccountRead): boolean {
    return getAccountPluginState(account)?.enabled === false;
  }

  // 展开/收起账号详情
  function toggleAccountExpand(accountId: string) {
    if (expandedAccountId === accountId) {
      setExpandedAccountId(null);
      setAccountStatus(null);
      setFailedDeliveries([]);
      setFailedInboundEvents([]);
    } else {
      setExpandedAccountId(accountId);
      void loadAccountDetail(accountId);
    }
  }

  // 打开新增弹窗
  function openCreateModal() {
    setEditingAccount(null);
    setAccountForm({
      plugin_id: '',
      account_code: '',
      display_name: '',
      connection_mode: 'webhook',
      config: {},
      status: 'draft',
    });
    setAccountModalOpen(true);
  }

  // 打开编辑弹窗
  function openEditModal(account: ChannelAccountRead) {
    setEditingAccount(account);
    setAccountForm({
      plugin_id: account.plugin_id,
      account_code: account.account_code,
      display_name: account.display_name,
      connection_mode: account.connection_mode,
      config: account.config,
      status: account.status,
    });
    setAccountModalOpen(true);
  }

  // 保存账号
  async function handleSaveAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) return;

    setModalLoading(true);
    setError('');
    setStatus('');

    try {
      if (editingAccount) {
        // 编辑模式
        const payload: ChannelAccountUpdate = {
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          config: accountForm.config,
          status: accountForm.status,
        };
        const result = await api.updateChannelAccount(currentHouseholdId, editingAccount.id, payload);
        setAccounts(current => current.map(a => (a.id === result.id ? result : a)));
        setStatus('平台账号已更新。');
      } else {
        // 新增模式
        const payload: ChannelAccountCreate = {
          plugin_id: accountForm.plugin_id,
          account_code: accountForm.account_code,
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          config: accountForm.config,
          status: accountForm.status,
        };
        const result = await api.createChannelAccount(currentHouseholdId, payload);
        setAccounts(current => [result, ...current]);
        setStatus('平台账号已创建。');
      }
      setAccountModalOpen(false);
    } catch (saveError) {
      setError(saveError instanceof ApiError ? (saveError.payload as { detail?: string }).detail ?? saveError.message : '保存失败');
    } finally {
      setModalLoading(false);
    }
  }

  // 探测账号
  async function handleProbeAccount(accountId: string) {
    if (!currentHouseholdId) return;

    setLoading(true);
    setError('');
    try {
      const result = await api.probeChannelAccount(currentHouseholdId, accountId);
      setAccounts(current => current.map(a => (a.id === result.account.id ? result.account : a)));
      if (expandedAccountId === accountId) {
        setAccountStatus(result);
      }
      setStatus('探测完成。');
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : '探测失败');
    } finally {
      setLoading(false);
    }
  }

  // 启用/停用账号
  async function handleToggleAccountStatus(account: ChannelAccountRead) {
    if (!currentHouseholdId) return;

    const newStatus = account.status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      const result = await api.updateChannelAccount(currentHouseholdId, account.id, { status: newStatus });
      setAccounts(current => current.map(a => (a.id === result.id ? result : a)));
      setStatus(newStatus === 'active' ? '账号已启用。' : '账号已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  const activeMembers = useMemo(() => members.filter(m => m.status === 'active'), [members]);

  return (
    <div className="settings-page">
      <Section title="通讯平台接入">
        {/* 顶部说明卡 */}
        <Card className="channel-access-notice">
          <div className="channel-access-notice__content">
            <h3>📋 关于通讯平台接入</h3>
            <p>在这里配置外部通讯平台（如 Telegram、Discord、飞书等）的机器人账号，让家庭成员可以在常用聊天工具里直接和 AI 对话。</p>
            <ul>
              <li><strong>平台账号</strong>：每个外部平台的机器人配置</li>
              <li><strong>成员绑定</strong>：把平台用户 ID 和家庭成员关联，让系统知道"谁在说话"</li>
              <li><strong>状态监控</strong>：查看平台连接状态和最近失败记录</li>
            </ul>
          </div>
        </Card>

        {/* 状态提示 */}
        {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
        {status && <div className="settings-note"><span>✅</span> {status}</div>}

        {/* 平台账号列表 */}
        <div className="channel-account-list">
          {loading && accounts.length === 0 ? (
            <div className="text-text-secondary">正在加载平台账号...</div>
          ) : accounts.length === 0 ? (
            <EmptyState
              icon="🔌"
              title="还没有配置平台账号"
              description="点击下方按钮添加第一个通讯平台机器人。"
              action={
                <button className="btn btn--primary" onClick={openCreateModal} disabled={availableChannelPlugins.length === 0}>
                  新增平台账号
                </button>
              }
            />
          ) : (
            <>
              <div className="channel-account-list__header">
                <span>已配置 {accounts.length} 个平台账号</span>
                <button className="btn btn--primary btn--sm" onClick={openCreateModal} disabled={availableChannelPlugins.length === 0}>
                  新增平台账号
                </button>
              </div>

              {accounts.map(account => {
                const platform = getPlatformInfo(account.platform_code);
                const statusInfo = formatStatus(account.status);
                const probeInfo = formatProbeStatus(account.last_probe_status);
                const isExpanded = expandedAccountId === account.id;
                const pluginState = getAccountPluginState(account);
                const pluginDisabled = isAccountPluginDisabled(account);
                const pluginDisabledReason = pluginState?.disabled_reason ?? '当前家庭已停用该通道插件';

                return (
                  <Card key={account.id} className="channel-account-card">
                    {/* 账号基本信息 */}
                    <div className="channel-account-card__header">
                      <div className="channel-account-card__icon">{platform.icon}</div>
                      <div className="channel-account-card__info">
                        <div className="channel-account-card__title">
                          <span className="channel-account-card__name">{account.display_name}</span>
                          <span className={`badge badge--${statusInfo.tone}`}>{statusInfo.label}</span>
                          <span className={`badge badge--${probeInfo.tone}`}>{probeInfo.label}</span>
                        </div>
                        <div className="channel-account-card__meta">
                          {platform.name} · {account.connection_mode}
                          {pluginDisabled && (
                            <span className="channel-account-card__error"> · 插件已停用</span>
                          )}
                          {account.last_error_message && (
                            <span className="channel-account-card__error"> · {account.last_error_message}</span>
                          )}
                        </div>
                        {pluginDisabled && (
                          <div className="channel-account-card__times">{pluginDisabledReason}</div>
                        )}
                        <div className="channel-account-card__times">
                          最近入站：{formatTimestamp(account.last_inbound_at)} · 最近出站：{formatTimestamp(account.last_outbound_at)}
                        </div>
                      </div>
                      <div className="channel-account-card__actions">
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => openEditModal(account)}
                          disabled={loading || pluginDisabled}
                          title={pluginDisabled ? '对应插件已停用，不能编辑账号配置' : undefined}
                        >
                          编辑
                        </button>
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => void handleProbeAccount(account.id)}
                          disabled={loading || pluginDisabled}
                          title={pluginDisabled ? '对应插件已停用，不能继续探测' : undefined}
                        >
                          立即探测
                        </button>
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => void handleToggleAccountStatus(account)}
                          disabled={loading || pluginDisabled}
                          title={pluginDisabled ? '对应插件已停用，不能单独切换账号状态' : undefined}
                        >
                          {account.status === 'disabled' ? '启用' : '停用'}
                        </button>
                        <button className="btn btn--outline btn--sm" onClick={() => toggleAccountExpand(account.id)}>
                          {isExpanded ? '收起详情' : '展开详情'}
                        </button>
                      </div>
                    </div>

                    {/* 账号详情区 */}
                    {isExpanded && (
                      <div className="channel-account-card__detail">
                        {detailLoading ? (
                          <div className="text-text-secondary">加载详情中...</div>
                        ) : (
                          <>
                            {/* 状态摘要 */}
                            {accountStatus && (
                              <div className="channel-detail-section">
                                <h4>状态摘要</h4>
                                <div className="channel-detail-stats">
                                  <div className="channel-detail-stat">
                                    <span className="channel-detail-stat__value">
                                      {accountStatus.recent_failure_summary.recent_failure_count}
                                    </span>
                                    <span className="channel-detail-stat__label">最近失败数</span>
                                  </div>
                                  <div className="channel-detail-stat">
                                    <span className="channel-detail-stat__value">
                                      {accountStatus.recent_delivery_count}
                                    </span>
                                    <span className="channel-detail-stat__label">最近出站数</span>
                                  </div>
                                  <div className="channel-detail-stat">
                                    <span className="channel-detail-stat__value">
                                      {accountStatus.recent_inbound_count}
                                    </span>
                                    <span className="channel-detail-stat__label">最近入站数</span>
                                  </div>
                                </div>
                                {accountStatus.recent_failure_summary.last_error_message && (
                                  <div className="channel-detail-error">
                                    <strong>最近错误：</strong>{accountStatus.recent_failure_summary.last_error_message}
                                    <span className="channel-detail-error__time">
                                      （{formatTimestamp(accountStatus.recent_failure_summary.last_failed_at)}）
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* 成员绑定面板 */}
                            <div className="channel-detail-section">
                              <h4>成员绑定</h4>
                              <ChannelAccountBindingsPanel
                                householdId={currentHouseholdId ?? ''}
                                accountId={account.id}
                                members={activeMembers}
                              />
                            </div>

                            {/* 失败记录 */}
                            {(failedDeliveries.length > 0 || failedInboundEvents.length > 0) && (
                              <div className="channel-detail-section">
                                <h4>最近失败记录</h4>
                                {failedDeliveries.length > 0 && (
                                  <div className="channel-failure-list">
                                    <h5>出站失败（最近 5 条）</h5>
                                    {failedDeliveries.map(d => (
                                      <div key={d.id} className="channel-failure-item">
                                        <span className="channel-failure-item__type">{d.delivery_type}</span>
                                        <span className="channel-failure-item__error">{d.last_error_message ?? '未知错误'}</span>
                                        <span className="channel-failure-item__time">{formatTimestamp(d.created_at)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {failedInboundEvents.length > 0 && (
                                  <div className="channel-failure-list">
                                    <h5>入站失败（最近 5 条）</h5>
                                    {failedInboundEvents.map(e => (
                                      <div key={e.id} className="channel-failure-item">
                                        <span className="channel-failure-item__type">{e.event_type}</span>
                                        <span className="channel-failure-item__error">{e.error_message ?? '未知错误'}</span>
                                        <span className="channel-failure-item__time">{formatTimestamp(e.received_at)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </Card>
                );
              })}
            </>
          )}
        </div>
      </Section>

      {/* 新增/编辑账号弹窗 */}
      {accountModalOpen && (
        <div className="member-modal-overlay" onClick={() => setAccountModalOpen(false)}>
          <div className="member-modal" onClick={e => e.stopPropagation()}>
            <div className="member-modal__header">
              <h3>{editingAccount ? '编辑平台账号' : '新增平台账号'}</h3>
              <p>配置外部通讯平台的机器人接入。</p>
            </div>
            <form className="settings-form" onSubmit={handleSaveAccount}>
              <div className="form-group">
                <label>平台类型</label>
                <select
                  className="form-select"
                  value={accountForm.plugin_id}
                  onChange={e => setAccountForm(f => ({ ...f, plugin_id: e.target.value }))}
                  disabled={!!editingAccount}
                  required
                >
                  <option value="">请选择平台</option>
                  {availableChannelPlugins.map(plugin => (
                    <option key={plugin.pluginId} value={plugin.pluginId}>
                      {plugin.icon} {plugin.name}
                    </option>
                  ))}
                </select>
                {!editingAccount && (
                  <div className="form-help">
                    这里只显示当前家庭仍然启用的通讯通道插件；已在插件管理里停用的插件不会出现在这里。
                  </div>
                )}
                {!editingAccount && availableChannelPlugins.length === 0 && (
                  <div className="form-help">当前没有可用的通讯通道插件，请先去插件管理里启用对应插件。</div>
                )}
              </div>
              <div className="form-group">
                <label>账号代码</label>
                <input
                  className="form-input"
                  value={accountForm.account_code}
                  onChange={e => setAccountForm(f => ({ ...f, account_code: e.target.value }))}
                  disabled={!!editingAccount}
                  placeholder="my-telegram-bot"
                  required
                />
                <div className="form-help">家庭内唯一的英文标识，创建后不可修改。</div>
              </div>
              <div className="form-group">
                <label>显示名称</label>
                <input
                  className="form-input"
                  value={accountForm.display_name}
                  onChange={e => setAccountForm(f => ({ ...f, display_name: e.target.value }))}
                  placeholder="我的 Telegram 机器人"
                  required
                />
              </div>
              <div className="form-group">
                <label>连接方式</label>
                <select
                  className="form-select"
                  value={accountForm.connection_mode}
                  onChange={e => setAccountForm(f => ({ ...f, connection_mode: e.target.value as typeof accountForm.connection_mode }))}
                >
                  <option value="webhook">Webhook</option>
                  <option value="polling">Polling</option>
                  <option value="websocket">WebSocket</option>
                </select>
              </div>
              <div className="form-group">
                <label>状态</label>
                <select
                  className="form-select"
                  value={accountForm.status}
                  onChange={e => setAccountForm(f => ({ ...f, status: e.target.value as typeof accountForm.status }))}
                >
                  <option value="draft">草稿</option>
                  <option value="active">启用</option>
                  <option value="disabled">停用</option>
                </select>
                <div className="form-help">建议先设为草稿，配置完成后再启用。</div>
              </div>

              {/* 平台专属配置字段 */}
              {(() => {
                const platformCode = editingAccount?.platform_code
                  ?? availableChannelPlugins.find(plugin => plugin.pluginId === accountForm.plugin_id)?.platformCode;
                const configFields = platformCode ? PLATFORM_CONFIG_FIELDS[platformCode] : null;
                if (!configFields || configFields.length === 0) return null;
                return (
                  <div className="form-group channel-config-section">
                    <label>平台配置</label>
                    <div className="channel-config-fields">
                      {configFields.map(field => (
                        <div key={field.key} className="channel-config-field">
                          <label className="channel-config-field__label">
                            {field.label}
                            {field.required && <span className="required-mark">*</span>}
                          </label>
                          <input
                            type={field.type}
                            className="form-input"
                            value={(accountForm.config[field.key] as string) ?? ''}
                            onChange={e => setAccountForm(f => ({
                              ...f,
                              config: { ...f.config, [field.key]: e.target.value },
                            }))}
                            placeholder={field.placeholder}
                            required={field.required}
                          />
                          {field.helpText && <div className="form-help">{field.helpText}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setAccountModalOpen(false)} disabled={modalLoading}>
                  取消
                </button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>
                  {modalLoading ? '保存中...' : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
