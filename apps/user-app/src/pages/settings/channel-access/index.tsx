import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import { GuardedPage, useHouseholdContext, useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, EmptyState, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';
import { SettingsDialog, SettingsNotice } from '../components/SettingsSharedBlocks';
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

type MessageKey = Parameters<typeof getPageMessage>[1];
type PlatformInfo = { code: string; nameKey: MessageKey | null; icon: string };
type ConfigFieldDef = {
  key: string;
  label: string;
  type: 'text' | 'password';
  required: boolean;
  placeholder: string;
  helpText?: string;
};
type ConfigFieldMessageDef = {
  key: string;
  labelKey: MessageKey;
  type: 'text' | 'password';
  required: boolean;
  placeholderKey: MessageKey;
  helpTextKey?: MessageKey;
};
type AccountFormState = {
  plugin_id: string;
  display_name: string;
  connection_mode: ChannelConnectionMode;
  config: Record<string, unknown>;
  status: ChannelAccountStatus;
};

const PLATFORM_CONFIG_FIELDS: Record<string, ConfigFieldMessageDef[]> = {
  discord: [
    {
      key: 'application_public_key',
      labelKey: 'settings.channelAccess.configField.discord.applicationPublicKey.label',
      type: 'text',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.discord.applicationPublicKey.placeholder',
      helpTextKey: 'settings.channelAccess.configField.discord.applicationPublicKey.help',
    },
    {
      key: 'bot_token',
      labelKey: 'settings.channelAccess.configField.discord.botToken.label',
      type: 'password',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.discord.botToken.placeholder',
      helpTextKey: 'settings.channelAccess.configField.discord.botToken.help',
    },
  ],
  feishu: [
    {
      key: 'app_id',
      labelKey: 'settings.channelAccess.configField.feishu.appId.label',
      type: 'text',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.feishu.appId.placeholder',
      helpTextKey: 'settings.channelAccess.configField.feishu.appId.help',
    },
    {
      key: 'app_secret',
      labelKey: 'settings.channelAccess.configField.feishu.appSecret.label',
      type: 'password',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.feishu.appSecret.placeholder',
      helpTextKey: 'settings.channelAccess.configField.feishu.appSecret.help',
    },
    {
      key: 'encrypt_key',
      labelKey: 'settings.channelAccess.configField.feishu.encryptKey.label',
      type: 'password',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.feishu.encryptKey.placeholder',
      helpTextKey: 'settings.channelAccess.configField.feishu.encryptKey.help',
    },
    {
      key: 'base_url',
      labelKey: 'settings.channelAccess.configField.feishu.baseUrl.label',
      type: 'text',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.feishu.baseUrl.placeholder',
      helpTextKey: 'settings.channelAccess.configField.feishu.baseUrl.help',
    },
  ],
  dingtalk: [
    {
      key: 'app_key',
      labelKey: 'settings.channelAccess.configField.dingtalk.appKey.label',
      type: 'text',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.dingtalk.appKey.placeholder',
      helpTextKey: 'settings.channelAccess.configField.dingtalk.appKey.help',
    },
    {
      key: 'app_secret',
      labelKey: 'settings.channelAccess.configField.dingtalk.appSecret.label',
      type: 'password',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.dingtalk.appSecret.placeholder',
      helpTextKey: 'settings.channelAccess.configField.dingtalk.appSecret.help',
    },
  ],
  wecom_app: [
    {
      key: 'corp_id',
      labelKey: 'settings.channelAccess.configField.wecomApp.corpId.label',
      type: 'text',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.wecomApp.corpId.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomApp.corpId.help',
    },
    {
      key: 'corp_secret',
      labelKey: 'settings.channelAccess.configField.wecomApp.corpSecret.label',
      type: 'password',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.wecomApp.corpSecret.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomApp.corpSecret.help',
    },
    {
      key: 'agent_id',
      labelKey: 'settings.channelAccess.configField.wecomApp.agentId.label',
      type: 'text',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.wecomApp.agentId.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomApp.agentId.help',
    },
    {
      key: 'callback_token',
      labelKey: 'settings.channelAccess.configField.wecomApp.callbackToken.label',
      type: 'password',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.wecomApp.callbackToken.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomApp.callbackToken.help',
    },
    {
      key: 'encoding_aes_key',
      labelKey: 'settings.channelAccess.configField.wecomApp.encodingAesKey.label',
      type: 'password',
      required: true,
      placeholderKey: 'settings.channelAccess.configField.wecomApp.encodingAesKey.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomApp.encodingAesKey.help',
    },
  ],
  wecom_bot: [
    {
      key: 'webhook_url',
      labelKey: 'settings.channelAccess.configField.wecomBot.webhookUrl.label',
      type: 'text',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.wecomBot.webhookUrl.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomBot.webhookUrl.help',
    },
    {
      key: 'key',
      labelKey: 'settings.channelAccess.configField.wecomBot.key.label',
      type: 'password',
      required: false,
      placeholderKey: 'settings.channelAccess.configField.wecomBot.key.placeholder',
      helpTextKey: 'settings.channelAccess.configField.wecomBot.key.help',
    },
  ],
};

const PLATFORMS: PlatformInfo[] = [
  { code: 'telegram', nameKey: 'settings.channelAccess.platform.telegram', icon: '✈️' },
  { code: 'discord', nameKey: 'settings.channelAccess.platform.discord', icon: '🎮' },
  { code: 'feishu', nameKey: 'settings.channelAccess.platform.feishu', icon: '🪶' },
  { code: 'dingtalk', nameKey: 'settings.channelAccess.platform.dingtalk', icon: '💬' },
  { code: 'wecom_app', nameKey: 'settings.channelAccess.platform.wecomApp', icon: '🏢' },
  { code: 'wecom_bot', nameKey: 'settings.channelAccess.platform.wecomBot', icon: '🤖' },
];

function buildInitialAccountForm(): AccountFormState {
  return { plugin_id: '', display_name: '', connection_mode: 'polling', config: {}, status: 'draft' };
}

function normalizeLocale(locale?: string) {
  return locale?.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
}

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find((item) => item.code === platformCode) ?? {
    code: platformCode,
    nameKey: null,
    icon: '🔌',
  };
}

