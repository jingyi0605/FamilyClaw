import type { ThemeId as SharedThemeId } from '@familyclaw/user-core';

/* ============================================================
 * FamilyClaw 用户前端 - 主题设计 Token
 * 
 * 8 套主题，每套以四字成语命名
 * 主题只影响颜色/阴影/圆角/字号，不影响信息结构
 * ============================================================ */

export type ThemeId = SharedThemeId;

export interface ThemeTokens {
  id: ThemeId;
  label: string;
  description: string;
  emoji: string;

  /* 背景层级 */
  bgApp: string;
  bgSurface: string;
  bgCard: string;
  bgCardHover: string;
  bgSidebar: string;
  bgInput: string;

  /* 文字 */
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textInverse: string;

  /* 品牌色 */
  brandPrimary: string;
  brandPrimaryHover: string;
  brandPrimaryLight: string;
  brandSecondary: string;

  /* 语义色 */
  success: string;
  successLight: string;
  warning: string;
  warningLight: string;
  danger: string;
  dangerLight: string;
  info: string;
  infoLight: string;

  /* 边框和分割 */
  border: string;
  borderLight: string;
  divider: string;

  /* 阴影 */
  shadowSm: string;
  shadowMd: string;
  shadowLg: string;

  /* 圆角 */
  radiusSm: string;
  radiusMd: string;
  radiusLg: string;
  radiusXl: string;

  /* 字号 */
  fontSizeXs: string;
  fontSizeSm: string;
  fontSizeMd: string;
  fontSizeLg: string;
  fontSizeXl: string;
  fontSizeXxl: string;
  fontSizeHero: string;

  /* 间距 */
  spacingXs: string;
  spacingSm: string;
  spacingMd: string;
  spacingLg: string;
  spacingXl: string;
  spacingXxl: string;

  /* 导航 */
  navWidth: string;
  navBg: string;
  navText: string;
  navTextActive: string;
  navItemHover: string;
  navItemActive: string;

  /* 过渡 */
  transition: string;

  /* 特效（新增） */
  glowColor: string;
  gradientPrimary: string;
  gradientCard: string;
  animationSpeed: string;
}

/* 基础 token 默认值 */
const baseTokens = {
  radiusSm: '6px',
  radiusMd: '10px',
  radiusLg: '14px',
  radiusXl: '20px',

  fontSizeXs: '0.75rem',
  fontSizeSm: '0.8125rem',
  fontSizeMd: '0.9375rem',
  fontSizeLg: '1.125rem',
  fontSizeXl: '1.375rem',
  fontSizeXxl: '1.75rem',
  fontSizeHero: '2.25rem',

  spacingXs: '4px',
  spacingSm: '8px',
  spacingMd: '16px',
  spacingLg: '24px',
  spacingXl: '32px',
  spacingXxl: '48px',

  navWidth: '240px',
  transition: '0.2s ease',
  animationSpeed: '0.3s',
};

/* ── 1. 春和景明 ── 默认浅色，温暖宁静 */
export const chunHeJingMing: ThemeTokens = {
  ...baseTokens,
  id: 'chun-he-jing-ming',
  label: '春和景明',
  description: '温暖宁静，适合日常使用',
  emoji: '🌸',

  bgApp: '#f7f5f2',
  bgSurface: '#ffffff',
  bgCard: '#ffffff',
  bgCardHover: '#fffcf8',
  bgSidebar: '#faf8f5',
  bgInput: '#f5f3f0',

  textPrimary: '#1a1a1a',
  textSecondary: '#5a5a5a',
  textTertiary: '#999999',
  textInverse: '#ffffff',

  brandPrimary: '#d97756',
  brandPrimaryHover: '#c2654a',
  brandPrimaryLight: '#fdf0eb',
  brandSecondary: '#6b9e78',

  success: '#52a960',
  successLight: '#eef7ef',
  warning: '#e0a040',
  warningLight: '#fdf6e8',
  danger: '#d95050',
  dangerLight: '#fdeaea',
  info: '#5090d0',
  infoLight: '#eaf3fb',

  border: '#e8e4df',
  borderLight: '#f0ece7',
  divider: '#eeebe6',

  shadowSm: '0 1px 3px rgba(0,0,0,0.06)',
  shadowMd: '0 2px 8px rgba(0,0,0,0.08)',
  shadowLg: '0 4px 20px rgba(0,0,0,0.10)',

  navBg: '#faf8f5',
  navText: '#666666',
  navTextActive: '#d97756',
  navItemHover: 'rgba(217, 119, 86, 0.06)',
  navItemActive: 'rgba(217, 119, 86, 0.10)',

  glowColor: 'rgba(217, 119, 86, 0.2)',
  gradientPrimary: 'linear-gradient(135deg, #fdf0eb, #ffffff)',
  gradientCard: 'none',
};

