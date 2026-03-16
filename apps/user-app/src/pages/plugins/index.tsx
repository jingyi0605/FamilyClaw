import { useCallback, useEffect, useMemo, useState } from 'react';
import { BadgeCheck, Package, Zap } from 'lucide-react';
import { GuardedPage, useHouseholdContext } from '../../runtime';
import { useI18n } from '../../runtime/h5-shell';
import { Card, EmptyState, Section } from '../family/base';
import { SettingsPageShell } from '../settings/SettingsPageShell';
import { PluginDetailDrawer } from '../settings/components/PluginDetailDrawer';
import { ApiError, settingsApi } from '../settings/settingsApi';
import type { PluginManifestType, PluginRegistryItem } from '../settings/settingsTypes';

type ViewMode = 'card' | 'list';

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) {
    return values.enUS;
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return values.zhTW;
  }
  return values.zhCN;
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

function formatPluginType(type: PluginManifestType, locale: string | undefined) {
  const labels: Record<PluginManifestType, { zhCN: string; zhTW: string; enUS: string }> = {
    connector: { zhCN: '连接器', zhTW: '連接器', enUS: 'Connector' },
    'memory-ingestor': { zhCN: '记忆摄取', zhTW: '記憶攝取', enUS: 'Memory Ingestor' },
    action: { zhCN: '动作', zhTW: '動作', enUS: 'Action' },
    'agent-skill': { zhCN: 'Agent 技能', zhTW: 'Agent 技能', enUS: 'Agent Skill' },
    channel: { zhCN: '通讯通道', zhTW: '通訊通道', enUS: 'Channel' },
    'locale-pack': { zhCN: '语言包', zhTW: '語言包', enUS: 'Locale Pack' },
    'region-provider': { zhCN: '地区提供器', zhTW: '地區提供器', enUS: 'Region Provider' },
  };
  return pickLocaleText(locale, labels[type]);
}

function getInitialViewMode(): ViewMode {
  if (typeof window === 'undefined') {
    return 'card';
  }
  const saved = window.localStorage.getItem(VIEW_MODE_KEY);
  return saved === 'list' ? 'list' : 'card';
}

function formatSourceType(sourceType: PluginRegistryItem['source_type'], locale: string | undefined): { label: string; tone: 'info' | 'success' | 'warning' } {
  switch (sourceType) {
    case 'builtin':
      return { label: pickLocaleText(locale, { zhCN: '内置', zhTW: '內建', enUS: 'Built-in' }), tone: 'info' };
    case 'official':
      return { label: pickLocaleText(locale, { zhCN: '官方', zhTW: '官方', enUS: 'Official' }), tone: 'success' };
    case 'third_party':
      return { label: pickLocaleText(locale, { zhCN: '第三方', zhTW: '第三方', enUS: 'Third-party' }), tone: 'warning' };
    default:
      return { label: sourceType, tone: 'info' };
  }
}

function formatRiskLevel(riskLevel: PluginRegistryItem['risk_level'], locale: string | undefined): { label: string; tone: 'success' | 'warning' | 'danger' } {
  switch (riskLevel) {
    case 'low':
      return { label: pickLocaleText(locale, { zhCN: '低风险', zhTW: '低風險', enUS: 'Low risk' }), tone: 'success' };
    case 'medium':
      return { label: pickLocaleText(locale, { zhCN: '中风险', zhTW: '中風險', enUS: 'Medium risk' }), tone: 'warning' };
    case 'high':
      return { label: pickLocaleText(locale, { zhCN: '高风险', zhTW: '高風險', enUS: 'High risk' }), tone: 'danger' };
    default:
      return { label: riskLevel, tone: 'warning' };
  }
}

