export type StorageAdapter = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

export type ThemeId =
  | 'chun-he-jing-ming'
  | 'yue-lang-xing-xi'
  | 'ming-cha-qiu-hao'
  | 'wan-zi-qian-hong'
  | 'feng-chi-dian-che'
  | 'xing-he-wan-li'
  | 'qing-shan-lv-shui'
  | 'jin-xiu-qian-cheng';

export interface ThemeOption {
  id: ThemeId;
  label: string;
  description: string;
  accentColor: string;
  previewSurface: string;
}

export const THEME_STORAGE_KEY = 'familyclaw-theme';
export const DEFAULT_THEME_ID: ThemeId = 'chun-he-jing-ming';

const THEME_OPTIONS: ThemeOption[] = [
  {
    id: 'chun-he-jing-ming',
    label: '春和景明',
    description: '温暖宁静，适合日常使用',
    accentColor: '#d97756',
    previewSurface: '#f7f5f2',
  },
  {
    id: 'yue-lang-xing-xi',
    label: '月朗星稀',
    description: '柔和深色，减少视觉疲劳',
    accentColor: '#7c9ef5',
    previewSurface: '#1a1d27',
  },
  {
    id: 'ming-cha-qiu-hao',
    label: '明察秋毫',
    description: '更大字号、更高对比度',
    accentColor: '#b04020',
    previewSurface: '#f5f5f0',
  },
  {
    id: 'wan-zi-qian-hong',
    label: '万紫千红',
    description: '鲜艳活泼，色彩缤纷',
    accentColor: '#e040a0',
    previewSurface: '#fef8ff',
  },
  {
    id: 'feng-chi-dian-che',
    label: '风驰电掣',
    description: '霓虹电网，赛博激光',
    accentColor: '#00f0ff',
    previewSurface: '#1f1032',
  },
  {
    id: 'xing-he-wan-li',
    label: '星河万里',
    description: '星云浮动，宇宙漫游',
    accentColor: '#b480ff',
    previewSurface: '#161a35',
  },
  {
    id: 'qing-shan-lv-shui',
    label: '青山绿水',
    description: '自然清新，森林氧吧',
    accentColor: '#2e8b57',
    previewSurface: '#f2f7f3',
  },
  {
    id: 'jin-xiu-qian-cheng',
    label: '锦绣前程',
    description: '正金尊贵，大气磅礴',
    accentColor: '#ffd700',
    previewSurface: '#181408',
  },
];

export function listThemeOptions(): ThemeOption[] {
  return THEME_OPTIONS.map(option => ({ ...option }));
}

export function resolveThemeId(themeId: string | null | undefined, fallback: ThemeId = DEFAULT_THEME_ID): ThemeId {
  const normalized = (themeId ?? '').trim();
  const matched = THEME_OPTIONS.find(option => option.id === normalized);
  return matched?.id ?? fallback;
}

export function isElderFriendlyTheme(themeId: string | null | undefined): boolean {
  return resolveThemeId(themeId) === 'ming-cha-qiu-hao';
}

export async function getStoredThemeId(
  storage: StorageAdapter,
  storageKey = THEME_STORAGE_KEY,
  fallback: ThemeId = DEFAULT_THEME_ID,
) {
  const stored = await storage.getItem(storageKey);
  return resolveThemeId(stored, fallback);
}

export async function persistThemeId(
  storage: StorageAdapter,
  themeId: string | null | undefined,
  storageKey = THEME_STORAGE_KEY,
  fallback: ThemeId = DEFAULT_THEME_ID,
) {
  const nextThemeId = resolveThemeId(themeId, fallback);
  await storage.setItem(storageKey, nextThemeId);
  return nextThemeId;
}