/* ── 2. 月朗星稀 ── 深色护眼 */
export const yueLangXingXi: ThemeTokens = {
  ...baseTokens,
  id: 'yue-lang-xing-xi',
  label: '月朗星稀',
  description: '柔和深色，减少视觉疲劳',
  emoji: '🌙',

  bgApp: '#0f1117',
  bgSurface: '#1a1d27',
  bgCard: '#1e2130',
  bgCardHover: '#252840',
  bgSidebar: '#151822',
  bgInput: '#252840',

  textPrimary: '#e2e4ea',
  textSecondary: '#9da1b0',
  textTertiary: '#5c6070',
  textInverse: '#0f1117',

  brandPrimary: '#7c9ef5',
  brandPrimaryHover: '#9db6ff',
  brandPrimaryLight: 'rgba(124, 158, 245, 0.12)',
  brandSecondary: '#7db88a',

  success: '#6abe78',
  successLight: 'rgba(106, 190, 120, 0.12)',
  warning: '#e8b65a',
  warningLight: 'rgba(232, 182, 90, 0.12)',
  danger: '#e86060',
  dangerLight: 'rgba(232, 96, 96, 0.12)',
  info: '#68a8e0',
  infoLight: 'rgba(104, 168, 224, 0.12)',

  border: '#2a2e3e',
  borderLight: '#22263a',
  divider: '#262a3a',

  shadowSm: '0 1px 3px rgba(0,0,0,0.4)',
  shadowMd: '0 2px 8px rgba(0,0,0,0.5)',
  shadowLg: '0 4px 20px rgba(0,0,0,0.6)',

  navBg: '#151822',
  navText: '#6a6e80',
  navTextActive: '#7c9ef5',
  navItemHover: 'rgba(124, 158, 245, 0.08)',
  navItemActive: 'rgba(124, 158, 245, 0.14)',

  glowColor: 'rgba(124, 158, 245, 0.25)',
  gradientPrimary: 'linear-gradient(135deg, #1a1d27, #252840)',
  gradientCard: 'none',
};

/* ── 3. 明察秋毫 ── 长辈友好高对比 */
export const mingChaQiuHao: ThemeTokens = {
  ...baseTokens,
  id: 'ming-cha-qiu-hao',
  label: '明察秋毫',
  description: '更大字号、更高对比度',
  emoji: '🔍',

  bgApp: '#f5f5f0',
  bgSurface: '#ffffff',
  bgCard: '#ffffff',
  bgCardHover: '#faf8f0',
  bgSidebar: '#f0efe8',
  bgInput: '#f0efe8',

  textPrimary: '#111111',
  textSecondary: '#3a3a3a',
  textTertiary: '#666666',
  textInverse: '#ffffff',

  brandPrimary: '#b04020',
  brandPrimaryHover: '#9a3518',
  brandPrimaryLight: '#fce8e0',
  brandSecondary: '#2a7040',

  success: '#1a7a30',
  successLight: '#e0f5e5',
  warning: '#c08000',
  warningLight: '#fdf0d0',
  danger: '#c02020',
  dangerLight: '#fce0e0',
  info: '#2060b0',
  infoLight: '#dce8f8',

  border: '#ccccbb',
  borderLight: '#ddddd0',
  divider: '#d0d0c5',

  shadowSm: '0 1px 4px rgba(0,0,0,0.1)',
  shadowMd: '0 2px 10px rgba(0,0,0,0.12)',
  shadowLg: '0 4px 24px rgba(0,0,0,0.15)',

  fontSizeXs: '0.875rem',
  fontSizeSm: '1rem',
  fontSizeMd: '1.125rem',
  fontSizeLg: '1.375rem',
  fontSizeXl: '1.625rem',
  fontSizeXxl: '2rem',
  fontSizeHero: '2.75rem',

  spacingSm: '10px',
  spacingMd: '20px',
  spacingLg: '30px',
  spacingXl: '40px',

  radiusSm: '8px',
  radiusMd: '12px',
  radiusLg: '16px',

  navBg: '#f0efe8',
  navText: '#555555',
  navTextActive: '#b04020',
  navItemHover: 'rgba(176, 64, 32, 0.08)',
  navItemActive: 'rgba(176, 64, 32, 0.14)',

  glowColor: 'rgba(176, 64, 32, 0.2)',
  gradientPrimary: 'linear-gradient(135deg, #fce8e0, #ffffff)',
  gradientCard: 'none',
};

