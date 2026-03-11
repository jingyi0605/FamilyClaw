/* ============================================================
 * AppLayout - 全局主布局壳子
 * 左侧导航 + 右侧内容区
 * ============================================================ */
import { Outlet } from 'react-router-dom';
import { ShellNav } from '../components/ShellNav';
import { useHouseholdContext } from '../state/household';

export function AppLayout() {
  const { currentHousehold, households, setCurrentHouseholdId } = useHouseholdContext();

  return (
    <div className="app-layout">
      <ShellNav />
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
