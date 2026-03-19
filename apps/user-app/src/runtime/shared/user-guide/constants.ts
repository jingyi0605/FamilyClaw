export const USER_GUIDE_AUTO_START_STORAGE_KEY = 'familyclaw:user-app-guide:auto-start';
export const USER_GUIDE_SESSION_STORAGE_KEY = 'familyclaw:user-app-guide:session';
export const USER_GUIDE_DEFAULT_ANCHOR_TIMEOUT_MS = 1200;

export const USER_GUIDE_ANCHOR_IDS = {
  homeOverview: 'user-guide.home.overview',
  familyOverview: 'user-guide.family.overview',
  assistantOverview: 'user-guide.assistant.overview',
  memoriesOverview: 'user-guide.memories.overview',
  settingsReplay: 'user-guide.settings.replay',
  shellNavigation: 'user-guide.shell.navigation',
} as const;

export type UserGuideAnchorId = typeof USER_GUIDE_ANCHOR_IDS[keyof typeof USER_GUIDE_ANCHOR_IDS];
