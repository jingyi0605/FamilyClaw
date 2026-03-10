/* ============================================================
 * SettingsNav - 设置页二级侧边导航
 * ============================================================ */
import { NavLink } from 'react-router-dom';
import { Palette, Bot, Globe, Bell, HeartHandshake, Link as LinkIcon } from 'lucide-react';
import { useI18n } from '../i18n';

const settingsItems = [
  { to: '/settings/appearance', icon: <Palette size={20} />, labelKey: 'settings.appearance' as const, descKey: 'settings.appearanceDesc' as const },
  { to: '/settings/ai', icon: <Bot size={20} />, labelKey: 'settings.ai' as const, descKey: 'settings.aiDesc' as const },
  { to: '/settings/language', icon: <Globe size={20} />, labelKey: 'settings.language' as const, descKey: 'settings.languageDesc' as const },
  { to: '/settings/notifications', icon: <Bell size={20} />, labelKey: 'settings.notifications' as const, descKey: 'settings.notificationsDesc' as const },
  { to: '/settings/accessibility', icon: <HeartHandshake size={20} />, labelKey: 'settings.accessibility' as const, descKey: 'settings.accessibilityDesc' as const },
  { to: '/settings/integrations', icon: <LinkIcon size={20} />, labelKey: 'settings.integrations' as const, descKey: 'settings.integrationsDesc' as const },
];

export function SettingsNav() {
  const { t } = useI18n();

  return (
    <nav className="settings-nav">
      {settingsItems.map(item => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) => `settings-nav__item ${isActive ? 'settings-nav__item--active' : ''}`}
        >
          <span className="settings-nav__icon">{item.icon}</span>
          <div className="settings-nav__text">
            <span className="settings-nav__label">{t(item.labelKey)}</span>
            <span className="settings-nav__desc">{t(item.descKey)}</span>
          </div>
        </NavLink>
      ))}
    </nav>
  );
}
