/* ============================================================
 * 设置页 - 二级导航 + 6 个子页面
 * ============================================================ */
import { Outlet, useMatch, Navigate } from 'react-router-dom';
import { useI18n } from '../i18n';
import { useTheme, themeList, type ThemeId } from '../theme';
import { PageHeader, Card, Section, ToggleSwitch } from '../components/base';
import { SettingsNav } from '../components/SettingsNav';

/* ---- 设置布局 ---- */
export function SettingsLayout() {
  const { t } = useI18n();
  const isRoot = useMatch('/settings');

  if (isRoot) {
    return <Navigate to="/settings/appearance" replace />;
  }

  return (
    <div className="page page--settings">
      <PageHeader title={t('settings.title')} />
      <div className="settings-layout">
        <SettingsNav />
        <div className="settings-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/* ---- 外观主题 ---- */
export function SettingsAppearance() {
  const { t } = useI18n();
  const { themeId, setTheme } = useTheme();

  return (
    <div className="settings-page">
      <Section title={t('settings.appearance.theme')}>
        <div className="theme-grid">
          {themeList.map(th => (
            <div
              key={th.id}
              className={`theme-card ${themeId === th.id ? 'theme-card--active' : ''}`}
              onClick={() => setTheme(th.id)}
              style={{
                '--preview-bg': th.bgApp,
                '--preview-card': th.bgCard,
                '--preview-brand': th.brandPrimary,
                '--preview-text': th.textPrimary,
                '--preview-glow': th.glowColor,
              } as React.CSSProperties}
            >
              {/* 主题预览色块 */}
              <div className="theme-card__preview">
                <div className="theme-card__preview-bg">
                  <div className="theme-card__preview-sidebar" />
                  <div className="theme-card__preview-content">
                    <div className="theme-card__preview-bar" />
                    <div className="theme-card__preview-cards">
                      <div className="theme-card__preview-mini" />
                      <div className="theme-card__preview-mini" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="theme-card__info">
                <span className="theme-card__emoji">{th.emoji}</span>
                <div className="theme-card__text">
                  <span className="theme-card__label">{th.label}</span>
                  <span className="theme-card__desc">{th.description}</span>
                </div>
                {themeId === th.id && <span className="theme-card__check">✓</span>}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

/* ---- AI 配置 ---- */
export function SettingsAi() {
  const { t } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.ai.assistantName')}</label>
            <input type="text" className="form-input" defaultValue="家庭助手" />
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyTone')}</label>
            <select className="form-select">
              <option>温和友好</option>
              <option>简洁干练</option>
              <option>活泼有趣</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.replyLength')}</label>
            <select className="form-select">
              <option>适中</option>
              <option>简短</option>
              <option>详细</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.ai.outputLanguage')}</label>
            <select className="form-select">
              <option>中文</option>
              <option>English</option>
            </select>
          </div>

          <div className="settings-toggles">
            <ToggleSwitch checked={true} label={t('settings.ai.useMemory')} description={t('settings.ai.useMemoryDesc')} />
            <ToggleSwitch checked={true} label={t('settings.ai.suggestReminder')} description={t('settings.ai.suggestReminderDesc')} />
            <ToggleSwitch checked={false} label={t('settings.ai.suggestScene')} description={t('settings.ai.suggestSceneDesc')} />
          </div>

          <div className="form-group">
            <label>{t('settings.ai.privacyLevel')}</label>
            <select className="form-select">
              <option>标准</option>
              <option>严格</option>
              <option>宽松</option>
            </select>
          </div>
        </div>
        <div className="settings-note">
          <span>ℹ️</span> {t('settings.ai.advancedNote')}
        </div>
      </Section>
    </div>
  );
}

/* ---- 语言与地区 ---- */
export function SettingsLanguage() {
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.language')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.language.interfaceLang')}</label>
            <select className="form-select" value={locale} onChange={e => setLocale(e.target.value as 'zh-CN' | 'en-US')}>
              <option value="zh-CN">中文（简体）</option>
              <option value="en-US">English</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.dateFormat')}</label>
            <select className="form-select">
              <option>YYYY-MM-DD</option>
              <option>MM/DD/YYYY</option>
              <option>DD/MM/YYYY</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t('settings.language.timeFormat')}</label>
            <select className="form-select">
              <option>24 小时制</option>
              <option>12 小时制</option>
            </select>
          </div>
        </div>
      </Section>
    </div>
  );
}

/* ---- 通知偏好 ---- */
export function SettingsNotifications() {
  const { t } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.notifications')}>
        <div className="settings-form">
          <div className="form-group">
            <label>{t('settings.notifications.method')}</label>
            <select className="form-select">
              <option>浏览器通知 + 站内消息</option>
              <option>仅站内消息</option>
              <option>全部关闭</option>
            </select>
          </div>
          <div className="settings-toggles">
            <ToggleSwitch checked={false} label={t('settings.notifications.dnd')} description="开启后在指定时间段内不会收到通知" />
          </div>
          <div className="form-group">
            <label>{t('settings.notifications.scope')}</label>
            <select className="form-select">
              <option>全部通知</option>
              <option>仅紧急通知</option>
              <option>仅与我相关</option>
            </select>
          </div>
        </div>
      </Section>
    </div>
  );
}

/* ---- 长辈友好模式 ---- */
export function SettingsAccessibility() {
  const { t } = useI18n();
  const { themeId, setTheme } = useTheme();
  const isElder = themeId === 'ming-cha-qiu-hao';

  return (
    <div className="settings-page">
      <Section title={t('settings.accessibility')}>
        <div className="settings-toggles">
          <ToggleSwitch
            checked={isElder}
            label={t('settings.accessibility.enable')}
            description={t('settings.accessibility.enableDesc')}
            onChange={v => setTheme(v ? 'ming-cha-qiu-hao' : 'chun-he-jing-ming')}
          />
        </div>
        <div className="elder-preview">
          <Card className="elder-preview-card">
            <h3>预览效果</h3>
            <p style={{ fontSize: isElder ? '1.125rem' : '0.9375rem' }}>
              {isElder
                ? '长辈友好模式已开启。界面使用更大的字号和更高的对比度。'
                : '当前为标准模式。开启长辈友好模式后，界面会更适合年长用户使用。'}
            </p>
          </Card>
        </div>
      </Section>
    </div>
  );
}

/* ---- 设备与集成 ---- */
export function SettingsIntegrations() {
  const { t } = useI18n();

  return (
    <div className="settings-page">
      <Section title={t('settings.integrations.haStatus')}>
        <Card className="integration-status-card">
          <div className="integration-status">
            <span className="integration-status__indicator integration-status__indicator--online" />
            <div className="integration-status__text">
              <span className="integration-status__label">Home Assistant</span>
              <span className="integration-status__detail">已连接 · {t('settings.integrations.lastSync')}：5 分钟前</span>
            </div>
            <button className="btn btn--outline btn--sm">{t('settings.integrations.syncNow')}</button>
          </div>
        </Card>
      </Section>
      <Section title={t('settings.integrations.devices')}>
        <div className="device-list">
          {[
            { name: '客厅主灯', room: '客厅', status: '在线', type: '灯光' },
            { name: '空调', room: '主卧', status: '在线', type: '温控' },
            { name: '门锁', room: '玄关', status: '在线', type: '安防' },
            { name: '扫地机器人', room: '客厅', status: '离线', type: '清洁' },
          ].map((device, i) => (
            <Card key={i} className="device-card">
              <div className="device-card__info">
                <span className="device-card__name">{device.name}</span>
                <span className="device-card__room">{device.room} · {device.type}</span>
              </div>
              <span className={`badge badge--${device.status === '在线' ? 'success' : 'secondary'}`}>
                {device.status}
              </span>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}
