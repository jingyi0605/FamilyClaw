/* ============================================================
 * ShellNav - 左侧主导航
 * ============================================================ */
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Home, Users, MessageSquareText, BookOpenText, Settings, PanelLeftClose, PanelLeft, ChevronUp, LogOut, Building2 } from 'lucide-react';
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

interface ShellNavProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function ShellNav({ collapsed = false, onToggleCollapse }: ShellNavProps) {
  const { t } = useI18n();
  const { actor, logout } = useAuthContext();
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  return (
    <aside className={`shell-nav ${collapsed ? 'shell-nav--collapsed' : ''}`}>
      {/* 品牌 */}
      <div className="shell-nav__brand">
        <span className="shell-nav__logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-brand-primary">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7Z" />
            <circle cx="12" cy="9" r="2.5" />
          </svg>
        </span>
        {!collapsed && <span className="shell-nav__name">FamilyClaw</span>}
      </div>

      {/* 主导航 - 位置固定，不受家庭切换影响 */}
      <nav className="shell-nav__links">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `shell-nav__link ${isActive ? 'shell-nav__link--active' : ''}`}
            title={t(item.labelKey)}
          >
            <span className="shell-nav__link-icon">{item.icon}</span>
            <span className="shell-nav__link-label">{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>

      {/* 底部区域 */}
      <div className="shell-nav__footer">
        {/* 用户设置区 - 可展开 */}
        <div className={`shell-nav__user-menu ${userMenuOpen ? 'is-open' : ''}`}>
          <button
            className="shell-nav__user-trigger"
            type="button"
            onClick={() => setUserMenuOpen(prev => !prev)}
            title={actor?.username ?? '用户设置'}
          >
            <span className="shell-nav__user-avatar">
              {actor?.username?.charAt(0).toUpperCase() ?? '?'}
            </span>
            <span className="shell-nav__user-name">{actor?.username ?? '未登录'}</span>
            <ChevronUp size={14} className={`shell-nav__user-chevron ${userMenuOpen ? 'is-rotated' : ''}`} />
          </button>

          {/* 用户菜单下拉内容 */}
          {userMenuOpen && (
            <div className="shell-nav__user-dropdown">
              {/* 家庭切换 */}
              <div className="shell-nav__dropdown-section">
                <div className="shell-nav__dropdown-label">
                  <Building2 size={14} />
                  <span>当前家庭</span>
                </div>
                <select
                  className="shell-nav__household-select"
                  value={currentHousehold?.id ?? ''}
                  onChange={e => {
                    setCurrentHouseholdId(e.target.value);
                    setUserMenuOpen(false);
                  }}
                >
                  {households.map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
              </div>

              {/* 退出登录 */}
              <div className="shell-nav__dropdown-section">
                <button
                  className="shell-nav__logout-btn"
                  type="button"
                  onClick={() => void logout()}
                >
                  <LogOut size={16} />
                  <span>退出登录</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 收起/展开按钮 - 始终在底部 */}
        {onToggleCollapse && (
          <button
            className="shell-nav__toggle"
            type="button"
            onClick={onToggleCollapse}
            title={collapsed ? '展开导航' : '收起导航'}
          >
            <span className="shell-nav__link-icon">
              {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
            </span>
            <span className="shell-nav__toggle-label">{collapsed ? '展开' : '收起'}</span>
          </button>
        )}
      </div>
    </aside>
  );
}
