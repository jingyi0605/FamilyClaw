import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react';
import Taro from '@tarojs/taro';
import { BadgeCheck, Download, ExternalLink, Eye, GitFork, Package, RefreshCw, Settings2, Star, X, Zap } from 'lucide-react';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n, useTheme } from '../../runtime/h5-shell';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, EmptyState, Section } from '../family/base';
import {
  shouldBlockDeleteCurrentThemePlugin,
  shouldBlockDisableCurrentThemePlugin,
} from './pluginStateGuards';
import { SettingsPageShell } from '../settings/SettingsPageShell';
import { PluginDetailDrawer } from '../settings/components/PluginDetailDrawer';
import { SettingsDialog } from '../settings/components/SettingsSharedBlocks';
import { ApiError, settingsApi } from '../settings/settingsApi';
import type {
  MarketplaceCatalogItemRead,
  MarketplaceInstallStateRead,
  MarketplaceRepoProvider,
  MarketplaceSourceRead,
  PluginManifestType,
  PluginPackageInstallRead,
  PluginRegistryItem,
  PluginVersionOperationResultRead,
  PluginVersionOperationType,
} from '../settings/settingsTypes';

type ViewMode = 'card' | 'list';

const VIEW_MODE_KEY = 'plugin-view-mode';
const SHOW_BUILTIN_PLUGINS_KEY = 'plugin-show-builtin';
const FILTERABLE_TYPES: PluginManifestType[] = [
  'connector',
  'memory-ingestor',
  'action',
  'agent-skill',
  'channel',
  'locale-pack',
  'region-provider',
  'theme-pack',
  'ai-provider',
];

const MARKETPLACE_REPO_PROVIDERS: MarketplaceRepoProvider[] = ['github', 'gitlab', 'gitee', 'gitea'];

type MarketplaceSourceFormState = {
  repo_provider: MarketplaceRepoProvider | '';
  repo_url: string;
  api_base_url: string;
  branch: string;
  entry_root: string;
  mirror_repo_url: string;
  mirror_repo_provider: MarketplaceRepoProvider | '';
  mirror_api_base_url: string;
};

function createEmptyMarketplaceForm(): MarketplaceSourceFormState {
  return {
    repo_provider: '',
    repo_url: '',
    api_base_url: '',
    branch: '',
    entry_root: '',
    mirror_repo_url: '',
    mirror_repo_provider: '',
    mirror_api_base_url: '',
  };
}

function resolveDateLocale(locale: string | undefined) {
  if (locale?.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return 'zh-TW';
  }
  return 'zh-CN';
}

function getInitialViewMode(): ViewMode {
  if (typeof window === 'undefined') {
    return 'card';
  }
  const saved = window.localStorage.getItem(VIEW_MODE_KEY);
  return saved === 'list' ? 'list' : 'card';
}

function getInitialShowBuiltinPlugins() {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(SHOW_BUILTIN_PLUGINS_KEY) === 'true';
}

function formatPluginType(type: PluginManifestType, locale: string | undefined) {
  switch (type) {
    case 'connector':
      return getPageMessage(locale, 'settings.plugin.type.connector');
    case 'memory-ingestor':
      return getPageMessage(locale, 'settings.plugin.type.memoryIngestor');
    case 'action':
      return getPageMessage(locale, 'settings.plugin.type.action');
    case 'agent-skill':
      return getPageMessage(locale, 'settings.plugin.type.agentSkill');
    case 'channel':
      return getPageMessage(locale, 'settings.plugin.type.channel');
    case 'locale-pack':
      return getPageMessage(locale, 'settings.plugin.type.localePack');
    case 'region-provider':
      return getPageMessage(locale, 'settings.plugin.type.regionProvider');
    case 'theme-pack':
      return getPageMessage(locale, 'settings.plugin.type.themePack');
    case 'ai-provider':
      return getPageMessage(locale, 'settings.plugin.type.aiProvider');
    default:
      return type;
  }
}

function formatSourceType(sourceType: PluginRegistryItem['source_type'], locale: string | undefined): { label: string; tone: 'info' | 'success' | 'warning' } {
  switch (sourceType) {
    case 'builtin':
      return { label: getPageMessage(locale, 'settings.plugin.source.builtin'), tone: 'info' };
    case 'official':
      return { label: getPageMessage(locale, 'settings.plugin.source.official'), tone: 'success' };
    case 'third_party':
      return { label: getPageMessage(locale, 'settings.plugin.source.thirdParty'), tone: 'warning' };
    default:
      return { label: sourceType, tone: 'info' };
  }
}

function formatRiskLevel(riskLevel: PluginRegistryItem['risk_level'], locale: string | undefined): { label: string; tone: 'success' | 'warning' | 'danger' } {
  switch (riskLevel) {
    case 'low':
      return { label: getPageMessage(locale, 'settings.plugin.risk.low'), tone: 'success' };
    case 'medium':
      return { label: getPageMessage(locale, 'settings.plugin.risk.medium'), tone: 'warning' };
    case 'high':
      return { label: getPageMessage(locale, 'settings.plugin.risk.high'), tone: 'danger' };
    default:
      return { label: riskLevel, tone: 'warning' };
  }
}

function formatJobStatus(status: string, locale: string | undefined): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'succeeded':
      return { label: getPageMessage(locale, 'settings.plugin.job.succeeded'), tone: 'success' };
    case 'queued':
      return { label: getPageMessage(locale, 'settings.plugin.job.queued'), tone: 'warning' };
    case 'running':
      return { label: getPageMessage(locale, 'settings.plugin.job.running'), tone: 'warning' };
    case 'retry_waiting':
      return { label: getPageMessage(locale, 'settings.plugin.job.retryWaiting'), tone: 'warning' };
    case 'waiting_response':
      return { label: getPageMessage(locale, 'settings.plugin.job.waitingResponse'), tone: 'warning' };
    case 'failed':
      return { label: getPageMessage(locale, 'settings.plugin.job.failed'), tone: 'danger' };
    case 'cancelled':
      return { label: getPageMessage(locale, 'settings.plugin.job.cancelled'), tone: 'secondary' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatTimestamp(value: string | null, locale: string | undefined) {
  if (!value) {
    return getPageMessage(locale, 'plugins.noneYet');
  }
  try {
    return new Date(value).toLocaleString(resolveDateLocale(locale));
  } catch {
    return value;
  }
}

function renderPluginIcon(sourceType: PluginRegistryItem['source_type']) {
  switch (sourceType) {
    case 'builtin':
      return <Package aria-hidden="true" />;
    case 'official':
      return <BadgeCheck aria-hidden="true" />;
    case 'third_party':
      return <Zap aria-hidden="true" />;
    default:
      return <Package aria-hidden="true" />;
  }
}

function formatMarketplaceTrustedLevel(
  trustedLevel: MarketplaceSourceRead['trusted_level'],
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' } {
  if (trustedLevel === 'official') {
    return { label: getPageMessage(locale, 'plugins.marketplace.source.official'), tone: 'success' };
  }
  return { label: getPageMessage(locale, 'plugins.marketplace.source.thirdParty'), tone: 'warning' };
}

function formatMarketplaceSyncStatus(
  status: MarketplaceSourceRead['last_sync_status'],
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'success':
      return { label: getPageMessage(locale, 'plugins.marketplace.sync.success'), tone: 'success' };
    case 'syncing':
      return { label: getPageMessage(locale, 'plugins.marketplace.sync.syncing'), tone: 'warning' };
    case 'failed':
      return { label: getPageMessage(locale, 'plugins.marketplace.sync.failed'), tone: 'danger' };
    case 'idle':
    default:
      return { label: getPageMessage(locale, 'plugins.marketplace.sync.idle'), tone: 'secondary' };
  }
}

