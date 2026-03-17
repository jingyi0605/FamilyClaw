import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  MarketplaceCatalogItemRead,
  MarketplaceVersionEntry,
  PluginJobListItemRead,
  PluginJobListRead,
  PluginManifestType,
  PluginRegistryItem,
  PluginRiskLevel,
  PluginSourceType,
  PluginVersionGovernanceRead,
  PluginVersionOperationResultRead,
  PluginVersionOperationType,
} from '../settingsTypes';

function resolveDateLocale(locale: string | undefined) {
  if (locale?.toLowerCase().startsWith('en')) return 'en-US';
  if (locale?.toLowerCase().startsWith('zh-tw')) return 'zh-TW';
  return 'zh-CN';
}

function formatSourceType(sourceType: PluginSourceType, locale: string | undefined) {
  switch (sourceType) {
    case 'builtin':
      return { label: getPageMessage(locale, 'settings.plugin.source.builtin'), tone: 'info' as const };
    case 'official':
      return { label: getPageMessage(locale, 'settings.plugin.source.official'), tone: 'success' as const };
    case 'third_party':
      return { label: getPageMessage(locale, 'settings.plugin.source.thirdParty'), tone: 'warning' as const };
    default:
      return { label: sourceType, tone: 'info' as const };
  }
}

function formatRiskLevel(riskLevel: PluginRiskLevel, locale: string | undefined) {
  switch (riskLevel) {
    case 'low':
      return {
        label: getPageMessage(locale, 'settings.plugin.risk.low'),
        tone: 'success' as const,
        desc: getPageMessage(locale, 'settings.plugin.risk.lowDesc'),
      };
    case 'medium':
      return {
        label: getPageMessage(locale, 'settings.plugin.risk.medium'),
        tone: 'warning' as const,
        desc: getPageMessage(locale, 'settings.plugin.risk.mediumDesc'),
      };
    case 'high':
      return {
        label: getPageMessage(locale, 'settings.plugin.risk.high'),
        tone: 'danger' as const,
        desc: getPageMessage(locale, 'settings.plugin.risk.highDesc'),
      };
    default:
      return { label: riskLevel, tone: 'warning' as const, desc: '' };
  }
}

function formatJobStatus(status: string, locale: string | undefined) {
  switch (status) {
    case 'succeeded':
      return { label: getPageMessage(locale, 'settings.plugin.job.succeeded'), tone: 'success' as const };
    case 'queued':
      return { label: getPageMessage(locale, 'settings.plugin.job.queued'), tone: 'warning' as const };
    case 'running':
      return { label: getPageMessage(locale, 'settings.plugin.job.running'), tone: 'warning' as const };
    case 'retry_waiting':
      return { label: getPageMessage(locale, 'settings.plugin.job.retryWaiting'), tone: 'warning' as const };
    case 'waiting_response':
      return { label: getPageMessage(locale, 'settings.plugin.job.waitingResponse'), tone: 'warning' as const };
    case 'failed':
      return { label: getPageMessage(locale, 'settings.plugin.job.failed'), tone: 'danger' as const };
    case 'cancelled':
      return { label: getPageMessage(locale, 'settings.plugin.job.cancelled'), tone: 'secondary' as const };
    default:
      return { label: status, tone: 'secondary' as const };
  }
}

function formatPluginType(type: PluginManifestType, locale: string | undefined) {
  const keyMap: Record<PluginManifestType, keyof typeof import('../../../runtime/h5-shell/i18n/pageMessages.en-US').PAGE_MESSAGES_EN_US> = {
    connector: 'settings.plugin.type.connector',
    'memory-ingestor': 'settings.plugin.type.memoryIngestor',
    action: 'settings.plugin.type.action',
    'agent-skill': 'settings.plugin.type.agentSkill',
    channel: 'settings.plugin.type.channel',
    'locale-pack': 'settings.plugin.type.localePack',
    'region-provider': 'settings.plugin.type.regionProvider',
    'theme-pack': 'settings.plugin.type.themePack',
    'ai-provider': 'settings.plugin.type.aiProvider',
  };
  return getPageMessage(locale, keyMap[type]);
}

function formatTimestamp(value: string | null, locale: string | undefined) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString(resolveDateLocale(locale));
  } catch {
    return value;
  }
}

