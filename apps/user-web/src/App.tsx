/* ============================================================
 * App 路由配置
 * ============================================================ */
import { Navigate, Route, Routes } from 'react-router-dom';
import { useEffect } from 'react';
import { useI18n } from './i18n';
import { AppLayout } from './layouts/AppLayout';
import { SetupGuard } from './layouts/SetupGuard';
import { HouseholdProvider } from './state/household';
import { SetupProvider } from './state/setup';
import { useAuthContext } from './state/auth';
import { api } from './lib/api';
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
import { SettingsChannelAccess } from './pages/SettingsChannelAccessPage';
import { SettingsPluginsPage } from './pages/SettingsPluginsPage';
import { LoginPage } from './pages/LoginPage';
import { useHouseholdContext } from './state/household';

function HouseholdLocaleSync() {
  const { currentHouseholdId } = useHouseholdContext();
  const { replacePluginLocales } = useI18n();

  useEffect(() => {
    if (!currentHouseholdId) {
      replacePluginLocales([]);
      return;
    }

    let cancelled = false;

    void api.listHouseholdLocales(currentHouseholdId)
      .then(response => {
        if (cancelled) return;
        replacePluginLocales(
          response.items.map(item => ({
            id: item.locale_id,
            label: item.label,
            nativeLabel: item.native_label,
            fallback: item.fallback ?? undefined,
            messages: item.messages,
            source: 'plugin' as const,
            sourceType: item.source_type,
            pluginId: item.plugin_id,
            overriddenPluginIds: item.overridden_plugin_ids,
          })),
        );
      })
      .catch(() => {
        if (cancelled) return;
        replacePluginLocales([]);
      });

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, replacePluginLocales]);

  return null;
}

function AuthenticatedUserApp() {
  return (
    <HouseholdProvider>
      <HouseholdLocaleSync />
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
            <Route
              path="/"
              element={(
                <SetupGuard mode="protected">
                  <HomePage />
                </SetupGuard>
              )}
            />

            <Route path="/family" element={<FamilyLayout />}>
              <Route index element={<FamilyOverview />} />
              <Route path="rooms" element={<FamilyRooms />} />
              <Route path="members" element={<FamilyMembers />} />
              <Route path="relationships" element={<FamilyRelationships />} />
            </Route>

            <Route
              path="/conversation"
              element={(
                <SetupGuard mode="protected">
                  <AssistantPage />
                </SetupGuard>
              )}
            />
            <Route path="/assistant" element={<Navigate to="/conversation" replace />} />

            <Route path="/memories" element={<MemoriesPage />} />

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
              <Route
                path="channel-access"
                element={(
                  <SetupGuard mode="protected">
                    <SettingsChannelAccess />
                  </SetupGuard>
                )}
              />
              <Route
                path="plugins"
                element={(
                  <SetupGuard mode="protected">
                    <SettingsPluginsPage />
                  </SetupGuard>
                )}
              />
            </Route>
          </Route>
        </Routes>
      </SetupProvider>
    </HouseholdProvider>
  );
}

export default function App() {
  const { actor, authLoading } = useAuthContext();
  const { t } = useI18n();

  if (authLoading) {
    return <div className="auth-screen__loading">{t('auth.loading')}</div>;
  }

  if (!actor || !actor.authenticated) {
    return <LoginPage />;
  }

  return <AuthenticatedUserApp />;
}
