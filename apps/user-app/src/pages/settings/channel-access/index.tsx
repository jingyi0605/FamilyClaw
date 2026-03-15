import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import { useDidShow } from '@tarojs/taro';
import {
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginRegistryItem,
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

type PlatformInfo = {
  code: string;
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

const CONNECTION_MODE_OPTIONS: Array<{ value: ChannelAccountRead['connection_mode']; label: string }> = [
  { value: 'webhook', label: 'Webhook' },
  { value: 'polling', label: 'Polling' },
  { value: 'websocket', label: 'WebSocket' },
];

const ACCOUNT_STATUS_OPTIONS: Array<{ value: ChannelAccountRead['status']; label: string }> = [
  { value: 'draft', label: '草稿' },
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
];

const BINDING_STATUS_OPTIONS: Array<{ value: MemberChannelBindingRead['binding_status']; label: string }> = [
  { value: 'active', label: '生效' },
  { value: 'disabled', label: '停用' },
];

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', name: 'Telegram', icon: '📱' },
  { code: 'discord', name: 'Discord', icon: '💬' },
  { code: 'feishu', name: '飞书', icon: '🐦' },
  { code: 'dingtalk', name: '钉钉', icon: '📌' },
  { code: 'wecom_app', name: '企业微信应用', icon: '🏢' },
  { code: 'wecom_bot', name: '企业微信群机器人', icon: '🤖' },
] as const;

const PLATFORM_CONFIG_FIELDS: Record<string, ConfigFieldDef[]> = {
  telegram: [
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: true, placeholder: '123456:ABC-DEF1234', helpText: '从 @BotFather 获取。' },
    { key: 'webhook_secret', label: 'Webhook Secret', type: 'password', required: false, placeholder: '可选安全密钥' },
  ],
  discord: [
    { key: 'application_public_key', label: 'Application Public Key', type: 'text', required: true, placeholder: 'abc123def456' },
    { key: 'bot_token', label: 'Bot Token', type: 'password', required: false, placeholder: '可选，主动发消息时使用' },
  ],
  feishu: [
    { key: 'app_id', label: 'App ID', type: 'text', required: true, placeholder: 'cli_xxx' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: true, placeholder: '应用密钥' },
  ],
  dingtalk: [
    { key: 'app_key', label: 'App Key', type: 'text', required: true, placeholder: 'dingxxx' },
    { key: 'app_secret', label: 'App Secret', type: 'password', required: false, placeholder: '可选 API 凭证' },
  ],
  wecom_app: [
    { key: 'corp_id', label: '企业 ID', type: 'text', required: true, placeholder: 'ww1234567890abcdef' },
    { key: 'corp_secret', label: '应用 Secret', type: 'password', required: true, placeholder: '应用凭证密钥' },
    { key: 'agent_id', label: 'Agent ID', type: 'text', required: true, placeholder: '1000001' },
  ],
  wecom_bot: [
    { key: 'webhook_url', label: 'Webhook URL', type: 'text', required: false, placeholder: 'https://qyapi.weixin.qq.com/...' },
    { key: 'key', label: '机器人 Key', type: 'password', required: false, placeholder: '群机器人的 key 参数' },
  ],
};

type AccountForm = {
  pluginId: string;
  accountCode: string;
  displayName: string;
  connectionMode: ChannelAccountRead['connection_mode'];
  status: ChannelAccountRead['status'];
  config: Record<string, unknown>;
};

type BindingForm = {
  memberId: string;
  externalUserId: string;
  externalChatId: string;
  displayHint: string;
  bindingStatus: MemberChannelBindingRead['binding_status'];
};

function buildAccountForm(): AccountForm {
  return {
    pluginId: '',
    accountCode: '',
    displayName: '',
    connectionMode: 'webhook',
    status: 'draft',
    config: {},
  };
}

