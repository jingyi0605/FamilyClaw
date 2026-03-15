import { useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { useAuthContext } from '../../auth';
import { useHouseholdContext } from '../../household';

const navItems = [
  { url: '/pages/home/index', label: '首页', aliases: ['/', '/home'] },
  { url: '/pages/family/index', label: '家庭', aliases: ['/family'] },
  { url: '/pages/assistant/index', label: '助手', aliases: ['/assistant'] },
  { url: '/pages/memories/index', label: '记忆', aliases: ['/memories'] },
  { url: '/pages/settings/index', label: '设置', aliases: ['/settings'] },
];

function normalizePath(pathname: string) {
  return pathname.split('?')[0] || '/';
}

export function ShellNav(props: { collapsed: boolean; onToggleCollapse: () => void }) {
  const { actor, logout } = useAuthContext();
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const currentPath = useMemo(() => {
    if (typeof window === 'undefined') {
      return '/';
    }
    return normalizePath(window.location.pathname);
  }, []);

  return (
    <aside className={`shell-nav ${props.collapsed ? 'shell-nav--collapsed' : ''}`}>
      <div className="shell-nav__brand">
        <span className="shell-nav__logo">⌘</span>
        {!props.collapsed ? <span className="shell-nav__name">FamilyClaw</span> : null}
      </div>

      <nav className="shell-nav__links">
        {navItems.map(item => {
          const isActive = item.aliases.includes(currentPath);
          return (
            <button
              key={item.url}
              type="button"
              className={`shell-nav__link ${isActive ? 'shell-nav__link--active' : ''}`}
              title={item.label}
              onClick={() => void Taro.reLaunch({ url: item.url })}
            >
              <span className="shell-nav__link-icon">{item.label.slice(0, 1)}</span>
              <span className="shell-nav__link-label">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="shell-nav__footer">
        <div className={`shell-nav__user-menu ${userMenuOpen ? 'is-open' : ''}`}>
          <button
            className="shell-nav__user-trigger"
            type="button"
            onClick={() => setUserMenuOpen(current => !current)}
            title={actor?.username ?? '用户菜单'}
          >
            <span className="shell-nav__user-avatar">{actor?.username?.slice(0, 1).toUpperCase() ?? '?'}</span>
            <span className="shell-nav__user-name">{actor?.username ?? '未登录'}</span>
            <span className={`shell-nav__user-chevron ${userMenuOpen ? 'is-rotated' : ''}`}>⌃</span>
          </button>

          {userMenuOpen ? (
            <div className="shell-nav__user-dropdown">
              <div className="shell-nav__dropdown-section">
                <div className="shell-nav__dropdown-label">
                  <span>当前家庭</span>
                </div>
                <select
                  className="shell-nav__household-select"
                  value={currentHousehold?.id ?? ''}
                  onChange={event => {
                    setCurrentHouseholdId(event.target.value);
                    setUserMenuOpen(false);
                  }}
                >
                  {households.map(household => (
                    <option key={household.id} value={household.id}>
                      {household.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="shell-nav__dropdown-section">
                <button
                  className="shell-nav__logout-btn"
                  type="button"
                  onClick={() => void logout()}
                >
                  <span>退出登录</span>
                </button>
              </div>
            </div>
          ) : null}
        </div>

        <button
          className="shell-nav__toggle"
          type="button"
          title={props.collapsed ? '展开导航' : '收起导航'}
          onClick={props.onToggleCollapse}
        >
          <span className="shell-nav__link-icon">{props.collapsed ? '»' : '«'}</span>
          <span className="shell-nav__toggle-label">{props.collapsed ? '展开' : '收起'}</span>
        </button>
      </div>
    </aside>
  );
}
