import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Taro from '@tarojs/taro';
import { Gamepad2, Building2, Bot, Plus, Puzzle, MessageSquare } from 'lucide-react';
import { GuardedPage, useHouseholdContext, useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, EmptyState, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { ChannelAccountBindingsPanel } from '../components/ChannelAccountBindingsPanel';
import { PluginArtifactList } from '../components/PluginArtifactList';
import { SettingsDialog, SettingsNotice } from '../components/SettingsSharedBlocks';
import {
  resolvePluginConfigSectionDescription,
  resolvePluginConfigSectionTitle,
  resolvePluginConfigSubmitText,
  resolvePluginFieldLabel,
  resolvePluginMaybeKey,
  resolvePluginOptionLabel,
  resolvePluginTextValue,
  resolvePluginWidgetHelpText,
  resolvePluginWidgetPlaceholder,
} from '../pluginConfigI18n';
import { ApiError, settingsApi } from '../settingsApi';
import {
  TelegramLogo,
  DiscordLogo,
  FeishuLogo,
  DingtalkLogo,
} from './assets/PlatformLogos';
import type {
  ChannelLegacyAccountConfigField,
  ChannelAccountPluginActionExecuteRead,
  ChannelAccountRead,
  ChannelAccountPluginStatusSummaryRead,
  ChannelAccountStatus,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelConnectionMode,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  Member,
  PluginConfigFormRead,
  PluginManifestConfigPreviewAction,
  PluginManifestConfigField,
  PluginManifestFieldUiSchema,
  PluginManifestRuntimeStateItem,
  PluginManifestRuntimeStateSection,
  PluginManifestUiSection,
  PluginRegistryItem,
} from '../settingsTypes';

type MessageKey = Parameters<typeof getPageMessage>[1];
type PlatformInfo = {
  code: string;
  nameKey?: MessageKey;
  descriptionKey?: MessageKey;
  Logo?: typeof TelegramLogo;
  Icon: typeof MessageSquare;
};
type AvailableChannelPlugin = {
  pluginId: string;
  platformCode: string;
  displayName: string;
  description: string;
  Logo?: typeof TelegramLogo;
  Icon: typeof MessageSquare;
};
type LegacyFallbackConfigField = {
  key: string;
  labelKey: MessageKey;
  type: ChannelLegacyAccountConfigField['type'];
  required: boolean;
  placeholderKey: MessageKey;
  helpTextKey?: MessageKey;
};
type PluginConfigFieldDef = {
  mode: 'plugin_field';
  field: PluginManifestConfigField;
  widget?: PluginManifestFieldUiSchema;
};
type LegacyConfigFieldDef = {
  mode: 'legacy_field';
  key: string;
  label: string;
  type: ChannelLegacyAccountConfigField['type'];
  required: boolean;
  placeholder: string;
  helpText?: string;
};
type ConfigFieldDef = PluginConfigFieldDef | LegacyConfigFieldDef;
type AccountFormState = {
  plugin_id: string;
  display_name: string;
  connection_mode: ChannelConnectionMode;
  config: Record<string, unknown>;
  status: ChannelAccountStatus;
};

const PLATFORMS: PlatformInfo[] = [
  {
    code: 'telegram',
    nameKey: 'settings.channelAccess.platform.telegram',
    descriptionKey: 'settings.channelAccess.platformDescription.telegram',
    Logo: TelegramLogo,
    Icon: MessageSquare,
  },
  {
    code: 'discord',
    nameKey: 'settings.channelAccess.platform.discord',
    descriptionKey: 'settings.channelAccess.platformDescription.discord',
    Logo: DiscordLogo,
    Icon: Gamepad2,
  },
  {
    code: 'feishu',
    nameKey: 'settings.channelAccess.platform.feishu',
    descriptionKey: 'settings.channelAccess.platformDescription.feishu',
    Logo: FeishuLogo,
    Icon: Building2,
  },
  {
    code: 'dingtalk',
    nameKey: 'settings.channelAccess.platform.dingtalk',
    descriptionKey: 'settings.channelAccess.platformDescription.dingtalk',
    Logo: DingtalkLogo,
    Icon: Bot,
  },
];

const PLATFORM_CONFIG_FIELDS: Record<string, LegacyFallbackConfigField[]> = {};

function buildInitialAccountForm(): AccountFormState {
  return { plugin_id: '', display_name: '', connection_mode: 'polling', config: {}, status: 'draft' };
}

function normalizeLocale(locale?: string) {
  return locale?.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
}

function getPlatformInfo(platformCode: string): PlatformInfo {
  return PLATFORMS.find((item) => item.code === platformCode) ?? {
    code: platformCode,
    Icon: Puzzle,
  };
}

function buildAvailableChannelPlugin(
  plugin: PluginRegistryItem,
  locale: string | undefined,
): AvailableChannelPlugin | null {
  if (!plugin.enabled) return null;
  const platformCode = plugin.capabilities.channel?.platform_code ?? plugin.id.replace(/^channel-/, '');
  if (!platformCode) return null;
  const platformInfo = getPlatformInfo(platformCode);
  return {
    pluginId: plugin.id,
    platformCode,
    displayName: platformInfo.nameKey ? getPageMessage(locale, platformInfo.nameKey) : plugin.name,
    description: platformInfo.descriptionKey
      ? getPageMessage(locale, platformInfo.descriptionKey)
      : getPageMessage(locale, 'settings.channelAccess.platformDescription.pluginProvided', { pluginName: plugin.name }),
    Logo: platformInfo.Logo,
    Icon: platformInfo.Icon,
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

function resolvePluginSummaryNotice(summary: ChannelAccountPluginStatusSummaryRead): {
  tone: 'info' | 'success' | 'error';
  icon: string;
} {
  if (summary.tone === 'success') return { tone: 'success', icon: '✓' };
  if (summary.tone === 'danger') return { tone: 'error', icon: '⚠️' };
  if (summary.tone === 'warning') return { tone: 'info', icon: '!' };
  return { tone: 'info', icon: 'ℹ️' };
}

function renderPluginStatusSummary(
  summary: ChannelAccountPluginStatusSummaryRead,
  locale: string | undefined,
  t: (key: MessageKey, params?: Record<string, string | number>) => string,
) {
  const notice = resolvePluginSummaryNotice(summary);
  return (
    <SettingsNotice tone={notice.tone} icon={notice.icon}>
      <>
        <strong>{summary.title ?? t('settings.channelAccess.detail.pluginStatusFallback')}</strong>
        {` ${summary.message ?? t('settings.channelAccess.detail.pluginStatusEmpty')}`}
        {summary.last_error_message ? (
          <span className="channel-detail-error__time">{summary.last_error_message}</span>
        ) : null}
        {summary.updated_at ? (
          <span className="channel-detail-error__time">
            {t('settings.channelAccess.detail.pluginStatusUpdatedAt', {
              time: formatTimestamp(summary.updated_at, locale),
            })}
          </span>
        ) : null}
      </>
    </SettingsNotice>
  );
}

function getConfigFields(
  plugin: PluginRegistryItem | null,
  platformCode: string | null,
  locale: string | undefined,
  _translate: (key: string, params?: Record<string, string | number>) => string,
): ConfigFieldDef[] {
  const configSpec = plugin?.config_specs?.find((item) => item.scope_type === 'channel_account') ?? null;
  if (configSpec) {
    const fieldMap = new Map(configSpec.config_schema.fields.map((field) => [field.key, field]));
    const widgets = configSpec.ui_schema.widgets ?? {};
    const orderedKeys = configSpec.ui_schema.field_order?.filter((key) => fieldMap.has(key))
      ?? configSpec.config_schema.fields.map((field) => field.key);
    return orderedKeys.flatMap<PluginConfigFieldDef>((key) => {
      const field = fieldMap.get(key);
      if (!field) return [];
      return [{
        mode: 'plugin_field',
        field,
        widget: widgets[key],
      }];
    });
  }

  const legacyFields = plugin?.capabilities.channel?.ui?.account_config_fields;
  if (legacyFields?.length) {
    return legacyFields.map<LegacyConfigFieldDef>((field) => ({
      mode: 'legacy_field',
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      placeholder: field.placeholder ?? '',
      helpText: field.help_text ?? undefined,
    }));
  }

  const fallbackFields = platformCode ? (PLATFORM_CONFIG_FIELDS[platformCode] ?? []) : [];
  return fallbackFields.map<LegacyConfigFieldDef>((field) => ({
    mode: 'legacy_field',
    key: field.key,
    label: getPageMessage(locale, field.labelKey),
    type: field.type,
    required: field.required,
    placeholder: getPageMessage(locale, field.placeholderKey),
    helpText: field.helpTextKey ? getPageMessage(locale, field.helpTextKey) : undefined,
  }));
}

function getScalarValue(values: Record<string, unknown>, key: string): string {
  const value = values[key];
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return '';
}

function getMultiEnumValues(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function formatJsonEditorValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function formatDisplayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function isPluginFieldVisible(
  fieldKey: string,
  values: Record<string, unknown>,
  widgets: Record<string, PluginManifestFieldUiSchema> | undefined,
): boolean {
  const rules = widgets?.[fieldKey]?.visible_when ?? [];
  if (rules.length === 0) {
    return true;
  }
  return rules.every((rule) => {
    const currentValue = values[rule.field];
    if (rule.operator === 'truthy') return Boolean(currentValue);
    if (rule.operator === 'equals') return currentValue === rule.value;
    if (rule.operator === 'not_equals') return currentValue !== rule.value;
    if (rule.operator === 'in') return Array.isArray(rule.value) && rule.value.includes(currentValue);
    return true;
  });
}

function getPreviewActionErrorKey(actionKey: string): string {
  return `__preview_action__:${actionKey}`;
}

function getRuntimeItemErrorKey(itemKey: string): string {
  return `__runtime_item__:${itemKey}`;
}

function isMeaningfulRuntimeValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length > 0;
  }
  return true;
}

function getObjectPathValue(payload: unknown, source: string): unknown {
  if (!source.trim()) {
    return undefined;
  }
  const parts = source.split('.').map((item) => item.trim()).filter(Boolean);
  let current: unknown = payload;
  for (const part of parts) {
    if (Array.isArray(current)) {
      const index = Number(part);
      current = Number.isInteger(index) ? current[index] : undefined;
      continue;
    }
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function getSupportedConnectionModes(plugin: PluginRegistryItem | null): ChannelConnectionMode[] {
  return (plugin?.capabilities.channel?.inbound_modes ?? []).filter((mode): mode is ChannelConnectionMode => (
    mode === 'webhook' || mode === 'polling' || mode === 'websocket'
  ));
}

function resolveDefaultConnectionMode(plugin: PluginRegistryItem | null): ChannelConnectionMode {
  return getSupportedConnectionModes(plugin)[0] ?? 'polling';
}

function resolveChannelAccountDisplayNameForSubmit(form: AccountFormState, fallback: string): string {
  const accountLabel = getScalarValue(form.config, 'account_label').trim();
  if (accountLabel) return accountLabel;
  const displayName = form.display_name.trim();
  if (displayName) return displayName;
  return fallback;
}

function SettingsChannelAccessContent() {
  const { currentHouseholdId } = useHouseholdContext();
  const { locale, t: translate } = useI18n();
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
  const [platformSelectOpen, setPlatformSelectOpen] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [accountModalMode, setAccountModalMode] = useState<'create' | 'edit'>('create');
  const [editingAccount, setEditingAccount] = useState<ChannelAccountRead | null>(null);
  const [transientDraftAccountId, setTransientDraftAccountId] = useState<string | null>(null);
  const [accountForm, setAccountForm] = useState<AccountFormState>(buildInitialAccountForm);
  const [accountFieldErrors, setAccountFieldErrors] = useState<Record<string, string>>({});
  const [configPreview, setConfigPreview] = useState<PluginConfigFormRead | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewLoadingActionKey, setPreviewLoadingActionKey] = useState<string | null>(null);
  const [previewResultActionKey, setPreviewResultActionKey] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [pluginActionLoadingKey, setPluginActionLoadingKey] = useState<string | null>(null);
  const [pluginActionResult, setPluginActionResult] = useState<ChannelAccountPluginActionExecuteRead | null>(null);

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
  const availableChannelPlugins = useMemo(
    () => channelPlugins
      .map((plugin) => buildAvailableChannelPlugin(plugin, locale))
      .filter((plugin): plugin is AvailableChannelPlugin => plugin !== null),
    [channelPlugins, locale],
  );
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
    setPluginActionResult(null);
    setPluginActionLoadingKey(null);
  }

  function toggleAccountExpand(accountId: string) {
    if (expandedAccountId === accountId) {
      resetExpandedState();
      return;
    }
    setExpandedAccountId(accountId);
    setPluginActionResult(null);
    void loadAccountDetail(accountId);
  }

  function openCreateModal() {
    setPlatformSelectOpen(true);
  }

  function resetAccountModalState() {
    setAccountModalOpen(false);
    setAccountModalMode('create');
    setEditingAccount(null);
    setTransientDraftAccountId(null);
    setAccountForm(buildInitialAccountForm());
    setAccountFieldErrors({});
    setConfigPreview(null);
    setPreviewLoading(false);
    setPreviewLoadingActionKey(null);
    setPreviewResultActionKey(null);
  }

  async function closeAccountModal() {
    if (modalLoading || previewLoading) return;
    if (transientDraftAccountId && currentHouseholdId) {
      setModalLoading(true);
      try {
        await settingsApi.deleteChannelAccount(currentHouseholdId, transientDraftAccountId);
      } catch (closeError) {
        setError(
          closeError instanceof ApiError
            ? formatApiErrorMessage(closeError, locale)
            : closeError instanceof Error
              ? closeError.message
              : t('settings.channelAccess.status.deleteFailed'),
        );
        setModalLoading(false);
        return;
      }
      setModalLoading(false);
    }
    resetAccountModalState();
  }

  async function selectPlatform(pluginId: string) {
    const plugin = channelPluginMap.get(pluginId) ?? null;
    if (!plugin || !currentHouseholdId) return;
    const availablePlugin = availableChannelPlugins.find((item) => item.pluginId === pluginId) ?? null;
    const defaultDisplayName = availablePlugin?.displayName ?? plugin.name;
    const defaultMode = resolveDefaultConnectionMode(plugin);
    setPlatformSelectOpen(false);
    setModalLoading(true);
    setError('');
    try {
      const draftAccount = await settingsApi.createChannelAccount(currentHouseholdId, {
        plugin_id: pluginId,
        display_name: defaultDisplayName,
        connection_mode: defaultMode,
        config: {},
        status: 'draft',
      });
      setAccountModalMode('create');
      setEditingAccount(draftAccount);
      setTransientDraftAccountId(draftAccount.id);
      setAccountForm({
        plugin_id: draftAccount.plugin_id,
        display_name: draftAccount.display_name,
        connection_mode: draftAccount.connection_mode,
        config: {
          ...draftAccount.config,
          account_label: getScalarValue(draftAccount.config, 'account_label') || draftAccount.display_name,
        },
        status: draftAccount.status,
      });
      setAccountFieldErrors({});
      setConfigPreview(null);
      setPreviewLoadingActionKey(null);
      setPreviewResultActionKey(null);
      setAccountModalOpen(true);
    } catch (selectError) {
      setError(
        selectError instanceof ApiError
          ? formatApiErrorMessage(selectError, locale)
          : selectError instanceof Error
            ? selectError.message
            : t('settings.channelAccess.status.createFailed'),
      );
    } finally {
      setModalLoading(false);
    }
  }

  function openEditModal(account: ChannelAccountRead) {
    setAccountModalMode('edit');
    setEditingAccount(account);
    setTransientDraftAccountId(null);
    setAccountForm({
      plugin_id: account.plugin_id,
      display_name: account.display_name,
      connection_mode: account.connection_mode,
      config: {
        ...account.config,
        account_label: getScalarValue(account.config, 'account_label') || account.display_name,
      },
      status: account.status,
    });
    setAccountFieldErrors({});
    setConfigPreview(null);
    setPreviewLoadingActionKey(null);
    setPreviewResultActionKey(null);
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
    if (!currentHouseholdId || !editingAccount) return;
    const nextFieldErrors = { ...accountFieldErrors };
    if (validateRuntimeRequirements(nextFieldErrors)) {
      setAccountFieldErrors(nextFieldErrors);
      return;
    }
    setModalLoading(true);
    setError('');
    setStatus('');
    try {
      const nextDisplayName = resolveChannelAccountDisplayNameForSubmit(
        accountForm,
        editingAccount.display_name,
      );
      const payload: ChannelAccountUpdate = {
        display_name: nextDisplayName,
        connection_mode: accountForm.connection_mode,
        config: accountForm.config,
        status: accountForm.status,
      };
      const result = await settingsApi.updateChannelAccount(currentHouseholdId, editingAccount.id, payload);
      setAccounts((current) => {
        if (accountModalMode === 'create') {
          return [result, ...current];
        }
        return current.map((item) => item.id === result.id ? result : item);
      });
      setStatus(
        accountModalMode === 'create'
          ? t('settings.channelAccess.status.createSuccess')
          : t('settings.channelAccess.status.updateSuccess'),
      );
      resetAccountModalState();
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

  async function handlePreviewAccountConfig(action?: PluginManifestConfigPreviewAction) {
    if (!currentHouseholdId || !editingAccount || !selectedPlugin?.entrypoints.config_preview) return;
    setPreviewLoading(true);
    setPreviewLoadingActionKey(action?.key ?? '__default__');
    setError('');
    setAccountFieldErrors((current) => {
      const nextErrors = { ...current };
      if (action) {
        delete nextErrors[getPreviewActionErrorKey(action.key)];
      }
      return nextErrors;
    });
    try {
      const previewForm = await settingsApi.previewHouseholdPluginConfigForm(currentHouseholdId, selectedPlugin.id, {
        scope_type: 'channel_account',
        scope_key: editingAccount.id,
        values: accountForm.config,
        secret_values: {},
        clear_secret_fields: [],
        action_key: action?.action_key ?? action?.key ?? null,
      });
      setConfigPreview(previewForm);
      setPreviewResultActionKey(action?.key ?? '__default__');
      setAccountFieldErrors((current) => ({
        ...current,
        ...previewForm.view.field_errors,
      }));
      setAccountForm((current) => ({
        ...current,
        config: { ...current.config, ...previewForm.view.values },
      }));
    } catch (previewError) {
      setError(
        previewError instanceof ApiError
          ? formatApiErrorMessage(previewError, locale)
          : previewError instanceof Error
            ? previewError.message
            : t('settings.channelAccess.status.previewFailed'),
      );
      if (action) {
        setAccountFieldErrors((current) => ({
          ...current,
          [getPreviewActionErrorKey(action.key)]: previewError instanceof Error
            ? previewError.message
            : t('settings.channelAccess.status.previewFailed'),
        }));
      }
    } finally {
      setPreviewLoading(false);
      setPreviewLoadingActionKey(null);
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

  async function handleExecutePluginAction(
    account: ChannelAccountRead,
    actionKey: string,
  ) {
    if (!currentHouseholdId || !accountStatus) return;
    const action = accountStatus.plugin_actions.find((item) => item.key === actionKey);
    if (!action || action.disabled) return;

    if (action.requires_confirmation) {
      const confirmResult = await Taro.showModal({
        title: t('settings.channelAccess.pluginAction.confirmTitle'),
        content: action.confirmation_text
          ?? action.description
          ?? t('settings.channelAccess.pluginAction.confirmFallback'),
        confirmText: t('settings.channelAccess.pluginAction.confirmButton'),
        cancelText: t('settings.channelAccess.actions.cancel'),
      });
      if (!confirmResult.confirm) return;
    }

    setPluginActionLoadingKey(action.key);
    setError('');
    setStatus('');
    try {
      const result = await settingsApi.executeChannelAccountPluginAction(
        currentHouseholdId,
        account.id,
        action.key,
        { payload: {} },
      );
      setPluginActionResult(result);
      await loadAccounts();
      if (expandedAccountId === account.id) {
        await loadAccountDetail(account.id);
      }
      setStatus(result.message ?? t('settings.channelAccess.status.pluginActionSuccess'));
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? formatApiErrorMessage(actionError, locale)
          : actionError instanceof Error
            ? actionError.message
            : t('settings.channelAccess.status.actionFailed'),
      );
    } finally {
      setPluginActionLoadingKey(null);
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
    () => getConfigFields(selectedPlugin, selectedPlatformCode, locale, translate),
    [selectedPlugin, selectedPlatformCode, locale, translate],
  );
  const pluginConfigSpec = selectedPlugin?.config_specs?.find((item) => item.scope_type === 'channel_account') ?? null;
  const pluginConfigWidgets = pluginConfigSpec?.ui_schema.widgets;
  const previewActions = pluginConfigSpec?.ui_schema.actions ?? [];
  const runtimeSections = pluginConfigSpec?.ui_schema.runtime_sections ?? [];
  const previewRuntimeState = configPreview?.view.runtime_state ?? {};
  const previewArtifacts = configPreview?.view.preview_artifacts ?? [];
  const visibleConfigFields = useMemo(
    () => configFields.filter((item) => {
      if (item.mode === 'legacy_field') {
        return true;
      }
      return isPluginFieldVisible(item.field.key, accountForm.config, pluginConfigWidgets);
    }),
    [accountForm.config, configFields, pluginConfigWidgets],
  );
  const visiblePluginSections = useMemo(() => {
    if (!pluginConfigSpec) {
      return [];
    }
    const fieldDefMap = new Map(
      visibleConfigFields
        .filter((item): item is PluginConfigFieldDef => item.mode === 'plugin_field')
        .map((item) => [item.field.key, item]),
    );
    return pluginConfigSpec.ui_schema.sections
      .map((section) => ({
        section,
        fields: section.fields
          .map((fieldKey) => fieldDefMap.get(fieldKey) ?? null)
          .filter((item): item is PluginConfigFieldDef => item !== null),
      }))
      .filter(({ section, fields }) => (
        fields.length > 0
        || getSectionPreviewActions(section.id).length > 0
        || getSectionRuntimeSections(section.id).length > 0
      ));
  }, [pluginConfigSpec, visibleConfigFields, previewActions, runtimeSections, previewResultActionKey, accountModalMode]);
  const hasStagedPreviewUi = previewActions.length > 0 || runtimeSections.length > 0;
  const canPreviewConfig = Boolean(selectedPlugin?.entrypoints.config_preview && editingAccount?.id);
  const supportedConnectionModes = useMemo(() => getSupportedConnectionModes(selectedPlugin), [selectedPlugin]);

  useEffect(() => {
    if (!selectedPlugin || supportedConnectionModes.length === 0) return;
    const defaultMode = resolveDefaultConnectionMode(selectedPlugin);
    if (!supportedConnectionModes.includes(accountForm.connection_mode)) {
      setAccountForm((current) => ({ ...current, connection_mode: defaultMode }));
    }
  }, [accountForm.connection_mode, selectedPlugin, supportedConnectionModes]);

  function resolveActionLabel(action: PluginManifestConfigPreviewAction): string {
    return resolvePluginTextValue(action.label, action.label_key, translate) || action.key;
  }

  function resolveActionDescription(action: PluginManifestConfigPreviewAction): string {
    return resolvePluginTextValue(action.description, action.description_key, translate) || '';
  }

  function resolveRuntimeText(value: string | null | undefined, valueKey: string | null | undefined): string {
    return resolvePluginTextValue(value ?? null, valueKey ?? null, translate) || '';
  }

  function getSectionPreviewActions(sectionId: string): PluginManifestConfigPreviewAction[] {
    return previewActions.filter((action) => (
      action.section_id === sectionId
      && (action.modes ?? ['create', 'edit']).includes(accountModalMode)
    ));
  }

  function getSectionRuntimeSections(sectionId: string): PluginManifestRuntimeStateSection[] {
    return runtimeSections.filter((section) => (
      section.section_id === sectionId
      && (!section.action_key || section.action_key === previewResultActionKey)
    ));
  }

  function isPreviewActionReady(action: PluginManifestConfigPreviewAction): boolean {
    return (action.depends_on_fields ?? []).every((fieldKey) => isMeaningfulRuntimeValue(accountForm.config[fieldKey]));
  }

  function getConfigField(fieldKey: string): PluginManifestConfigField | null {
    if (!pluginConfigSpec) {
      return null;
    }
    return pluginConfigSpec.config_schema.fields.find((field) => field.key === fieldKey) ?? null;
  }

  function buildRuntimeSelectionValue(item: PluginManifestRuntimeStateItem, candidate: unknown): unknown {
    if (item.selection_mode === 'field') {
      return getObjectPathValue(candidate, item.selection_value_field ?? '');
    }
    const payload: Record<string, unknown> = {};
    for (const fieldPath of item.selection_object_fields ?? []) {
      const fieldName = fieldPath.split('.').at(-1)?.trim();
      if (!fieldName) {
        continue;
      }
      payload[fieldName] = getObjectPathValue(candidate, fieldPath);
    }
    return payload;
  }

  function isRuntimeCandidateSelected(item: PluginManifestRuntimeStateItem, candidate: unknown): boolean {
    if (!item.target_field || !item.selected_match_field) {
      return false;
    }
    const currentValue = accountForm.config[item.target_field];
    const candidateValue = getObjectPathValue(candidate, item.selected_match_field);
    if (item.selection_mode === 'field') {
      return currentValue === candidateValue;
    }
    const currentMatchValue = getObjectPathValue(currentValue, item.selected_match_field);
    return currentMatchValue === candidateValue;
  }

  function validateRuntimeRequirements(nextErrors: Record<string, string>): boolean {
    let hasError = false;
    for (const section of runtimeSections) {
      if (section.action_key && section.action_key !== previewResultActionKey) {
        continue;
      }
      for (const item of section.items) {
        const errorKey = getRuntimeItemErrorKey(item.key);
        if (item.kind !== 'candidate_select' || !item.required || !item.target_field) {
          nextErrors[errorKey] = '';
          continue;
        }
        const selectedValue = accountForm.config[item.target_field];
        if (isMeaningfulRuntimeValue(selectedValue)) {
          nextErrors[errorKey] = '';
          continue;
        }
        nextErrors[errorKey] = resolveRuntimeText(item.required_message, item.required_message_key)
          || `${resolveRuntimeText(item.label, item.label_key) || item.target_field} ${t('settings.channelAccess.form.requiredSuffix')}`;
        hasError = true;
      }
    }
    return hasError;
  }

  function updateConfigValue(fieldKey: string, value: unknown) {
    const resetActions = previewActions.filter((action) => (action.reset_on_change_fields ?? []).includes(fieldKey));
    const resetFieldKeys = new Set<string>();
    for (const action of resetActions) {
      for (const clearField of action.clear_fields_on_reset ?? []) {
        resetFieldKeys.add(clearField);
      }
    }
    setAccountForm((current) => ({
      ...current,
      config: (() => {
        const nextConfig = { ...current.config, [fieldKey]: value };
        for (const clearField of resetFieldKeys) {
          delete nextConfig[clearField];
        }
        return nextConfig;
      })(),
    }));
    setAccountFieldErrors((current) => {
      const nextErrors = { ...current };
      delete nextErrors[fieldKey];
      for (const action of resetActions) {
        delete nextErrors[getPreviewActionErrorKey(action.key)];
      }
      for (const clearField of resetFieldKeys) {
        delete nextErrors[clearField];
      }
      if (Object.keys(nextErrors).length === Object.keys(current).length) {
        return current;
      }
      return nextErrors;
    });
    setConfigPreview(null);
    setPreviewLoadingActionKey(null);
    setPreviewResultActionKey(null);
  }

  function renderConfigField(fieldDef: ConfigFieldDef) {
    if (fieldDef.mode === 'legacy_field') {
      return (
        <div key={fieldDef.key} className="channel-config-field">
          <label className="channel-config-field__label">
            {fieldDef.label}
            {fieldDef.required ? <span className="required-mark">*</span> : null}
          </label>
          <input
            type={fieldDef.type}
            className="form-input"
            value={String(accountForm.config[fieldDef.key] ?? '')}
            onChange={(event) => updateConfigValue(fieldDef.key, event.target.value)}
            placeholder={fieldDef.placeholder}
            required={fieldDef.required}
          />
          {fieldDef.helpText ? <div className="form-help">{fieldDef.helpText}</div> : null}
          {accountFieldErrors[fieldDef.key] ? (
            <div className="form-help">{resolvePluginMaybeKey(accountFieldErrors[fieldDef.key], translate)}</div>
          ) : null}
        </div>
      );
    }

    const { field, widget } = fieldDef;
    const label = resolvePluginFieldLabel(field, translate);
    const helpText = resolvePluginWidgetHelpText(widget, field, translate);
    const placeholder = resolvePluginWidgetPlaceholder(widget, translate);
    const fieldError = accountFieldErrors[field.key];
    const widgetType = widget?.widget;
    const rawValue = accountForm.config[field.key];
    const displayValue = formatDisplayValue(rawValue ?? field.default);

    if (widgetType === 'display') {
      return (
        <div key={field.key} className="channel-config-field channel-config-field--display">
          <label className="channel-config-field__label">{label}</label>
          <pre className="channel-config-field__display">
            {displayValue || helpText || t('settings.channelAccess.form.displayWidgetEmpty')}
          </pre>
          {helpText ? <div className="form-help">{helpText}</div> : null}
        </div>
      );
    }

    if (field.type === 'secret') {
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">
            {label}
            {field.required ? <span className="required-mark">*</span> : null}
          </label>
          <input
            type="password"
            className="form-input"
            value={getScalarValue(accountForm.config, field.key)}
            onChange={(event) => updateConfigValue(field.key, event.target.value)}
            placeholder={placeholder || undefined}
            required={field.required}
          />
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    if (field.type === 'boolean') {
      if (widgetType === 'switch') {
        return (
          <div key={field.key} className="channel-config-field">
            <label className="channel-config-field__label">{label}</label>
            <label className="channel-config-field__toggle">
              <input
                type="checkbox"
                checked={rawValue === true}
                onChange={(event) => updateConfigValue(field.key, event.target.checked)}
              />
              <span>{rawValue === true ? t('settings.channelAccess.form.booleanTrue') : t('settings.channelAccess.form.booleanFalse')}</span>
            </label>
            {helpText ? <div className="form-help">{helpText}</div> : null}
            {fieldError ? <div className="form-help">{fieldError}</div> : null}
          </div>
        );
      }
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">{label}</label>
          <select
            className="form-select"
            value={rawValue === true ? 'true' : 'false'}
            onChange={(event) => updateConfigValue(field.key, event.target.value === 'true')}
          >
            <option value="false">{t('settings.channelAccess.form.booleanFalse')}</option>
            <option value="true">{t('settings.channelAccess.form.booleanTrue')}</option>
          </select>
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    if (field.type === 'enum') {
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">
            {label}
            {field.required ? <span className="required-mark">*</span> : null}
          </label>
          <select
            className="form-select"
            value={getScalarValue(accountForm.config, field.key)}
            onChange={(event) => updateConfigValue(field.key, event.target.value)}
          >
            <option value="">{t('settings.channelAccess.form.selectPlaceholder')}</option>
            {(field.enum_options ?? []).map((option: NonNullable<PluginManifestConfigField['enum_options']>[number]) => (
              <option key={option.value} value={option.value}>{resolvePluginOptionLabel(option, translate)}</option>
            ))}
          </select>
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    if (field.type === 'multi_enum') {
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">{label}</label>
          <select
            className="form-select"
            multiple
            value={getMultiEnumValues(rawValue)}
            onChange={(event) => {
              const nextValues = Array.from(event.target.selectedOptions).map((option) => option.value);
              updateConfigValue(field.key, nextValues);
            }}
          >
            {(field.enum_options ?? []).map((option: NonNullable<PluginManifestConfigField['enum_options']>[number]) => (
              <option key={option.value} value={option.value}>{resolvePluginOptionLabel(option, translate)}</option>
            ))}
          </select>
          <div className="form-help">{t('settings.channelAccess.form.multiSelectHint')}</div>
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    if (field.type === 'json') {
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">{label}</label>
          <textarea
            className="form-input"
            value={formatJsonEditorValue(rawValue)}
            onChange={(event) => updateConfigValue(field.key, event.target.value)}
            placeholder={placeholder || undefined}
            rows={6}
          />
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    if (field.type === 'text' || widgetType === 'textarea') {
      return (
        <div key={field.key} className="channel-config-field">
          <label className="channel-config-field__label">
            {label}
            {field.required ? <span className="required-mark">*</span> : null}
          </label>
          <textarea
            className="form-input"
            value={getScalarValue(accountForm.config, field.key)}
            onChange={(event) => updateConfigValue(field.key, event.target.value)}
            placeholder={placeholder || undefined}
            rows={4}
            required={field.required}
          />
          {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
        </div>
      );
    }

    const inputType = field.type === 'integer' || field.type === 'number' ? 'number' : 'text';
    return (
      <div key={field.key} className="channel-config-field">
        <label className="channel-config-field__label">
          {label}
          {field.required ? <span className="required-mark">*</span> : null}
        </label>
        <input
          type={inputType}
          className="form-input"
          value={getScalarValue(accountForm.config, field.key)}
          onChange={(event) => {
            if (field.type === 'integer') {
              const rawInput = event.target.value;
              updateConfigValue(field.key, rawInput === '' ? '' : Number.parseInt(rawInput, 10));
              return;
            }
            if (field.type === 'number') {
              const rawInput = event.target.value;
              updateConfigValue(field.key, rawInput === '' ? '' : Number(rawInput));
              return;
            }
            updateConfigValue(field.key, event.target.value);
          }}
          placeholder={placeholder || undefined}
          required={field.required}
          step={field.type === 'integer' ? 1 : undefined}
        />
        {helpText ? <div className="form-help">{helpText}</div> : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, translate)}</div> : null}
      </div>
    );
  }

  function renderRuntimeStateItem(item: PluginManifestRuntimeStateItem) {
    const runtimeValue = getObjectPathValue(previewRuntimeState, item.source);
    const itemLabel = resolveRuntimeText(item.label, item.label_key);
    const itemDescription = resolveRuntimeText(item.description, item.description_key);
    const itemError = accountFieldErrors[getRuntimeItemErrorKey(item.key)];

    if (item.kind === 'status_badge') {
      if (!isMeaningfulRuntimeValue(runtimeValue)) {
        return null;
      }
      const selectedOption = (item.status_options ?? []).find((option) => option.value === runtimeValue) ?? null;
      const badgeTone = selectedOption?.tone ?? 'neutral';
      const toneStyle = badgeTone === 'success'
        ? { background: 'rgba(22, 163, 74, 0.12)', color: '#166534' }
        : badgeTone === 'warning'
          ? { background: 'rgba(245, 158, 11, 0.14)', color: '#92400e' }
          : badgeTone === 'danger'
            ? { background: 'rgba(220, 38, 38, 0.12)', color: '#991b1b' }
            : badgeTone === 'info'
              ? { background: 'rgba(14, 165, 233, 0.12)', color: '#0c4a6e' }
              : { background: 'rgba(15, 23, 42, 0.06)', color: '#475569' };
      const badgeLabel = selectedOption
        ? resolveRuntimeText(selectedOption.label, selectedOption.label_key)
        : (typeof runtimeValue === 'string' ? runtimeValue : '');
      return (
        <div key={item.key} className="channel-config-field">
          {itemLabel ? <label className="channel-config-field__label">{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              borderRadius: '999px',
              padding: '6px 12px',
              fontSize: '13px',
              fontWeight: 600,
              marginTop: itemLabel || itemDescription ? '8px' : 0,
              ...toneStyle,
            }}
          >
            {badgeLabel || t('settings.channelAccess.form.previewEmpty')}
          </div>
          {itemError ? <div className="form-help">{resolvePluginMaybeKey(itemError, translate)}</div> : null}
        </div>
      );
    }

    if (item.kind === 'link') {
      const linkUrl = typeof runtimeValue === 'string' ? runtimeValue.trim() : '';
      const linkText = resolveRuntimeText(
        typeof getObjectPathValue(previewRuntimeState, item.link_text_source ?? '') === 'string'
          ? String(getObjectPathValue(previewRuntimeState, item.link_text_source ?? ''))
          : item.link_text,
        item.link_text_key,
      );
      const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
      return (
        <div key={item.key} className="channel-config-field">
          {itemLabel ? <label className="channel-config-field__label">{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          {linkUrl ? (
            <a
              href={linkUrl}
              target="_blank"
              rel="noreferrer"
              className="plugin-artifact-card__link"
              style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}
            >
              {linkText || t('settings.channelAccess.form.previewOpenArtifact')}
            </a>
          ) : (
            <div className="form-help" style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
              {emptyText || t('settings.channelAccess.form.previewEmpty')}
            </div>
          )}
          {itemError ? <div className="form-help">{resolvePluginMaybeKey(itemError, translate)}</div> : null}
        </div>
      );
    }

    if (item.kind === 'candidate_select') {
      const candidates = Array.isArray(runtimeValue) ? runtimeValue : [];
      const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
      return (
        <div key={item.key} className="channel-config-field">
          {itemLabel ? <label className="channel-config-field__label">{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          {candidates.length === 0 ? (
            <div className="form-help" style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
              {emptyText || t('settings.channelAccess.form.previewEmpty')}
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '8px', marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
              {candidates.map((candidate, index) => {
                const label = (item.option_label_fields ?? [])
                  .map((fieldPath) => getObjectPathValue(candidate, fieldPath))
                  .find((fieldValue) => typeof fieldValue === 'string' && fieldValue.trim()) as string | undefined;
                const descriptionParts = (item.option_description_fields ?? [])
                  .map((fieldPath) => getObjectPathValue(candidate, fieldPath))
                  .filter((fieldValue): fieldValue is string => typeof fieldValue === 'string' && fieldValue.trim().length > 0);
                const candidateKey = String(getObjectPathValue(candidate, item.selected_match_field ?? '') ?? index);
                const selected = isRuntimeCandidateSelected(item, candidate);
                return (
                  <button
                    key={`${item.key}-${candidateKey}`}
                    className="btn"
                    type="button"
                    onClick={() => {
                      if (!item.target_field) {
                        return;
                      }
                      const nextValue = buildRuntimeSelectionValue(item, candidate);
                      setAccountForm((current) => ({
                        ...current,
                        config: { ...current.config, [item.target_field!]: nextValue },
                      }));
                      setAccountFieldErrors((current) => ({
                        ...current,
                        [item.target_field!]: '',
                        [getRuntimeItemErrorKey(item.key)]: '',
                      }));
                    }}
                    style={{
                      textAlign: 'left',
                      border: selected ? '1px solid var(--brand-primary)' : '1px solid var(--border-light)',
                      background: selected ? 'var(--brand-primary-light)' : 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      borderRadius: '12px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: descriptionParts.length > 0 ? '4px' : 0 }}>
                      {label || candidateKey}
                    </div>
                    {descriptionParts.length > 0 ? (
                      <div className="form-help">{descriptionParts.join(' / ')}</div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
          {itemError ? <div className="form-help" style={{ marginTop: '8px' }}>{resolvePluginMaybeKey(itemError, translate)}</div> : null}
        </div>
      );
    }

    const textValue = typeof runtimeValue === 'string'
      ? runtimeValue
      : typeof runtimeValue === 'number' || typeof runtimeValue === 'boolean'
        ? String(runtimeValue)
        : isMeaningfulRuntimeValue(runtimeValue)
          ? formatJsonEditorValue(runtimeValue)
          : '';
    const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
    return (
      <div key={item.key} className="channel-config-field">
        {itemLabel ? <label className="channel-config-field__label">{itemLabel}</label> : null}
        {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
        <div className="form-help" style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
          {textValue || emptyText || t('settings.channelAccess.form.previewEmpty')}
        </div>
        {itemError ? <div className="form-help">{resolvePluginMaybeKey(itemError, translate)}</div> : null}
      </div>
    );
  }

  function renderConfigPreviewPanel(section: PluginManifestUiSection) {
    const sectionActions = getSectionPreviewActions(section.id);
    const sectionRuntimeSections = getSectionRuntimeSections(section.id);
    const shouldRenderArtifacts = previewArtifacts.length > 0 && (
      sectionActions.some((action) => action.key === previewResultActionKey)
      || sectionRuntimeSections.some((runtimeSection) => !runtimeSection.action_key || runtimeSection.action_key === previewResultActionKey)
    );
    if (sectionActions.length === 0 && sectionRuntimeSections.length === 0 && !shouldRenderArtifacts) {
      return null;
    }
    return (
      <div className="form-group channel-config-preview" key={`preview-${section.id}`}>
        {sectionActions.map((action) => {
          const actionError = accountFieldErrors[getPreviewActionErrorKey(action.key)];
          const actionLoading = previewLoadingActionKey === action.key;
          return (
            <div key={action.key} className="channel-config-preview__action">
              <label>{resolveActionLabel(action)}</label>
              {resolveActionDescription(action) ? <div className="form-help">{resolveActionDescription(action)}</div> : null}
              <div style={{ marginTop: '8px' }}>
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => void handlePreviewAccountConfig(action)}
                  disabled={previewLoading || modalLoading || !isPreviewActionReady(action)}
                >
                  {actionLoading ? t('settings.channelAccess.actions.previewing') : resolveActionLabel(action)}
                </button>
              </div>
              {!isPreviewActionReady(action) ? (
                <div className="form-help" style={{ marginTop: '8px' }}>
                  {t('settings.channelAccess.form.previewDependencyHint')}
                </div>
              ) : null}
              {actionError ? (
                <div className="form-help" style={{ marginTop: '8px' }}>
                  {resolvePluginMaybeKey(actionError, translate)}
                </div>
              ) : null}
            </div>
          );
        })}
        {sectionRuntimeSections.map((runtimeSection) => (
          <div key={runtimeSection.key} className="channel-config-preview__runtime">
            {resolveRuntimeText(runtimeSection.title, runtimeSection.title_key) ? (
              <>
                <label>{resolveRuntimeText(runtimeSection.title, runtimeSection.title_key)}</label>
                {resolveRuntimeText(runtimeSection.description, runtimeSection.description_key) ? (
                  <div className="form-help">{resolveRuntimeText(runtimeSection.description, runtimeSection.description_key)}</div>
                ) : null}
              </>
            ) : null}
            <div className="channel-config-fields">
              {runtimeSection.items
                .filter((item) => !item.action_key || item.action_key === previewResultActionKey)
                .map((item) => renderRuntimeStateItem(item))}
            </div>
          </div>
        ))}
        {shouldRenderArtifacts ? (
          <PluginArtifactList
            items={previewArtifacts}
            artifactFallback={t('settings.channelAccess.form.previewArtifactFallback')}
            openLinkText={t('settings.channelAccess.form.previewOpenArtifact')}
          />
        ) : null}
      </div>
    );
  }

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
                  const pluginState = getAccountPluginState(account);
                  const platformName = platform.nameKey ? t(platform.nameKey) : pluginState?.name ?? account.platform_code;
                  const statusInfo = formatStatus(account.status, locale);
                  const probeInfo = formatProbeStatus(account.last_probe_status, locale);
                  const isExpanded = expandedAccountId === account.id;
                  const pluginDisabled = isAccountPluginDisabled(account);
                  const pluginDisabledReason = pluginState?.disabled_reason ?? t('settings.channelAccess.status.pluginDisabledFallback');
                  const supportsMemberBinding = pluginState?.capabilities.channel?.supports_member_binding !== false;
                  const accountMessageClassName = account.last_probe_status === 'ok'
                    ? 'channel-account-card__success'
                    : 'channel-account-card__error';
                  const currentPluginStatusSummary = accountStatus?.plugin_status_summary ?? pluginActionResult?.status_summary ?? null;

                  return (
                    <Card key={account.id} className="channel-account-card">
                      <div className="channel-account-card__header">
                        <div className="channel-account-card__icon">
                          <platform.Icon size={24} />
                        </div>
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
                              {accountStatus?.plugin_status_summary || accountStatus?.plugin_actions.length || pluginActionResult ? (
                                <div className="channel-detail-section">
                                  <h4>{t('settings.channelAccess.detail.pluginActionsTitle')}</h4>
                                  {currentPluginStatusSummary ? (
                                    renderPluginStatusSummary(currentPluginStatusSummary, locale, t)
                                  ) : (
                                    <div className="text-text-secondary">
                                      {t('settings.channelAccess.detail.pluginStatusEmpty')}
                                    </div>
                                  )}
                                  {accountStatus?.plugin_actions.length ? (
                                    <div className="channel-account-card__actions">
                                      {accountStatus.plugin_actions.map((action) => (
                                        <button
                                          key={action.key}
                                          className={`btn btn--outline btn--sm${action.variant === 'danger' ? ' btn--danger' : ''}`}
                                          onClick={() => void handleExecutePluginAction(account, action.key)}
                                          disabled={loading || action.disabled || pluginActionLoadingKey === action.key}
                                          title={action.disabled_reason ?? action.description ?? undefined}
                                        >
                                          {pluginActionLoadingKey === action.key
                                            ? t('settings.channelAccess.pluginAction.running')
                                            : action.label}
                                        </button>
                                      ))}
                                    </div>
                                  ) : null}
                                  {pluginActionResult ? (
                                    <div className="form-help">
                                      <strong>{pluginActionResult.action.label}</strong>
                                      {pluginActionResult.message
                                        ? ` ${pluginActionResult.message}`
                                        : ''}
                                      <PluginArtifactList
                                        items={pluginActionResult.artifacts}
                                        artifactFallback={t('settings.channelAccess.pluginAction.artifactFallback')}
                                        openLinkText={t('settings.channelAccess.pluginAction.openArtifact')}
                                        className="plugin-artifact-list--compact"
                                      />
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
          title={accountModalMode === 'edit'
            ? t('settings.channelAccess.modal.editTitle')
            : t('settings.channelAccess.modal.createTitle')}
          description={t('settings.channelAccess.modal.description')}
          onClose={() => { void closeAccountModal(); }}
          closeDisabled={modalLoading || previewLoading}
          onSubmit={handleSaveAccount}
          actions={(
            <>
              <button
                className="btn btn--outline btn--sm"
                type="button"
                onClick={() => { void closeAccountModal(); }}
                disabled={modalLoading || previewLoading}
              >
                {t('settings.channelAccess.actions.cancel')}
              </button>
              <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading || previewLoading}>
                {modalLoading
                  ? t('settings.channelAccess.actions.saving')
                  : (pluginConfigSpec
                    ? (resolvePluginConfigSubmitText(pluginConfigSpec, translate) || t('settings.channelAccess.actions.save'))
                    : t('settings.channelAccess.actions.save'))}
              </button>
            </>
          )}
        >
          {supportedConnectionModes.length > 1 ? (
            <div className="form-group">
              <label>{t('settings.channelAccess.form.connectionMode')}</label>
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
              <div className="form-help">
                {t('settings.channelAccess.form.connectionModeMultiHelp')}
              </div>
            </div>
          ) : null}
          {pluginConfigSpec ? (
            visiblePluginSections.map(({ section, fields }) => (
              <div key={section.id} className="form-group channel-config-section">
                <label>{resolvePluginConfigSectionTitle(section, translate) || t('settings.channelAccess.form.platformConfig')}</label>
                {resolvePluginConfigSectionDescription(section, translate) ? (
                  <div className="form-help">{resolvePluginConfigSectionDescription(section, translate)}</div>
                ) : null}
                <div className="channel-config-fields">
                  {fields.map((field) => renderConfigField(field))}
                </div>
                {canPreviewConfig ? renderConfigPreviewPanel(section) : null}
              </div>
            ))
          ) : visibleConfigFields.length > 0 ? (
            <div className="form-group channel-config-section">
              <label>{t('settings.channelAccess.form.platformConfig')}</label>
              <div className="channel-config-fields">
                {visibleConfigFields.map((field) => renderConfigField(field))}
              </div>
            </div>
          ) : null}
          {canPreviewConfig && !hasStagedPreviewUi ? (
            <div className="form-group channel-config-preview">
              <div className="channel-config-preview__header">
                <label>{t('settings.channelAccess.form.previewTitle')}</label>
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => void handlePreviewAccountConfig()}
                  disabled={previewLoading || modalLoading}
                >
                  {previewLoading
                    ? t('settings.channelAccess.actions.previewing')
                    : t('settings.channelAccess.actions.refreshPreview')}
                </button>
              </div>
              <div className="form-help">{t('settings.channelAccess.form.previewHelp')}</div>
              {previewArtifacts.length ? (
                <PluginArtifactList
                  items={previewArtifacts}
                  artifactFallback={t('settings.channelAccess.form.previewArtifactFallback')}
                  openLinkText={t('settings.channelAccess.form.previewOpenArtifact')}
                />
              ) : (
                <div className="form-help">{t('settings.channelAccess.form.previewEmpty')}</div>
              )}
            </div>
          ) : null}
        </SettingsDialog>

        {/* 平台选择对话框 */}
        {platformSelectOpen ? (
          <div className="member-modal-overlay" onClick={() => setPlatformSelectOpen(false)}>
            <div className="member-modal platform-select-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{t('settings.channelAccess.platformSelect.title')}</h3>
                  <p>{t('settings.channelAccess.platformSelect.description')}</p>
                </div>
                <button
                  type="button"
                  className="member-modal__close"
                  onClick={() => setPlatformSelectOpen(false)}
                  aria-label={t('settings.channelAccess.actions.cancel')}
                >
                  ×
                </button>
              </div>
              <div className="platform-select-grid">
                {availableChannelPlugins.map((plugin) => {
                  const { Logo, Icon, description, displayName } = plugin;
                  return (
                    <button
                      key={plugin.pluginId}
                      type="button"
                      className="platform-select-card"
                      onClick={() => void selectPlatform(plugin.pluginId)}
                    >
                      <div className="platform-select-card__logo">
                        {Logo ? <Logo width={48} height={48} /> : <Icon size={32} />}
                      </div>
                      <div className="platform-select-card__body">
                        <h4 className="platform-select-card__name">{displayName}</h4>
                        <p className="platform-select-card__desc">{description}</p>
                      </div>
                      <div className="platform-select-card__arrow">
                        <Plus size={20} />
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="platform-select-footer">
                <div className="platform-select-footer__icon">
                  <Puzzle size={16} />
                </div>
                <span className="platform-select-footer__text">
                  {t('settings.channelAccess.platformSelect.footer')}
                </span>
              </div>
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
