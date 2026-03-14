/* ============================================================
 * 插件管理设置页
 * ============================================================ */
import { useEffect, useState, useMemo } from 'react';
import { useI18n } from '../i18n';
import { Card, Section, EmptyState } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { api, ApiError } from '../lib/api';
import { PluginDetailDrawer } from '../components/PluginDetailDrawer';
import type { PluginRegistryItem, PluginMountRead, PluginJobListRead } from '../lib/types';

type PluginSourceType = 'builtin' | 'official' | 'third_party';
type PluginRiskLevel = 'low' | 'medium' | 'high';

function formatSourceType(sourceType: PluginSourceType): { label: string; tone: 'info' | 'success' | 'warning' } {
  switch (sourceType) {
    case 'builtin':
      return { label: '内置', tone: 'info' };
    case 'official':
      return { label: '官方', tone: 'success' };
    case 'third_party':
      return { label: '第三方', tone: 'warning' };
    default:
      return { label: sourceType, tone: 'info' };
  }
}

function formatRiskLevel(riskLevel: PluginRiskLevel): { label: string; tone: 'success' | 'warning' | 'danger' } {
  switch (riskLevel) {
    case 'low':
      return { label: '低风险', tone: 'success' };
    case 'medium':
      return { label: '中等风险', tone: 'warning' };
    case 'high':
      return { label: '高风险', tone: 'danger' };
    default:
      return { label: riskLevel, tone: 'warning' };
  }
}

function formatJobStatus(status: string): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'succeeded':
      return { label: '成功', tone: 'success' };
    case 'queued':
      return { label: '排队中', tone: 'warning' };
    case 'running':
      return { label: '执行中', tone: 'warning' };
    case 'retry_waiting':
      return { label: '等待重试', tone: 'warning' };
    case 'waiting_response':
      return { label: '等待响应', tone: 'warning' };
    case 'failed':
      return { label: '失败', tone: 'danger' };
    case 'cancelled':
      return { label: '已取消', tone: 'secondary' };
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