function formatStatus(
  status: string,
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (status === 'active') return { label: getPageMessage(locale, 'settings.channelAccess.accountStatus.active'), tone: 'success' };
  if (status === 'draft') return { label: getPageMessage(locale, 'settings.channelAccess.accountStatus.draft'), tone: 'secondary' };
  if (status === 'degraded') return { label: getPageMessage(locale, 'settings.channelAccess.accountStatus.degraded'), tone: 'warning' };
  if (status === 'disabled') return { label: getPageMessage(locale, 'settings.channelAccess.accountStatus.disabled'), tone: 'secondary' };
  return { label: status, tone: 'secondary' };
}

function formatProbeStatus(
  status: string | null,
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'secondary' | 'danger' } {
  if (!status) return { label: getPageMessage(locale, 'settings.channelAccess.probeStatus.unchecked'), tone: 'secondary' };
  if (status === 'ok') return { label: getPageMessage(locale, 'settings.channelAccess.probeStatus.ok'), tone: 'success' };
  if (status === 'failed') return { label: getPageMessage(locale, 'settings.channelAccess.probeStatus.failed'), tone: 'danger' };
  if (status === 'pending') return { label: getPageMessage(locale, 'settings.channelAccess.probeStatus.pending'), tone: 'warning' };
  return { label: status, tone: 'secondary' };
}

function formatConnectionMode(mode: ChannelConnectionMode, locale: string | undefined) {
  if (mode === 'webhook') return getPageMessage(locale, 'settings.channelAccess.connectionMode.webhook');
  if (mode === 'polling') return getPageMessage(locale, 'settings.channelAccess.connectionMode.polling');
  if (mode === 'websocket') return getPageMessage(locale, 'settings.channelAccess.connectionMode.websocket');
  return mode;
}

function formatTimestamp(value: string | null, locale: string | undefined) {
  if (!value) return getPageMessage(locale, 'settings.channelAccess.time.empty');
  try {
    return new Date(value).toLocaleString(normalizeLocale(locale));
  } catch {
    return value;
  }
}

