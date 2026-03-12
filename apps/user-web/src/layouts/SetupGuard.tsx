/* ============================================================
 * SetupGuard - 统一控制初始化向导准入
 * ============================================================ */
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Card } from '../components/base';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';

type SetupGuardMode = 'protected' | 'setup';

export function SetupGuard({
  mode,
  children,
}: {
  mode: SetupGuardMode;
  children: ReactNode;
}) {
  const location = useLocation();
  const { currentHouseholdId, householdsLoading, households } = useHouseholdContext();
  const { setupStatus, setupStatusLoading, setupStatusError, refreshSetupStatus } = useSetupContext();

  // 当没有选中家庭时，需要判断是正在加载还是确实没有家庭
  if (!currentHouseholdId) {
    // 正在加载家庭列表，显示加载状态
    if (householdsLoading) {
      return (
        <div className="setup-guard">
          <Card className="setup-guard__card">
            <h2>正在加载家庭信息</h2>
            <p>请稍候...</p>
          </Card>
        </div>
      );
    }
    // 加载完成但没有家庭
    if (households.length === 0) {
      // 如果已经在 /setup 页面，直接放行让 SetupWizardPage 处理
      if (location.pathname === '/setup') {
        return <>{children}</>;
      }
      // 其他页面需要重定向到初始化向导创建家庭
      return <Navigate to="/setup" replace state={{ from: location.pathname }} />;
    }
    // 有家庭但未选中（理论上 HouseholdProvider 会自动选择第一个），暂时显示加载状态
    return (
      <div className="setup-guard">
        <Card className="setup-guard__card">
          <h2>正在选择家庭</h2>
          <p>请稍候...</p>
        </Card>
      </div>
    );
  }

  if (householdsLoading || setupStatusLoading) {
    return (
      <div className="setup-guard">
        <Card className="setup-guard__card">
          <h2>正在检查家庭初始化状态</h2>
          <p>先别急，让系统判断这个家庭现在该放行，还是该进向导。</p>
        </Card>
      </div>
    );
  }

  if (setupStatusError) {
    return (
      <div className="setup-guard">
        <Card className="setup-guard__card">
          <h2>初始化状态加载失败</h2>
          <p>{setupStatusError}</p>
          <button className="btn btn--primary" onClick={() => void refreshSetupStatus()}>
            重试
          </button>
        </Card>
      </div>
    );
  }

  if (!setupStatus) {
    return <>{children}</>;
  }

  if (mode === 'protected' && setupStatus.is_required) {
    return <Navigate to="/setup" replace state={{ from: location.pathname }} />;
  }

  if (mode === 'setup' && !setupStatus.is_required && setupStatus.missing_requirements.length === 0) {
    const stateValue = location.state as { from?: unknown } | null;
    const fallbackPath = typeof stateValue?.from === 'string' ? stateValue.from : '/';
    return <Navigate to={fallbackPath} replace />;
  }

  return <>{children}</>;
}
