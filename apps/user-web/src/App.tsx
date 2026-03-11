/* ============================================================
 * App 路由配置
 * ============================================================ */
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { SetupGuard } from './layouts/SetupGuard';
import { HouseholdProvider } from './state/household';
import { SetupProvider } from './state/setup';
import { useAuthContext } from './state/auth';
import { HomePage } from './pages/HomePage';
import { FamilyLayout, FamilyOverview, FamilyRooms, FamilyMembers, FamilyRelationships } from './pages/FamilyPage';
import { AssistantPage } from './pages/AssistantPage';
import { MemoriesPage } from './pages/MemoriesPage';
import { SetupWizardPage } from './pages/SetupWizardPage';
import {
  SettingsLayout,
  SettingsAppearance,
  SettingsAi,
  SettingsLanguage,
  SettingsNotifications,
  SettingsAccessibility,
  SettingsIntegrations,
} from './pages/SettingsPage';
import { LoginPage } from './pages/LoginPage';

function AuthenticatedUserApp() {
  return (
    <HouseholdProvider>
      <SetupProvider>
    <Routes>
      <Route
        path="/setup"
        element={(
          <SetupGuard mode="setup">
            <SetupWizardPage />
          </SetupGuard>
        )}
      />

      <Route element={<AppLayout />}>
        {/* 首页 */}
        <Route
          path="/"
          element={(
            <SetupGuard mode="protected">
              <HomePage />
            </SetupGuard>
          )}
        />

        {/* 家庭 */}
        <Route path="/family" element={<FamilyLayout />}>
          <Route index element={<FamilyOverview />} />
          <Route path="rooms" element={<FamilyRooms />} />
          <Route path="members" element={<FamilyMembers />} />
          <Route path="relationships" element={<FamilyRelationships />} />
        </Route>

        {/* 对话 */}
        <Route
          path="/conversation"
          element={(
            <SetupGuard mode="protected">
              <AssistantPage />
            </SetupGuard>
          )}
        />
        <Route path="/assistant" element={<Navigate to="/conversation" replace />} />

        {/* 记忆 */}
        <Route path="/memories" element={<MemoriesPage />} />

        {/* 设置 */}
        <Route path="/settings" element={<SettingsLayout />}>
          <Route path="appearance" element={<SettingsAppearance />} />
          <Route
            path="ai"
            element={(
              <SetupGuard mode="protected">
                <SettingsAi />
              </SetupGuard>
            )}
          />
          <Route path="language" element={<SettingsLanguage />} />
          <Route path="notifications" element={<SettingsNotifications />} />
          <Route path="accessibility" element={<SettingsAccessibility />} />
          <Route path="integrations" element={<SettingsIntegrations />} />
        </Route>
      </Route>
    </Routes>
      </SetupProvider>
    </HouseholdProvider>
  );
}

export default function App() {
  const { actor, authLoading } = useAuthContext();

  if (authLoading) {
    return <div className="auth-screen__loading">正在确认登录状态...</div>;
  }

  if (!actor || !actor.authenticated) {
    return <LoginPage />;
  }

  return <AuthenticatedUserApp />;
}