/* ── 4. 万紫千红 ── 鲜艳活泼，色彩丰富 */
export const wanZiQianHong: ThemeTokens = {
  ...baseTokens,
  id: 'wan-zi-qian-hong',
  label: '万紫千红',
  description: '鲜艳活泼，色彩缤纷',
  emoji: '🌈',

  bgApp: '#fef8ff',
  bgSurface: '#ffffff',
  bgCard: '#ffffff',
  bgCardHover: '#fef0ff',
  bgSidebar: '#fdf5fe',
  bgInput: '#faf0fb',

  textPrimary: '#2a1540',
  textSecondary: '#6a4580',
  textTertiary: '#a080b8',
  textInverse: '#ffffff',

  brandPrimary: '#e040a0',
  brandPrimaryHover: '#d03090',
  brandPrimaryLight: '#fde8f5',
  brandSecondary: '#40b0e0',

  success: '#20c060',
  successLight: '#e0fbe8',
  warning: '#f0a020',
  warningLight: '#fef6e0',
  danger: '#e04060',
  dangerLight: '#fde0e8',
  info: '#4088f0',
  infoLight: '#e0ecfe',

  border: '#f0d0f0',
  borderLight: '#f8e0f8',
  divider: '#f4d8f4',

  shadowSm: '0 1px 4px rgba(224, 64, 160, 0.08)',
  shadowMd: '0 3px 12px rgba(224, 64, 160, 0.10)',
  shadowLg: '0 6px 24px rgba(224, 64, 160, 0.12)',

  navBg: '#fdf5fe',
  navText: '#8060a0',
  navTextActive: '#e040a0',
  navItemHover: 'rgba(224, 64, 160, 0.06)',
  navItemActive: 'rgba(224, 64, 160, 0.12)',

  glowColor: 'rgba(224, 64, 160, 0.3)',
  gradientPrimary: 'linear-gradient(135deg, #fde8f5, #e0ecfe)',
  gradientCard: 'linear-gradient(135deg, rgba(224,64,160,0.03), rgba(64,136,240,0.03))',
};

/* ── 5. 风驰电掣 ── 霓虹电网，赛博激光 */
export const fengChiDianChe: ThemeTokens = {
  ...baseTokens,
  id: 'feng-chi-dian-che',
  label: '风驰电掣',
  description: '霓虹电网，赛博激光',
  emoji: '⚡',

  bgApp: '#160a22',
  bgSurface: '#1f1032',
  bgCard: '#251440',
  bgCardHover: '#2d1850',
  bgSidebar: '#1a0c2a',
  bgInput: '#281648',

  textPrimary: '#ffffff',
  textSecondary: '#c8e0ff',
  textTertiary: '#80a8d0',
  textInverse: '#160a22',

  brandPrimary: '#00f0ff',
  brandPrimaryHover: '#40f8ff',
  brandPrimaryLight: 'rgba(0, 240, 255, 0.12)',
  brandSecondary: '#ff00ff',

  success: '#00ff88',
  successLight: 'rgba(0, 255, 136, 0.12)',
  warning: '#ffaa00',
  warningLight: 'rgba(255, 170, 0, 0.12)',
  danger: '#ff3060',
  dangerLight: 'rgba(255, 48, 96, 0.12)',
  info: '#4080ff',
  infoLight: 'rgba(64, 128, 255, 0.12)',

  border: '#30184a',
  borderLight: '#28103e',
  divider: '#2c1444',

  shadowSm: '0 0 10px rgba(0, 240, 255, 0.2)',
  shadowMd: '0 0 20px rgba(0, 240, 255, 0.25)',
  shadowLg: '0 0 40px rgba(0, 240, 255, 0.3)',

  navBg: '#10001a',
  navText: '#506080',
  navTextActive: '#00f0ff',
  navItemHover: 'rgba(0, 240, 255, 0.08)',
  navItemActive: 'rgba(0, 240, 255, 0.15)',

  glowColor: 'rgba(0, 240, 255, 0.5)',
  gradientPrimary: 'linear-gradient(135deg, rgba(0,240,255,0.08), rgba(255,0,255,0.06))',
  gradientCard: 'linear-gradient(135deg, rgba(0,240,255,0.05), rgba(255,0,255,0.03))',
  animationSpeed: '0.4s',
};

