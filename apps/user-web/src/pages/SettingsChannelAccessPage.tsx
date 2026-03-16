/* ============================================================
 * 通讯平台接入设置页
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { Card, EmptyState, Section } from '../components/base';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';
import { DynamicPluginConfigForm } from '../components/plugin-config/DynamicPluginConfigForm';
import { api, ApiError } from '../lib/api';
import type {
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  PluginConfigForm,
  PluginConfigUpdatePayload,
  PluginManifestConfigSpec,
  PluginRegistryItem,
} from '../lib/types';
import { useHouseholdContext } from '../state/household';

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

type ChannelPluginSpec = NonNullable<PluginRegistryItem['capabilities']['channel']>;

type ConfigDraft = {
  payload: PluginConfigUpdatePayload;
  hasErrors: boolean;
};

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', name: 'Telegram', icon: '📨' },
  { code: 'discord', name: 'Discord', icon: '🎮' },
  { code: 'feishu', name: '飞书', icon: '🪽' },
  { code: 'dingtalk', name: '钉钉', icon: '🔔' },
  { code: 'wecom-app', name: '企业微信应用', icon: '🏢' },
  { code: 'wecom-bot', name: '企业微信机器人', icon: '🤖' },
];

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find(item => item.code === platformCode) ?? {
    code: platformCode,
    name: platformCode,
    icon: '📌',
  };
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
  if (!status) {
    return { label: '未探测', tone: 'secondary' };
  }
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
  if (!ts) {
    return '暂无';
  }
  try {
    return new Date(ts).toLocaleString('zh-CN');
  } catch {
    return ts;
  }
}

function getChannelPluginSpec(plugin: PluginRegistryItem | null): ChannelPluginSpec | null {
  return plugin?.capabilities.channel ?? null;
}

function supportsMemberBinding(plugin: PluginRegistryItem | null): boolean {
  return getChannelPluginSpec(plugin)?.supports_member_binding ?? true;
}

function getChannelAccountConfigSpec(plugin: PluginRegistryItem | null): PluginManifestConfigSpec | null {
  return plugin?.config_specs.find(item => item.scope_type === 'channel_account') ?? null;
}

function buildEmptyChannelConfigForm(pluginId: string, configSpec: PluginManifestConfigSpec): PluginConfigForm {
  const values: Record<string, unknown> = {};
  const secretFields: Record<string, { has_value: boolean; masked?: string | null }> = {};

  for (const field of configSpec.config_schema.fields) {
    if (field.type === 'secret') {
      secretFields[field.key] = { has_value: false, masked: null };
      continue;
    }
    if (field.default !== undefined) {
      values[field.key] = field.default;
    }
  }

  return {
    plugin_id: pluginId,
    config_spec: configSpec,
    view: {
      scope_type: 'channel_account',
      scope_key: '__pending__',
      schema_version: configSpec.schema_version,
      state: 'unconfigured',
      values,
      secret_fields: secretFields,
      field_errors: {},
    },
  };
}

export function SettingsChannelAccess() {
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
  const [configForm, setConfigForm] = useState<PluginConfigForm | null>(null);
  const [configFormLoading, setConfigFormLoading] = useState(false);
  const [configFormError, setConfigFormError] = useState('');
  const [configDraft, setConfigDraft] = useState<ConfigDraft | null>(null);
  const [accountForm, setAccountForm] = useState<{
    plugin_id: string;
    account_code: string;
    display_name: string;
    connection_mode: 'webhook' | 'polling' | 'websocket';
    status: 'draft' | 'active' | 'degraded' | 'disabled';
  }>({
    plugin_id: '',
    account_code: '',
    display_name: '',
    connection_mode: 'webhook',
    status: 'draft',
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

    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const [pluginsResult, accountsResult, membersResult] = await Promise.all([
          api.listRegisteredPlugins(currentHouseholdId),
          api.listChannelAccounts(currentHouseholdId),
          api.listMembers(currentHouseholdId),
        ]);
        if (cancelled) {
          return;
        }
        setChannelPlugins(pluginsResult.items.filter(plugin => plugin.types.includes('channel')));
        setAccounts(accountsResult);
        setMembers(membersResult.items);
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

  const activeMembers = useMemo(() => members.filter(member => member.status === 'active'), [members]);

  const currentModalPlugin = useMemo(() => {
    if (editingAccount) {
      return channelPluginMap.get(editingAccount.plugin_id) ?? null;
    }
    return channelPluginMap.get(accountForm.plugin_id) ?? null;
  }, [accountForm.plugin_id, channelPluginMap, editingAccount]);

  useEffect(() => {
    if (!accountModalOpen) {
      setConfigForm(null);
      setConfigFormLoading(false);
      setConfigFormError('');
      setConfigDraft(null);
      return;
    }

    if (!currentHouseholdId || !currentModalPlugin) {
      setConfigForm(null);
      setConfigFormLoading(false);
      setConfigFormError('');
      setConfigDraft(null);
      return;
    }

    const configSpec = getChannelAccountConfigSpec(currentModalPlugin);
    if (!configSpec) {
      setConfigForm(null);
      setConfigFormLoading(false);
      setConfigFormError('');
      setConfigDraft(null);
      return;
    }

    if (!editingAccount) {
      setConfigForm(buildEmptyChannelConfigForm(currentModalPlugin.id, configSpec));
      setConfigFormLoading(false);
      setConfigFormError('');
      setConfigDraft(null);
      return;
    }

    let cancelled = false;
    const loadConfigForm = async () => {
      setConfigFormLoading(true);
      setConfigFormError('');
      try {
        const result = await api.getPluginConfigForm(currentHouseholdId, editingAccount.plugin_id, {
          scope_type: 'channel_account',
          scope_key: editingAccount.id,
        });
        if (!cancelled) {
          setConfigForm(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setConfigFormError(loadError instanceof ApiError ? loadError.message : '加载平台配置失败');
          setConfigForm(buildEmptyChannelConfigForm(currentModalPlugin.id, configSpec));
        }
      } finally {
        if (!cancelled) {
          setConfigFormLoading(false);
        }
      }
    };

    void loadConfigForm();

    return () => {
      cancelled = true;
    };
  }, [accountModalOpen, currentHouseholdId, currentModalPlugin, editingAccount]);

  async function loadAccountDetail(accountId: string) {
    if (!currentHouseholdId) {
      return;
    }

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
      account_code: '',
      display_name: '',
      connection_mode: 'webhook',
      status: 'draft',
    });
    setConfigForm(null);
    setConfigFormError('');
    setConfigDraft(null);
    setAccountModalOpen(true);
  }

  function openEditModal(account: ChannelAccountRead) {
    setEditingAccount(account);
    setAccountForm({
      plugin_id: account.plugin_id,
      account_code: account.account_code,
      display_name: account.display_name,
      connection_mode: account.connection_mode,
      status: account.status,
    });
    setConfigForm(null);
    setConfigFormError('');
    setConfigDraft(null);
    setAccountModalOpen(true);
  }

  async function handleSaveAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId) {
      return;
    }

    setModalLoading(true);
    setError('');
    setStatus('');

    if (configDraft?.hasErrors) {
      setModalLoading(false);
      setError('平台配置里还有没修好的字段，先把表单错误处理掉。');
      return;
    }

    try {
      let savedAccount: ChannelAccountRead;
      if (editingAccount) {
        const payload: ChannelAccountUpdate = {
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          status: accountForm.status,
        };
        savedAccount = await api.updateChannelAccount(currentHouseholdId, editingAccount.id, payload);
      } else {
        const payload: ChannelAccountCreate = {
          plugin_id: accountForm.plugin_id,
          account_code: accountForm.account_code,
          display_name: accountForm.display_name,
          connection_mode: accountForm.connection_mode,
          status: accountForm.status,
        };
        savedAccount = await api.createChannelAccount(currentHouseholdId, payload);
      }

      setAccounts(current => {
        const exists = current.some(account => account.id === savedAccount.id);
        if (exists) {
          return current.map(account => (account.id === savedAccount.id ? savedAccount : account));
        }
        return [savedAccount, ...current];
      });

      if (configForm && configDraft) {
        try {
          const savedConfigForm = await api.savePluginConfigForm(currentHouseholdId, savedAccount.plugin_id, {
            ...configDraft.payload,
            scope_type: 'channel_account',
            scope_key: savedAccount.id,
          });
          setConfigForm(savedConfigForm);
          setConfigFormError('');
        } catch (configSaveError) {
          const configSaveMessage =
            configSaveError instanceof ApiError
              ? ((configSaveError.payload as { detail?: string }).detail ?? configSaveError.message)
              : configSaveError instanceof Error
                ? configSaveError.message
                : '平台配置保存失败';
          setConfigFormError(configSaveMessage);
          setStatus(editingAccount ? '平台账号基础信息已更新。' : '平台账号已创建。');
          setError(`${configSaveMessage} 请重新打开编辑继续处理。`);
          setAccountModalOpen(false);
          return;
        }
      }

      setStatus(editingAccount ? '平台账号已更新。' : '平台账号已创建。');
      setAccountModalOpen(false);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? ((saveError.payload as { detail?: string }).detail ?? saveError.message)
          : saveError instanceof Error
            ? saveError.message
            : '保存失败',
      );
    } finally {
      setModalLoading(false);
    }
  }

  async function handleProbeAccount(accountId: string) {
    if (!currentHouseholdId) {
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await api.probeChannelAccount(currentHouseholdId, accountId);
      setAccounts(current => current.map(account => (account.id === result.account.id ? result.account : account)));
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

  async function handleToggleAccountStatus(account: ChannelAccountRead) {
    if (!currentHouseholdId) {
      return;
    }

    const nextStatus = account.status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      const result = await api.updateChannelAccount(currentHouseholdId, account.id, { status: nextStatus });
      setAccounts(current => current.map(item => (item.id === result.id ? result : item)));
      setStatus(nextStatus === 'active' ? '账号已启用。' : '账号已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="settings-page">
      <Section title="通讯平台接入">
        <Card className="channel-access-notice">
          <div className="channel-access-notice__content">
            <h3>关于通讯平台接入</h3>
            <p>在这里配置外部通讯平台的机器人账号，让家庭成员可以直接在常用聊天工具里和系统对话。</p>
            <ul>
              <li><strong>平台账号</strong>：管理每个平台的 Bot 配置。</li>
              <li><strong>成员绑定</strong>：把外部平台用户和家庭成员对上，系统才知道消息是谁发的。</li>
              <li><strong>状态观测</strong>：查看最近入站、出站和失败情况，排查问题不再靠猜。</li>
            </ul>
          </div>
        </Card>

        {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
        {status && <div className="settings-note"><span>✅</span> {status}</div>}

        <div className="channel-account-list">
          {loading && accounts.length === 0 ? (
            <div className="text-text-secondary">正在加载平台账号...</div>
          ) : accounts.length === 0 ? (
            <EmptyState
              icon="📌"
              title="还没有配置平台账号"
              description="先添加一个通讯平台账号，再去做成员绑定。"
              action={(
                <button
                  className="btn btn--primary"
                  onClick={openCreateModal}
                  disabled={availableChannelPlugins.length === 0}
                >
                  新增平台账号
                </button>
              )}
            />
          ) : (
            <>
              <div className="channel-account-list__header">
                <span>已配置 {accounts.length} 个平台账号</span>
                <button
                  className="btn btn--primary btn--sm"
                  onClick={openCreateModal}
                  disabled={availableChannelPlugins.length === 0}
                >
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
                const pluginDisabledReason = pluginState?.disabled_reason ?? '当前家庭已停用这个通道插件。';

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
                          {platform.name} / {account.connection_mode}
                          {pluginDisabled && <span className="channel-account-card__error"> / 插件已停用</span>}
                          {account.last_error_message && (
                            <span className="channel-account-card__error"> / {account.last_error_message}</span>
                          )}
                        </div>
                        {pluginDisabled && (
                          <div className="channel-account-card__times">{pluginDisabledReason}</div>
                        )}
                        <div className="channel-account-card__times">
                          最近入站：{formatTimestamp(account.last_inbound_at)} / 最近出站：{formatTimestamp(account.last_outbound_at)}
                        </div>
                      </div>
                      <div className="channel-account-card__actions">
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => openEditModal(account)}
                          disabled={loading || pluginDisabled}
                        >
                          编辑
                        </button>
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => void handleProbeAccount(account.id)}
                          disabled={loading || pluginDisabled}
                        >
                          立即探测
                        </button>
                        <button
                          className="btn btn--outline btn--sm"
                          onClick={() => void handleToggleAccountStatus(account)}
                          disabled={loading || pluginDisabled}
                        >
                          {account.status === 'disabled' ? '启用' : '停用'}
                        </button>
                        <button className="btn btn--outline btn--sm" onClick={() => toggleAccountExpand(account.id)}>
                          {isExpanded ? '收起详情' : '展开详情'}
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="channel-account-card__detail">
                        {detailLoading ? (
                          <div className="text-text-secondary">加载详情中...</div>
                        ) : (
                          <>
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
                                    <span className="channel-detail-stat__value">{accountStatus.recent_delivery_count}</span>
                                    <span className="channel-detail-stat__label">最近出站数</span>
                                  </div>
                                  <div className="channel-detail-stat">
                                    <span className="channel-detail-stat__value">{accountStatus.recent_inbound_count}</span>
                                    <span className="channel-detail-stat__label">最近入站数</span>
                                  </div>
                                </div>
                                {accountStatus.recent_failure_summary.last_error_message && (
                                  <div className="channel-detail-error">
                                    <strong>最近错误：</strong>
                                    {accountStatus.recent_failure_summary.last_error_message}
                                    <span className="channel-detail-error__time">
                                      （{formatTimestamp(accountStatus.recent_failure_summary.last_failed_at)}）
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}

                            <div className="channel-detail-section">
                              <h4>成员绑定</h4>
                              <ChannelAccountBindingsPanel
                                householdId={currentHouseholdId ?? ''}
                                accountId={account.id}
                                members={activeMembers}
                                plugin={pluginState}
                                supportsMemberBinding={supportsMemberBinding(pluginState)}
                              />
                            </div>

                            {(failedDeliveries.length > 0 || failedInboundEvents.length > 0) && (
                              <div className="channel-detail-section">
                                <h4>最近失败记录</h4>
                                {failedDeliveries.length > 0 && (
                                  <div className="channel-failure-list">
                                    <h5>出站失败（最近 5 条）</h5>
                                    {failedDeliveries.map(delivery => (
                                      <div key={delivery.id} className="channel-failure-item">
                                        <span className="channel-failure-item__type">{delivery.delivery_type}</span>
                                        <span className="channel-failure-item__error">
                                          {delivery.last_error_message ?? '未知错误'}
                                        </span>
                                        <span className="channel-failure-item__time">{formatTimestamp(delivery.created_at)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {failedInboundEvents.length > 0 && (
                                  <div className="channel-failure-list">
                                    <h5>入站失败（最近 5 条）</h5>
                                    {failedInboundEvents.map(inboundEvent => (
                                      <div key={inboundEvent.id} className="channel-failure-item">
                                        <span className="channel-failure-item__type">{inboundEvent.event_type}</span>
                                        <span className="channel-failure-item__error">
                                          {inboundEvent.error_message ?? '未知错误'}
                                        </span>
                                        <span className="channel-failure-item__time">
                                          {formatTimestamp(inboundEvent.received_at)}
                                        </span>
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

      {accountModalOpen && (
        <div className="member-modal-overlay" onClick={() => setAccountModalOpen(false)}>
          <div className="member-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <h3>{editingAccount ? '编辑平台账号' : '新增平台账号'}</h3>
              <p>账号配置字段直接来自对应 channel 插件声明，宿主这里只做通用渲染。</p>
            </div>
            <form className="settings-form" onSubmit={handleSaveAccount}>
              <div className="form-group">
                <label>平台类型</label>
                <select
                  className="form-select"
                  value={accountForm.plugin_id}
                  onChange={event => setAccountForm(form => ({ ...form, plugin_id: event.target.value }))}
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
                  <div className="form-help">这里只展示当前家庭仍然启用的通讯通道插件。</div>
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
                  onChange={event => setAccountForm(form => ({ ...form, account_code: event.target.value }))}
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
                  onChange={event => setAccountForm(form => ({ ...form, display_name: event.target.value }))}
                  placeholder="我的 Telegram 机器人"
                  required
                />
              </div>

              <div className="form-group">
                <label>连接方式</label>
                <select
                  className="form-select"
                  value={accountForm.connection_mode}
                  onChange={event => setAccountForm(form => ({
                    ...form,
                    connection_mode: event.target.value as typeof accountForm.connection_mode,
                  }))}
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
                  onChange={event => setAccountForm(form => ({
                    ...form,
                    status: event.target.value as typeof accountForm.status,
                  }))}
                >
                  <option value="draft">草稿</option>
                  <option value="active">启用</option>
                  <option value="disabled">停用</option>
                </select>
                <div className="form-help">建议先保存成草稿，确认配置无误后再启用。</div>
              </div>

              {configForm && (
                <div className="form-group channel-config-section">
                  <label>平台配置</label>
                  {configFormLoading ? (
                    <div className="form-help">正在加载平台配置...</div>
                  ) : (
                    <>
                      <DynamicPluginConfigForm
                        configSpec={configForm.config_spec}
                        view={configForm.view}
                        showActions={false}
                        onDraftChange={setConfigDraft}
                        formError={configFormError}
                      />
                      <div className="form-help">这里的字段直接来自插件配置协议，页面自己不再维护一份字段常量。</div>
                    </>
                  )}
                </div>
              )}

              {!configForm && !!currentModalPlugin && (
                <div className="form-group">
                  <label>平台配置</label>
                  <div className="form-help">
                    当前插件没有声明账号级配置协议，页面不会再猜字段。
                  </div>
                </div>
              )}

              <div className="member-modal__actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => setAccountModalOpen(false)}
                  disabled={modalLoading}
                >
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
