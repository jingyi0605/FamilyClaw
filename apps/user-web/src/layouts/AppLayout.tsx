/* ============================================================
 * AppLayout - 全局主布局壳子
 * 左侧导航 + 右侧内容区
 * ============================================================ */
import { Outlet } from 'react-router-dom';
import { ShellNav } from '../components/ShellNav';

export function AppLayout() {
  return (
    <div className="app-layout">
      <ShellNav />
      <main className="app-layout__main">
        <Outlet />
      </main>
    </div>
  );
}