function formatUpdateState(state: string | null | undefined, locale: string | undefined) {
  switch (state) {
    case 'up_to_date':
      return getPageMessage(locale, 'settings.plugin.versionState.upToDate');
    case 'upgrade_available':
    case 'update_available':
      return getPageMessage(locale, 'settings.plugin.versionState.upgradeAvailable');
    case 'upgrade_blocked':
      return getPageMessage(locale, 'settings.plugin.versionState.upgradeBlocked');
    case 'installed_newer_than_market':
      return getPageMessage(locale, 'settings.plugin.versionState.installedNewerThanMarket');
    case 'not_market_managed':
      return getPageMessage(locale, 'settings.plugin.versionState.notMarketManaged');
    case 'unknown':
      return getPageMessage(locale, 'settings.plugin.versionState.unknown');
    default:
      return state ?? getPageMessage(locale, 'settings.plugin.versionState.unknown');
  }
}

function formatCompatibilityStatus(state: string | null | undefined, locale: string | undefined) {
  switch (state) {
    case 'compatible':
      return getPageMessage(locale, 'settings.plugin.compatibilityState.compatible');
    case 'host_too_old':
      return getPageMessage(locale, 'settings.plugin.compatibilityState.hostTooOld');
    case 'unknown':
    default:
      return getPageMessage(locale, 'settings.plugin.compatibilityState.unknown');
  }
}

function formatVersionValue(value: string | null | undefined, locale: string | undefined) {
  if (!value) {
    return getPageMessage(locale, 'settings.plugin.versionValue.unknown');
  }
  return `v${value}`;
}

function buildCompatibilityEntries(
  value: Record<string, unknown> | null | undefined,
  prefix = '',
): Array<{ label: string; value: string }> {
  if (!value) {
    return [];
  }

  const entries: Array<{ label: string; value: string }> = [];

  for (const [key, rawValue] of Object.entries(value)) {
    const nextLabel = prefix ? `${prefix}.${key}` : key;
    if (rawValue === null || rawValue === undefined) {
      continue;
    }
    if (Array.isArray(rawValue)) {
      entries.push({ label: nextLabel, value: rawValue.map(item => String(item)).join(', ') });
      continue;
    }
    if (typeof rawValue === 'object') {
      entries.push(...buildCompatibilityEntries(rawValue as Record<string, unknown>, nextLabel));
      continue;
    }
    entries.push({ label: nextLabel, value: String(rawValue) });
  }

  return entries;
}

