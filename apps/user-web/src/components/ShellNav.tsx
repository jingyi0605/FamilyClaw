/* ============================================================
 * ShellNav - 左侧主导航
 * ============================================================ */
import { NavLink } from 'react-router-dom';
import { Home, Users, MessageSquareText, BookOpenText, Settings } from 'lucide-react';
import { useI18n } from '../i18n';
import { useAuthContext } from '../state/auth';
import { useHouseholdContext } from '../state/household';

const navItems = [
  { to: '/', icon: <Home size={20} strokeWidth={2.5} />, labelKey: 'nav.home' as const, end: true },
  { to: '/family', icon: <Users size={20} strokeWidth={2.5} />, labelKey: 'nav.family' as const },
  { to: '/conversation', icon: <MessageSquareText size={20} strokeWidth={2.5} />, labelKey: 'nav.assistant' as const },
  { to: '/memories', icon: <BookOpenText size={20} strokeWidth={2.5} />, labelKey: 'nav.memories' as const },
  { to: '/settings', icon: <Settings size={20} strokeWidth={2.5} />, labelKey: 'nav.settings' as const },
];

export function ShellNav() {
  const { t } = useI18n();
  const { actor, logout } = useAuthContext();
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();

  return (
    <aside className="shell-nav">
      <div className="shell-nav__brand">
        <span className="shell-nav__logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-brand-primary">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7Z" />
            <circle cx="12" cy="9" r="2.5" />
          </svg>
        </span>
        <span className="shell-nav__name">FamilyClaw</span>
      </div>

      {/* 家庭切换 */}
      <div className="shell-nav__household">
        <select
          className="household-select"
          value={currentHousehold?.id ?? ''}
          onChange={e => setCurrentHouseholdId(e.target.value)}
        >
          {households.map(h => (
            <option key={h.id} value={h.id}>{h.name}</option>
          ))}
        </select>
      </div>

      {/* 主导航 */}
      <nav className="shell-nav__links">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `shell-nav__link ${isActive ? 'shell-nav__link--active' : ''}`}
          >
            <span className="shell-nav__link-icon">{item.icon}</span>
            <span className="shell-nav__link-label">{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>

      <div className="shell-nav__footer">
        <div className="shell-nav__account">{actor?.username ?? '未登录'}</div>
        <button className="shell-nav__logout" type="button" onClick={() => void logout()}>
          退出登录
        </button>
        <span className="shell-nav__version">v0.1.0</span>
      </div>
    </aside>
  );
}