function formatApiErrorMessage(error: ApiError, locale: string | undefined): string {
  const payload = error.payload as { detail?: unknown } | undefined;
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const message = 'msg' in item && typeof item.msg === 'string' ? item.msg : null;
        const location = 'loc' in item && Array.isArray(item.loc)
          ? item.loc
            .filter((part: unknown): part is string | number => typeof part === 'string' || typeof part === 'number')
            .join('.')
          : '';
        if (message && location) return `${location}: ${message}`;
        return message;
      })
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) {
      return messages.join(getPageMessage(locale, 'settings.channelAccess.separator.errorList'));
    }
  }
  return error.message || getPageMessage(locale, 'settings.channelAccess.status.saveFailed');
}

function getConfigFields(
  plugin: PluginRegistryItem | null,
  platformCode: string | null,
  locale: string | undefined,
): ConfigFieldDef[] {
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

  const fallbackFields = platformCode ? (PLATFORM_CONFIG_FIELDS[platformCode] ?? []) : [];
  return fallbackFields.map((field) => ({
    key: field.key,
    label: getPageMessage(locale, field.labelKey),
    type: field.type,
    required: field.required,
    placeholder: getPageMessage(locale, field.placeholderKey),
    helpText: field.helpTextKey ? getPageMessage(locale, field.helpTextKey) : undefined,
  }));
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
  const { locale } = useI18n();
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

  const t = (key: MessageKey, params?: Record<string, string | number>) => getPageMessage(locale, key, params);
  const separator = t('settings.channelAccess.separator.dot');

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: t('settings.channelAccess.sectionTitle') }).catch(() => undefined);
  }, [locale]);

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
      if (!cancelled?.()) {
        setError(loadError instanceof Error ? loadError.message : t('settings.channelAccess.status.loadAccountsFailed'));
      }
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
      setError(loadError instanceof Error ? loadError.message : t('settings.channelAccess.status.loadDetailsFailed'));
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
    setAccountForm({
      plugin_id: account.plugin_id,
      display_name: account.display_name,
      connection_mode: account.connection_mode,
      config: account.config,
      status: account.status,
    });
    setAccountModalOpen(true);
  }

  async function handleRefreshAccounts() {
    setStatus('');
    const loaded = await loadAccounts();
    if (!loaded) return;
    if (expandedAccountId) await loadAccountDetail(expandedAccountId);
    setStatus(t('settings.channelAccess.status.refreshSuccess'));
  }

  async function handleSaveAccount(event: FormEvent<HTMLFormElement>) {
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
        setStatus(t('settings.channelAccess.status.updateSuccess'));
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
        setStatus(t('settings.channelAccess.status.createSuccess'));
      }
      setAccountModalOpen(false);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? formatApiErrorMessage(saveError, locale)
          : saveError instanceof Error
            ? saveError.message
            : t('settings.channelAccess.status.saveFailed'),
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
      if (expandedAccountId === accountId) setAccountStatus(result);
      setStatus(t('settings.channelAccess.status.probeSuccess'));
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : t('settings.channelAccess.status.probeFailed'));
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
      setStatus(
        nextStatus === 'active'
          ? t('settings.channelAccess.status.enableSuccess')
          : t('settings.channelAccess.status.disableSuccess'),
      );
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : t('settings.channelAccess.status.actionFailed'));
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteAccount(account: ChannelAccountRead) {
    if (!currentHouseholdId) return;
    const result = await Taro.showModal({
      title: t('settings.channelAccess.modal.deleteTitle'),
      content: t('settings.channelAccess.modal.deleteContent', { name: account.display_name }),
      confirmText: t('settings.channelAccess.modal.deleteConfirm'),
      cancelText: t('settings.channelAccess.actions.cancel'),
    });
    if (!result.confirm) return;
    setLoading(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.deleteChannelAccount(currentHouseholdId, account.id);
      setAccounts((current) => current.filter((item) => item.id !== account.id));
      if (expandedAccountId === account.id) resetExpandedState();
      setStatus(t('settings.channelAccess.status.deleteSuccess'));
    } catch (deleteError) {
      setError(
        deleteError instanceof ApiError
          ? formatApiErrorMessage(deleteError, locale)
          : deleteError instanceof Error
            ? deleteError.message
            : t('settings.channelAccess.status.deleteFailed'),
      );
    } finally {
      setLoading(false);
    }
  }

  const selectedPlugin = editingAccount?.plugin_id
    ? channelPluginMap.get(editingAccount.plugin_id) ?? null
    : accountForm.plugin_id
      ? channelPluginMap.get(accountForm.plugin_id) ?? null
      : null;
  const selectedPlatformCode = editingAccount?.platform_code
    ?? availableChannelPlugins.find((plugin) => plugin.pluginId === accountForm.plugin_id)?.platformCode
    ?? null;
  const configFields = useMemo(
    () => getConfigFields(selectedPlugin, selectedPlatformCode, locale),
    [selectedPlugin, selectedPlatformCode, locale],
  );
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
      <button className="btn btn--outline btn--sm" onClick={() => void handleRefreshAccounts()} disabled={loading}>
        {t('settings.channelAccess.actions.refresh')}
      </button>
      <button
        className="btn btn--primary btn--sm"
        onClick={openCreateModal}
        disabled={availableChannelPlugins.length === 0 || loading}
      >
        {t('settings.channelAccess.actions.addAccount')}
      </button>
    </div>
  );

  return (
    <SettingsPageShell activeKey="channel-access">
      <div className="settings-page">
        <Section title={t('settings.channelAccess.sectionTitle')}>
          <Card className="channel-access-notice">
            <div className="channel-access-notice__content">
              <h3>{t('settings.channelAccess.notice.title')}</h3>
              <p>{t('settings.channelAccess.notice.description')}</p>
            </div>
          </Card>
          {error ? <SettingsNotice tone="error" icon="⚠️">{error}</SettingsNotice> : null}
          {status ? <SettingsNotice tone="success" icon="✓">{status}</SettingsNotice> : null}
          <div className="channel-account-list">
            {loading && accounts.length === 0 ? <div className="text-text-secondary">{t('settings.channelAccess.list.loading')}</div> : null}
            {!loading && accounts.length === 0 ? (
              <EmptyState
                icon="🔌"
                title={t('settings.channelAccess.list.emptyTitle')}
                description={t('settings.channelAccess.list.emptyDescription')}
                action={headerActions}
              />
            ) : null}
            {accounts.length > 0 ? (
              <>
                <div className="channel-account-list__header">
                  <span>{t('settings.channelAccess.list.configuredCount', { count: accounts.length })}</span>
                  {headerActions}
                </div>
                {accounts.map((account) => {
                  const platform = getPlatformInfo(account.platform_code);
                  const platformName = platform.nameKey ? t(platform.nameKey) : account.platform_code;
                  const statusInfo = formatStatus(account.status, locale);
                  const probeInfo = formatProbeStatus(account.last_probe_status, locale);
                  const isExpanded = expandedAccountId === account.id;
                  const pluginState = getAccountPluginState(account);
                  const pluginDisabled = isAccountPluginDisabled(account);
                  const pluginDisabledReason = pluginState?.disabled_reason ?? t('settings.channelAccess.status.pluginDisabledFallback');
                  const supportsMemberBinding = pluginState?.capabilities.channel?.supports_member_binding !== false;
                  const accountMessageClassName = account.last_probe_status === 'ok'
                    ? 'channel-account-card__success'
                    : 'channel-account-card__error';

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
                            <span>{platformName}</span>
                            <span>{separator}</span>
                            <span>{formatConnectionMode(account.connection_mode, locale)}</span>
                            {pluginDisabled ? (
                              <>
                                <span>{separator}</span>
                                <span className="channel-account-card__error">{t('settings.channelAccess.card.pluginDisabled')}</span>
                              </>
                            ) : null}
                            {account.last_error_message ? (
                              <>
                                <span>{separator}</span>
                                <span className={accountMessageClassName}>{account.last_error_message}</span>
                              </>
                            ) : null}
                          </div>
                          {pluginDisabled ? <div className="channel-account-card__times">{pluginDisabledReason}</div> : null}
                          <div className="channel-account-card__times">
                            <span>{t('settings.channelAccess.card.recentReceived', { time: formatTimestamp(account.last_inbound_at, locale) })}</span>
                            <span>{separator}</span>
                            <span>{t('settings.channelAccess.card.recentSent', { time: formatTimestamp(account.last_outbound_at, locale) })}</span>
                          </div>
                        </div>
                        <div className="channel-account-card__actions">
                          <button
                            className="btn btn--outline btn--sm"
                            onClick={() => openEditModal(account)}
                            disabled={loading || pluginDisabled}
                          >
                            {t('settings.channelAccess.actions.edit')}
                          </button>
                          <button
                            className="btn btn--outline btn--sm"
                            onClick={() => void handleProbeAccount(account.id)}
                            disabled={loading || pluginDisabled}
                          >
                            {t('settings.channelAccess.actions.checkConnection')}
                          </button>
                          <button
                            className="btn btn--outline btn--sm"
                            onClick={() => void handleToggleAccountStatus(account)}
                            disabled={loading || pluginDisabled}
                          >
                            {account.status === 'disabled'
                              ? t('settings.channelAccess.actions.enable')
                              : t('settings.channelAccess.actions.disable')}
                          </button>
                          <button
                            className="btn btn--outline btn--sm"
                            onClick={() => void handleDeleteAccount(account)}
                            disabled={loading}
                          >
                            {t('settings.channelAccess.actions.delete')}
                          </button>
                          <button className="btn btn--outline btn--sm" onClick={() => toggleAccountExpand(account.id)}>
                            {isExpanded
                              ? t('settings.channelAccess.actions.hideDetails')
                              : t('settings.channelAccess.actions.viewDetails')}
                          </button>
                        </div>
                      </div>
                      {isExpanded ? (
                        <div className="channel-account-card__detail">
                          {detailLoading ? <div className="text-text-secondary">{t('settings.channelAccess.detail.loading')}</div> : (
                            <>
                              {accountStatus ? (
                                <div className="channel-detail-section">
                                  <h4>{t('settings.channelAccess.detail.connectionTitle')}</h4>
                                  <div className="channel-detail-stats">
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">
                                        {accountStatus.recent_failure_summary.recent_failure_count}
                                      </span>
                                      <span className="channel-detail-stat__label">
                                        {t('settings.channelAccess.detail.recentFailureCount')}
                                      </span>
                                    </div>
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">{accountStatus.recent_delivery_count}</span>
                                      <span className="channel-detail-stat__label">
                                        {t('settings.channelAccess.detail.recentDeliveryCount')}
                                      </span>
                                    </div>
                                    <div className="channel-detail-stat">
                                      <span className="channel-detail-stat__value">{accountStatus.recent_inbound_count}</span>
                                      <span className="channel-detail-stat__label">
                                        {t('settings.channelAccess.detail.recentInboundCount')}
                                      </span>
                                    </div>
                                  </div>
                                  {accountStatus.recent_failure_summary.last_error_message ? (
                                    <div className="channel-detail-error">
                                      <strong>{t('settings.channelAccess.detail.lastFailure')}</strong>
                                      {accountStatus.recent_failure_summary.last_error_message}
                                      <span className="channel-detail-error__time">
                                        {t('settings.channelAccess.detail.lastFailureTime', {
                                          time: formatTimestamp(accountStatus.recent_failure_summary.last_failed_at, locale),
                                        })}
                                      </span>
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                              <div className="channel-detail-section">
                                <h4>{t('settings.channelAccess.detail.memberBindings')}</h4>
                                <ChannelAccountBindingsPanel
                                  householdId={currentHouseholdId ?? ''}
                                  accountId={account.id}
                                  members={activeMembers}
                                  plugin={pluginState}
                                  supportsMemberBinding={supportsMemberBinding}
                                />
                              </div>
                              {failedDeliveries.length > 0 || failedInboundEvents.length > 0 ? (
                                <div className="channel-detail-section">
                                  <h4>{t('settings.channelAccess.detail.recentFailures')}</h4>
                                  {failedDeliveries.length > 0 ? (
                                    <div className="channel-failure-list">
                                      <h5>{t('settings.channelAccess.detail.failedDeliveriesTitle')}</h5>
                                      {failedDeliveries.map((item) => (
                                        <div key={item.id} className="channel-failure-item">
                                          <span className="channel-failure-item__type">{item.delivery_type}</span>
                                          <span className="channel-failure-item__error">
                                            {item.last_error_message ?? t('settings.channelAccess.detail.unknownError')}
                                          </span>
                                          <span className="channel-failure-item__time">{formatTimestamp(item.created_at, locale)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                  {failedInboundEvents.length > 0 ? (
                                    <div className="channel-failure-list">
                                      <h5>{t('settings.channelAccess.detail.failedInboundTitle')}</h5>
                                      {failedInboundEvents.map((item) => (
                                        <div key={item.id} className="channel-failure-item">
                                          <span className="channel-failure-item__type">{item.event_type}</span>
                                          <span className="channel-failure-item__error">
                                            {item.error_message ?? t('settings.channelAccess.detail.unknownError')}
                                          </span>
                                          <span className="channel-failure-item__time">{formatTimestamp(item.received_at, locale)}</span>
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
            ) : null}
          </div>
        </Section>
        <SettingsDialog
          open={accountModalOpen}
          title={editingAccount ? t('settings.channelAccess.modal.editTitle') : t('settings.channelAccess.modal.createTitle')}
          description={t('settings.channelAccess.modal.description')}
          onClose={() => setAccountModalOpen(false)}
          onSubmit={handleSaveAccount}
          actions={(
            <>
              <button
                className="btn btn--outline btn--sm"
                type="button"
                onClick={() => setAccountModalOpen(false)}
                disabled={modalLoading}
              >
                {t('settings.channelAccess.actions.cancel')}
              </button>
              <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>
                {modalLoading ? t('settings.channelAccess.actions.saving') : t('settings.channelAccess.actions.save')}
              </button>
            </>
          )}
        >
          <div className="form-group">
            <label>{t('settings.channelAccess.form.platformType')}</label>
            <select
              className="form-select"
              value={accountForm.plugin_id}
              onChange={(event) => {
                const nextPlugin = channelPluginMap.get(event.target.value) ?? null;
                setAccountForm((current) => ({
                  ...current,
                  plugin_id: event.target.value,
                  connection_mode: resolveDefaultConnectionMode(nextPlugin),
                }));
              }}
              disabled={Boolean(editingAccount)}
              required
            >
              <option value="">{t('settings.channelAccess.form.platformPlaceholder')}</option>
              {availableChannelPlugins.map((plugin) => (
                <option key={plugin.pluginId} value={plugin.pluginId}>
                  {plugin.icon} {plugin.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.channelAccess.form.displayName')}</label>
            <input
              className="form-input"
              value={accountForm.display_name}
              onChange={(event) => setAccountForm((current) => ({ ...current, display_name: event.target.value }))}
              placeholder={t('settings.channelAccess.form.displayNamePlaceholder')}
              required
            />
          </div>
          <div className="form-group">
            <label>{t('settings.channelAccess.form.connectionMode')}</label>
            {supportedConnectionModes.length > 1 ? (
              <select
                className="form-select"
                value={accountForm.connection_mode}
                onChange={(event) => setAccountForm((current) => ({
                  ...current,
                  connection_mode: event.target.value as ChannelConnectionMode,
                }))}
              >
                {supportedConnectionModes.map((mode) => (
                  <option key={mode} value={mode}>{formatConnectionMode(mode, locale)}</option>
                ))}
              </select>
            ) : (
              <div className="form-input form-input--readonly">{formatConnectionMode(accountForm.connection_mode, locale)}</div>
            )}
            <div className="form-help">
              {supportedConnectionModes.length <= 1
                ? t('settings.channelAccess.form.connectionModeSingleHelp')
                : t('settings.channelAccess.form.connectionModeMultiHelp')}
            </div>
          </div>
          <div className="form-group">
            <label>{t('settings.channelAccess.form.status')}</label>
            <select
              className="form-select"
              value={accountForm.status}
              onChange={(event) => setAccountForm((current) => ({
                ...current,
                status: event.target.value as ChannelAccountStatus,
              }))}
            >
              <option value="draft">{t('settings.channelAccess.accountStatus.draft')}</option>
              <option value="active">{t('settings.channelAccess.accountStatus.active')}</option>
              <option value="disabled">{t('settings.channelAccess.accountStatus.disabled')}</option>
            </select>
          </div>
          {configFields.length > 0 ? (
            <div className="form-group channel-config-section">
              <label>{t('settings.channelAccess.form.platformConfig')}</label>
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
                      value={String(accountForm.config[field.key] ?? '')}
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
          ) : null}
        </SettingsDialog>
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