function formatMarketplaceInstallState(
  state: MarketplaceInstallStateRead,
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  if (state.install_status === 'installed' && state.enabled) {
    return { label: getPageMessage(locale, 'plugins.marketplace.installState.enabled'), tone: 'success' };
  }
  if (state.install_status === 'installed' && state.config_status !== 'configured') {
    return { label: getPageMessage(locale, 'plugins.marketplace.installState.needsConfig'), tone: 'warning' };
  }
  if (state.install_status === 'installed') {
    return { label: getPageMessage(locale, 'plugins.marketplace.installState.installedDisabled'), tone: 'secondary' };
  }
  if (state.install_status === 'install_failed') {
    return { label: getPageMessage(locale, 'plugins.marketplace.installState.failed'), tone: 'danger' };
  }
  if (state.install_status === 'queued' || state.install_status === 'resolving' || state.install_status === 'downloading' || state.install_status === 'validating' || state.install_status === 'installing') {
    return { label: getPageMessage(locale, 'plugins.marketplace.installState.installing'), tone: 'warning' };
  }
  return { label: getPageMessage(locale, 'plugins.marketplace.installState.notInstalled'), tone: 'secondary' };
}

function formatVersionValue(value: string | null | undefined, locale: string | undefined) {
  if (!value) {
    return getPageMessage(locale, 'settings.plugin.versionValue.unknown');
  }
  return `v${value}`;
}

function formatVersionUpdateState(
  state: string | null | undefined,
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (state) {
    case 'up_to_date':
      return { label: getPageMessage(locale, 'settings.plugin.versionState.upToDate'), tone: 'success' };
    case 'upgrade_available':
    case 'update_available':
      return { label: getPageMessage(locale, 'settings.plugin.versionState.upgradeAvailable'), tone: 'warning' };
    case 'upgrade_blocked':
      return { label: getPageMessage(locale, 'settings.plugin.versionState.upgradeBlocked'), tone: 'danger' };
    case 'installed_newer_than_market':
      return { label: getPageMessage(locale, 'settings.plugin.versionState.installedNewerThanMarket'), tone: 'warning' };
    case 'not_market_managed':
      return { label: getPageMessage(locale, 'settings.plugin.versionState.notMarketManaged'), tone: 'secondary' };
    case 'unknown':
    default:
      return { label: getPageMessage(locale, 'settings.plugin.versionState.unknown'), tone: 'secondary' };
  }
}

function formatMarketplaceRepoProvider(provider: MarketplaceRepoProvider, locale: string | undefined) {
  switch (provider) {
    case 'github':
      return getPageMessage(locale, 'plugins.marketplace.provider.github');
    case 'gitlab':
      return getPageMessage(locale, 'plugins.marketplace.provider.gitlab');
    case 'gitee':
      return getPageMessage(locale, 'plugins.marketplace.provider.gitee');
    case 'gitea':
      return getPageMessage(locale, 'plugins.marketplace.provider.gitea');
    default:
      return provider;
  }
}

function formatVersionCompatibilityStatus(
  status: string | null | undefined,
  locale: string | undefined,
): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'compatible':
      return { label: getPageMessage(locale, 'settings.plugin.compatibilityState.compatible'), tone: 'success' };
    case 'host_too_old':
      return { label: getPageMessage(locale, 'settings.plugin.compatibilityState.hostTooOld'), tone: 'danger' };
    case 'unknown':
    default:
      return { label: getPageMessage(locale, 'settings.plugin.compatibilityState.unknown'), tone: 'secondary' };
  }
}

function formatMarketplaceMetric(value: number | null | undefined, locale: string | undefined) {
  if (value === null || value === undefined) {
    return getPageMessage(locale, 'plugins.marketplace.metric.unavailable');
  }
  return new Intl.NumberFormat(resolveDateLocale(locale)).format(value);
}

