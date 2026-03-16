import { useCallback, useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { BadgeCheck, Package, Zap } from 'lucide-react';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n } from '../../runtime/h5-shell';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, EmptyState, Section } from '../family/base';
import { SettingsPageShell } from '../settings/SettingsPageShell';
import { PluginDetailDrawer } from '../settings/components/PluginDetailDrawer';
import { ApiError, settingsApi } from '../settings/settingsApi';
import type { PluginManifestType, PluginRegistryItem } from '../settings/settingsTypes';

type ViewMode = 'card' | 'list';

const VIEW_MODE_KEY = 'plugin-view-mode';
const FILTERABLE_TYPES: PluginManifestType[] = [
  'connector',
  'memory-ingestor',
  'action',
  'agent-skill',
  'channel',
  'locale-pack',
  'region-provider',
];

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

function PluginsPageContent() {
  const { currentHouseholdId } = useHouseholdContext();
  const { locale, replacePluginLocales } = useI18n();
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
  const [viewMode, setViewMode] = useState<ViewMode>(getInitialViewMode);
  const [selectedTypes, setSelectedTypes] = useState<PluginManifestType[]>([]);

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

  const filteredPlugins = useMemo(() => {
    if (selectedTypes.length === 0) {
      return plugins;
    }
    return plugins.filter(plugin => plugin.types.some(type => selectedTypes.includes(type)));
  }, [plugins, selectedTypes]);

  const toggleTypeFilter = useCallback((type: PluginManifestType) => {
    setSelectedTypes(current => (
      current.includes(type)
        ? current.filter(item => item !== type)
        : [...current, type]
    ));
  }, []);

  const clearTypeFilter = useCallback(() => {
    setSelectedTypes([]);
  }, []);

  useEffect(() => {
    if (!currentHouseholdId) {
      setPlugins([]);
      return;
    }

    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError('');
      try {
        const registryResult = await settingsApi.listRegisteredPlugins(currentHouseholdId);
        if (!cancelled) {
          setPlugins(registryResult.items);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : page('plugins.loadFailed'));
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

  async function handleTogglePlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) {
      return;
    }

    setTogglingPluginId(plugin.id);
    setError('');
    setStatus('');

    try {
      const updated = await settingsApi.updatePluginState(currentHouseholdId, plugin.id, { enabled: !plugin.enabled });
      setPlugins(current => current.map(item => (item.id === updated.id ? updated : item)));
      setDetailPlugin(current => (current && current.id === updated.id ? updated : current));
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

  const pluginStats = useMemo(() => {
    const enabled = filteredPlugins.filter(plugin => plugin.enabled).length;
    const total = filteredPlugins.length;
    return { enabled, total, disabled: total - enabled };
  }, [filteredPlugins]);

  return (
    <SettingsPageShell activeKey="plugins">
      <div className="settings-page">
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
                    className={`plugin-filter__chip ${selectedTypes.length === 0 ? 'plugin-filter__chip--active' : ''}`}
                    onClick={clearTypeFilter}
                  >
                    {page('plugins.filter.all')}
                  </button>
                  {FILTERABLE_TYPES.map(type => (
                    <button
                      key={type}
                      className={`plugin-filter__chip ${selectedTypes.includes(type) ? 'plugin-filter__chip--active' : ''}`}
                      onClick={() => toggleTypeFilter(type)}
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
                {selectedTypes.length > 0 ? (
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

        <Section title={page('plugins.section.marketplace')}>
          <Card className="plugin-market-placeholder">
            <div className="plugin-market-placeholder__content">
              <span className="plugin-market-placeholder__icon">🛍</span>
              <h3>{page('plugins.marketplace.closedTitle')}</h3>
              <p>{page('plugins.marketplace.closedDesc')}</p>
            </div>
          </Card>
        </Section>

        <PluginDetailDrawer
          plugin={detailPlugin}
          householdId={currentHouseholdId}
          isOpen={drawerOpen}
          onClose={closePluginDetail}
          isEnabled={detailPlugin?.enabled ?? false}
          onToggle={(plugin) => {
            void handleTogglePlugin(plugin);
            closePluginDetail();
          }}
          isToggling={togglingPluginId === detailPlugin?.id}
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