export function PluginDetailDrawer(props: {
  plugin: PluginRegistryItem | null;
  marketplaceItem: MarketplaceCatalogItemRead | null;
  householdId: string | null;
  isOpen: boolean;
  onClose: () => void;
  isEnabled: boolean;
  onToggle: (plugin: PluginRegistryItem) => void;
  onOperateMarketplaceVersion: (
    item: MarketplaceCatalogItemRead,
    operation: PluginVersionOperationType,
    targetVersion: string,
  ) => Promise<PluginVersionOperationResultRead>;
  isToggling: boolean;
}) {
  const {
    plugin,
    marketplaceItem,
    householdId,
    isOpen,
    onClose,
    isEnabled,
    onToggle,
    onOperateMarketplaceVersion,
    isToggling,
  } = props;
  const { locale } = useI18n();
  const [jobs, setJobs] = useState<PluginJobListItemRead[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState('');
  const [versionTargets, setVersionTargets] = useState<MarketplaceVersionEntry[]>([]);
  const [versionGovernance, setVersionGovernance] = useState<PluginVersionGovernanceRead | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);
  const [versionError, setVersionError] = useState('');
  const [versionStatus, setVersionStatus] = useState('');
  const [selectedTargetVersion, setSelectedTargetVersion] = useState('');
  const [operatingVersion, setOperatingVersion] = useState<PluginVersionOperationType | null>(null);
  const copy = useMemo(() => ({
    jobsLoadFailed: getPageMessage(locale, 'settings.plugin.jobs.loadFailed'),
    versionLoadFailed: getPageMessage(locale, 'settings.plugin.versionSwitch.loadFailed'),
    enabled: getPageMessage(locale, 'settings.plugin.enabled'),
    disabled: getPageMessage(locale, 'settings.plugin.disabled'),
    thirdPartyTitle: getPageMessage(locale, 'settings.plugin.thirdPartyTitle'),
    thirdPartyDesc: getPageMessage(locale, 'settings.plugin.thirdPartyDesc'),
    highRiskTitle: getPageMessage(locale, 'settings.plugin.highRiskTitle'),
    waitingTitle: getPageMessage(locale, 'settings.plugin.waitingTitle'),
    waitingDesc: getPageMessage(locale, 'settings.plugin.waitingDesc'),
    latestFailedTitle: getPageMessage(locale, 'settings.plugin.latestFailedTitle'),
    disabledTitle: getPageMessage(locale, 'settings.plugin.disabledTitle'),
    disabledDesc: getPageMessage(locale, 'settings.plugin.disabledDesc'),
    basics: getPageMessage(locale, 'settings.plugin.section.basics'),
    version: getPageMessage(locale, 'settings.plugin.section.version'),
    installedVersion: getPageMessage(locale, 'settings.plugin.section.installedVersion'),
    latestVersion: getPageMessage(locale, 'settings.plugin.section.latestVersion'),
    latestCompatibleVersion: getPageMessage(locale, 'settings.plugin.section.latestCompatibleVersion'),
    updateState: getPageMessage(locale, 'settings.plugin.section.updateState'),
    compatibilityState: getPageMessage(locale, 'settings.plugin.section.compatibilityState'),
    blockedReason: getPageMessage(locale, 'settings.plugin.section.blockedReason'),
    versionGovernance: getPageMessage(locale, 'settings.plugin.section.versionGovernance'),
    compatibility: getPageMessage(locale, 'settings.plugin.section.compatibility'),
    noCompatibility: getPageMessage(locale, 'settings.plugin.section.noCompatibility'),
    type: getPageMessage(locale, 'settings.plugin.section.type'),
    source: getPageMessage(locale, 'settings.plugin.section.source'),
    permissions: getPageMessage(locale, 'settings.plugin.section.permissions'),
    noPermissions: getPageMessage(locale, 'settings.plugin.section.noPermissions'),
    triggers: getPageMessage(locale, 'settings.plugin.section.triggers'),
    entrypoints: getPageMessage(locale, 'settings.plugin.section.entrypoints'),
    locales: getPageMessage(locale, 'settings.plugin.section.locales'),
    jobs: getPageMessage(locale, 'settings.plugin.section.jobs'),
    loadingJobs: getPageMessage(locale, 'settings.plugin.section.loadingJobs'),
    attempts: getPageMessage(locale, 'settings.plugin.section.attempts'),
    noJobs: getPageMessage(locale, 'settings.plugin.section.noJobs'),
    close: getPageMessage(locale, 'settings.plugin.close'),
    processing: getPageMessage(locale, 'settings.plugin.processing'),
    disable: getPageMessage(locale, 'settings.plugin.disable'),
    enable: getPageMessage(locale, 'settings.plugin.enable'),
    targetVersion: getPageMessage(locale, 'settings.plugin.versionSwitch.targetVersion'),
    targetVersionPlaceholder: getPageMessage(locale, 'settings.plugin.versionSwitch.targetVersionPlaceholder'),
    loadingVersionInfo: getPageMessage(locale, 'settings.plugin.versionSwitch.loading'),
    noVersionTargets: getPageMessage(locale, 'settings.plugin.versionSwitch.noTargets'),
    upgrade: getPageMessage(locale, 'plugins.marketplace.action.upgrade'),
    rollback: getPageMessage(locale, 'plugins.marketplace.action.rollback'),
    upgradeProcessing: getPageMessage(locale, 'plugins.marketplace.action.upgrading'),
    rollbackProcessing: getPageMessage(locale, 'plugins.marketplace.action.rollingBack'),
  }), [locale]);

  useEffect(() => {
    if (!householdId || !plugin || !isOpen) {
      setJobs([]);
      return;
    }

    const activeHouseholdId = householdId;
    const activePlugin = plugin;
    let cancelled = false;

    async function loadJobs() {
      setJobsLoading(true);
      setJobsError('');
      try {
        const result: PluginJobListRead = await settingsApi.listPluginJobs(activeHouseholdId, {
          plugin_id: activePlugin.id,
          page_size: 10,
        });
        if (!cancelled) {
          setJobs(result.items);
        }
      } catch (error) {
        if (!cancelled) {
          setJobsError(error instanceof ApiError ? error.message : copy.jobsLoadFailed);
          setJobs([]);
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
  }, [copy.jobsLoadFailed, householdId, isOpen, plugin]);

  useEffect(() => {
    if (!plugin || !isOpen) {
      setVersionTargets([]);
      setVersionGovernance(null);
      setVersionLoading(false);
      setVersionError('');
      setVersionStatus('');
      setSelectedTargetVersion('');
      setOperatingVersion(null);
      return;
    }

    setVersionGovernance(marketplaceItem?.version_governance ?? plugin.version_governance ?? null);
    setVersionStatus('');
    setVersionError('');
    setSelectedTargetVersion('');

    if (!householdId || !marketplaceItem) {
      setVersionTargets([]);
      setVersionLoading(false);
      return;
    }

    const activeMarketplaceItem = marketplaceItem;
    const activePlugin = plugin;
    const activeHouseholdId = householdId;
    let cancelled = false;

    async function loadVersionInfo() {
      setVersionLoading(true);
      const [detailResult, governanceResult] = await Promise.allSettled([
        settingsApi.getMarketplaceEntryDetail(activeMarketplaceItem.source_id, activeMarketplaceItem.plugin_id, activeHouseholdId),
        settingsApi.getMarketplaceVersionGovernance(activeMarketplaceItem.source_id, activeMarketplaceItem.plugin_id, activeHouseholdId),
      ]);

      if (cancelled) {
        return;
      }

      let hasError = false;

      if (detailResult.status === 'fulfilled') {
        setVersionTargets(detailResult.value.versions);
      } else {
        setVersionTargets([]);
        hasError = true;
      }

      if (governanceResult.status === 'fulfilled') {
        setVersionGovernance(governanceResult.value);
      } else {
        setVersionGovernance(activeMarketplaceItem.version_governance ?? activePlugin.version_governance ?? null);
        hasError = true;
      }

      setVersionError(hasError ? copy.versionLoadFailed : '');
      setVersionLoading(false);
    }

    void loadVersionInfo();
    return () => {
      cancelled = true;
    };
  }, [
    copy.versionLoadFailed,
    householdId,
    isOpen,
    marketplaceItem,
    plugin,
  ]);

  if (!isOpen || !plugin) {
    return null;
  }

  const sourceInfo = formatSourceType(plugin.source_type, locale);
  const riskInfo = formatRiskLevel(plugin.risk_level, locale);
  const latestFailedJob = jobs.find((item) => item.job.status === 'failed');
  const latestWaitingJob = jobs.find((item) => item.job.status === 'waiting_response');
  const compatibilityEntries = buildCompatibilityEntries(plugin.compatibility);
  const effectiveGovernance = versionGovernance ?? marketplaceItem?.version_governance ?? plugin.version_governance ?? null;
  const installedVersion = effectiveGovernance?.installed_version ?? plugin.installed_version ?? plugin.version;
  const selectableTargets = versionTargets.filter(item => item.version !== installedVersion);
  const canOperateMarketplaceVersion = Boolean(
    marketplaceItem?.install_state.instance_id
    && selectedTargetVersion
    && selectedTargetVersion !== installedVersion,
  );

  async function handleMarketplaceVersionOperation(operation: PluginVersionOperationType) {
    if (!marketplaceItem || !selectedTargetVersion) {
      return;
    }
    setOperatingVersion(operation);
    setVersionError('');
    setVersionStatus('');
    try {
      const result = await onOperateMarketplaceVersion(marketplaceItem, operation, selectedTargetVersion);
      setVersionGovernance(result.governance);
      const statusKey = operation === 'upgrade'
        ? 'plugins.marketplace.status.upgraded'
        : 'plugins.marketplace.status.rolledBack';
      const message = result.state_change_reason
        ? getPageMessage(locale, 'plugins.marketplace.status.versionChangedWithState', {
            message: getPageMessage(locale, statusKey, { version: result.target_version }),
            reason: result.state_change_reason,
          })
        : getPageMessage(locale, statusKey, { version: result.target_version });
      setVersionStatus(message);
    } catch (error) {
      setVersionError(error instanceof ApiError ? error.message : copy.versionLoadFailed);
    } finally {
      setOperatingVersion(null);
    }
  }

  return (
    <div className="task-form-overlay" onClick={onClose}>
      <div className="task-form-drawer plugin-detail-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="task-form-drawer__header">
          <div className="plugin-detail-drawer__title-area">
            <h2>{plugin.name}</h2>
            <div className="plugin-detail-drawer__badges">
              <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
              <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
              <span className={`badge badge--${isEnabled ? 'success' : 'secondary'}`}>
                {isEnabled ? copy.enabled : copy.disabled}
              </span>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" type="button" onClick={onClose} aria-label={copy.close}>X</button>
        </div>

        <div className="task-form-drawer__body">
          {plugin.source_type === 'third_party' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--warning">
              <span className="plugin-detail-drawer__alert-icon">!</span>
              <div>
                <strong>{copy.thirdPartyTitle}</strong>
                <p>{copy.thirdPartyDesc}</p>
              </div>
            </div>
          ) : null}

          {plugin.risk_level === 'high' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">!</span>
              <div>
                <strong>{copy.highRiskTitle}</strong>
                <p>{riskInfo.desc}</p>
              </div>
            </div>
          ) : null}

          {latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">i</span>
              <div>
                <strong>{copy.waitingTitle}</strong>
                <p>{copy.waitingDesc}</p>
              </div>
            </div>
          ) : null}

          {latestFailedJob && !latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">!</span>
              <div>
                <strong>{copy.latestFailedTitle}</strong>
                {latestFailedJob.job.last_error_message ? <p>{latestFailedJob.job.last_error_message}</p> : null}
              </div>
            </div>
          ) : null}

          {!isEnabled ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">i</span>
              <div>
                <strong>{plugin.disabled_reason || copy.disabledTitle}</strong>
                <p>{copy.disabledDesc}</p>
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{copy.basics}</h3>
            <div className="plugin-detail-grid">
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">ID</span><span className="plugin-detail-grid__value">{plugin.id}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{copy.version}</span><span className="plugin-detail-grid__value">v{plugin.version}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{copy.installedVersion}</span><span className="plugin-detail-grid__value">{formatVersionValue(installedVersion, locale)}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{copy.updateState}</span><span className="plugin-detail-grid__value">{formatUpdateState(effectiveGovernance?.update_state ?? plugin.update_state, locale)}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{copy.type}</span><span className="plugin-detail-grid__value">{plugin.types.map((type) => formatPluginType(type, locale)).join(' / ')}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{copy.source}</span><span className={`plugin-detail-grid__value plugin-detail-grid__value--${sourceInfo.tone}`}>{sourceInfo.label}</span></div>
            </div>
          </div>

          <div className="plugin-detail-section">
            <h3>{copy.versionGovernance}</h3>
            {versionError ? <div className="settings-note settings-note--error">{versionError}</div> : null}
            {versionStatus ? <div className="settings-note settings-note--success">{versionStatus}</div> : null}
            {effectiveGovernance ? (
              <>
                <div className="plugin-detail-grid">
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.installedVersion}</span>
                    <span className="plugin-detail-grid__value">{formatVersionValue(effectiveGovernance.installed_version, locale)}</span>
                  </div>
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.latestVersion}</span>
                    <span className="plugin-detail-grid__value">{formatVersionValue(effectiveGovernance.latest_version, locale)}</span>
                  </div>
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.latestCompatibleVersion}</span>
                    <span className="plugin-detail-grid__value">{formatVersionValue(effectiveGovernance.latest_compatible_version, locale)}</span>
                  </div>
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.updateState}</span>
                    <span className="plugin-detail-grid__value">{formatUpdateState(effectiveGovernance.update_state, locale)}</span>
                  </div>
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.compatibilityState}</span>
                    <span className="plugin-detail-grid__value">{formatCompatibilityStatus(effectiveGovernance.compatibility_status, locale)}</span>
                  </div>
                  <div className="plugin-detail-grid__item">
                    <span className="plugin-detail-grid__label">{copy.blockedReason}</span>
                    <span className="plugin-detail-grid__value">{effectiveGovernance.blocked_reason || getPageMessage(locale, 'settings.plugin.versionValue.unknown')}</span>
                  </div>
                </div>

                {marketplaceItem?.install_state.instance_id ? (
                  <div className="plugin-detail-entrypoints">
                    <div className="plugin-detail-entrypoint-item">
                      <span className="plugin-detail-entrypoint-key">{copy.targetVersion}</span>
                      <span className="plugin-detail-entrypoint-value">
                        <select
                          className="marketplace-source-form__input"
                          value={selectedTargetVersion}
                          onChange={(event) => setSelectedTargetVersion(event.target.value)}
                          disabled={versionLoading || operatingVersion !== null}
                        >
                          <option value="">{copy.targetVersionPlaceholder}</option>
                          {selectableTargets.map((item) => (
                            <option key={item.version} value={item.version}>
                              {item.version}
                            </option>
                          ))}
                        </select>
                      </span>
                    </div>
                  </div>
                ) : null}

                {versionLoading ? (
                  <div className="plugin-detail-loading settings-loading-copy settings-loading-copy--center">{copy.loadingVersionInfo}</div>
                ) : null}
                {!versionLoading && marketplaceItem?.install_state.instance_id && selectableTargets.length === 0 ? (
                  <div className="plugin-detail-empty">{copy.noVersionTargets}</div>
                ) : null}
                {marketplaceItem?.install_state.instance_id ? (
                  <div className="marketplace-card__actions">
                    <button
                      className="btn btn--primary btn--sm"
                      type="button"
                      onClick={() => void handleMarketplaceVersionOperation('upgrade')}
                      disabled={!canOperateMarketplaceVersion || operatingVersion !== null}
                    >
                      {operatingVersion === 'upgrade' ? copy.upgradeProcessing : copy.upgrade}
                    </button>
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => void handleMarketplaceVersionOperation('rollback')}
                      disabled={!canOperateMarketplaceVersion || operatingVersion !== null}
                    >
                      {operatingVersion === 'rollback' ? copy.rollbackProcessing : copy.rollback}
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="plugin-detail-empty">{getPageMessage(locale, 'settings.plugin.versionSwitch.unavailable')}</p>
            )}
          </div>

          <div className="plugin-detail-section">
            <h3>{copy.compatibility}</h3>
            {compatibilityEntries.length > 0 ? (
              <div className="plugin-detail-entrypoints">
                {compatibilityEntries.map((item) => (
                  <div key={`${item.label}-${item.value}`} className="plugin-detail-entrypoint-item">
                    <span className="plugin-detail-entrypoint-key">{item.label}</span>
                    <span className="plugin-detail-entrypoint-value">{item.value}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="plugin-detail-empty">{copy.noCompatibility}</p>
            )}
          </div>

          <div className="plugin-detail-section">
            <h3>{copy.permissions}</h3>
            {plugin.permissions.length > 0 ? (
              <div className="plugin-detail-permissions">
                {plugin.permissions.map((permission) => <span key={permission} className="plugin-detail-permission-tag">{permission}</span>)}
              </div>
            ) : (
              <p className="plugin-detail-empty">{copy.noPermissions}</p>
            )}
          </div>

          {plugin.triggers.length > 0 ? (
            <div className="plugin-detail-section">
              <h3>{copy.triggers}</h3>
              <div className="plugin-detail-triggers">
                {plugin.triggers.map((trigger) => <span key={trigger} className="plugin-detail-trigger-tag">{trigger}</span>)}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{copy.entrypoints}</h3>
            <div className="plugin-detail-entrypoints">
              {Object.entries(plugin.entrypoints).filter(([, value]) => Boolean(value)).map(([key, value]) => (
                <div key={key} className="plugin-detail-entrypoint-item">
                  <span className="plugin-detail-entrypoint-key">{key}</span>
                  <span className="plugin-detail-entrypoint-value">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {plugin.locales.length > 0 ? (
            <div className="plugin-detail-section">
              <h3>{copy.locales}</h3>
              <div className="plugin-detail-permissions">
                {plugin.locales.map((item) => <span key={item.id} className="plugin-detail-permission-tag">{item.native_label}</span>)}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{copy.jobs}</h3>
            {jobsError ? <div className="settings-note settings-note--error">{jobsError}</div> : null}
            {jobsLoading ? (
              <div className="plugin-detail-loading settings-loading-copy settings-loading-copy--center">{copy.loadingJobs}</div>
            ) : jobs.length > 0 ? (
              <div className="plugin-job-list">
                {jobs.map((item) => {
                  const jobStatus = formatJobStatus(item.job.status, locale);
                  return (
                    <div key={item.job.id} className="plugin-job-item">
                      <div className="plugin-job-item__info">
                        <span className="plugin-job-item__trigger">{item.job.trigger}</span>
                        <span className={`badge badge--${jobStatus.tone}`}>{jobStatus.label}</span>
                      </div>
                      <div className="plugin-job-item__meta">
                        <span>{formatTimestamp(item.job.created_at, locale)}</span>
                        <span>/</span>
                        <span>{copy.attempts}: {item.job.current_attempt}/{item.job.max_attempts}</span>
                      </div>
                      {item.job.last_error_message ? <div className="plugin-job-item__error">{item.job.last_error_message}</div> : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="plugin-detail-empty">{copy.noJobs}</div>
            )}
          </div>
        </div>

        <div className="task-form-drawer__footer">
          <button className="btn btn--ghost" type="button" onClick={onClose}>{copy.close}</button>
          <button className="btn btn--primary" type="button" onClick={() => onToggle(plugin)} disabled={isToggling}>
            {isToggling ? copy.processing : isEnabled ? copy.disable : copy.enable}
          </button>
        </div>
      </div>
    </div>
  );
}
