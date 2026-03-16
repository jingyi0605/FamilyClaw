import { getThemeCssVariables, userAppThemeList } from '@familyclaw/user-ui';

type UserAppTheme = (typeof userAppThemeList)[number];

export function applyThemeDocument(theme: UserAppTheme) {
  if (typeof document === 'undefined') {
    return;
  }

  const root = document.documentElement;
  const variables = getThemeCssVariables(theme);

  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  root.setAttribute('data-theme', theme.id);
}
