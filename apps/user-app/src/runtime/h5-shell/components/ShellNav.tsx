import { useMemo, useState, type ReactNode } from 'react';
import Taro from '@tarojs/taro';
import {
  BookOpenText,
  Building2,
  ChevronUp,
  Home,
  LogOut,
  MessageSquareText,
  PanelLeft,
  PanelLeftClose,
  Settings,
  Users,
} from 'lucide-react';
import { useAuthContext } from '../../auth';
import { useHouseholdContext } from '../../household';
import { useI18n } from '../i18n/I18nProvider';

const navItems: {
  url: string;
  labelKey: string;
  aliases: string[];
  icon: ReactNode;
}[] = [
  { url: '/pages/home/index', labelKey: 'nav.home', aliases: ['/', '/home', '/pages/home/index'], icon: <Home size={20} strokeWidth={2.5} /> },
  { url: '/pages/family/index', labelKey: 'nav.family', aliases: ['/family', '/pages/family/index'], icon: <Users size={20} strokeWidth={2.5} /> },
  { url: '/pages/assistant/index', labelKey: 'nav.assistant', aliases: ['/conversation', '/assistant', '/pages/assistant/index'], icon: <MessageSquareText size={20} strokeWidth={2.5} /> },
  { url: '/pages/memories/index', labelKey: 'nav.memories', aliases: ['/memories', '/pages/memories/index'], icon: <BookOpenText size={20} strokeWidth={2.5} /> },
  {
    url: '/pages/settings/index',
    labelKey: 'nav.settings',
    aliases: [
      '/settings',
      '/pages/settings/index',
      '/pages/settings/ai/index',
      '/pages/settings/integrations/index',
      '/pages/settings/channel-access/index',
      '/pages/plugins/index',
    ],
    icon: <Settings size={20} strokeWidth={2.5} />,
  },
];

function normalizePath(pathname: string) {
  return pathname.split('?')[0] || '/';
}

export function ShellNav(props: { collapsed: boolean; onToggleCollapse: () => void }) {
  const { actor, logout } = useAuthContext();
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();
  const { t } = useI18n();
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
        <span className="shell-nav__logo">
          {/* FamilyClaw Logo: 爪印造型，象征家庭的守护与连接 */}
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-brand-primary">
            {/* 主掌垫 - 心形基底 */}
            <path
              d="M14 24c-1.5 0-3-1-4.5-2.5C7 19.5 4 16 4 12c0-3.5 2.5-6 5.5-6 1.8 0 3.2.8 4.5 2 1.3-1.2 2.7-2 4.5-2 3 0 5.5 2.5 5.5 6 0 4-3 7.5-5.5 9.5C17 23 15.5 24 14 24Z"
              fill="currentColor"
              opacity="0.9"
            />
            {/* 左上爪垫 */}
            <ellipse cx="7.5" cy="6" rx="2.5" ry="3" fill="currentColor" />
            {/* 中上爪垫 */}
            <ellipse cx="14" cy="4" rx="2.5" ry="3" fill="currentColor" />
            {/* 右上爪垫 */}
            <ellipse cx="20.5" cy="6" rx="2.5" ry="3" fill="currentColor" />
            {/* 左侧小爪垫 */}
            <ellipse cx="4.5" cy="10.5" rx="2" ry="2.5" fill="currentColor" opacity="0.8" />
            {/* 右侧小爪垫 */}
            <ellipse cx="23.5" cy="10.5" rx="2" ry="2.5" fill="currentColor" opacity="0.8" />
          </svg>
        </span>
        {!props.collapsed ? <span className="shell-nav__name">FamilyClaw</span> : null}
      </div>

      <nav className="shell-nav__links">
        {navItems.map((item) => {
          const isActive = item.aliases.includes(currentPath);
          const label = t(item.labelKey);
          return (
            <button
              key={item.url}
              type="button"
              className={`shell-nav__link ${isActive ? 'shell-nav__link--active' : ''}`}
              title={label}
              onClick={() => void Taro.reLaunch({ url: item.url })}
            >
              <span className="shell-nav__link-icon">{item.icon}</span>
              <span className="shell-nav__link-label">{label}</span>
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
            title={actor?.username ?? t('common.userMenu')}
          >
            <span className="shell-nav__user-avatar">{actor?.username?.slice(0, 1).toUpperCase() ?? '?'}</span>
            <span className="shell-nav__user-name">{actor?.username ?? t('common.notLoggedIn')}</span>
            <ChevronUp size={14} className={`shell-nav__user-chevron ${userMenuOpen ? 'is-rotated' : ''}`} />
          </button>

          {userMenuOpen ? (
            <div className="shell-nav__user-dropdown">
              <div className="shell-nav__dropdown-section">
                <div className="shell-nav__dropdown-label">
                  <Building2 size={14} />
                  <span>{t('common.currentHousehold')}</span>
                </div>
                <select
                  className="shell-nav__household-select"
                  value={currentHousehold?.id ?? ''}
                  onChange={(event) => {
                    setCurrentHouseholdId(event.target.value);
                    setUserMenuOpen(false);
                  }}
                >
                  {households.map((household) => (
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
                  <LogOut size={16} />
                  <span>{t('common.logout')}</span>
                </button>
              </div>
            </div>
          ) : null}
        </div>

        <button
          className="shell-nav__toggle"
          type="button"
          title={props.collapsed ? t('common.expand') : t('common.collapse')}
          onClick={props.onToggleCollapse}
        >
          <span className="shell-nav__link-icon">
            {props.collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </span>
          <span className="shell-nav__toggle-label">{props.collapsed ? t('common.expand') : t('common.collapse')}</span>
        </button>
      </div>
    </aside>
  );
}