export function SettingsPluginsPage() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();

  const [plugins, setPlugins] = useState<PluginRegistryItem[]>([]);
  const [mounts, setMounts] = useState<PluginMountRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  // 插件任务相关状态
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<PluginJobListRead | null>(null);
  const [jobsLoading, setJobsLoading] = useState(false);

  // 插件详情抽屉状态
  const [detailPlugin, setDetailPlugin] = useState<PluginRegistryItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 操作中状态
  const [togglingPluginId, setTogglingPluginId] = useState<string | null>(null);

  useEffect(() => {
    if (!currentHouseholdId) {
      setPlugins([]);
      setMounts([]);
      return;
    }

    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        // 并行加载已注册插件列表和已挂载插件列表
        const [registryResult, mountsResult] = await Promise.all([
          api.listRegisteredPlugins(currentHouseholdId),
          api.listPluginMounts(currentHouseholdId).catch(() => []),
        ]);
        if (!cancelled) {
          setPlugins(registryResult.items);
          setMounts(mountsResult);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : '加载插件列表失败');
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

  // 获取插件的启用状态（从 mounts 中查找）
  const getPluginEnabledState = (pluginId: string): boolean => {
    const mount = mounts.find(m => m.plugin_id === pluginId);
    return mount?.enabled ?? true; // 内置插件默认启用
  };

  // 加载选中插件的最近任务
  useEffect(() => {
    if (!currentHouseholdId || !selectedPluginId) {
      setJobs(null);
      return;
    }

    let cancelled = false;

    const loadJobs = async () => {
      setJobsLoading(true);
      try {
        const result = await api.listPluginJobs(currentHouseholdId, {
          plugin_id: selectedPluginId,
          page_size: 10,
        });
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
    };

    void loadJobs();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, selectedPluginId]);

  // 打开插件详情抽屉
  function openPluginDetail(plugin: PluginRegistryItem) {
    setDetailPlugin(plugin);
    setDrawerOpen(true);
  }

  // 关闭插件详情抽屉
  function closePluginDetail() {
    setDrawerOpen(false);
    // 延迟清空，等动画结束
    setTimeout(() => setDetailPlugin(null), 300);
  }

  async function handleTogglePlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) return;

    // 内置插件不支持禁用
    if (plugin.source_type === 'builtin') {
      setError('内置插件不支持禁用操作');
      return;
    }

    const currentEnabled = getPluginEnabledState(plugin.id);
    setTogglingPluginId(plugin.id);
    setError('');
    setStatus('');

    try {
      if (currentEnabled) {
        await api.disablePluginMount(currentHouseholdId, plugin.id);
        setStatus(t('plugins.disableSuccess'));
      } else {
        await api.enablePluginMount(currentHouseholdId, plugin.id);
        setStatus(t('plugins.enableSuccess'));
      }

      // 刷新挂载列表
      const mountsResult = await api.listPluginMounts(currentHouseholdId);
      setMounts(mountsResult);
    } catch (toggleError) {
      setError(toggleError instanceof ApiError ? toggleError.message : '操作失败');
    } finally {
      setTogglingPluginId(null);
    }
  }

  const pluginStats = useMemo(() => {
    const enabled = plugins.filter(p => getPluginEnabledState(p.id)).length;
    const total = plugins.length;
    return { enabled, total, disabled: total - enabled };
  }, [plugins, mounts]);

  return (
    <div className="settings-page">
      <Section title={t('plugins.installed')}>
        {/* 统计概览 */}
        {plugins.length > 0 && (
          <Card className="plugin-stats-card">
            <div className="plugin-stats">
              <div className="plugin-stat">
                <span className="plugin-stat__value">{pluginStats.total}</span>
                <span className="plugin-stat__label">{t('plugins.total')}</span>
              </div>
              <div className="plugin-stat">
                <span className="plugin-stat__value plugin-stat__value--success">{pluginStats.enabled}</span>
                <span className="plugin-stat__label">{t('plugins.enabled')}</span>
              </div>
              <div className="plugin-stat">
                <span className="plugin-stat__value plugin-stat__value--secondary">{pluginStats.disabled}</span>
                <span className="plugin-stat__label">{t('plugins.disabled')}</span>
              </div>
            </div>
          </Card>
        )}

        {/* 加载状态 */}
        {loading && plugins.length === 0 && (
          <div className="settings-note">
            <span>⏳</span> {t('common.loading')}
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <div className="settings-note settings-note--error">
            <span>⚠️</span> {error}
          </div>
        )}

        {/* 操作成功提示 */}
        {status && (
          <div className="settings-note settings-note--success">
            <span>✅</span> {status}
          </div>
        )}

        {/* 空状态 */}
        {!loading && plugins.length === 0 && !error && (
          <EmptyState
            title={t('plugins.empty')}
            description={t('plugins.emptyHint')}
          />
        )}

        {/* 插件列表 */}
        <div className="plugin-list">
          {plugins.map(plugin => {
            const sourceInfo = formatSourceType(plugin.source_type);
            const riskInfo = formatRiskLevel(plugin.risk_level);
            const isEnabled = getPluginEnabledState(plugin.id);
            const isToggling = togglingPluginId === plugin.id;
            const isSelected = selectedPluginId === plugin.id;
            const isBuiltin = plugin.source_type === 'builtin';

            return (
              <Card
                key={plugin.id}
                className={`plugin-card ${isSelected ? 'plugin-card--expanded' : ''}`}
              >
                <div className="plugin-card__header">
                  <div className="plugin-card__info">
                    <div className="plugin-card__title-row">
                      <span className="plugin-card__name">{plugin.name}</span>
                      <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
                      <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
                      <span className={`badge badge--${isEnabled ? 'success' : 'secondary'}`}>
                        {isEnabled ? t('plugins.status.enabled') : t('plugins.status.disabled')}
                      </span>
                    </div>
                    <div className="plugin-card__meta">
                      <span>{plugin.id}</span>
                      <span>·</span>
                      <span>v{plugin.version}</span>
                      <span>·</span>
                      <span>{plugin.types.join(', ')}</span>
                    </div>
                  </div>
                  <div className="plugin-card__actions">
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => openPluginDetail(plugin)}
                      title={t('plugins.action.viewDetail')}
                    >
                      {t('plugins.action.viewDetail')}
                    </button>
                    {!isBuiltin && (
                      <button
                        className="btn btn--outline btn--sm"
                        onClick={() => handleTogglePlugin(plugin)}
                        disabled={isToggling || loading}
                        title={isBuiltin ? '内置插件不支持禁用' : undefined}
                      >
                        {isToggling
                          ? t('common.loading')
                          : isEnabled
                            ? t('plugins.action.disable')
                            : t('plugins.action.enable')}
                      </button>
                    )}
                    <button
                      className="btn btn--outline btn--sm"
                      onClick={() => setSelectedPluginId(isSelected ? null : plugin.id)}
                      disabled={jobsLoading}
                    >
                      {isSelected ? t('common.back') : t('plugins.action.viewJobs')}
                    </button>
                  </div>
                </div>

                {/* 权限信息 */}
                {plugin.permissions.length > 0 && (
                  <div className="plugin-card__permissions">
                    <span className="plugin-card__permissions-label">{t('plugins.permissions')}:</span>
                    <span className="plugin-card__permissions-list">{plugin.permissions.join(', ')}</span>
                  </div>
                )}

                {/* 展开显示任务列表 */}
                {isSelected && (
                  <div className="plugin-card__jobs">
                    <h4>{t('plugins.recentJobs')}</h4>
                    {jobsLoading ? (
                      <div className="settings-note">{t('common.loading')}</div>
                    ) : jobs && jobs.items.length > 0 ? (
                      <div className="plugin-job-list">
                        {jobs.items.map(item => {
                          const jobStatus = formatJobStatus(item.job.status);
                          return (
                            <div key={item.job.id} className="plugin-job-item">
                              <div className="plugin-job-item__info">
                                <span className="plugin-job-item__trigger">{item.job.trigger}</span>
                                <span className={`badge badge--${jobStatus.tone}`}>{jobStatus.label}</span>
                              </div>
                              <div className="plugin-job-item__meta">
                                <span>{formatTimestamp(item.job.created_at)}</span>
                                <span>·</span>
                                <span>{t('plugins.jobAttempts')}: {item.job.current_attempt}/{item.job.max_attempts}</span>
                              </div>
                              {item.job.last_error_message && (
                                <div className="plugin-job-item__error">
                                  {item.job.last_error_message}
                                </div>
                              )}
                              {item.allowed_actions.length > 0 && (
                                <div className="plugin-job-item__actions">
                                  {item.allowed_actions.includes('retry') && (
                                    <button className="btn btn--outline btn--sm">{t('plugins.jobRetry')}</button>
                                  )}
                                  {item.allowed_actions.includes('confirm') && (
                                    <button className="btn btn--outline btn--sm">{t('plugins.jobConfirm')}</button>
                                  )}
                                  {item.allowed_actions.includes('cancel') && (
                                    <button className="btn btn--outline btn--sm">{t('plugins.jobCancel')}</button>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="settings-note">{t('plugins.noJobs')}</div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </Section>

      {/* 市场入口（降级占位） */}
      <Section title={t('plugins.market.title')}>
        <Card className="plugin-market-placeholder">
          <div className="plugin-market-placeholder__content">
            <span className="plugin-market-placeholder__icon">🏪</span>
            <h3>{t('plugins.market.comingSoon')}</h3>
            <p>{t('plugins.market.comingSoonHint')}</p>
          </div>
        </Card>
      </Section>

      {/* 插件详情抽屉 */}
      <PluginDetailDrawer
        plugin={detailPlugin}
        householdId={currentHouseholdId}
        isOpen={drawerOpen}
        onClose={closePluginDetail}
        isEnabled={detailPlugin ? getPluginEnabledState(detailPlugin.id) : false}
        onToggle={(plugin) => {
          handleTogglePlugin(plugin);
          // 操作后关闭抽屉
          closePluginDetail();
        }}
        isToggling={togglingPluginId === detailPlugin?.id}
      />
    </div>
  );
}
