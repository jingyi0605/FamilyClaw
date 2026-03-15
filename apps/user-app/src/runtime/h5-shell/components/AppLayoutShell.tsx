import { useEffect, useState, type ReactNode } from 'react';
import { useHouseholdContext } from '../../household';
import { ShellNav } from './ShellNav';

const NAV_COLLAPSE_BREAKPOINT = 1200;

export function AppLayoutShell(props: { children: ReactNode }) {
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.innerWidth < NAV_COLLAPSE_BREAKPOINT;
  });

  useEffect(() => {
    function handleResize() {
      if (window.innerWidth < NAV_COLLAPSE_BREAKPOINT) {
        setCollapsed(true);
      }
    }

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className={`app-layout ${collapsed ? 'app-layout--nav-collapsed' : ''}`}>
      <ShellNav collapsed={collapsed} onToggleCollapse={() => setCollapsed(current => !current)} />
      <main className="app-layout__main">
        <div className="mobile-household-bar">
          <label className="mobile-household-bar__label" htmlFor="mobile-household-select">
            当前家庭
          </label>
          <select
            id="mobile-household-select"
            className="household-select mobile-household-bar__select"
            value={currentHousehold?.id ?? ''}
            onChange={event => setCurrentHouseholdId(event.target.value)}
          >
            {households.map(household => (
              <option key={household.id} value={household.id}>
                {household.name}
              </option>
            ))}
          </select>
        </div>
        {props.children}
      </main>
    </div>
  );
}
