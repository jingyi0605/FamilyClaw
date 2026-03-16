import {
  userAppThemeList,
  userAppThemes,
  type ThemeId,
  type UserAppTheme,
} from '@familyclaw/user-ui';

export type ThemeTokens = UserAppTheme;

// 保留旧导出名，先让 H5 壳层继续吃原来的接口，再逐步把调用点迁到共享层命名。
export const legacyThemes = userAppThemes;
export const themes = legacyThemes;
export const themeList: ThemeTokens[] = userAppThemeList;

export type { ThemeId };
