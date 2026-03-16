/* ============================================================
 * 插件详情抽屉
 * 展示插件完整信息：描述、权限详情、任务历史、第三方来源警示
 * ============================================================ */
import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api, ApiError } from '../lib/api';
import type {
  PluginConfigForm,
  PluginRegistryItem,
  PluginJobListRead,
  PluginJobListItemRead,
  PluginSourceType,
  PluginRiskLevel,
  PluginManifestType,
} from '../lib/types';
import { DynamicPluginConfigForm } from './plugin-config/DynamicPluginConfigForm';

type PluginDetailDrawerProps = {
  plugin: PluginRegistryItem | null;
  householdId: string | null;
  isOpen: boolean;
  onClose: () => void;
  isEnabled: boolean;
  onToggle: (plugin: PluginRegistryItem) => void;
  isToggling: boolean;
};

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

function formatRiskLevel(riskLevel: PluginRiskLevel): { label: string; tone: 'success' | 'warning' | 'danger'; desc: string } {
  switch (riskLevel) {
    case 'low':
      return { label: '低风险', tone: 'success', desc: '该插件权限有限，安全风险较低' };
    case 'medium':
      return { label: '中等风险', tone: 'warning', desc: '该插件需要部分敏感权限，请注意审核' };
    case 'high':
      return { label: '高风险', tone: 'danger', desc: '该插件需要较高权限，请谨慎使用' };
    default:
      return { label: riskLevel, tone: 'warning', desc: '' };
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
  if (!ts) return '-';
  try {
    return new Date(ts).toLocaleString('zh-CN');
  } catch {
    return ts;
  }
}

function formatPluginType(type: PluginManifestType): string {
  const typeMap: Record<PluginManifestType, string> = {
    connector: '连接器',
    'memory-ingestor': '记忆摄取',
    action: '动作',
    'agent-skill': 'Agent 技能',
    channel: '通讯通道',
    'locale-pack': '语言包',
    'region-provider': '地区提供者',
  };
  return typeMap[type] || type;
}

export function PluginDetailDrawer({
  plugin,
  householdId,
  isOpen,
  onClose,
  isEnabled,
  onToggle,
  isToggling,
}: PluginDetailDrawerProps) {
  const { t } = useI18n();
  const [jobs, setJobs] = useState<PluginJobListItemRead[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState('');
  const [configForm, setConfigForm] = useState<PluginConfigForm | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState('');
  const [configStatus, setConfigStatus] = useState('');

  // 加载最近任务
  useEffect(() => {
    if (!householdId || !plugin || !isOpen) {
      setJobs([]);
      return;
    }

    let cancelled = false;

    const loadJobs = async () => {
      setJobsLoading(true);
      setJobsError('');
      try {
        const result: PluginJobListRead = await api.listPluginJobs(householdId, {
          plugin_id: plugin.id,
          page_size: 10,
        });
        if (!cancelled) {
          setJobs(result.items);
        }
      } catch (err) {
        if (!cancelled) {
          setJobsError(err instanceof ApiError ? err.message : '加载任务失败');
          setJobs([]);
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
  }, [householdId, plugin, isOpen]);

  useEffect(() => {
    if (!householdId || !plugin || !isOpen) {
      setConfigForm(null);
      setConfigError('');
      setConfigStatus('');
      return;
    }

    let cancelled = false;

    const loadConfig = async () => {
      setConfigLoading(true);
      setConfigError('');
      try {
        const scopes = await api.listPluginConfigScopes(householdId, plugin.id);
        const pluginScope = scopes.items.find(item => item.scope_type === 'plugin');
        const scopeInstance = pluginScope?.instances.find(item => item.scope_key === 'default') ?? pluginScope?.instances[0];
        if (!scopeInstance) {
          if (!cancelled) {
            setConfigForm(null);
          }
          return;
        }
        const form = await api.getPluginConfigForm(householdId, plugin.id, {
          scope_type: 'plugin',
          scope_key: scopeInstance.scope_key,
        });
        if (!cancelled) {
          setConfigForm(form);
        }
      } catch (err) {
        if (!cancelled) {
          setConfigError(err instanceof ApiError ? err.message : '加载插件配置失败');
          setConfigForm(null);
        }
      } finally {
        if (!cancelled) {
          setConfigLoading(false);
        }
      }
    };

    void loadConfig();

    return () => {
      cancelled = true;
    };
  }, [householdId, isOpen, plugin]);

  async function handleSavePluginConfig(payload: {
    scope_type: 'plugin' | 'channel_account';
    scope_key: string;
    values: Record<string, unknown>;
    clear_secret_fields?: string[];
  }) {
    if (!householdId || !plugin) {
      return;
    }

    setConfigSaving(true);
    setConfigError('');
    setConfigStatus('');
    try {
      const result = await api.savePluginConfigForm(householdId, plugin.id, payload);
      setConfigForm(result);
      setConfigStatus('插件配置已保存。');
    } catch (err) {
      setConfigError(err instanceof ApiError ? err.message : '保存插件配置失败');
    } finally {
      setConfigSaving(false);
    }
  }

  if (!isOpen || !plugin) return null;

  const sourceInfo = formatSourceType(plugin.source_type);
  const riskInfo = formatRiskLevel(plugin.risk_level);

  // 获取最近一次失败或等待响应的任务
  const latestFailedJob = jobs.find(j => j.job.status === 'failed');
  const latestWaitingJob = jobs.find(j => j.job.status === 'waiting_response');

  return (
    <div className="task-form-overlay" onClick={onClose}>
      <div
        className="task-form-drawer plugin-detail-drawer"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="task-form-drawer__header">
          <div className="plugin-detail-drawer__title-area">
            <h2>{plugin.name}</h2>
            <div className="plugin-detail-drawer__badges">
              <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
              <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
              <span className={`badge badge--${isEnabled ? 'success' : 'secondary'}`}>
                {isEnabled ? t('plugins.status.enabled') : t('plugins.status.disabled')}
              </span>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* 主体内容 */}
        <div className="task-form-drawer__body">
          {/* 第三方来源警示 */}
          {plugin.source_type === 'third_party' && (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--warning">
              <span className="plugin-detail-drawer__alert-icon">⚠️</span>
              <div>
                <strong>{t('plugins.detail.thirdPartyWarning')}</strong>
                <p>{t('plugins.detail.thirdPartyWarningDesc')}</p>
              </div>
            </div>
          )}

          {/* 高风险警示 */}
          {plugin.risk_level === 'high' && (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">🚨</span>
              <div>
                <strong>{t('plugins.detail.highRiskWarning')}</strong>
                <p>{riskInfo.desc}</p>
              </div>
            </div>
          )}

          {/* 任务状态警示 */}
          {latestWaitingJob && (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">⏳</span>
              <div>
                <strong>{t('plugins.detail.jobWaitingResponse')}</strong>
                <p>{t('plugins.detail.jobWaitingResponseDesc')}</p>
              </div>
            </div>
          )}

          {latestFailedJob && !latestWaitingJob && (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">❌</span>
              <div>
                <strong>{t('plugins.detail.jobFailed')}</strong>
                {latestFailedJob.job.last_error_message && (
                  <p>{latestFailedJob.job.last_error_message}</p>
                )}
              </div>
            </div>
          )}

          {!isEnabled && (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">⏸️</span>
              <div>
                <strong>{plugin.disabled_reason || '插件当前已停用'}</strong>
                <p>
                  {plugin.source_type === 'builtin'
                    ? '这个家庭里已经不会继续使用该内置插件能力。'
                    : '配置仍存在，但插件已停用；重新启用后会继续使用现有配置。'}
                </p>
              </div>
            </div>
          )}

          {/* 基本信息 */}
          <div className="plugin-detail-section">
            <h3>{t('plugins.detail.basicInfo')}</h3>
            <div className="plugin-detail-grid">
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">ID</span>
                <span className="plugin-detail-grid__value">{plugin.id}</span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">{t('plugins.detail.version')}</span>
                <span className="plugin-detail-grid__value">v{plugin.version}</span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">{t('plugins.detail.types')}</span>
                <span className="plugin-detail-grid__value">
                  {plugin.types.map(formatPluginType).join('、')}
                </span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">{t('plugins.detail.source')}</span>
                <span className={`plugin-detail-grid__value plugin-detail-grid__value--${sourceInfo.tone}`}>
                  {sourceInfo.label}
                </span>
              </div>
            </div>
          </div>

          {/* 权限信息 */}
          <div className="plugin-detail-section">
            <h3>{t('plugins.detail.permissions')}</h3>
            {plugin.permissions.length > 0 ? (
              <div className="plugin-detail-permissions">
                {plugin.permissions.map((perm, idx) => (
                  <span key={idx} className="plugin-detail-permission-tag">
                    {perm}
                  </span>
                ))}
              </div>
            ) : (
              <p className="plugin-detail-empty">{t('plugins.detail.noPermissions')}</p>
            )}
          </div>

          {/* 触发器 */}
          {plugin.triggers.length > 0 && (
            <div className="plugin-detail-section">
              <h3>{t('plugins.detail.triggers')}</h3>
              <div className="plugin-detail-triggers">
                {plugin.triggers.map((trigger, idx) => (
                  <span key={idx} className="plugin-detail-trigger-tag">
                    {trigger}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 入口点 */}
          <div className="plugin-detail-section">
            <h3>{t('plugins.detail.entrypoints')}</h3>
            <div className="plugin-detail-entrypoints">
              {Object.entries(plugin.entrypoints).map(([key, value]) => (
                value && (
                  <div key={key} className="plugin-detail-entrypoint">
                    <span className="plugin-detail-entrypoint__key">{key}</span>
                    <span className="plugin-detail-entrypoint__value">{value}</span>
                  </div>
                )
              ))}
              {!Object.values(plugin.entrypoints).some(Boolean) && (
                <p className="plugin-detail-empty">{t('plugins.detail.noEntrypoints')}</p>
              )}
            </div>
          </div>

          {/* 语言支持 */}
          {plugin.locales.length > 0 && (
            <div className="plugin-detail-section">
              <h3>{t('plugins.detail.locales')}</h3>
              <div className="plugin-detail-locales">
                {plugin.locales.map((locale) => (
                  <span key={locale.id} className="plugin-detail-locale-tag">
                    {locale.label} ({locale.id})
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="plugin-detail-section">
            <h3>插件配置</h3>
            {configLoading ? (
              <div className="plugin-detail-loading">正在加载配置...</div>
            ) : configForm ? (
              <>
                <DynamicPluginConfigForm
                  configSpec={configForm.config_spec}
                  view={configForm.view}
                  onSubmit={handleSavePluginConfig}
                  saving={configSaving}
                  formError={configError}
                />
                {configStatus && <div className="plugin-config-inline-status">{configStatus}</div>}
              </>
            ) : (
              <p className="plugin-detail-empty">
                {plugin.config_specs.some(item => item.scope_type === 'channel_account')
                  ? '这个插件只有账号级配置，请去通道接入页设置。'
                  : '这个插件没有插件级配置。'}
              </p>
            )}
          </div>

          {/* 最近任务 */}
          <div className="plugin-detail-section">
            <h3>{t('plugins.recentJobs')}</h3>
            {jobsLoading ? (
              <div className="plugin-detail-loading">{t('common.loading')}</div>
            ) : jobsError ? (
              <div className="plugin-detail-error">{jobsError}</div>
            ) : jobs.length > 0 ? (
              <div className="plugin-detail-jobs">
                {jobs.map((item) => {
                  const jobStatus = formatJobStatus(item.job.status);
                  return (
                    <div key={item.job.id} className="plugin-detail-job">
                      <div className="plugin-detail-job__header">
                        <span className="plugin-detail-job__trigger">{item.job.trigger}</span>
                        <span className={`badge badge--${jobStatus.tone}`}>{jobStatus.label}</span>
                      </div>
                      <div className="plugin-detail-job__meta">
                        <span>{formatTimestamp(item.job.created_at)}</span>
                        <span>·</span>
                        <span>{t('plugins.jobAttempts')}: {item.job.current_attempt}/{item.job.max_attempts}</span>
                      </div>
                      {item.job.last_error_message && (
                        <div className="plugin-detail-job__error">
                          {item.job.last_error_message}
                        </div>
                      )}
                      {item.allowed_actions.length > 0 && (
                        <div className="plugin-detail-job__actions">
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
              <p className="plugin-detail-empty">{t('plugins.noJobs')}</p>
            )}
          </div>
        </div>

        {/* 底部操作 */}
        <div className="task-form-drawer__actions">
          <button className="btn btn--ghost" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            className={`btn ${isEnabled ? 'btn--outline' : 'btn--primary'}`}
            onClick={() => onToggle(plugin)}
            disabled={isToggling}
          >
            {isToggling
              ? t('common.loading')
              : isEnabled
                ? t('plugins.action.disable')
                : t('plugins.action.enable')}
          </button>
        </div>
      </div>
    </div>
  );
}
