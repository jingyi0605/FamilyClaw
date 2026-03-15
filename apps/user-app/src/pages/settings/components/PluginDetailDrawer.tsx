import { useEffect, useState } from 'react';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  PluginJobListItemRead,
  PluginJobListRead,
  PluginManifestType,
  PluginRegistryItem,
  PluginRiskLevel,
  PluginSourceType,
} from '../settingsTypes';

function formatSourceType(sourceType: PluginSourceType): { label: string; tone: 'info' | 'success' | 'warning' } {
  switch (sourceType) {
    case 'builtin':
      return { label: '鍐呯疆', tone: 'info' };
    case 'official':
      return { label: '瀹樻柟', tone: 'success' };
    case 'third_party':
      return { label: '???', tone: 'warning' };
    default:
      return { label: sourceType, tone: 'info' };
  }
}

function formatRiskLevel(riskLevel: PluginRiskLevel): { label: string; tone: 'success' | 'warning' | 'danger'; desc: string } {
  switch (riskLevel) {
    case 'low':
      return { label: '???', tone: 'success', desc: '????????????????' };
    case 'medium':
      return { label: '???', tone: 'warning', desc: '?????????????????????' };
    case 'high':
      return { label: '???', tone: 'danger', desc: '?????????????????' };
    default:
      return { label: riskLevel, tone: 'warning', desc: '' };
  }
}

function formatJobStatus(status: string): { label: string; tone: 'success' | 'warning' | 'danger' | 'secondary' } {
  switch (status) {
    case 'succeeded':
      return { label: '鎴愬姛', tone: 'success' };
    case 'queued':
      return { label: '???', tone: 'warning' };
    case 'running':
      return { label: '???', tone: 'warning' };
    case 'retry_waiting':
      return { label: '绛夊緟閲嶈瘯', tone: 'warning' };
    case 'waiting_response':
      return { label: '绛夊緟鍝嶅簲', tone: 'warning' };
    case 'failed':
      return { label: '澶辫触', tone: 'danger' };
    case 'cancelled':
      return { label: '???', tone: 'secondary' };
    default:
      return { label: status, tone: 'secondary' };
  }
}

function formatTimestamp(value: string | null) {
  if (!value) {
    return '-';
  }
  try {
    return new Date(value).toLocaleString('zh-CN');
  } catch {
    return value;
  }
}

function formatPluginType(type: PluginManifestType) {
  const typeMap: Record<PluginManifestType, string> = {
    connector: '???',
    'memory-ingestor': '璁板繂鎽勫彇',
    action: '鍔ㄤ綔',
    'agent-skill': 'Agent ??',
    channel: '閫氳閫氶亾',
    'locale-pack': '???',
    'region-provider': '?????',
  };
  return typeMap[type] ?? type;
}

