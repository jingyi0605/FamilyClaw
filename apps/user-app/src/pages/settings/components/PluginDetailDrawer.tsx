import { useEffect, useState } from 'react';
import { useI18n } from '../../../runtime';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  PluginJobListItemRead,
  PluginJobListRead,
  PluginManifestType,
  PluginRegistryItem,
  PluginRiskLevel,
  PluginSourceType,
} from '../settingsTypes';

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
  if (locale?.toLowerCase().startsWith('en')) return 'en-US';
  if (locale?.toLowerCase().startsWith('zh-tw')) return 'zh-TW';
  return 'zh-CN';
}

function formatSourceType(sourceType: PluginSourceType, locale: string | undefined) {
  switch (sourceType) {
    case 'builtin':
      return { label: pickLocaleText(locale, { zhCN: '内置', zhTW: '內建', enUS: 'Built-in' }), tone: 'info' as const };
    case 'official':
      return { label: pickLocaleText(locale, { zhCN: '官方', zhTW: '官方', enUS: 'Official' }), tone: 'success' as const };
    case 'third_party':
      return { label: pickLocaleText(locale, { zhCN: '第三方', zhTW: '第三方', enUS: 'Third-party' }), tone: 'warning' as const };
    default:
      return { label: sourceType, tone: 'info' as const };
  }
}

function formatRiskLevel(riskLevel: PluginRiskLevel, locale: string | undefined) {
  switch (riskLevel) {
    case 'low':
      return {
        label: pickLocaleText(locale, { zhCN: '低风险', zhTW: '低風險', enUS: 'Low risk' }),
        tone: 'success' as const,
        desc: pickLocaleText(locale, {
          zhCN: '权限和行为都比较克制，风险相对低。',
          zhTW: '權限和行為都比較克制，風險相對低。',
          enUS: 'Permissions and behavior are relatively constrained.',
        }),
      };
    case 'medium':
      return {
        label: pickLocaleText(locale, { zhCN: '中风险', zhTW: '中風險', enUS: 'Medium risk' }),
        tone: 'warning' as const,
        desc: pickLocaleText(locale, {
          zhCN: '能做的事情更多，启用前最好确认权限范围。',
          zhTW: '能做的事情更多，啟用前最好確認權限範圍。',
          enUS: 'It can do more, so review the permission scope before enabling it.',
        }),
      };
    case 'high':
      return {
        label: pickLocaleText(locale, { zhCN: '高风险', zhTW: '高風險', enUS: 'High risk' }),
        tone: 'danger' as const,
        desc: pickLocaleText(locale, {
          zhCN: '这类插件能力很强，先确认来源、权限和维护状态，再决定要不要开。',
          zhTW: '這類外掛能力很強，先確認來源、權限和維護狀態，再決定要不要開。',
          enUS: 'This plugin is powerful. Verify source, permissions, and maintenance status before enabling it.',
        }),
      };
    default:
      return { label: riskLevel, tone: 'warning' as const, desc: '' };
  }
}

function formatJobStatus(status: string, locale: string | undefined) {
  switch (status) {
    case 'succeeded':
      return { label: pickLocaleText(locale, { zhCN: '成功', zhTW: '成功', enUS: 'Succeeded' }), tone: 'success' as const };
    case 'queued':
      return { label: pickLocaleText(locale, { zhCN: '排队中', zhTW: '排隊中', enUS: 'Queued' }), tone: 'warning' as const };
    case 'running':
      return { label: pickLocaleText(locale, { zhCN: '执行中', zhTW: '執行中', enUS: 'Running' }), tone: 'warning' as const };
    case 'retry_waiting':
      return { label: pickLocaleText(locale, { zhCN: '等待重试', zhTW: '等待重試', enUS: 'Waiting to retry' }), tone: 'warning' as const };
    case 'waiting_response':
      return { label: pickLocaleText(locale, { zhCN: '等待响应', zhTW: '等待回應', enUS: 'Waiting for response' }), tone: 'warning' as const };
    case 'failed':
      return { label: pickLocaleText(locale, { zhCN: '失败', zhTW: '失敗', enUS: 'Failed' }), tone: 'danger' as const };
    case 'cancelled':
      return { label: pickLocaleText(locale, { zhCN: '已取消', zhTW: '已取消', enUS: 'Cancelled' }), tone: 'secondary' as const };
    default:
      return { label: status, tone: 'secondary' as const };
  }
}

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