function openExternalLink(url: string) {
  if (typeof window !== 'undefined') {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

function normalizeOptionalText(value: string) {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function resolveApiErrorCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  const payload = error.payload;
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const directCode = (payload as { error_code?: unknown }).error_code;
  if (typeof directCode === 'string' && directCode.trim()) {
    return directCode;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== 'object') {
    return null;
  }
  const nestedCode = (detail as { error_code?: unknown }).error_code;
  if (typeof nestedCode === 'string' && nestedCode.trim()) {
    return nestedCode;
  }
  return null;
}

function PluginsPageContent() {
  const { currentHouseholdId } = useHouseholdContext();
  const { locale, replacePluginLocales } = useI18n();
  const { themeId, getThemeVersionInfo } = useTheme();
  const [plugins, setPlugins] = useState<PluginRegistryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof settingsApi.listPluginJobs>> | null>(null);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [detailPlugin, setDetailPlugin] = useState<PluginRegistryItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [togglingPluginId, setTogglingPluginId] = useState<string | null>(null);
  const [deletingPluginId, setDeletingPluginId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(getInitialViewMode);
  const [showBuiltinPlugins, setShowBuiltinPlugins] = useState(getInitialShowBuiltinPlugins);
  const [selectedType, setSelectedType] = useState<PluginManifestType | null>(null);
  const [marketSources, setMarketSources] = useState<MarketplaceSourceRead[]>([]);
  const [marketCatalog, setMarketCatalog] = useState<MarketplaceCatalogItemRead[]>([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState('');
  const [marketStatus, setMarketStatus] = useState('');
  const [sourceError, setSourceError] = useState('');
  const [sourceStatus, setSourceStatus] = useState('');
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [installingKey, setInstallingKey] = useState<string | null>(null);
  const [marketplaceBusyInstanceId, setMarketplaceBusyInstanceId] = useState<string | null>(null);
  const [marketplaceOpen, setMarketplaceOpen] = useState(false);
  const [sourceManagerOpen, setSourceManagerOpen] = useState(false);
  const [marketRefreshing, setMarketRefreshing] = useState(false);
  const [marketplaceForm, setMarketplaceForm] = useState<MarketplaceSourceFormState>(createEmptyMarketplaceForm);
  const [zipInstallOpen, setZipInstallOpen] = useState(false);
  const [zipOverwriteConfirmOpen, setZipOverwriteConfirmOpen] = useState(false);
  const [zipSelectedFile, setZipSelectedFile] = useState<File | null>(null);
  const [zipOverwriteFile, setZipOverwriteFile] = useState<File | null>(null);
  const [zipError, setZipError] = useState('');
  const [zipStatus, setZipStatus] = useState('');
  const [zipInstalling, setZipInstalling] = useState(false);
  const [zipInputResetSeed, setZipInputResetSeed] = useState(0);

  const page = useCallback(
    (key: Parameters<typeof getPageMessage>[1], params?: Parameters<typeof getPageMessage>[2]) => getPageMessage(locale, key, params),
    [locale],
  );

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: page('plugins.title') }).catch(() => undefined);
  }, [page]);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(VIEW_MODE_KEY, mode);
    }
  }, []);

  const handleShowBuiltinPluginsChange = useCallback((checked: boolean) => {
    setShowBuiltinPlugins(checked);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SHOW_BUILTIN_PLUGINS_KEY, checked ? 'true' : 'false');
    }
  }, []);

  const sourceFilteredPlugins = useMemo(() => {
    if (showBuiltinPlugins) {
      return plugins;
    }
    return plugins.filter(plugin => plugin.source_type !== 'builtin');
  }, [plugins, showBuiltinPlugins]);

  const filteredPlugins = useMemo(() => {
    if (!selectedType) {
      return sourceFilteredPlugins;
    }
    return sourceFilteredPlugins.filter(plugin => plugin.types.includes(selectedType));
  }, [sourceFilteredPlugins, selectedType]);

  const activeThemePluginId = useMemo(
    () => getThemeVersionInfo(themeId)?.pluginId ?? null,
    [getThemeVersionInfo, themeId],
  );

  const handleTypeFilterChange = useCallback((type: PluginManifestType) => {
    setSelectedType(type);
  }, []);

  const clearTypeFilter = useCallback(() => {
    setSelectedType(null);
  }, []);

  const reloadInstalledPlugins = useCallback(async () => {
    if (!currentHouseholdId) {
      setPlugins([]);
      return;
    }
    const registryResult = await settingsApi.listRegisteredPlugins(currentHouseholdId);
    setPlugins(registryResult.items);
  }, [currentHouseholdId]);

  const reloadMarketplace = useCallback(async () => {
    if (!currentHouseholdId) {
      setMarketSources([]);
      setMarketCatalog([]);
      return;
    }
    const [sourcesResult, catalogResult] = await Promise.all([
      settingsApi.listMarketplaceSources(),
      settingsApi.listMarketplaceCatalog(currentHouseholdId),
    ]);
    setMarketSources(sourcesResult);
    setMarketCatalog(catalogResult.items);
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId) {
      setPlugins([]);
      setMarketSources([]);
      setMarketCatalog([]);
      return;
    }

    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setMarketLoading(true);
      setError('');
      setMarketError('');
      setSourceError('');
      try {
        const [registryResult, sourcesResult, catalogResult] = await Promise.all([
          settingsApi.listRegisteredPlugins(currentHouseholdId),
          settingsApi.listMarketplaceSources(),
          settingsApi.listMarketplaceCatalog(currentHouseholdId),
        ]);
        if (!cancelled) {
          setPlugins(registryResult.items);
          setMarketSources(sourcesResult);
          setMarketCatalog(catalogResult.items);
        }
      } catch (loadError) {
        const message = loadError instanceof ApiError ? loadError.message : page('plugins.loadFailed');
        if (!cancelled) {
          setError(message);
          setMarketError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setMarketLoading(false);
        }
      }
    }

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, page]);

  useEffect(() => {
    if (!currentHouseholdId || !selectedPluginId) {
      setJobs(null);
      return;
    }

    const householdId = currentHouseholdId;
    const pluginId = selectedPluginId;
    let cancelled = false;

    async function loadJobs() {
      setJobsLoading(true);
      try {
        const result = await settingsApi.listPluginJobs(householdId, { plugin_id: pluginId, page_size: 10 });
        if (!cancelled) {
          setJobs(result);
        }
      } catch {
        if (!cancelled) {
          setJobs(null);
        }
      } finally {
        if (!cancelled) {
          setJobsLoading(false);
        }
      }
    }

    void loadJobs();
    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, selectedPluginId]);

  function openPluginDetail(plugin: PluginRegistryItem) {
    setDetailPlugin(plugin);
    setDrawerOpen(true);
  }

  function closePluginDetail() {
    setDrawerOpen(false);
    window.setTimeout(() => setDetailPlugin(null), 300);
  }

  const refreshPluginLocales = useCallback(async () => {
    if (!currentHouseholdId) {
      replacePluginLocales([]);
      return;
    }
    try {
      const response = await settingsApi.listHouseholdLocales(currentHouseholdId);
      replacePluginLocales(response.items);
    } catch {
      replacePluginLocales([]);
    }
  }, [currentHouseholdId, replacePluginLocales]);

  function resetZipInstallTransientState() {
    setZipSelectedFile(null);
    setZipOverwriteFile(null);
    setZipError('');
    setZipStatus('');
    setZipOverwriteConfirmOpen(false);
    setZipInputResetSeed(current => current + 1);
  }

  function handleOpenZipInstallDialog() {
    setZipInstallOpen(true);
    setZipError('');
    setZipStatus('');
  }

  function handleCloseZipInstallDialog() {
    if (zipInstalling) {
      return;
    }
    setZipInstallOpen(false);
    resetZipInstallTransientState();
  }

  function handleZipFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setZipSelectedFile(nextFile);
    setZipOverwriteFile(null);
    setZipError('');
    setZipStatus('');
  }

  const resolveZipInstallStatusMessage = useCallback((result: PluginPackageInstallRead) => {
    if (result.install_action === 'upgraded') {
      return page('plugins.zip.status.upgraded', {
        plugin: result.plugin_name,
        version: result.version,
      });
    }
    if (result.install_action === 'reinstalled') {
      return page('plugins.zip.status.reinstalled', {
        plugin: result.plugin_name,
        version: result.version,
      });
    }
    return page('plugins.zip.status.installed', {
      plugin: result.plugin_name,
      version: result.version,
    });
  }, [page]);

  const installPluginPackageFromZip = useCallback(async (file: File, overwrite: boolean) => {
    if (!currentHouseholdId) {
      return;
    }
    setZipInstalling(true);
    setZipError('');
    setZipStatus('');
    try {
      const result = await settingsApi.installPluginPackage(currentHouseholdId, file, { overwrite });
      await Promise.all([reloadInstalledPlugins(), reloadMarketplace()]);
      await refreshPluginLocales();
      const successMessage = resolveZipInstallStatusMessage(result);
      setError('');
      setStatus(successMessage);
      setZipStatus(successMessage);
      setZipInstallOpen(false);
      resetZipInstallTransientState();
    } catch (installError) {
      const errorCode = resolveApiErrorCode(installError);
      if (!overwrite && errorCode === 'plugin_package_conflict') {
        setZipOverwriteFile(file);
        setZipOverwriteConfirmOpen(true);
        return;
      }
      setZipError(installError instanceof ApiError ? installError.message : page('plugins.operationFailed'));
    } finally {
      setZipInstalling(false);
    }
  }, [
    currentHouseholdId,
    page,
    refreshPluginLocales,
    reloadInstalledPlugins,
    reloadMarketplace,
    resolveZipInstallStatusMessage,
  ]);

  async function handleZipInstallSubmit() {
    if (!zipSelectedFile) {
      setZipError(page('plugins.zip.error.fileRequired'));
      return;
    }
    const fileName = zipSelectedFile.name.toLowerCase();
    if (!fileName.endsWith('.zip')) {
      setZipError(page('plugins.zip.error.onlyZip'));
      return;
    }
    await installPluginPackageFromZip(zipSelectedFile, false);
  }

  async function handleZipOverwriteInstall() {
    if (!zipOverwriteFile) {
      setZipOverwriteConfirmOpen(false);
      return;
    }
    await installPluginPackageFromZip(zipOverwriteFile, true);
  }

  async function handleTogglePlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) {
      return;
    }

    setError('');
    setStatus('');

    if (shouldBlockDisableCurrentThemePlugin(plugin, activeThemePluginId)) {
      setError(page('plugins.themePack.disableInUse'));
      return;
    }

    setTogglingPluginId(plugin.id);

    try {
      const updated = await settingsApi.updatePluginState(currentHouseholdId, plugin.id, { enabled: !plugin.enabled });
      setPlugins(current => current.map(item => (item.id === updated.id ? updated : item)));
      setDetailPlugin(current => (current && current.id === updated.id ? updated : current));
      await reloadMarketplace();
      if (updated.types.includes('locale-pack')) {
        await refreshPluginLocales();
      }
      setStatus(page(updated.enabled ? 'plugins.status.enabled' : 'plugins.status.disabled'));
    } catch (toggleError) {
      setError(toggleError instanceof ApiError ? toggleError.message : page('plugins.operationFailed'));
    } finally {
      setTogglingPluginId(null);
    }
  }

  async function handleDeletePlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) {
      return;
    }

    setError('');
    setStatus('');

    if (shouldBlockDeleteCurrentThemePlugin(plugin, activeThemePluginId)) {
      const message = page('plugins.themePack.deleteInUse');
      setError(message);
      throw new Error(message);
    }

    setDeletingPluginId(plugin.id);

    try {
      await settingsApi.deletePlugin(currentHouseholdId, plugin.id);
      if (selectedPluginId === plugin.id) {
        setSelectedPluginId(null);
      }
      await Promise.all([reloadInstalledPlugins(), reloadMarketplace()]);
      await refreshPluginLocales();
      closePluginDetail();
      setStatus(page('settings.plugin.deleteSuccess', { plugin: plugin.name }));
    } catch (deleteError) {
      const message = deleteError instanceof ApiError
        ? deleteError.message
        : deleteError instanceof Error
          ? deleteError.message
          : page('settings.plugin.deleteFailed');
      setError(message);
      throw deleteError instanceof Error ? deleteError : new Error(message);
    } finally {
      setDeletingPluginId(null);
    }
  }

  async function handleMarketplaceSourceSubmit() {
    if (!marketplaceForm.repo_url.trim()) {
      setSourceError(page('plugins.marketplace.form.repoRequired'));
      return;
    }
    setSourceError('');
    setSourceStatus('');
    try {
      const mirrorRepoUrl = normalizeOptionalText(marketplaceForm.mirror_repo_url);
      await settingsApi.createMarketplaceSource({
        repo_url: marketplaceForm.repo_url.trim(),
        repo_provider: marketplaceForm.repo_provider || null,
        api_base_url: normalizeOptionalText(marketplaceForm.api_base_url),
        branch: normalizeOptionalText(marketplaceForm.branch),
        entry_root: normalizeOptionalText(marketplaceForm.entry_root),
        mirror_repo_url: mirrorRepoUrl,
        mirror_repo_provider: mirrorRepoUrl ? (marketplaceForm.mirror_repo_provider || null) : null,
        mirror_api_base_url: mirrorRepoUrl ? normalizeOptionalText(marketplaceForm.mirror_api_base_url) : null,
      });
      setMarketplaceForm(createEmptyMarketplaceForm());
      await reloadMarketplace();
      setSourceStatus(page('plugins.marketplace.status.sourceAdded'));
    } catch (submitError) {
      setSourceError(submitError instanceof ApiError ? submitError.message : page('plugins.operationFailed'));
    }
  }

  async function handleSyncMarketplaceSource(sourceId: string) {
    setSyncingSourceId(sourceId);
    setSourceError('');
    setSourceStatus('');
    try {
      await settingsApi.syncMarketplaceSource(sourceId);
      await reloadMarketplace();
      setSourceStatus(page('plugins.marketplace.status.synced'));
    } catch (syncError) {
      setSourceError(syncError instanceof ApiError ? syncError.message : page('plugins.operationFailed'));
    } finally {
      setSyncingSourceId(null);
    }
  }

  async function handleRefreshMarketplace() {
    setMarketRefreshing(true);
    setMarketError('');
    setMarketStatus('');
    try {
      await reloadMarketplace();
      setMarketStatus(page('plugins.marketplace.status.refreshed'));
    } catch (refreshError) {
      setMarketError(refreshError instanceof ApiError ? refreshError.message : page('plugins.operationFailed'));
    } finally {
      setMarketRefreshing(false);
    }
  }

  async function handleInstallMarketplacePlugin(item: MarketplaceCatalogItemRead) {
    if (!currentHouseholdId) {
      return;
    }
    const targetVersion = item.version_governance?.latest_compatible_version;
    if (!targetVersion) {
      setMarketError(item.version_governance?.blocked_reason || page('plugins.marketplace.status.noCompatibleVersion'));
      return;
    }
    const installKey = `${item.source_id}:${item.plugin_id}`;
    setInstallingKey(installKey);
    setMarketError('');
    setMarketStatus('');
    try {
      await settingsApi.createMarketplaceInstallTask({
        household_id: currentHouseholdId,
        source_id: item.source_id,
        plugin_id: item.plugin_id,
        version: targetVersion,
      });
      await Promise.all([reloadInstalledPlugins(), reloadMarketplace()]);
      setMarketStatus(page('plugins.marketplace.status.installed', { version: targetVersion }));
    } catch (installError) {
      setMarketError(installError instanceof ApiError ? installError.message : page('plugins.operationFailed'));
    } finally {
      setInstallingKey(null);
    }
  }

  async function handleToggleMarketplaceInstance(item: MarketplaceCatalogItemRead) {
    const instanceId = item.install_state.instance_id;
    if (!instanceId) {
      return;
    }
    setMarketplaceBusyInstanceId(instanceId);
    setMarketError('');
    setMarketStatus('');
    try {
      const nextEnabled = !item.install_state.enabled;
      await settingsApi.setMarketplaceInstanceEnabled(instanceId, { enabled: nextEnabled });
      await Promise.all([reloadInstalledPlugins(), reloadMarketplace()]);
      setMarketStatus(page(nextEnabled ? 'plugins.marketplace.status.enabled' : 'plugins.marketplace.status.disabled'));
    } catch (toggleError) {
      setMarketError(toggleError instanceof ApiError ? toggleError.message : page('plugins.operationFailed'));
    } finally {
      setMarketplaceBusyInstanceId(null);
    }
  }

  async function handleOperateMarketplaceVersion(
    item: MarketplaceCatalogItemRead,
    operation: PluginVersionOperationType,
    targetVersion: string,
  ): Promise<PluginVersionOperationResultRead> {
    if (!currentHouseholdId || !item.install_state.instance_id) {
      throw new Error('marketplace_instance_missing');
    }

    setMarketplaceBusyInstanceId(item.install_state.instance_id);
    setMarketError('');
    setMarketStatus('');

    try {
      const result = await settingsApi.operateMarketplaceInstanceVersion(item.install_state.instance_id, {
        household_id: currentHouseholdId,
        source_id: item.source_id,
        plugin_id: item.plugin_id,
        target_version: targetVersion,
        operation,
      });
      await Promise.all([reloadInstalledPlugins(), reloadMarketplace()]);
      const statusKey = operation === 'upgrade'
        ? 'plugins.marketplace.status.upgraded'
        : 'plugins.marketplace.status.rolledBack';
      const message = result.state_change_reason
        ? page('plugins.marketplace.status.versionChangedWithState', {
            message: page(statusKey, { version: result.target_version }),
            reason: result.state_change_reason,
          })
        : page(statusKey, { version: result.target_version });
      setMarketStatus(message);
      return result;
    } catch (operationError) {
      const message = operationError instanceof ApiError ? operationError.message : page('plugins.operationFailed');
      setMarketError(message);
      throw operationError;
    } finally {
      setMarketplaceBusyInstanceId(null);
    }
  }

  const pluginStats = useMemo(() => {
    const enabled = filteredPlugins.filter(plugin => plugin.enabled).length;
    const total = filteredPlugins.length;
    return { enabled, total, disabled: total - enabled };
  }, [filteredPlugins]);

  const installedPluginMap = useMemo(() => {
    return new Map(plugins.map(plugin => [plugin.id, plugin]));
  }, [plugins]);

  const detailMarketplaceItem = useMemo(() => {
    if (!detailPlugin) {
      return null;
    }
    if (detailPlugin.marketplace_instance_id) {
      const matchedByInstance = marketCatalog.find(item => item.install_state.instance_id === detailPlugin.marketplace_instance_id);
      if (matchedByInstance) {
        return matchedByInstance;
      }
    }
    return marketCatalog.find(item => item.plugin_id === detailPlugin.id && Boolean(item.install_state.instance_id)) ?? null;
  }, [detailPlugin, marketCatalog]);

  useEffect(() => {
    if (!detailPlugin) {
      return;
    }
    const latestPlugin = plugins.find(item => item.id === detailPlugin.id);
    if (latestPlugin && latestPlugin !== detailPlugin) {
      setDetailPlugin(latestPlugin);
    }
  }, [detailPlugin, plugins]);

  function renderMarketplaceCatalogContent() {
    return (
      <div className="plugin-marketplace-modal__body">
        {marketError ? <div className="settings-note settings-note--error"><span>⚠️</span> {marketError}</div> : null}
        {marketStatus ? <div className="settings-note settings-note--success"><span>✅</span> {marketStatus}</div> : null}

        {marketLoading && marketCatalog.length === 0 ? (
          <div className="settings-note">
            <span>⏳</span>
            {' '}
            {page('common.loading')}
          </div>
        ) : null}

        {!marketLoading && marketCatalog.length === 0 ? (
          <EmptyState
            title={page('plugins.marketplace.emptyTitle')}
            description={page('plugins.marketplace.emptyDesc')}
          />
        ) : null}

        {marketCatalog.length > 0 ? (
          <div className="marketplace-grid">
            {marketCatalog.map(item => {
              const trustedInfo = formatMarketplaceTrustedLevel(
                item.trusted_level === 'official' ? 'official' : 'third_party',
                locale,
              );
              const installInfo = formatMarketplaceInstallState(item.install_state, locale);
              const governance = item.version_governance;
              const updateInfo = formatVersionUpdateState(governance?.update_state, locale);
              const compatibilityInfo = formatVersionCompatibilityStatus(governance?.compatibility_status, locale);
              const installKey = `${item.source_id}:${item.plugin_id}`;
              const isInstalling = installingKey === installKey;
              const isBusyInstance = marketplaceBusyInstanceId === item.install_state.instance_id;
              const installedPlugin = installedPluginMap.get(item.plugin_id) ?? null;
              const preferredInstallVersion = governance?.latest_compatible_version ?? null;
              const canInstall = Boolean(preferredInstallVersion);
              const quickUpgradeVersion = governance?.latest_compatible_version ?? null;
              const governanceInstalledVersion = governance?.installed_version ?? null;
              const canEnable =
                item.install_state.instance_id &&
                (item.install_state.enabled || item.install_state.config_status === 'configured');
              const canQuickUpgrade = Boolean(
                item.install_state.instance_id
                && quickUpgradeVersion
                && governanceInstalledVersion
                && quickUpgradeVersion !== governanceInstalledVersion
                && governance?.update_state === 'upgrade_available',
              );
              const toggleLabel = item.install_state.enabled
                ? page('plugins.marketplace.action.disable')
                : page('plugins.marketplace.action.enable');

              return (
                <Card key={installKey} className="marketplace-card">
                  <div className="marketplace-card__header">
                    <div>
                      <div className="marketplace-card__title">
                        <span>{item.name}</span>
                        <span className={`badge badge--${trustedInfo.tone}`}>{trustedInfo.label}</span>
                        <span className={`badge badge--${installInfo.tone}`}>{installInfo.label}</span>
                        <span className={`badge badge--${updateInfo.tone}`}>{updateInfo.label}</span>
                      </div>
                      <div className="marketplace-card__meta">
                        <span>{item.plugin_id}</span>
                        <span>·</span>
                        <span>{item.source_name}</span>
                      </div>
                    </div>
                    <button className="btn btn--ghost btn--sm" onClick={() => openExternalLink(item.source_repo)}>
                      <ExternalLink size={14} />
                      GitHub
                    </button>
                  </div>

                  <p className="marketplace-card__summary">{item.summary}</p>

                  <div className="marketplace-card__metrics">
                    <span><Star size={14} /> {formatMarketplaceMetric(item.repository_metrics?.stargazers_count, locale)}</span>
                    <span><GitFork size={14} /> {formatMarketplaceMetric(item.repository_metrics?.forks_count, locale)}</span>
                    <span><Eye size={14} /> {formatMarketplaceMetric(item.repository_metrics?.views_count, locale)}</span>
                  </div>

                  <div className="marketplace-card__tags">
                    {item.categories.slice(0, 3).map(category => (
                      <span key={category} className="badge badge--secondary">{category}</span>
                    ))}
                    {item.permissions.slice(0, 2).map(permission => (
                      <span key={permission} className="badge badge--info">{permission}</span>
                    ))}
                    <span className={`badge badge--${compatibilityInfo.tone}`}>{compatibilityInfo.label}</span>
                  </div>

                  <div className="plugin-detail-entrypoints">
                    <div className="plugin-detail-entrypoint-item">
                      <span className="plugin-detail-entrypoint-key">{page('settings.plugin.section.installedVersion')}</span>
                      <span className="plugin-detail-entrypoint-value">
                        {formatVersionValue(governance?.installed_version ?? item.install_state.installed_version, locale)}
                      </span>
                    </div>
                    <div className="plugin-detail-entrypoint-item">
                      <span className="plugin-detail-entrypoint-key">{page('settings.plugin.section.latestVersion')}</span>
                      <span className="plugin-detail-entrypoint-value">{formatVersionValue(governance?.latest_version ?? item.latest_version, locale)}</span>
                    </div>
                    <div className="plugin-detail-entrypoint-item">
                      <span className="plugin-detail-entrypoint-key">{page('settings.plugin.section.latestCompatibleVersion')}</span>
                      <span className="plugin-detail-entrypoint-value">{formatVersionValue(governance?.latest_compatible_version, locale)}</span>
                    </div>
                    <div className="plugin-detail-entrypoint-item">
                      <span className="plugin-detail-entrypoint-key">{page('settings.plugin.section.updateState')}</span>
                      <span className="plugin-detail-entrypoint-value">{updateInfo.label}</span>
                    </div>
                  </div>

                  <div className="marketplace-card__actions">
                    {item.install_state.install_status === 'not_installed' || item.install_state.install_status === 'install_failed' ? (
                      <button
                        className="btn btn--primary btn--sm"
                        onClick={() => void handleInstallMarketplacePlugin(item)}
                        disabled={isInstalling || !canInstall}
                      >
                        <Download size={14} />
                        {isInstalling
                          ? page('plugins.marketplace.action.installing')
                          : page('plugins.marketplace.action.installVersion', { version: preferredInstallVersion ?? page('settings.plugin.versionValue.unknown') })}
                      </button>
                    ) : null}

                    {canQuickUpgrade && quickUpgradeVersion ? (
                      <button
                        className="btn btn--primary btn--sm"
                        onClick={() => void handleOperateMarketplaceVersion(item, 'upgrade', quickUpgradeVersion)}
                        disabled={isBusyInstance}
                      >
                        <RefreshCw size={14} className={isBusyInstance ? 'animate-spin' : undefined} />
                        {isBusyInstance
                          ? page('plugins.marketplace.action.updating')
                          : page('plugins.marketplace.action.upgradeVersion', { version: quickUpgradeVersion })}
                      </button>
                    ) : null}

                    {item.install_state.instance_id ? (
                      <button
                        className="btn btn--outline btn--sm"
                        onClick={() => void handleToggleMarketplaceInstance(item)}
                        disabled={isBusyInstance || !canEnable}
                      >
                        <BadgeCheck size={14} />
                        {isBusyInstance ? page('plugins.marketplace.action.updating') : toggleLabel}
                      </button>
                    ) : null}

                    {installedPlugin ? (
                      <button className="btn btn--ghost btn--sm" onClick={() => openPluginDetail(installedPlugin)}>
                        <Settings2 size={14} />
                        {page('plugins.marketplace.action.configure')}
                      </button>
                    ) : null}
                  </div>

                  {governance?.blocked_reason ? (
                    <div className="marketplace-card__hint">{governance.blocked_reason}</div>
                  ) : null}
                  {!item.repository_metrics?.availability.views_count ? (
                    <div className="marketplace-card__hint">{page('plugins.marketplace.viewsHint')}</div>
                  ) : null}
                </Card>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  function renderMarketplaceSourceManagerContent() {
    return (
      <div className="plugin-marketplace-modal__body">
        <Card className="marketplace-panel">
          <div className="marketplace-source-form">
            <div className="marketplace-source-form__section">
              <span className="marketplace-source-form__section-title">{page('plugins.marketplace.form.primarySection')}</span>
              <span className="marketplace-source-form__section-hint">{page('plugins.marketplace.form.primarySectionHint')}</span>
            </div>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.repoProviderLabel')}</span>
              <select
                className="marketplace-source-form__input"
                value={marketplaceForm.repo_provider}
                onChange={event => setMarketplaceForm(current => ({ ...current, repo_provider: event.target.value as MarketplaceRepoProvider | '' }))}
              >
                <option value="">{page('plugins.marketplace.form.autoDetectProvider')}</option>
                {MARKETPLACE_REPO_PROVIDERS.map(provider => (
                  <option key={provider} value={provider}>
                    {formatMarketplaceRepoProvider(provider, locale)}
                  </option>
                ))}
              </select>
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.repoLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.repo_url}
                onChange={event => setMarketplaceForm(current => ({ ...current, repo_url: event.target.value }))}
                placeholder={page('plugins.marketplace.form.repoPlaceholder')}
              />
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.apiBaseUrlLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.api_base_url}
                onChange={event => setMarketplaceForm(current => ({ ...current, api_base_url: event.target.value }))}
                placeholder={page('plugins.marketplace.form.apiBaseUrlPlaceholder')}
              />
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.branchLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.branch}
                onChange={event => setMarketplaceForm(current => ({ ...current, branch: event.target.value }))}
                placeholder={page('plugins.marketplace.form.branchPlaceholder')}
              />
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.entryRootLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.entry_root}
                onChange={event => setMarketplaceForm(current => ({ ...current, entry_root: event.target.value }))}
                placeholder={page('plugins.marketplace.form.entryRootPlaceholder')}
              />
            </label>

            <div className="marketplace-source-form__section">
              <span className="marketplace-source-form__section-title">{page('plugins.marketplace.form.mirrorSection')}</span>
              <span className="marketplace-source-form__section-hint">{page('plugins.marketplace.form.mirrorSectionHint')}</span>
            </div>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.mirrorRepoLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.mirror_repo_url}
                onChange={event => setMarketplaceForm(current => ({ ...current, mirror_repo_url: event.target.value }))}
                placeholder={page('plugins.marketplace.form.mirrorRepoPlaceholder')}
              />
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.mirrorProviderLabel')}</span>
              <select
                className="marketplace-source-form__input"
                value={marketplaceForm.mirror_repo_provider}
                onChange={event => setMarketplaceForm(current => ({ ...current, mirror_repo_provider: event.target.value as MarketplaceRepoProvider | '' }))}
              >
                <option value="">{page('plugins.marketplace.form.autoDetectProvider')}</option>
                {MARKETPLACE_REPO_PROVIDERS.map(provider => (
                  <option key={provider} value={provider}>
                    {formatMarketplaceRepoProvider(provider, locale)}
                  </option>
                ))}
              </select>
            </label>

            <label className="marketplace-source-form__field">
              <span className="marketplace-source-form__label">{page('plugins.marketplace.form.mirrorApiBaseUrlLabel')}</span>
              <input
                className="marketplace-source-form__input"
                value={marketplaceForm.mirror_api_base_url}
                onChange={event => setMarketplaceForm(current => ({ ...current, mirror_api_base_url: event.target.value }))}
                placeholder={page('plugins.marketplace.form.mirrorApiBaseUrlPlaceholder')}
              />
            </label>

            <button className="btn btn--primary btn--sm marketplace-source-form__submit" onClick={() => void handleMarketplaceSourceSubmit()}>
              <Package size={14} />
              {page('plugins.marketplace.form.add')}
            </button>
          </div>

          {sourceError ? <div className="settings-note settings-note--error"><span>⚠️</span> {sourceError}</div> : null}
          {sourceStatus ? <div className="settings-note settings-note--success"><span>✅</span> {sourceStatus}</div> : null}

          <div className="marketplace-sources">
            {marketSources.map(source => {
              const trustedInfo = formatMarketplaceTrustedLevel(source.trusted_level, locale);
              const syncInfo = formatMarketplaceSyncStatus(source.last_sync_status, locale);
              const isSyncing = syncingSourceId === source.source_id;
              const repoProviderLabel = formatMarketplaceRepoProvider(source.repo_provider, locale);
              const mirrorProviderLabel = source.mirror_repo_provider ? formatMarketplaceRepoProvider(source.mirror_repo_provider, locale) : null;
              const isEffectiveRepoDifferent = source.effective_repo_url !== source.repo_url;
              const mirrorRepoUrl = source.mirror_repo_url;

              return (
                <div key={source.source_id} className="marketplace-source-card">
                  <div className="marketplace-source-card__top">
                    <div>
                      <div className="marketplace-source-card__title">
                        <span>{source.name}</span>
                        <span className={`badge badge--${trustedInfo.tone}`}>{trustedInfo.label}</span>
                        <span className={`badge badge--${syncInfo.tone}`}>{syncInfo.label}</span>
                        <span className="badge badge--info">{repoProviderLabel}</span>
                      </div>
                      <div className="marketplace-source-card__meta">
                        {source.owner ? <span>{page('plugins.marketplace.source.ownerValue', { owner: source.owner })}</span> : null}
                        {source.branch ? <span>{page('plugins.marketplace.source.branchValue', { branch: source.branch })}</span> : null}
                        {source.entry_root ? <span>{page('plugins.marketplace.source.entryRootValue', { entryRoot: source.entry_root })}</span> : null}
                      </div>
                    </div>
                    <button
                      className="btn btn--outline btn--sm"
                      onClick={() => void handleSyncMarketplaceSource(source.source_id)}
                      disabled={isSyncing}
                    >
                      <RefreshCw size={14} className={isSyncing ? 'animate-spin' : undefined} />
                      {isSyncing ? page('plugins.marketplace.action.syncing') : page('plugins.marketplace.action.sync')}
                    </button>
                  </div>
                  <div className="marketplace-source-card__details">
                    <div className="marketplace-source-card__detail">
                      <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.repoLabel')}</span>
                      <button type="button" className="marketplace-source-card__link" onClick={() => openExternalLink(source.repo_url)}>
                        <span>{source.repo_url}</span>
                        <ExternalLink size={14} />
                      </button>
                    </div>
                    {source.api_base_url ? (
                      <div className="marketplace-source-card__detail">
                        <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.apiBaseUrlLabel')}</span>
                        <span className="marketplace-source-card__detail-value">{source.api_base_url}</span>
                      </div>
                    ) : null}
                    {isEffectiveRepoDifferent ? (
                      <div className="marketplace-source-card__detail">
                        <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.effectiveRepoLabel')}</span>
                        <button type="button" className="marketplace-source-card__link" onClick={() => openExternalLink(source.effective_repo_url)}>
                          <span>{source.effective_repo_url}</span>
                          <ExternalLink size={14} />
                        </button>
                      </div>
                    ) : null}
                    {mirrorRepoUrl ? (
                      <div className="marketplace-source-card__detail">
                        <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.mirrorRepoLabel')}</span>
                        <button type="button" className="marketplace-source-card__link" onClick={() => openExternalLink(mirrorRepoUrl)}>
                          <span>{mirrorRepoUrl}</span>
                          <ExternalLink size={14} />
                        </button>
                      </div>
                    ) : null}
                    {mirrorProviderLabel ? (
                      <div className="marketplace-source-card__detail">
                        <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.mirrorProviderLabel')}</span>
                        <span className="marketplace-source-card__detail-value">{mirrorProviderLabel}</span>
                      </div>
                    ) : null}
                    {source.mirror_api_base_url ? (
                      <div className="marketplace-source-card__detail">
                        <span className="marketplace-source-card__detail-label">{page('plugins.marketplace.source.mirrorApiBaseUrlLabel')}</span>
                        <span className="marketplace-source-card__detail-value">{source.mirror_api_base_url}</span>
                      </div>
                    ) : null}
                  </div>
                  <div className="marketplace-source-card__foot">
                    <span>{page('plugins.marketplace.lastSynced')}</span>
                    <span>{formatTimestamp(source.last_synced_at, locale)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <SettingsPageShell activeKey="plugins">
      <div className="settings-page">
        <div className="plugins-page-actions">
          <div className="plugin-builtin-toggle">
            <span className="plugin-builtin-toggle__label">{page('plugins.filter.showBuiltin')}</span>
            <button
              type="button"
              className={`toggle-switch toggle-switch--compact ${showBuiltinPlugins ? 'toggle-switch--on' : ''}`}
              onClick={() => handleShowBuiltinPluginsChange(!showBuiltinPlugins)}
              aria-checked={showBuiltinPlugins}
              aria-label={page('plugins.filter.showBuiltin')}
              role="switch"
            >
              <div className="toggle-switch__thumb" />
            </button>
          </div>
          <div className="plugins-page-actions__actions">
            <button className="btn btn--outline" onClick={handleOpenZipInstallDialog}>
              <Download size={16} />
              {page('plugins.zip.openButton')}
            </button>
            <button className="btn btn--primary" onClick={() => setMarketplaceOpen(true)}>
              <Package size={16} />
              {page('plugins.marketplace.openButton')}
            </button>
          </div>
        </div>

        <Section title={page('plugins.section.installed')}>
          {plugins.length > 0 ? (
            <div className="plugin-toolbar">
              <div className="plugin-view-toggle">
                <button
                  className={`plugin-view-toggle__btn ${viewMode === 'card' ? 'plugin-view-toggle__btn--active' : ''}`}
                  onClick={() => handleViewModeChange('card')}
                  title={page('plugins.view.card')}
                >
                  ▥
                </button>
                <button
                  className={`plugin-view-toggle__btn ${viewMode === 'list' ? 'plugin-view-toggle__btn--active' : ''}`}
                  onClick={() => handleViewModeChange('list')}
                  title={page('plugins.view.list')}
                >
                  ▤
                </button>
              </div>

              <div className="plugin-filter">
                <span className="plugin-filter__label">{page('plugins.filter.label')}</span>
                <div className="plugin-filter__chips">
                  <button
                    className={`plugin-filter__chip ${selectedType === null ? 'plugin-filter__chip--active' : ''}`}
                    onClick={clearTypeFilter}
                  >
                    {page('plugins.filter.all')}
                  </button>
                  {FILTERABLE_TYPES.map(type => (
                    <button
                      key={type}
                      className={`plugin-filter__chip ${selectedType === type ? 'plugin-filter__chip--active' : ''}`}
                      onClick={() => handleTypeFilterChange(type)}
                    >
                      {formatPluginType(type, locale)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : null}

          {plugins.length > 0 ? (
            <Card className="plugin-stats-card">
              <div className="plugin-stats">
                <div className="plugin-stat">
                  <span className="plugin-stat__value">{pluginStats.total}</span>
                  <span className="plugin-stat__label">{page('plugins.stats.total')}</span>
                </div>
                <div className="plugin-stat">
                  <span className="plugin-stat__value plugin-stat__value--success">{pluginStats.enabled}</span>
                  <span className="plugin-stat__label">{page('plugins.status.enabled')}</span>
                </div>
                <div className="plugin-stat">
                  <span className="plugin-stat__value plugin-stat__value--secondary">{pluginStats.disabled}</span>
                  <span className="plugin-stat__label">{page('plugins.status.disabled')}</span>
                </div>
                {selectedType !== null ? (
                  <div className="plugin-stat">
                    <span className="plugin-stat__value">{filteredPlugins.length}</span>
                    <span className="plugin-stat__label">{page('plugins.stats.filtered')}</span>
                  </div>
                ) : null}
              </div>
            </Card>
          ) : null}

          {loading && plugins.length === 0 ? (
            <div className="settings-note">
              <span>⏳</span>
              {' '}
              {page('common.loading')}
            </div>
          ) : null}
          {error ? <div className="settings-note settings-note--error"><span>⚠️</span> {error}</div> : null}
          {status ? <div className="settings-note settings-note--success"><span>✅</span> {status}</div> : null}
          {!loading && plugins.length === 0 && !error ? (
            <EmptyState
              title={page('plugins.empty.none')}
              description={page('plugins.empty.noneDesc')}
            />
          ) : null}
          {!loading && plugins.length > 0 && filteredPlugins.length === 0 ? (
            <EmptyState
              title={page('plugins.empty.filtered')}
              description={page('plugins.empty.filteredDesc')}
            />
          ) : null}

          {viewMode === 'card' && filteredPlugins.length > 0 ? (
            <div className="plugin-list">
              {filteredPlugins.map(plugin => {
                const sourceInfo = formatSourceType(plugin.source_type, locale);
                const riskInfo = formatRiskLevel(plugin.risk_level, locale);
                const isEnabled = plugin.enabled;
                const isToggling = togglingPluginId === plugin.id;
                const isSelected = selectedPluginId === plugin.id;
                const iconClass = `plugin-card__icon plugin-card__icon--${plugin.source_type}`;

                return (
                  <Card key={plugin.id} className={`plugin-card ${isSelected ? 'plugin-card--expanded' : ''}`}>
                    <div className="plugin-card__header">
                      <div className={iconClass}>{renderPluginIcon(plugin.source_type)}</div>
                      <div className="plugin-card__info">
                        <div className="plugin-card__title-row">
                          <span className="plugin-card__name">{plugin.name}</span>
                        </div>
                        <div className="plugin-card__meta">
                          <span>{plugin.id}</span>
                          <span>·</span>
                          <span>v{plugin.version}</span>
                        </div>
                      </div>
                      <div className="plugin-card__toggle">
                        <div
                          className={`toggle-switch toggle-switch--compact ${isEnabled ? 'toggle-switch--on' : ''} ${isToggling ? 'toggle-switch--loading' : ''}`}
                          onClick={() => !isToggling && void handleTogglePlugin(plugin)}
                          title={page(isEnabled ? 'settings.plugin.disable' : 'settings.plugin.enable')}
                        >
                          <div className="toggle-switch__thumb" />
                        </div>
                      </div>
                    </div>

                    <div className="plugin-card__tags">
                      <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
                      <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
                      {plugin.types.slice(0, 2).map(type => (
                        <span key={type} className="badge badge--secondary">{formatPluginType(type, locale)}</span>
                      ))}
                      {plugin.types.length > 2 ? <span className="badge badge--secondary">+{plugin.types.length - 2}</span> : null}
                    </div>

                    <div className="plugin-card__footer">
                      <button className="btn btn--ghost btn--sm" onClick={() => openPluginDetail(plugin)}>
                        {page('plugins.action.details')}
                      </button>
                      <button
                        className="btn btn--outline btn--sm"
                        onClick={() => setSelectedPluginId(isSelected ? null : plugin.id)}
                        disabled={jobsLoading}
                      >
                        {page('plugins.action.jobs')}
                      </button>
                    </div>

                    {isSelected ? (
                      <div className="plugin-card__jobs">
                        <h4>{getPageMessage(locale, 'settings.plugin.section.jobs')}</h4>
                        {jobsLoading ? (
                          <div className="settings-note">{getPageMessage(locale, 'settings.plugin.section.loadingJobs')}</div>
                        ) : jobs && jobs.items.length > 0 ? (
                          <div className="plugin-job-list">
                            {jobs.items.map(item => {
                              const jobStatus = formatJobStatus(item.job.status, locale);
                              return (
                                <div key={item.job.id} className="plugin-job-item">
                                  <div className="plugin-job-item__info">
                                    <span className="plugin-job-item__trigger">{item.job.trigger}</span>
                                    <span className={`badge badge--${jobStatus.tone}`}>{jobStatus.label}</span>
                                  </div>
                                  <div className="plugin-job-item__meta">
                                    <span>{formatTimestamp(item.job.created_at, locale)}</span>
                                    <span>·</span>
                                    <span>
                                      {getPageMessage(locale, 'settings.plugin.section.attempts')}
                                      ：
                                      {item.job.current_attempt}/{item.job.max_attempts}
                                    </span>
                                  </div>
                                  {item.job.last_error_message ? <div className="plugin-job-item__error">{item.job.last_error_message}</div> : null}
                                  {item.allowed_actions.length > 0 ? (
                                    <div className="plugin-job-item__actions">
                                      {item.allowed_actions.includes('retry') ? <button className="btn btn--outline btn--sm">{page('plugins.action.retry')}</button> : null}
                                      {item.allowed_actions.includes('confirm') ? <button className="btn btn--outline btn--sm">{page('plugins.action.confirm')}</button> : null}
                                      {item.allowed_actions.includes('cancel') ? <button className="btn btn--outline btn--sm">{page('plugins.action.cancel')}</button> : null}
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="settings-note">{getPageMessage(locale, 'settings.plugin.section.noJobs')}</div>
                        )}
                      </div>
                    ) : null}
                  </Card>
                );
              })}
            </div>
          ) : null}

          {viewMode === 'list' && filteredPlugins.length > 0 ? (
            <div className="plugin-table-wrapper">
              <table className="plugin-table">
                <thead>
                  <tr>
                    <th className="plugin-table__th plugin-table__th--name">{page('plugins.table.name')}</th>
                    <th className="plugin-table__th plugin-table__th--types">{page('plugins.table.type')}</th>
                    <th className="plugin-table__th plugin-table__th--source">{page('plugins.table.source')}</th>
                    <th className="plugin-table__th plugin-table__th--risk">{page('plugins.table.risk')}</th>
                    <th className="plugin-table__th plugin-table__th--status">{page('plugins.table.status')}</th>
                    <th className="plugin-table__th plugin-table__th--actions">{page('plugins.table.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPlugins.map(plugin => {
                    const sourceInfo = formatSourceType(plugin.source_type, locale);
                    const riskInfo = formatRiskLevel(plugin.risk_level, locale);
                    const isEnabled = plugin.enabled;
                    const isToggling = togglingPluginId === plugin.id;

                    return (
                      <tr key={plugin.id} className="plugin-table__row">
                        <td className="plugin-table__td plugin-table__td--name">
                          <div className="plugin-table__name-cell">
                            <span className="plugin-table__name">{plugin.name}</span>
                            <span className="plugin-table__id">{plugin.id} · v{plugin.version}</span>
                          </div>
                        </td>
                        <td className="plugin-table__td plugin-table__td--types">
                          {plugin.types.map(type => formatPluginType(type, locale)).join('、')}
                        </td>
                        <td className="plugin-table__td plugin-table__td--source">
                          <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
                        </td>
                        <td className="plugin-table__td plugin-table__td--risk">
                          <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
                        </td>
                        <td className="plugin-table__td plugin-table__td--status">
                          <div
                            className={`toggle-switch toggle-switch--compact ${isEnabled ? 'toggle-switch--on' : ''} ${isToggling ? 'toggle-switch--loading' : ''}`}
                            onClick={() => !isToggling && void handleTogglePlugin(plugin)}
                            title={page(isEnabled ? 'settings.plugin.disable' : 'settings.plugin.enable')}
                          >
                            <div className="toggle-switch__thumb" />
                          </div>
                        </td>
                        <td className="plugin-table__td plugin-table__td--actions">
                          <button className="btn btn--ghost btn--sm" onClick={() => openPluginDetail(plugin)}>
                            {page('plugins.action.details')}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </Section>

        <SettingsDialog
          open={zipInstallOpen}
          title={page('plugins.zip.dialogTitle')}
          description={page('plugins.zip.dialogDesc')}
          className="plugin-marketplace-source-modal"
          headerExtra={(
            <button
              type="button"
              className="member-modal__close"
              onClick={handleCloseZipInstallDialog}
              aria-label={page('plugins.zip.dialogClose')}
              disabled={zipInstalling}
            >
              <X size={16} />
            </button>
          )}
          onClose={handleCloseZipInstallDialog}
        >
          <div className="plugin-marketplace-source-modal__body">
            {zipError ? <div className="settings-note settings-note--error">{zipError}</div> : null}
            {zipStatus ? <div className="settings-note settings-note--success">{zipStatus}</div> : null}
            <div className="settings-form-grid">
              <div className="settings-form-field settings-form-field--full">
                <label className="settings-form-label">
                  {page('plugins.zip.fileLabel')}
                </label>
                <div className="file-upload-wrapper">
                  <input
                    key={zipInputResetSeed}
                    id="plugin-zip-package"
                    type="file"
                    accept=".zip,application/zip"
                    onChange={handleZipFileChange}
                    disabled={zipInstalling}
                    className="file-upload-wrapper__input"
                  />
                  <label htmlFor="plugin-zip-package" className="file-upload-wrapper__button">
                    <Package size={18} />
                    <span>{page('plugins.zip.selectFile')}</span>
                  </label>
                  {zipSelectedFile ? (
                    <span className="file-upload-wrapper__filename">{zipSelectedFile.name}</span>
                  ) : (
                    <span className="file-upload-wrapper__placeholder">{page('plugins.zip.fileHint')}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="plugin-marketplace-source-form__actions">
              <button
                type="button"
                className="btn btn--outline"
                onClick={handleCloseZipInstallDialog}
                disabled={zipInstalling}
              >
                {page('plugins.action.cancel')}
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => void handleZipInstallSubmit()}
                disabled={zipInstalling}
              >
                {page(zipInstalling ? 'plugins.zip.action.installing' : 'plugins.zip.action.install')}
              </button>
            </div>
          </div>
        </SettingsDialog>

        <SettingsDialog
          open={zipOverwriteConfirmOpen}
          title={page('plugins.zip.overwriteDialogTitle')}
          description={page('plugins.zip.overwriteDialogDesc')}
          className="plugin-marketplace-source-modal"
          headerExtra={(
            <button
              type="button"
              className="member-modal__close"
              onClick={() => {
                if (!zipInstalling) {
                  setZipOverwriteConfirmOpen(false);
                  setZipOverwriteFile(null);
                }
              }}
              aria-label={page('plugins.zip.overwriteDialogClose')}
              disabled={zipInstalling}
            >
              <X size={16} />
            </button>
          )}
          onClose={() => {
            if (!zipInstalling) {
              setZipOverwriteConfirmOpen(false);
              setZipOverwriteFile(null);
            }
          }}
        >
          <div className="plugin-marketplace-source-modal__body">
            <div className="settings-note settings-note--warning">
              {page('plugins.zip.overwriteConfirmText', { file: zipOverwriteFile?.name ?? '' })}
            </div>
            <div className="plugin-marketplace-source-form__actions">
              <button
                type="button"
                className="btn btn--outline"
                onClick={() => {
                  if (!zipInstalling) {
                    setZipOverwriteConfirmOpen(false);
                    setZipOverwriteFile(null);
                  }
                }}
                disabled={zipInstalling}
              >
                {page('plugins.action.cancel')}
              </button>
              <button
                type="button"
                className="btn btn--danger"
                onClick={() => void handleZipOverwriteInstall()}
                disabled={zipInstalling}
              >
                {page(zipInstalling ? 'plugins.zip.action.installing' : 'plugins.zip.action.overwriteInstall')}
              </button>
            </div>
          </div>
        </SettingsDialog>

        <SettingsDialog
          open={marketplaceOpen}
          title={page('plugins.marketplace.panelTitle')}
          description={page('plugins.marketplace.panelDesc')}
          className="plugin-marketplace-modal"
          headerExtra={(
            <div className="plugin-marketplace-modal__header-actions">
              <button
                type="button"
                className="btn btn--outline btn--sm plugin-marketplace-modal__action-btn"
                onClick={() => void handleRefreshMarketplace()}
                disabled={marketRefreshing}
              >
                <RefreshCw size={14} className={marketRefreshing ? 'animate-spin' : undefined} />
                {page('plugins.marketplace.action.refresh')}
              </button>
              <button
                type="button"
                className="btn btn--primary btn--sm plugin-marketplace-modal__action-btn"
                onClick={() => setSourceManagerOpen(true)}
              >
                <Settings2 size={14} />
                {page('plugins.marketplace.action.sourceSettings')}
              </button>
              <button
                type="button"
                className="member-modal__close"
                onClick={() => setMarketplaceOpen(false)}
                aria-label={page('plugins.marketplace.modalClose')}
              >
                <X size={16} />
              </button>
            </div>
          )}
          onClose={() => setMarketplaceOpen(false)}
        >
          {renderMarketplaceCatalogContent()}
        </SettingsDialog>

        <SettingsDialog
          open={sourceManagerOpen}
          title={page('plugins.marketplace.sourceDialogTitle')}
          description={page('plugins.marketplace.sourceDialogDesc')}
          className="plugin-marketplace-source-modal"
          headerExtra={(
            <button
              type="button"
              className="member-modal__close"
              onClick={() => setSourceManagerOpen(false)}
              aria-label={page('plugins.marketplace.sourceDialogClose')}
            >
              <X size={16} />
            </button>
          )}
          onClose={() => setSourceManagerOpen(false)}
        >
          {renderMarketplaceSourceManagerContent()}
        </SettingsDialog>

        <PluginDetailDrawer
          plugin={detailPlugin}
          marketplaceItem={detailMarketplaceItem}
          householdId={currentHouseholdId}
          isOpen={drawerOpen}
          onClose={closePluginDetail}
          isEnabled={detailPlugin?.enabled ?? false}
          onToggle={(plugin) => {
            void handleTogglePlugin(plugin);
            closePluginDetail();
          }}
          onOperateMarketplaceVersion={handleOperateMarketplaceVersion}
          isToggling={togglingPluginId === detailPlugin?.id}
          onDelete={handleDeletePlugin}
          isDeleting={deletingPluginId === detailPlugin?.id}
          canDelete={detailPlugin?.source_type !== 'builtin'}
        />
      </div>
    </SettingsPageShell>
  );
}

export default function PluginsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/plugins/index">
      <PluginsPageContent />
    </GuardedPage>
  );
}