export function PluginDetailDrawer(props: {
  plugin: PluginRegistryItem | null;
  householdId: string | null;
  isOpen: boolean;
  onClose: () => void;
  isEnabled: boolean;
  onToggle: (plugin: PluginRegistryItem) => void;
  isToggling: boolean;
}) {
  const { plugin, householdId, isOpen, onClose, isEnabled, onToggle, isToggling } = props;
  const [jobs, setJobs] = useState<PluginJobListItemRead[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState('');

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
          setJobsError(error instanceof ApiError ? error.message : '鍔犺浇浠诲姟澶辫触');
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
  }, [householdId, isOpen, plugin]);

  if (!isOpen || !plugin) {
    return null;
  }

  const sourceInfo = formatSourceType(plugin.source_type);
  const riskInfo = formatRiskLevel(plugin.risk_level);
  const latestFailedJob = jobs.find((item) => item.job.status === 'failed');
  const latestWaitingJob = jobs.find((item) => item.job.status === 'waiting_response');

  return (
    <div className="task-form-overlay" onClick={onClose}>
      <div className="task-form-drawer plugin-detail-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="task-form-drawer__header">
          <div className="plugin-detail-drawer__title-area">
            <h2>{plugin.name}</h2>
            <div className="plugin-detail-drawer__badges">
              <span className={`badge badge--${sourceInfo.tone}`}>{sourceInfo.label}</span>
              <span className={`badge badge--${riskInfo.tone}`}>{riskInfo.label}</span>
              <span className={`badge badge--${isEnabled ? 'success' : 'secondary'}`}>{isEnabled ? '???' : '???'}</span>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose}>脳</button>
        </div>

        <div className="task-form-drawer__body">
          {plugin.source_type === 'third_party' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--warning">
              <span className="plugin-detail-drawer__alert-icon">鈿狅笍</span>
              <div>
                <strong>Third-party plugin</strong>
                <p>This plugin comes from a third-party source. Check its permissions, stability, and maintenance status carefully.</p>
              </div>
            </div>
          ) : null}

          {plugin.risk_level === 'high' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">馃毃</span>
              <div>
                <strong>High-risk plugin</strong>
                <p>{riskInfo.desc}</p>
              </div>
            </div>
          ) : null}

          {latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">!</span>
              <div>
                <strong>A recent job is waiting for a response</strong>
                <p>Handle that job first before deciding whether the plugin is actually stuck.</p>
              </div>
            </div>
          ) : null}

          {latestFailedJob && !latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">!</span>
              <div>
                <strong>Latest job failed</strong>
                {latestFailedJob.job.last_error_message ? <p>{latestFailedJob.job.last_error_message}</p> : null}
              </div>
            </div>
          ) : null}

          {!isEnabled ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">鈴革笍</span>
              <div>
                <strong>{plugin.disabled_reason || '???????'}</strong>
                <p>The configuration is still there and will be reused after the plugin is enabled again.</p>
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>鍩烘湰淇℃伅</h3>
            <div className="plugin-detail-grid">
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">ID</span>
                <span className="plugin-detail-grid__value">{plugin.id}</span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">鐗堟湰</span>
                <span className="plugin-detail-grid__value">v{plugin.version}</span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">绫诲瀷</span>
                <span className="plugin-detail-grid__value">{plugin.types.map(formatPluginType).join('?')}</span>
              </div>
              <div className="plugin-detail-grid__item">
                <span className="plugin-detail-grid__label">鏉ユ簮</span>
                <span className={`plugin-detail-grid__value plugin-detail-grid__value--${sourceInfo.tone}`}>{sourceInfo.label}</span>
              </div>
            </div>
          </div>

          <div className="plugin-detail-section">
            <h3>鏉冮檺</h3>
            {plugin.permissions.length > 0 ? (
              <div className="plugin-detail-permissions">
                {plugin.permissions.map((permission) => (
                  <span key={permission} className="plugin-detail-permission-tag">{permission}</span>
                ))}
              </div>
            ) : (
              <p className="plugin-detail-empty">No extra permissions declared.</p>
            )}
          </div>

          {plugin.triggers.length > 0 ? (
            <div className="plugin-detail-section">
              <h3>Triggers</h3>
              <div className="plugin-detail-triggers">
                {plugin.triggers.map((trigger) => (
                  <span key={trigger} className="plugin-detail-trigger-tag">{trigger}</span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>Entrypoints</h3>
            <div className="plugin-detail-entrypoints">
              {Object.entries(plugin.entrypoints).map(([key, value]) => value ? (
                <div key={key} className="plugin-detail-entrypoint">
                  <span className="plugin-detail-entrypoint__key">{key}</span>
                  <span className="plugin-detail-entrypoint__value">{value}</span>
                </div>
              ) : null)}
              {!Object.values(plugin.entrypoints).some(Boolean) ? <p className="plugin-detail-empty">No entrypoints declared.</p> : null}
            </div>
          </div>

          {plugin.locales.length > 0 ? (
            <div className="plugin-detail-section">
              <h3>璇█鏀寔</h3>
              <div className="plugin-detail-locales">
                {plugin.locales.map((locale) => (
                  <span key={locale.id} className="plugin-detail-locale-tag">{locale.label} ({locale.id})</span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>Recent Jobs</h3>
            {jobsLoading ? (
              <div className="plugin-detail-loading settings-loading-copy settings-loading-copy--center">正在加载最近任务...</div>
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
                        <span>路</span>
                        <span>Attempts: {item.job.current_attempt}/{item.job.max_attempts}</span>
                      </div>
                      {item.job.last_error_message ? <div className="plugin-detail-job__error">{item.job.last_error_message}</div> : null}
                      {item.allowed_actions.length > 0 ? (
                        <div className="plugin-detail-job__actions">
                          {item.allowed_actions.includes('retry') ? <button className="btn btn--outline btn--sm">閲嶈瘯</button> : null}
                          {item.allowed_actions.includes('confirm') ? <button className="btn btn--outline btn--sm">纭</button> : null}
                          {item.allowed_actions.includes('cancel') ? <button className="btn btn--outline btn--sm">鍙栨秷</button> : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="plugin-detail-empty">No recent jobs.</p>
            )}
          </div>
        </div>

        <div className="task-form-drawer__actions">
          <button className="btn btn--ghost" onClick={onClose}>鍏抽棴</button>
          <button className={`btn ${isEnabled ? 'btn--outline' : 'btn--primary'}`} onClick={() => onToggle(plugin)} disabled={isToggling}>
            {isToggling ? '澶勭悊涓?..' : isEnabled ? '鍋滅敤' : '鍚敤'}
          </button>
        </div>
      </div>
    </div>
  );
}
