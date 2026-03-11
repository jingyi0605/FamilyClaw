/* ============================================================
 * App 路由配置
 * ============================================================ */
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { HomePage } from './pages/HomePage';
import { FamilyLayout, FamilyOverview, FamilyRooms, FamilyMembers, FamilyRelationships } from './pages/FamilyPage';
import { AssistantPage } from './pages/AssistantPage';
import { MemoriesPage } from './pages/MemoriesPage';
import {
  SettingsLayout,
  SettingsAppearance,
  SettingsAi,
  SettingsLanguage,
  SettingsNotifications,
  SettingsAccessibility,
  SettingsIntegrations,
} from './pages/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        {/* 首页 */}
        <Route path="/" element={<HomePage />} />

        {/* 家庭 */}
        <Route path="/family" element={<FamilyLayout />}>
          <Route index element={<FamilyOverview />} />
          <Route path="rooms" element={<FamilyRooms />} />
          <Route path="members" element={<FamilyMembers />} />
          <Route path="relationships" element={<FamilyRelationships />} />
        </Route>

        {/* 对话 */}
        <Route path="/conversation" element={<AssistantPage />} />
        <Route path="/assistant" element={<Navigate to="/conversation" replace />} />

        {/* 记忆 */}
        <Route path="/memories" element={<MemoriesPage />} />

        {/* 设置 */}
        <Route path="/settings" element={<SettingsLayout />}>
          <Route path="appearance" element={<SettingsAppearance />} />
          <Route path="ai" element={<SettingsAi />} />
          <Route path="language" element={<SettingsLanguage />} />
          <Route path="notifications" element={<SettingsNotifications />} />
          <Route path="accessibility" element={<SettingsAccessibility />} />
          <Route path="integrations" element={<SettingsIntegrations />} />
        </Route>
      </Route>
    </Routes>
  );
}
