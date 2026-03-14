/* ============================================================
 * AppLayout - 全局主布局壳子
 * 左侧导航 + 右侧内容区
 * ============================================================ */
import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { ShellNav } from '../components/ShellNav';
import { useHouseholdContext } from '../state/household';

// 响应式断点：宽度小于此值时导航默认收起
const NAV_COLLAPSE_BREAKPOINT = 1200;

export function AppLayout() {
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();
  const [navCollapsed, setNavCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < NAV_COLLAPSE_BREAKPOINT;
  });

  // 响应式检测：根据窗口宽度自动调整导航状态
  useEffect(() => {
    const handleResize = () => {
      const shouldCollapse = window.innerWidth < NAV_COLLAPSE_BREAKPOINT;
      setNavCollapsed(prev => {
        // 只在断点切换时更新，避免用户手动设置后被覆盖
        if (shouldCollapse !== prev && window.innerWidth < NAV_COLLAPSE_BREAKPOINT !== prev) {
          return shouldCollapse;
        }
        return prev;
      });
    };

    // 使用防抖避免频繁触发
    let resizeTimer: ReturnType<typeof setTimeout>;
    const debouncedResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(handleResize, 150);
    };

    window.addEventListener('resize', debouncedResize);
    return () => {
      window.removeEventListener('resize', debouncedResize);
      clearTimeout(resizeTimer);
    };
  }, []);

  const toggleNav = () => setNavCollapsed(prev => !prev);

  return (
    <div className={`app-layout ${navCollapsed ? 'app-layout--nav-collapsed' : ''}`}>
      <ShellNav collapsed={navCollapsed} onToggleCollapse={toggleNav} />
      <main className="app-layout__main">
        <div className="mobile-household-bar">
          <label className="mobile-household-bar__label" htmlFor="mobile-household-select">当前家庭</label>
          <select
            id="mobile-household-select"
            className="household-select mobile-household-bar__select"
            value={currentHousehold?.id ?? ''}
            onChange={event => setCurrentHouseholdId(event.target.value)}
          >
            {households.map(household => (
              <option key={household.id} value={household.id}>{household.name}</option>
            ))}
          </select>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
