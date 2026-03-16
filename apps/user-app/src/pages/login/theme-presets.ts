import {
  userAppThemeList,
  userAppThemes,
} from '@familyclaw/user-ui';
import { applyThemeDocument } from '../../runtime/h5-shell/theme/applyThemeDocument';

type ThemeId = keyof typeof userAppThemes;

type LoginThemePreset = {
  id: ThemeId;
  label: string;
  description: string;
  emoji: string;
};

export const loginThemeList: LoginThemePreset[] = userAppThemeList.map(theme => ({
  id: theme.id,
  label: theme.label,
  description: theme.description,
  emoji: theme.emoji,
}));

export function getLoginThemePreset(themeId: ThemeId) {
  return loginThemeList.find(theme => theme.id === themeId) ?? loginThemeList[0];
}

export function applyLoginThemeCssVariables(themeId: ThemeId) {
  const theme = userAppThemes[themeId] ?? userAppThemeList[0];
  applyThemeDocument(theme);
}
