/* ============================================================
 * ShellNav - 左侧主导航
 * ============================================================ */
import { NavLink } from 'react-router-dom';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';

const navItems = [
  { to: '/', icon: '🏠', labelKey: 'nav.home' as const, end: true },
  { to: '/family', icon: '👨‍👩‍👧‍👦', labelKey: 'nav.family' as const },
  { to: '/assistant', icon: '💬', labelKey: 'nav.assistant' as const },
  { to: '/memories', icon: '📝', labelKey: 'nav.memories' as const },
  { to: '/settings', icon: '⚙️', labelKey: 'nav.settings' as const },
];

export function ShellNav() {
  const { t } = useI18n();
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();

  return (
    <aside className="shell-nav">
      <div className="shell-nav__brand">
        <span className="shell-nav__logo">🐾</span>
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
        <span className="shell-nav__version">v0.1.0</span>
      </div>
    </aside>
  );
}
