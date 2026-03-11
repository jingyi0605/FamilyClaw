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
  const { currentHouseholdId, householdsLoading } = useHouseholdContext();
  const { setupStatus, setupStatusLoading, setupStatusError, refreshSetupStatus } = useSetupContext();

  if (!currentHouseholdId) {
    return <>{children}</>;
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