/* ── 6. 星河万里 ── 深空星云 */
export const xingHeWanLi: ThemeTokens = {
  ...baseTokens,
  id: 'xing-he-wan-li',
  label: '星河万里',
  description: '星云浮动，宇宙漫游',
  emoji: '🚀',

  bgApp: '#0f1228',
  bgSurface: '#161a35',
  bgCard: '#1c2045',
  bgCardHover: '#242855',
  bgSidebar: '#12162c',
  bgInput: '#22264c',

  textPrimary: '#f0f4ff',
  textSecondary: '#aab4e0',
  textTertiary: '#7888b8',
  textInverse: '#0f1228',

  brandPrimary: '#b480ff',
  brandPrimaryHover: '#c8a0ff',
  brandPrimaryLight: 'rgba(180, 128, 255, 0.14)',
  brandSecondary: '#40d0b0',

  success: '#40e090',
  successLight: 'rgba(64, 224, 144, 0.12)',
  warning: '#f0c040',
  warningLight: 'rgba(240, 192, 64, 0.12)',
  danger: '#f05070',
  dangerLight: 'rgba(240, 80, 112, 0.12)',
  info: '#50a0f0',
  infoLight: 'rgba(80, 160, 240, 0.12)',

  border: '#1c1c50',
  borderLight: '#181845',
  divider: '#1a1a4a',

  shadowSm: '0 0 10px rgba(180, 128, 255, 0.15)',
  shadowMd: '0 0 24px rgba(180, 128, 255, 0.2)',
  shadowLg: '0 0 48px rgba(180, 128, 255, 0.25)',

  navBg: '#080a22',
  navText: '#485078',
  navTextActive: '#b480ff',
  navItemHover: 'rgba(180, 128, 255, 0.08)',
  navItemActive: 'rgba(180, 128, 255, 0.16)',

  glowColor: 'rgba(180, 128, 255, 0.4)',
  gradientPrimary: 'linear-gradient(135deg, rgba(180,128,255,0.1), rgba(64,208,176,0.06))',
  gradientCard: 'linear-gradient(135deg, rgba(180,128,255,0.05), rgba(64,208,176,0.03))',
  animationSpeed: '0.5s',
};