function formatJobStatus(status: string, locale: string | undefined): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'succeeded':
      return { label: pickLocaleText(locale, { zhCN: '成功', zhTW: '成功', enUS: 'Succeeded' }), tone: 'success' };
    case 'queued':
      return { label: pickLocaleText(locale, { zhCN: '排队中', zhTW: '排隊中', enUS: 'Queued' }), tone: 'warning' };
    case 'running':
      return { label: pickLocaleText(locale, { zhCN: '执行中', zhTW: '執行中', enUS: 'Running' }), tone: 'warning' };
    case 'retry_waiting':
      return { label: pickLocaleText(locale, { zhCN: '等待重试', zhTW: '等待重試', enUS: 'Waiting to retry' }), tone: 'warning' };
    case 'waiting_response':
      return { label: pickLocaleText(locale, { zhCN: '等待响应', zhTW: '等待回應', enUS: 'Waiting for response' }), tone: 'warning' };
    case 'failed':
      return { label: pickLocaleText(locale, { zhCN: '失败', zhTW: '失敗', enUS: 'Failed' }), tone: 'danger' };
    case 'cancelled':
      return { label: pickLocaleText(locale, { zhCN: '已取消', zhTW: '已取消', enUS: 'Cancelled' }), tone: 'secondary' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatTimestamp(value: string | null, locale: string | undefined) {
  if (!value) return pickLocaleText(locale, { zhCN: '暂无', zhTW: '暫無', enUS: 'None yet' });
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

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(VIEW_MODE_KEY, mode);
    }
  }, []);

  const filteredPlugins = useMemo(() => {
    if (selectedTypes.length === 0) return plugins;
    return plugins.filter((plugin) => plugin.types.some((type) => selectedTypes.includes(type)));
  }, [plugins, selectedTypes]);

  const toggleTypeFilter = useCallback((type: PluginManifestType) => {
    setSelectedTypes((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type]);
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
          setError(loadError instanceof ApiError ? loadError.message : pickLocaleText(locale, {
            zhCN: '加载插件列表失败',
            zhTW: '載入外掛列表失敗',
            enUS: 'Failed to load plugins',
          }));
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
  }, [currentHouseholdId, locale]);

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
    if (!currentHouseholdId) return;
    setTogglingPluginId(plugin.id);
    setError('');
    setStatus('');
    try {
      const updated = await settingsApi.updatePluginState(currentHouseholdId, plugin.id, { enabled: !plugin.enabled });
      setPlugins((current) => current.map((item) => item.id === updated.id ? updated : item));
      setDetailPlugin((current) => current && current.id === updated.id ? updated : current);
      if (updated.types.includes('locale-pack')) {
        await refreshPluginLocales();
      }
      setStatus(updated.enabled
        ? pickLocaleText(locale, { zhCN: '插件已启用', zhTW: '外掛已啟用', enUS: 'Plugin enabled' })
        : pickLocaleText(locale, { zhCN: '插件已停用', zhTW: '外掛已停用', enUS: 'Plugin disabled' }));
    } catch (toggleError) {
      setError(toggleError instanceof ApiError ? toggleError.message : pickLocaleText(locale, {
        zhCN: '操作失败',
        zhTW: '操作失敗',
        enUS: 'Operation failed',
      }));
    } finally {
      setTogglingPluginId(null);
    }
  }

  const pluginStats = useMemo(() => {
    const enabled = filteredPlugins.filter((plugin) => plugin.enabled).length;
    const total = filteredPlugins.length;
    return { enabled, total, disabled: total - enabled };
  }, [filteredPlugins]);

  return (
    <SettingsPageShell activeKey="plugins">
      <div className="settings-page">
        <Section title={pickLocaleText(locale, { zhCN: '已安装插件', zhTW: '已安裝外掛', enUS: 'Installed Plugins' })}>
          {plugins.length > 0 ? (
            <div className="plugin-toolbar">
              <div className="plugin-view-toggle">
                <button className={`plugin-view-toggle__btn ${viewMode === 'card' ? 'plugin-view-toggle__btn--active' : ''}`} onClick={() => handleViewModeChange('card')} title={pickLocaleText(locale, { zhCN: '卡片视图', zhTW: '卡片視圖', enUS: 'Card view' })}>▥</button>
                <button className={`plugin-view-toggle__btn ${viewMode === 'list' ? 'plugin-view-toggle__btn--active' : ''}`} onClick={() => handleViewModeChange('list')} title={pickLocaleText(locale, { zhCN: '列表视图', zhTW: '列表視圖', enUS: 'List view' })}>▤</button>
              </div>

              <div className="plugin-filter">
                <span className="plugin-filter__label">{pickLocaleText(locale, { zhCN: '按类型筛选：', zhTW: '依類型篩選：', enUS: 'Filter by type:' })}</span>
                <div className="plugin-filter__chips">
                  <button className={`plugin-filter__chip ${selectedTypes.length === 0 ? 'plugin-filter__chip--active' : ''}`} onClick={clearTypeFilter}>{pickLocaleText(locale, { zhCN: '全部', zhTW: '全部', enUS: 'All' })}</button>
                  {FILTERABLE_TYPES.map((type) => (
                    <button key={type} className={`plugin-filter__chip ${selectedTypes.includes(type) ? 'plugin-filter__chip--active' : ''}`} onClick={() => toggleTypeFilter(type)}>
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
                <div className="plugin-stat"><span className="plugin-stat__value">{pluginStats.total}</span><span className="plugin-stat__label">{pickLocaleText(locale, { zhCN: '总数', zhTW: '總數', enUS: 'Total' })}</span></div>
                <div className="plugin-stat"><span className="plugin-stat__value plugin-stat__value--success">{pluginStats.enabled}</span><span className="plugin-stat__label">{pickLocaleText(locale, { zhCN: '已启用', zhTW: '已啟用', enUS: 'Enabled' })}</span></div>
                <div className="plugin-stat"><span className="plugin-stat__value plugin-stat__value--secondary">{pluginStats.disabled}</span><span className="plugin-stat__label">{pickLocaleText(locale, { zhCN: '已停用', zhTW: '已停用', enUS: 'Disabled' })}</span></div>
                {selectedTypes.length > 0 ? <div className="plugin-stat"><span className="plugin-stat__value">{filteredPlugins.length}</span><span className="plugin-stat__label">{pickLocaleText(locale, { zhCN: '筛选结果', zhTW: '篩選結果', enUS: 'Filtered' })}</span></div> : null}
              </div>
            </Card>
          ) : null}

          {loading && plugins.length === 0 ? <div className="settings-note"><span>⏳</span> {pickLocaleText(locale, { zhCN: '加载中...', zhTW: '載入中...', enUS: 'Loading...' })}</div> : null}
          {error ? <div className="settings-note settings-note--error"><span>⚠️</span> {error}</div> : null}
          {status ? <div className="settings-note settings-note--success"><span>✓</span> {status}</div> : null}
          {!loading && plugins.length === 0 && !error ? <EmptyState title={pickLocaleText(locale, { zhCN: '还没有可展示的插件', zhTW: '還沒有可顯示的外掛', enUS: 'No plugins to show' })} description={pickLocaleText(locale, { zhCN: '当前家庭还没有注册成功的插件。', zhTW: '目前家庭還沒有註冊成功的外掛。', enUS: 'No plugins have been registered for this household yet.' })} /> : null}
          {!loading && plugins.length > 0 && filteredPlugins.length === 0 ? <EmptyState title={pickLocaleText(locale, { zhCN: '没有筛选结果', zhTW: '沒有篩選結果', enUS: 'No matching plugins' })} description={pickLocaleText(locale, { zhCN: '你把列表筛空了，换个条件。', zhTW: '你把列表篩空了，換個條件。', enUS: 'Your current filters removed everything. Try another filter.' })} /> : null}

          {viewMode === 'card' && filteredPlugins.length > 0 ? (
            <div className="plugin-list">
              {filteredPlugins.map((plugin) => {
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
                        <div className={`toggle-switch toggle-switch--compact ${isEnabled ? 'toggle-switch--on' : ''} ${isToggling ? 'toggle-switch--loading' : ''}`} onClick={() => !isToggling && void handleTogglePlugin(plugin)} title={pickLocaleText(locale, { zhCN: isEnabled ? '停用' : '启用', zhTW: isEnabled ? '停用' : '啟用', enUS: isEnabled ? 'Disable' : 'Enable' })}>
                          <div className="toggle-switch__thumb" />
                        </div>
                      </div>
                    </div>

                    <div className="plugin-card__tags">
                      <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
                      <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
                      {plugin.types.slice(0, 2).map((type) => <span key={type} className="badge badge--secondary">{formatPluginType(type, locale)}</span>)}
                      {plugin.types.length > 2 ? <span className="badge badge--secondary">+{plugin.types.length - 2}</span> : null}
                    </div>

                    <div className="plugin-card__footer">
                      <button className="btn btn--ghost btn--sm" onClick={() => openPluginDetail(plugin)}>{pickLocaleText(locale, { zhCN: '查看详情', zhTW: '查看詳情', enUS: 'Details' })}</button>
                      <button className="btn btn--outline btn--sm" onClick={() => setSelectedPluginId(isSelected ? null : plugin.id)} disabled={jobsLoading}>{pickLocaleText(locale, { zhCN: '查看任务', zhTW: '查看任務', enUS: 'Jobs' })}</button>
                    </div>

                    {isSelected ? (
                      <div className="plugin-card__jobs">
                        <h4>{pickLocaleText(locale, { zhCN: '最近任务', zhTW: '最近任務', enUS: 'Recent Jobs' })}</h4>
                        {jobsLoading ? (
                          <div className="settings-note">{pickLocaleText(locale, { zhCN: '加载中...', zhTW: '載入中...', enUS: 'Loading...' })}</div>
                        ) : jobs && jobs.items.length > 0 ? (
                          <div className="plugin-job-list">
                            {jobs.items.map((item) => {
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
                                    <span>{pickLocaleText(locale, { zhCN: '尝试次数', zhTW: '嘗試次數', enUS: 'Attempts' })}：{item.job.current_attempt}/{item.job.max_attempts}</span>
                                  </div>
                                  {item.job.last_error_message ? <div className="plugin-job-item__error">{item.job.last_error_message}</div> : null}
                                  {item.allowed_actions.length > 0 ? (
                                    <div className="plugin-job-item__actions">
                                      {item.allowed_actions.includes('retry') ? <button className="btn btn--outline btn--sm">{pickLocaleText(locale, { zhCN: '重试', zhTW: '重試', enUS: 'Retry' })}</button> : null}
                                      {item.allowed_actions.includes('confirm') ? <button className="btn btn--outline btn--sm">{pickLocaleText(locale, { zhCN: '确认', zhTW: '確認', enUS: 'Confirm' })}</button> : null}
                                      {item.allowed_actions.includes('cancel') ? <button className="btn btn--outline btn--sm">{pickLocaleText(locale, { zhCN: '取消', zhTW: '取消', enUS: 'Cancel' })}</button> : null}
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="settings-note">{pickLocaleText(locale, { zhCN: '最近没有任务', zhTW: '最近沒有任務', enUS: 'No recent jobs' })}</div>
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
                    <th className="plugin-table__th plugin-table__th--name">{pickLocaleText(locale, { zhCN: '名称', zhTW: '名稱', enUS: 'Name' })}</th>
                    <th className="plugin-table__th plugin-table__th--types">{pickLocaleText(locale, { zhCN: '类型', zhTW: '類型', enUS: 'Type' })}</th>
                    <th className="plugin-table__th plugin-table__th--source">{pickLocaleText(locale, { zhCN: '来源', zhTW: '來源', enUS: 'Source' })}</th>
                    <th className="plugin-table__th plugin-table__th--risk">{pickLocaleText(locale, { zhCN: '风险', zhTW: '風險', enUS: 'Risk' })}</th>
                    <th className="plugin-table__th plugin-table__th--status">{pickLocaleText(locale, { zhCN: '状态', zhTW: '狀態', enUS: 'Status' })}</th>
                    <th className="plugin-table__th plugin-table__th--actions">{pickLocaleText(locale, { zhCN: '操作', zhTW: '操作', enUS: 'Actions' })}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPlugins.map((plugin) => {
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
                        <td className="plugin-table__td plugin-table__td--types">{plugin.types.map((type) => formatPluginType(type, locale)).join('、')}</td>
                        <td className="plugin-table__td plugin-table__td--source"><span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span></td>
                        <td className="plugin-table__td plugin-table__td--risk"><span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span></td>
                        <td className="plugin-table__td plugin-table__td--status">
                          <div className={`toggle-switch toggle-switch--compact ${isEnabled ? 'toggle-switch--on' : ''} ${isToggling ? 'toggle-switch--loading' : ''}`} onClick={() => !isToggling && void handleTogglePlugin(plugin)} title={pickLocaleText(locale, { zhCN: isEnabled ? '停用' : '启用', zhTW: isEnabled ? '停用' : '啟用', enUS: isEnabled ? 'Disable' : 'Enable' })}>
                            <div className="toggle-switch__thumb" />
                          </div>
                        </td>
                        <td className="plugin-table__td plugin-table__td--actions">
                          <button className="btn btn--ghost btn--sm" onClick={() => openPluginDetail(plugin)}>{pickLocaleText(locale, { zhCN: '查看详情', zhTW: '查看詳情', enUS: 'Details' })}</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </Section>

        <Section title={pickLocaleText(locale, { zhCN: '插件市场', zhTW: '外掛市場', enUS: 'Plugin Marketplace' })}>
          <Card className="plugin-market-placeholder">
            <div className="plugin-market-placeholder__content">
              <span className="plugin-market-placeholder__icon">🛍</span>
              <h3>{pickLocaleText(locale, { zhCN: '市场入口暂未开放', zhTW: '市場入口暫未開放', enUS: 'Marketplace not open yet' })}</h3>
              <p>{pickLocaleText(locale, { zhCN: '先把已安装插件管稳，再谈市场。这不是拖延，是避免一地鸡毛。', zhTW: '先把已安裝外掛管穩，再談市場。這不是拖延，是避免一地雞毛。', enUS: 'Stabilize installed plugins first, then talk about a marketplace. That is not procrastination. It is basic engineering hygiene.' })}</p>
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