function buildBindingForm(): BindingForm {
  return {
    memberId: '',
    externalUserId: '',
    externalChatId: '',
    displayHint: '',
    bindingStatus: 'active',
  };
}

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find(item => item.code === platformCode) ?? { code: platformCode, name: platformCode, icon: '🔌' };
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

export default function SettingsChannelAccessPage() {
  const { bootstrap, refresh } = useAppRuntime();
  const [accounts, setAccounts] = useState<ChannelAccountRead[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [channelPlugins, setChannelPlugins] = useState<PluginRegistryItem[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [editingAccountId, setEditingAccountId] = useState('');
  const [accountForm, setAccountForm] = useState<AccountForm>(buildAccountForm());
  const [accountStatus, setAccountStatus] = useState<ChannelAccountStatusRead | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<ChannelDeliveryRead[]>([]);
  const [failedInboundEvents, setFailedInboundEvents] = useState<ChannelInboundEventRead[]>([]);
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [editingBindingId, setEditingBindingId] = useState('');
  const [bindingForm, setBindingForm] = useState<BindingForm>(buildBindingForm());
  const [pageLoading, setPageLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [busyKey, setBusyKey] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const activeHouseholdIdRef = useRef('');
  const loadRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const bindingRequestIdRef = useRef(0);

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';
  const selectedAccount = useMemo(() => accounts.find(item => item.id === selectedAccountId) ?? null, [accounts, selectedAccountId]);
  const activeMembers = useMemo(() => members.filter(item => item.status === 'active'), [members]);
  const availableChannelPlugins = useMemo(
    () => channelPlugins.filter(plugin => plugin.enabled && plugin.types.includes('channel')),
    [channelPlugins],
  );
  const currentPlatformCode = useMemo(() => {
    if (editingAccountId && selectedAccount) {
      return selectedAccount.platform_code;
    }
    return availableChannelPlugins.find(plugin => plugin.id === accountForm.pluginId)?.capabilities.channel?.platform_code ?? '';
  }, [accountForm.pluginId, availableChannelPlugins, editingAccountId, selectedAccount]);

  const loadWorkspace = useCallback(async () => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      activeHouseholdIdRef.current = householdId;
      setAccounts([]);
      setMembers([]);
      setChannelPlugins([]);
      setSelectedAccountId('');
      setEditingAccountId('');
      setAccountForm(buildAccountForm());
      setAccountStatus(null);
      setFailedDeliveries([]);
      setFailedInboundEvents([]);
      setBindings([]);
      setEditingBindingId('');
      setBindingForm(buildBindingForm());
      setStatus('');
      setError('');
    }

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    try {
      const [pluginRegistry, accountRows, memberRows] = await Promise.all([
        coreApiClient.listRegisteredPlugins(householdId),
        coreApiClient.listChannelAccounts(householdId),
        coreApiClient.listMembers(householdId),
      ]);

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      setChannelPlugins(pluginRegistry.items.filter(plugin => plugin.types.includes('channel')));
      setAccounts(accountRows);
      setMembers(memberRows.items);
      setSelectedAccountId(current => {
        if (current && accountRows.some(item => item.id === current)) {
          return current;
        }
        return accountRows[0]?.id ?? '';
      });

      if (editingAccountId && !accountRows.some(item => item.id === editingAccountId)) {
        setEditingAccountId('');
        setAccountForm(buildAccountForm());
      }
    } catch (loadError) {
      if (requestId === loadRequestIdRef.current) {
        setError(loadError instanceof Error ? loadError.message : '通讯平台接入页加载失败');
      }
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [currentHouseholdId, editingAccountId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useDidShow(() => {
    if (currentHouseholdId) {
      void loadWorkspace();
    }
  });

  useEffect(() => {
    if (!currentHouseholdId || !selectedAccountId) {
      setAccountStatus(null);
      setFailedDeliveries([]);
      setFailedInboundEvents([]);
      setBindings([]);
      return;
    }

    const requestId = ++detailRequestIdRef.current;
    setDetailLoading(true);
    setError('');

    void Promise.all([
      coreApiClient.getChannelAccountStatus(currentHouseholdId, selectedAccountId),
      coreApiClient.listChannelDeliveries(currentHouseholdId, { channel_account_id: selectedAccountId, status: 'failed' }),
      coreApiClient.listChannelInboundEvents(currentHouseholdId, { channel_account_id: selectedAccountId, status: 'failed' }),
    ])
      .then(([statusResult, deliveryRows, inboundRows]) => {
        if (requestId !== detailRequestIdRef.current) {
          return;
        }
        setAccountStatus(statusResult);
        setFailedDeliveries(deliveryRows.slice(0, 5));
        setFailedInboundEvents(inboundRows.slice(0, 5));
      })
      .catch(loadError => {
        if (requestId === detailRequestIdRef.current) {
          setError(loadError instanceof Error ? loadError.message : '读取平台账号详情失败');
        }
      })
      .finally(() => {
        if (requestId === detailRequestIdRef.current) {
          setDetailLoading(false);
        }
      });
  }, [currentHouseholdId, selectedAccountId]);

  useEffect(() => {
    if (!currentHouseholdId || !selectedAccountId) {
      setBindings([]);
      return;
    }

    const requestId = ++bindingRequestIdRef.current;
    setBindingsLoading(true);

    void coreApiClient.listChannelAccountBindings(currentHouseholdId, selectedAccountId)
      .then(result => {
        if (requestId !== bindingRequestIdRef.current) {
          return;
        }
        setBindings(result);
      })
      .catch(loadError => {
        if (requestId === bindingRequestIdRef.current) {
          setError(loadError instanceof Error ? loadError.message : '读取成员绑定失败');
        }
      })
      .finally(() => {
        if (requestId === bindingRequestIdRef.current) {
          setBindingsLoading(false);
        }
      });
  }, [currentHouseholdId, selectedAccountId]);

  useEffect(() => {
    setEditingBindingId('');
    setBindingForm(buildBindingForm());
  }, [selectedAccountId]);

  async function reloadWorkspace(successMessage?: string) {
    await Promise.all([
      loadWorkspace(),
      refresh(),
    ]);
    if (successMessage) {
      setStatus(successMessage);
    }
  }

  function startEditAccount(account: ChannelAccountRead) {
    setEditingAccountId(account.id);
    setSelectedAccountId(account.id);
    setAccountForm({
      pluginId: account.plugin_id,
      accountCode: account.account_code,
      displayName: account.display_name,
      connectionMode: account.connection_mode,
      status: account.status,
      config: account.config,
    });
    setStatus('');
    setError('');
  }

  async function handleSaveAccount() {
    if (!currentHouseholdId) {
      setError('当前没有可用的家庭上下文');
      return;
    }

    if (!accountForm.pluginId || !accountForm.accountCode.trim() || !accountForm.displayName.trim()) {
      setError('平台插件、账号代码和显示名称都必须填写');
      return;
    }

    setBusyKey('account-save');
    setStatus('');
    setError('');

    try {
      if (editingAccountId) {
        const payload: ChannelAccountUpdate = {
          display_name: accountForm.displayName.trim(),
          connection_mode: accountForm.connectionMode,
          config: accountForm.config,
          status: accountForm.status,
        };
        await coreApiClient.updateChannelAccount(currentHouseholdId, editingAccountId, payload);
        await reloadWorkspace('平台账号已更新。');
      } else {
        const payload: ChannelAccountCreate = {
          plugin_id: accountForm.pluginId,
          account_code: accountForm.accountCode.trim(),
          display_name: accountForm.displayName.trim(),
          connection_mode: accountForm.connectionMode,
          config: accountForm.config,
          status: accountForm.status,
        };
        await coreApiClient.createChannelAccount(currentHouseholdId, payload);
        await reloadWorkspace('平台账号已创建。');
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存平台账号失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleProbeAccount(accountId: string) {
    if (!currentHouseholdId) {
      return;
    }

    setBusyKey(`probe-${accountId}`);
    setStatus('');
    setError('');

    try {
      await coreApiClient.probeChannelAccount(currentHouseholdId, accountId);
      await reloadWorkspace('平台账号探测已完成。');
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : '探测平台账号失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleToggleAccount(account: ChannelAccountRead) {
    if (!currentHouseholdId) {
      return;
    }

    setBusyKey(`toggle-${account.id}`);
    setStatus('');
    setError('');

    try {
      await coreApiClient.updateChannelAccount(currentHouseholdId, account.id, {
        status: account.status === 'disabled' ? 'active' : 'disabled',
      });
      await reloadWorkspace(account.status === 'disabled' ? '平台账号已启用。' : '平台账号已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '切换平台账号状态失败');
    } finally {
      setBusyKey('');
    }
  }

  function startEditBinding(binding: MemberChannelBindingRead) {
    setEditingBindingId(binding.id);
    setBindingForm({
      memberId: binding.member_id,
      externalUserId: binding.external_user_id,
      externalChatId: binding.external_chat_id ?? '',
      displayHint: binding.display_hint ?? '',
      bindingStatus: binding.binding_status,
    });
    setStatus('');
    setError('');
  }

  async function handleSaveBinding() {
    if (!currentHouseholdId || !selectedAccountId) {
      return;
    }

    if (!bindingForm.memberId || !bindingForm.externalUserId.trim()) {
      setError('成员和外部用户 ID 都必须填写');
      return;
    }

    setBusyKey('binding-save');
    setStatus('');
    setError('');

    try {
      if (editingBindingId) {
        const payload: MemberChannelBindingUpdate = {
          external_user_id: bindingForm.externalUserId.trim(),
          external_chat_id: bindingForm.externalChatId.trim() || null,
          display_hint: bindingForm.displayHint.trim() || null,
          binding_status: bindingForm.bindingStatus,
        };
        await coreApiClient.updateChannelAccountBinding(currentHouseholdId, selectedAccountId, editingBindingId, payload);
        setEditingBindingId('');
        setBindingForm(buildBindingForm());
        await reloadWorkspace('成员绑定已更新。');
      } else {
        const payload: MemberChannelBindingCreate = {
          channel_account_id: selectedAccountId,
          member_id: bindingForm.memberId,
          external_user_id: bindingForm.externalUserId.trim(),
          external_chat_id: bindingForm.externalChatId.trim() || null,
          display_hint: bindingForm.displayHint.trim() || null,
          binding_status: bindingForm.bindingStatus,
        };
        await coreApiClient.createChannelAccountBinding(currentHouseholdId, selectedAccountId, payload);
        setBindingForm(buildBindingForm());
        await reloadWorkspace('成员绑定已创建。');
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存成员绑定失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleToggleBinding(binding: MemberChannelBindingRead) {
    if (!currentHouseholdId || !selectedAccountId) {
      return;
    }

    setBusyKey(`binding-toggle-${binding.id}`);
    setStatus('');
    setError('');

    try {
      await coreApiClient.updateChannelAccountBinding(currentHouseholdId, selectedAccountId, binding.id, {
        binding_status: binding.binding_status === 'disabled' ? 'active' : 'disabled',
      });
      await reloadWorkspace(binding.binding_status === 'disabled' ? '成员绑定已恢复。' : '成员绑定已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '切换成员绑定状态失败');
    } finally {
      setBusyKey('');
    }
  }

  return (
    <MainShellPage
      currentNav="settings"
      title="通讯平台接入已经进入 user-app"
      description="平台账号、探测、失败记录和成员绑定都在这里，H5 不再缺这块硬功能。"
    >
      <PageSection title="通讯接入总览" description="先看当前家庭到底接了多少平台账号。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="平台账号" value={`${accounts.length}`} tone={accounts.length > 0 ? 'success' : 'warning'} />
        <StatusCard label="可用通道插件" value={`${channelPlugins.length}`} tone={channelPlugins.length > 0 ? 'info' : 'warning'} />
        <StatusCard label="成员数量" value={`${members.length}`} tone="success" />
        {pageLoading ? <SectionNote>正在读取平台账号与成员绑定...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
      </PageSection>

      <PageSection title="平台账号列表" description="平台账号是正式设置能力，不是临时脚手架。新增、编辑、探测和启停都在这里做。">
        {accounts.length === 0 ? (
          <EmptyStateCard title="当前还没有平台账号" description="先在下面创建一个平台账号，才能继续做探测、失败记录和成员绑定。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {accounts.map(account => {
              const active = account.id === selectedAccountId;
              const platform = getPlatformInfo(account.platform_code);
              return (
                <View
                  key={account.id}
                  onClick={() => setSelectedAccountId(account.id)}
                  style={{
                    background: active ? '#eef5ff' : '#ffffff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '28px', fontWeight: '600' }}>
                    {platform.icon} {account.display_name}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                    {platform.name} · {account.connection_mode} · 最近探测 {account.last_probe_status ?? '未探测'}
                  </Text>
                  <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px', marginTop: '6px' }}>
                    最近入站：{formatRelativeTime(account.last_inbound_at)} · 最近出站：{formatRelativeTime(account.last_outbound_at)}
                  </Text>
                  {account.last_error_message ? (
                    <SectionNote tone="warning">{account.last_error_message}</SectionNote>
                  ) : null}
                  <ActionRow>
                    <SecondaryButton onClick={() => startEditAccount(account)}>
                      编辑账号
                    </SecondaryButton>
                    <SecondaryButton disabled={busyKey === `probe-${account.id}`} onClick={() => void handleProbeAccount(account.id)}>
                      {busyKey === `probe-${account.id}` ? '探测中...' : '立即探测'}
                    </SecondaryButton>
                    <SecondaryButton disabled={busyKey === `toggle-${account.id}`} onClick={() => void handleToggleAccount(account)}>
                      {busyKey === `toggle-${account.id}` ? '处理中...' : account.status === 'disabled' ? '启用账号' : '停用账号'}
                    </SecondaryButton>
                  </ActionRow>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="平台账号表单" description="这里只填当前后端已经支持的平台字段，不发明不存在的配置。">
        <ActionRow>
          <PrimaryButton onClick={() => { setEditingAccountId(''); setAccountForm(buildAccountForm()); }}>
            新增平台账号
          </PrimaryButton>
          <SecondaryButton onClick={() => void loadWorkspace()}>
            重新读取平台账号
          </SecondaryButton>
        </ActionRow>
        <FormField label="通道插件">
          {availableChannelPlugins.length === 0 ? (
            <SectionNote tone="warning">当前没有已启用的通讯通道插件，请先去插件页启用对应插件。</SectionNote>
          ) : (
            <OptionPills
              value={accountForm.pluginId}
              disabled={Boolean(editingAccountId)}
              options={availableChannelPlugins.map(plugin => ({ value: plugin.id, label: plugin.name }))}
              onChange={value => setAccountForm(current => ({ ...current, pluginId: value }))}
            />
          )}
        </FormField>
        <FormField label="账号代码" hint="家庭内唯一标识。创建后不建议随便改。">
          <TextInput value={accountForm.accountCode} disabled={Boolean(editingAccountId)} onInput={value => setAccountForm(current => ({ ...current, accountCode: value }))} />
        </FormField>
        <FormField label="显示名称">
          <TextInput value={accountForm.displayName} onInput={value => setAccountForm(current => ({ ...current, displayName: value }))} />
        </FormField>
        <FormField label="连接方式">
          <OptionPills value={accountForm.connectionMode} options={CONNECTION_MODE_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setAccountForm(current => ({ ...current, connectionMode: value }))} />
        </FormField>
        <FormField label="账号状态">
          <OptionPills value={accountForm.status} options={ACCOUNT_STATUS_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setAccountForm(current => ({ ...current, status: value }))} />
        </FormField>
        {(PLATFORM_CONFIG_FIELDS[currentPlatformCode] ?? []).map(field => (
          <FormField key={field.key} label={field.required ? `${field.label} *` : field.label} hint={field.helpText}>
            <TextInput
              value={String(accountForm.config[field.key] ?? '')}
              password={field.type === 'password'}
              placeholder={field.placeholder}
              onInput={value => setAccountForm(current => ({
                ...current,
                config: { ...current.config, [field.key]: value },
              }))}
            />
          </FormField>
        ))}
        <ActionRow>
          <PrimaryButton disabled={busyKey === 'account-save'} onClick={() => void handleSaveAccount()}>
            {busyKey === 'account-save' ? '保存中...' : editingAccountId ? '保存平台账号' : '创建平台账号'}
          </PrimaryButton>
          <SecondaryButton onClick={() => { setEditingAccountId(''); setAccountForm(buildAccountForm()); }}>
            重置账号表单
          </SecondaryButton>
        </ActionRow>
      </PageSection>

      <PageSection title="账号详情与失败记录" description="状态探测和失败记录必须可见，不然所谓接入就是黑盒。">
        {!selectedAccount ? (
          <EmptyStateCard title="还没选中平台账号" description="先从上面的列表选一个账号，这里才能看到状态探测和失败记录。" />
        ) : detailLoading ? (
          <EmptyStateCard title="正在读取账号详情" description="共享通道 API 正在返回最近状态和失败记录。" />
        ) : (
          <>
            <StatusCard label="当前账号" value={selectedAccount.display_name} tone="info" />
            <StatusCard label="最近失败数" value={`${accountStatus?.recent_failure_summary.recent_failure_count ?? 0}`} tone={accountStatus?.recent_failure_summary.recent_failure_count ? 'warning' : 'success'} />
            <StatusCard label="最近出站数" value={`${accountStatus?.recent_delivery_count ?? 0}`} tone="info" />
            <StatusCard label="最近入站数" value={`${accountStatus?.recent_inbound_count ?? 0}`} tone="info" />
            {accountStatus?.recent_failure_summary.last_error_message ? (
              <SectionNote tone="warning">
                最近错误：{accountStatus.recent_failure_summary.last_error_message}（{formatRelativeTime(accountStatus.recent_failure_summary.last_failed_at)}）
              </SectionNote>
            ) : (
              <SectionNote tone="success">当前没有新的失败摘要。</SectionNote>
            )}
            {failedDeliveries.length > 0 ? (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <Text style={{ color: userAppTokens.colorText, fontSize: '24px', fontWeight: '600' }}>最近出站失败</Text>
                {failedDeliveries.map(item => (
                  <View key={item.id} style={{ background: '#fff8ec', border: `1px solid ${userAppTokens.colorWarning}`, borderRadius: userAppTokens.radiusLg, padding: userAppTokens.spacingSm }}>
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px' }}>{item.delivery_type}</Text>
                    <Text style={{ color: userAppTokens.colorWarning, display: 'block', fontSize: '20px', marginTop: '4px' }}>{item.last_error_message ?? '未知错误'}</Text>
                    <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '18px', marginTop: '4px' }}>{formatRelativeTime(item.created_at)}</Text>
                  </View>
                ))}
              </View>
            ) : null}
            {failedInboundEvents.length > 0 ? (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
                <Text style={{ color: userAppTokens.colorText, fontSize: '24px', fontWeight: '600' }}>最近入站失败</Text>
                {failedInboundEvents.map(item => (
                  <View key={item.id} style={{ background: '#fff8ec', border: `1px solid ${userAppTokens.colorWarning}`, borderRadius: userAppTokens.radiusLg, padding: userAppTokens.spacingSm }}>
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '22px' }}>{item.event_type}</Text>
                    <Text style={{ color: userAppTokens.colorWarning, display: 'block', fontSize: '20px', marginTop: '4px' }}>{item.error_message ?? '未知错误'}</Text>
                    <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '18px', marginTop: '4px' }}>{formatRelativeTime(item.received_at)}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </>
        )}
      </PageSection>

      <PageSection title="成员绑定" description="平台用户 ID 到家庭成员的绑定必须在当前家庭上下文下保持一致。">
        {!selectedAccount ? (
          <EmptyStateCard title="当前没有可绑定的账号" description="先选中一个平台账号，再做成员绑定。" />
        ) : (
          <>
            <FormField label="家庭成员">
              {activeMembers.length === 0 ? (
                <SectionNote tone="warning">当前家庭没有活跃成员，没法创建绑定。</SectionNote>
              ) : (
                <OptionPills value={bindingForm.memberId} disabled={Boolean(editingBindingId)} options={activeMembers.map(member => ({ value: member.id, label: member.name }))} onChange={value => setBindingForm(current => ({ ...current, memberId: value }))} />
              )}
            </FormField>
            <FormField label="外部用户 ID">
              <TextInput value={bindingForm.externalUserId} onInput={value => setBindingForm(current => ({ ...current, externalUserId: value }))} />
            </FormField>
            <FormField label="外部会话 ID">
              <TextInput value={bindingForm.externalChatId} onInput={value => setBindingForm(current => ({ ...current, externalChatId: value }))} />
            </FormField>
            <FormField label="备注">
              <TextInput value={bindingForm.displayHint} onInput={value => setBindingForm(current => ({ ...current, displayHint: value }))} />
            </FormField>
            <FormField label="绑定状态">
              <OptionPills value={bindingForm.bindingStatus} options={BINDING_STATUS_OPTIONS.map(option => ({ value: option.value, label: option.label }))} onChange={value => setBindingForm(current => ({ ...current, bindingStatus: value }))} />
            </FormField>
            <ActionRow>
              <PrimaryButton disabled={busyKey === 'binding-save'} onClick={() => void handleSaveBinding()}>
                {busyKey === 'binding-save' ? '保存中...' : editingBindingId ? '保存成员绑定' : '创建成员绑定'}
              </PrimaryButton>
              <SecondaryButton onClick={() => { setEditingBindingId(''); setBindingForm(buildBindingForm()); }}>
                重置绑定表单
              </SecondaryButton>
            </ActionRow>
            {bindingsLoading ? (
              <EmptyStateCard title="正在读取成员绑定" description="共享通道绑定 API 正在返回当前账号的成员绑定列表。" />
            ) : bindings.length === 0 ? (
              <EmptyStateCard title="当前还没有成员绑定" description="你可以直接用上面的表单创建第一条绑定。" />
            ) : (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                {bindings.map(binding => {
                  const member = members.find(item => item.id === binding.member_id);
                  return (
                    <View
                      key={binding.id}
                      style={{
                        background: '#ffffff',
                        border: `1px solid ${userAppTokens.colorBorder}`,
                        borderRadius: userAppTokens.radiusLg,
                        padding: userAppTokens.spacingMd,
                      }}
                    >
                      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', fontWeight: '600' }}>
                        {member?.name ?? binding.member_id}
                      </Text>
                      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '4px' }}>
                        外部用户 ID：{binding.external_user_id}
                      </Text>
                      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '4px' }}>
                        外部会话：{binding.external_chat_id ?? '未填写'} · 状态：{binding.binding_status}
                      </Text>
                      {binding.display_hint ? <SectionNote>{binding.display_hint}</SectionNote> : null}
                      <ActionRow>
                        <SecondaryButton onClick={() => startEditBinding(binding)}>
                          编辑绑定
                        </SecondaryButton>
                        <SecondaryButton disabled={busyKey === `binding-toggle-${binding.id}`} onClick={() => void handleToggleBinding(binding)}>
                          {busyKey === `binding-toggle-${binding.id}` ? '处理中...' : binding.binding_status === 'disabled' ? '恢复绑定' : '停用绑定'}
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
    </MainShellPage>
  );
}