/* ── 7. 青山绿水 ── 自然森林 */
export const qingShanLvShui: ThemeTokens = {
  ...baseTokens,
  id: 'qing-shan-lv-shui',
  label: '青山绿水',
  description: '自然清新，森林氧吧',
  emoji: '🌿',

  bgApp: '#f2f7f3',
  bgSurface: '#ffffff',
  bgCard: '#ffffff',
  bgCardHover: '#f0f8f2',
  bgSidebar: '#eaf4ec',
  bgInput: '#edf5ef',

  textPrimary: '#1a2e1e',
  textSecondary: '#466050',
  textTertiary: '#80a090',
  textInverse: '#ffffff',

  brandPrimary: '#2e8b57',
  brandPrimaryHover: '#268050',
  brandPrimaryLight: '#e0f5ea',
  brandSecondary: '#8b6b2e',

  success: '#2ea060',
  successLight: '#e0f8e8',
  warning: '#c09030',
  warningLight: '#fdf5e0',
  danger: '#c05040',
  dangerLight: '#fce8e5',
  info: '#3080b0',
  infoLight: '#e0f0f8',

  border: '#c8e0d0',
  borderLight: '#d8eee0',
  divider: '#d0e8d8',

  shadowSm: '0 1px 4px rgba(46, 139, 87, 0.06)',
  shadowMd: '0 3px 10px rgba(46, 139, 87, 0.08)',
  shadowLg: '0 6px 24px rgba(46, 139, 87, 0.10)',

  navBg: '#eaf4ec',
  navText: '#5a7a66',
  navTextActive: '#2e8b57',
  navItemHover: 'rgba(46, 139, 87, 0.06)',
  navItemActive: 'rgba(46, 139, 87, 0.12)',

  glowColor: 'rgba(46, 139, 87, 0.2)',
  gradientPrimary: 'linear-gradient(135deg, #e0f5ea, #ffffff)',
  gradientCard: 'linear-gradient(135deg, rgba(46,139,87,0.02), rgba(139,107,46,0.02))',
};

/* ── 8. 锦绣前程 ── 正金色华贵 */
export const jinXiuQianCheng: ThemeTokens = {
  ...baseTokens,
  id: 'jin-xiu-qian-cheng',
  label: '锦绣前程',
  description: '正金尊贵，大气磅礡',
  emoji: '👑',

  bgApp: '#0e0c08',
  bgSurface: '#181408',
  bgCard: '#1e1a0e',
  bgCardHover: '#282014',
  bgSidebar: '#141008',
  bgInput: '#22200e',

  textPrimary: '#fff8e0',
  textSecondary: '#c8b880',
  textTertiary: '#887840',
  textInverse: '#0e0c08',

  brandPrimary: '#ffd700',
  brandPrimaryHover: '#ffe040',
  brandPrimaryLight: 'rgba(255, 215, 0, 0.14)',
  brandSecondary: '#ff8c00',

  success: '#90c840',
  successLight: 'rgba(144, 200, 64, 0.12)',
  warning: '#ffa500',
  warningLight: 'rgba(255, 165, 0, 0.12)',
  danger: '#e05040',
  dangerLight: 'rgba(224, 80, 64, 0.12)',
  info: '#70a8d0',
  infoLight: 'rgba(112, 168, 208, 0.12)',

  border: '#3a3010',
  borderLight: '#302a0c',
  divider: '#342e10',

  shadowSm: '0 1px 6px rgba(255, 215, 0, 0.12)',
  shadowMd: '0 3px 16px rgba(255, 215, 0, 0.15)',
  shadowLg: '0 6px 32px rgba(255, 215, 0, 0.2)',

  navBg: '#141008',
  navText: '#887840',
  navTextActive: '#ffd700',
  navItemHover: 'rgba(255, 215, 0, 0.06)',
  navItemActive: 'rgba(255, 215, 0, 0.14)',

  glowColor: 'rgba(255, 215, 0, 0.35)',
  gradientPrimary: 'linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,140,0,0.06))',
  gradientCard: 'linear-gradient(135deg, rgba(255,215,0,0.04), rgba(255,140,0,0.02))',
};

/* 全部主题注册 */
export const themes: Record<ThemeId, ThemeTokens> = {
  'chun-he-jing-ming': chunHeJingMing,
  'yue-lang-xing-xi': yueLangXingXi,
  'ming-cha-qiu-hao': mingChaQiuHao,
  'wan-zi-qian-hong': wanZiQianHong,
  'feng-chi-dian-che': fengChiDianChe,
  'xing-he-wan-li': xingHeWanLi,
  'qing-shan-lv-shui': qingShanLvShui,
  'jin-xiu-qian-cheng': jinXiuQianCheng,
};

/* 主题列表（有序，用于渲染选择卡片） */
export const themeList: ThemeTokens[] = [
  chunHeJingMing,
  yueLangXingXi,
  mingChaQiuHao,
  wanZiQianHong,
  fengChiDianChe,
  xingHeWanLi,
  qingShanLvShui,
  jinXiuQianCheng,
];