function formatTimestamp(value: string | null, locale: string | undefined) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString(resolveDateLocale(locale));
  } catch {
    return value;
  }
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
  const { locale } = useI18n();
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
          setJobsError(error instanceof ApiError ? error.message : pickLocaleText(locale, {
            zhCN: '加载任务失败',
            zhTW: '載入任務失敗',
            enUS: 'Failed to load jobs',
          }));
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
  }, [householdId, isOpen, locale, plugin]);

  if (!isOpen || !plugin) {
    return null;
  }

  const sourceInfo = formatSourceType(plugin.source_type, locale);
  const riskInfo = formatRiskLevel(plugin.risk_level, locale);
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
              <span className={`badge badge--${isEnabled ? 'success' : 'secondary'}`}>
                {pickLocaleText(locale, { zhCN: isEnabled ? '已启用' : '已停用', zhTW: isEnabled ? '已啟用' : '已停用', enUS: isEnabled ? 'Enabled' : 'Disabled' })}
              </span>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose}>×</button>
        </div>

        <div className="task-form-drawer__body">
          {plugin.source_type === 'third_party' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--warning">
              <span className="plugin-detail-drawer__alert-icon">⚠️</span>
              <div>
                <strong>{pickLocaleText(locale, { zhCN: '第三方插件', zhTW: '第三方外掛', enUS: 'Third-party plugin' })}</strong>
                <p>{pickLocaleText(locale, { zhCN: '来源不在系统可控范围内，先看权限、稳定性和维护状态。', zhTW: '來源不在系統可控範圍內，先看權限、穩定性和維護狀態。', enUS: 'This plugin is not controlled by the system. Review permissions, stability, and maintenance before trusting it.' })}</p>
              </div>
            </div>
          ) : null}

          {plugin.risk_level === 'high' ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">⛔</span>
              <div>
                <strong>{pickLocaleText(locale, { zhCN: '高风险插件', zhTW: '高風險外掛', enUS: 'High-risk plugin' })}</strong>
                <p>{riskInfo.desc}</p>
              </div>
            </div>
          ) : null}

          {latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">ℹ️</span>
              <div>
                <strong>{pickLocaleText(locale, { zhCN: '最近有任务在等响应', zhTW: '最近有任務在等回應', enUS: 'A recent job is waiting for a response' })}</strong>
                <p>{pickLocaleText(locale, { zhCN: '先处理这条任务，再判断插件是不是真的卡住了。', zhTW: '先處理這條任務，再判斷外掛是不是真的卡住了。', enUS: 'Handle that job first before deciding whether the plugin is actually stuck.' })}</p>
              </div>
            </div>
          ) : null}

          {latestFailedJob && !latestWaitingJob ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--danger">
              <span className="plugin-detail-drawer__alert-icon">⚠️</span>
              <div>
                <strong>{pickLocaleText(locale, { zhCN: '最近一次任务失败', zhTW: '最近一次任務失敗', enUS: 'Latest job failed' })}</strong>
                {latestFailedJob.job.last_error_message ? <p>{latestFailedJob.job.last_error_message}</p> : null}
              </div>
            </div>
          ) : null}

          {!isEnabled ? (
            <div className="plugin-detail-drawer__alert plugin-detail-drawer__alert--info">
              <span className="plugin-detail-drawer__alert-icon">⏸️</span>
              <div>
                <strong>{plugin.disabled_reason || pickLocaleText(locale, { zhCN: '当前插件处于停用状态', zhTW: '目前外掛處於停用狀態', enUS: 'This plugin is currently disabled' })}</strong>
                <p>{pickLocaleText(locale, { zhCN: '配置还在，重新启用时会继续复用。', zhTW: '設定還在，重新啟用時會繼續復用。', enUS: 'The configuration is still there and will be reused when the plugin is enabled again.' })}</p>
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{pickLocaleText(locale, { zhCN: '基本信息', zhTW: '基本資訊', enUS: 'Basics' })}</h3>
            <div className="plugin-detail-grid">
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">ID</span><span className="plugin-detail-grid__value">{plugin.id}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{pickLocaleText(locale, { zhCN: '版本', zhTW: '版本', enUS: 'Version' })}</span><span className="plugin-detail-grid__value">v{plugin.version}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{pickLocaleText(locale, { zhCN: '类型', zhTW: '類型', enUS: 'Type' })}</span><span className="plugin-detail-grid__value">{plugin.types.map((type) => formatPluginType(type, locale)).join('、')}</span></div>
              <div className="plugin-detail-grid__item"><span className="plugin-detail-grid__label">{pickLocaleText(locale, { zhCN: '来源', zhTW: '來源', enUS: 'Source' })}</span><span className={`plugin-detail-grid__value plugin-detail-grid__value--${sourceInfo.tone}`}>{sourceInfo.label}</span></div>
            </div>
          </div>

          <div className="plugin-detail-section">
            <h3>{pickLocaleText(locale, { zhCN: '权限', zhTW: '權限', enUS: 'Permissions' })}</h3>
            {plugin.permissions.length > 0 ? (
              <div className="plugin-detail-permissions">
                {plugin.permissions.map((permission) => <span key={permission} className="plugin-detail-permission-tag">{permission}</span>)}
              </div>
            ) : (
              <p className="plugin-detail-empty">{pickLocaleText(locale, { zhCN: '没有声明额外权限。', zhTW: '沒有宣告額外權限。', enUS: 'No extra permissions declared.' })}</p>
            )}
          </div>

          {plugin.triggers.length > 0 ? (
            <div className="plugin-detail-section">
              <h3>{pickLocaleText(locale, { zhCN: '触发器', zhTW: '觸發器', enUS: 'Triggers' })}</h3>
              <div className="plugin-detail-triggers">
                {plugin.triggers.map((trigger) => <span key={trigger} className="plugin-detail-trigger-tag">{trigger}</span>)}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{pickLocaleText(locale, { zhCN: '入口点', zhTW: '入口點', enUS: 'Entrypoints' })}</h3>
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
              <h3>{pickLocaleText(locale, { zhCN: '语言支持', zhTW: '語言支援', enUS: 'Locales' })}</h3>
              <div className="plugin-detail-permissions">
                {plugin.locales.map((item) => <span key={item.id} className="plugin-detail-permission-tag">{item.native_label}</span>)}
              </div>
            </div>
          ) : null}

          <div className="plugin-detail-section">
            <h3>{pickLocaleText(locale, { zhCN: '最近任务', zhTW: '最近任務', enUS: 'Recent Jobs' })}</h3>
            {jobsError ? <div className="settings-note settings-note--error"><span>⚠️</span> {jobsError}</div> : null}
            {jobsLoading ? (
              <div className="plugin-detail-loading settings-loading-copy settings-loading-copy--center">{pickLocaleText(locale, { zhCN: '正在加载最近任务...', zhTW: '正在載入最近任務...', enUS: 'Loading recent jobs...' })}</div>
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
                        <span>·</span>
                        <span>{pickLocaleText(locale, { zhCN: '尝试次数', zhTW: '嘗試次數', enUS: 'Attempts' })}：{item.job.current_attempt}/{item.job.max_attempts}</span>
                      </div>
                      {item.job.last_error_message ? <div className="plugin-job-item__error">{item.job.last_error_message}</div> : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="plugin-detail-empty">{pickLocaleText(locale, { zhCN: '最近没有任务记录。', zhTW: '最近沒有任務紀錄。', enUS: 'No recent jobs.' })}</div>
            )}
          </div>
        </div>

        <div className="task-form-drawer__footer">
          <button className="btn btn--ghost" onClick={onClose}>{pickLocaleText(locale, { zhCN: '关闭', zhTW: '關閉', enUS: 'Close' })}</button>
          <button className="btn btn--primary" onClick={() => onToggle(plugin)} disabled={isToggling}>
            {isToggling
              ? pickLocaleText(locale, { zhCN: '处理中...', zhTW: '處理中...', enUS: 'Processing...' })
              : pickLocaleText(locale, {
                zhCN: isEnabled ? '停用插件' : '启用插件',
                zhTW: isEnabled ? '停用外掛' : '啟用外掛',
                enUS: isEnabled ? 'Disable Plugin' : 'Enable Plugin',
              })}
          </button>
        </div>
      </div>
    </div>
  );
}
