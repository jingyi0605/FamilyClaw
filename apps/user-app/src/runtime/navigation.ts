import { BootstrapSnapshot, HouseholdSetupStatus } from '@familyclaw/user-core';

export const APP_ROUTES = {
  entry: '/pages/entry/index',
  login: '/pages/login/index',
  setup: '/pages/setup/index',
  home: '/pages/home/index',
  family: '/pages/family/index',
  assistant: '/pages/assistant/index',
  memories: '/pages/memories/index',
  settings: '/pages/settings/index',
  settingsAi: '/pages/settings/ai/index',
  settingsIntegrations: '/pages/settings/integrations/index',
  settingsChannelAccess: '/pages/settings/channel-access/index',
  plugins: '/pages/plugins/index',
} as const;

export type MainNavKey = 'home' | 'family' | 'assistant' | 'memories' | 'settings' | 'plugins';

export const MAIN_NAV_ITEMS: Array<{
  key: MainNavKey;
  label: string;
  url: string;
}> = [
  { key: 'home', label: '首页', url: APP_ROUTES.home },
  { key: 'family', label: '家庭', url: APP_ROUTES.family },
  { key: 'assistant', label: '助手', url: APP_ROUTES.assistant },
  { key: 'memories', label: '记忆', url: APP_ROUTES.memories },
  { key: 'settings', label: '设置', url: APP_ROUTES.settings },
  { key: 'plugins', label: '插件', url: APP_ROUTES.plugins },
];

export function isSetupComplete(setupStatus: HouseholdSetupStatus | null) {
  if (!setupStatus) {
    return true;
  }

  return (
    setupStatus.status === 'completed'
    || setupStatus.current_step === 'finish'
    || setupStatus.completed_steps.includes('finish')
  );
}

export function needsBlockingSetup(setupStatus: HouseholdSetupStatus | null) {
  if (!setupStatus || isSetupComplete(setupStatus) || !setupStatus.is_required) {
    return false;
  }

  return setupStatus.current_step === 'family_profile' || setupStatus.current_step === 'first_member';
}

export function hasDeferredSetupWork(setupStatus: HouseholdSetupStatus | null) {
  if (!setupStatus || isSetupComplete(setupStatus) || !setupStatus.is_required) {
    return false;
  }

  return !needsBlockingSetup(setupStatus);
}

export function resolveBootstrapRoute(snapshot: BootstrapSnapshot | null) {
  if (!snapshot?.actor?.authenticated) {
    return APP_ROUTES.login;
  }

  if (!snapshot.currentHousehold || needsBlockingSetup(snapshot.setupStatus)) {
    return APP_ROUTES.setup;
  }

  return APP_ROUTES.home;
}
