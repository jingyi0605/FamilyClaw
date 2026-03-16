import {
  getThemeCssVariables,
  userAppThemeList,
  type ThemeId,
} from '@familyclaw/user-ui';

type LoginThemePreset = {
  id: ThemeId;
  label: string;
  description: string;
  emoji: string;
  vars: Record<string, string>;
};

export const loginThemeList: LoginThemePreset[] = userAppThemeList.map(theme => ({
  id: theme.id,
  label: theme.label,
  description: theme.description,
  emoji: theme.emoji,
  vars: { ...getThemeCssVariables(theme) },
}));

export function getLoginThemePreset(themeId: ThemeId) {
  return loginThemeList.find(theme => theme.id === themeId) ?? loginThemeList[0];
}

export function applyLoginThemeCssVariables(themeId: ThemeId) {
  if (typeof document === 'undefined') {
    return;
  }

  const theme = getLoginThemePreset(themeId);
  const root = document.documentElement;

  for (const [key, value] of Object.entries(theme.vars)) {
    root.style.setProperty(key, value);
  }
}
