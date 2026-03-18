/**
 * RN 端设计 Token
 *
 * 从 @familyclaw/user-ui 的默认主题（春和景明）中提取原始值，
 * 将 CSS px 字符串转为 RN 所需的纯数字，保持品牌语义一致。
 *
 * 三层结构：
 *   1. rnFoundationTokens  – 尺寸/间距/圆角/字号（固定数值）
 *   2. rnSemanticTokens    – 颜色，按用途语义分组
 *   3. rnComponentTokens   – 预组合的组件样式 token
 */
import { userAppThemes } from '@familyclaw/user-ui';

const defaultTheme = userAppThemes['chun-he-jing-ming'];

/* ─── 基础 Token ─── */

export const rnFoundationTokens = {
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  radius: {
    sm: 6,
    md: 10,
    lg: 14,
    xl: 20,
    full: 999,
  },
  fontSize: {
    xs: 12,
    sm: 13,
    md: 15,
    lg: 18,
    xl: 22,
    xxl: 28,
    hero: 36,
  },
  lineHeight: {
    tight: 1.3,
    normal: 1.5,
    relaxed: 1.6,
  },
} as const;

/* ─── 语义 Token ─── */

export const rnSemanticTokens = {
  surface: {
    page: defaultTheme.bgApp,
    shell: defaultTheme.bgSurface,
    card: defaultTheme.bgCard,
    cardHover: defaultTheme.bgCardHover,
    sidebar: defaultTheme.bgSidebar,
    muted: defaultTheme.bgInput,
  },
  text: {
    primary: defaultTheme.textPrimary,
    secondary: defaultTheme.textSecondary,
    tertiary: defaultTheme.textTertiary,
    inverse: defaultTheme.textInverse,
  },
  border: {
    default: defaultTheme.border,
    subtle: defaultTheme.borderLight,
    divider: defaultTheme.divider,
  },
  action: {
    primary: defaultTheme.brandPrimary,
    primaryHover: defaultTheme.brandPrimaryHover,
    primaryLight: defaultTheme.brandPrimaryLight,
    secondary: defaultTheme.brandSecondary,
  },
  state: {
    success: defaultTheme.success,
    successLight: defaultTheme.successLight,
    warning: defaultTheme.warning,
    warningLight: defaultTheme.warningLight,
    danger: defaultTheme.danger,
    dangerLight: defaultTheme.dangerLight,
    info: defaultTheme.info,
    infoLight: defaultTheme.infoLight,
  },
  nav: {
    background: defaultTheme.navBg,
    text: defaultTheme.navText,
    textActive: defaultTheme.navTextActive,
  },
} as const;

/* ─── 组件 Token ─── */

export const rnComponentTokens = {
  text: {
    body: {
      color: rnSemanticTokens.text.primary,
      fontSize: rnFoundationTokens.fontSize.md,
      fontWeight: '400' as const,
      lineHeight: rnFoundationTokens.fontSize.md * rnFoundationTokens.lineHeight.relaxed,
    },
    caption: {
      color: rnSemanticTokens.text.secondary,
      fontSize: rnFoundationTokens.fontSize.sm,
      fontWeight: '400' as const,
      lineHeight: rnFoundationTokens.fontSize.sm * rnFoundationTokens.lineHeight.normal,
    },
    label: {
      color: rnSemanticTokens.text.primary,
      fontSize: rnFoundationTokens.fontSize.md,
      fontWeight: '600' as const,
      lineHeight: rnFoundationTokens.fontSize.md * rnFoundationTokens.lineHeight.normal,
    },
    title: {
      color: rnSemanticTokens.text.primary,
      fontSize: rnFoundationTokens.fontSize.xl,
      fontWeight: '600' as const,
      lineHeight: rnFoundationTokens.fontSize.xl * rnFoundationTokens.lineHeight.tight,
    },
    hero: {
      color: rnSemanticTokens.text.primary,
      fontSize: rnFoundationTokens.fontSize.hero,
      fontWeight: '700' as const,
      lineHeight: rnFoundationTokens.fontSize.hero * rnFoundationTokens.lineHeight.tight,
    },
  },
  card: {
    default: {
      backgroundColor: rnSemanticTokens.surface.card,
      borderColor: rnSemanticTokens.border.subtle,
      borderWidth: 1,
      borderRadius: rnFoundationTokens.radius.lg,
      padding: rnFoundationTokens.spacing.md,
    },
    muted: {
      backgroundColor: rnSemanticTokens.surface.muted,
      borderColor: rnSemanticTokens.border.subtle,
      borderWidth: 1,
      borderRadius: rnFoundationTokens.radius.md,
      padding: rnFoundationTokens.spacing.sm,
    },
    warning: {
      backgroundColor: rnSemanticTokens.state.warningLight,
      borderColor: rnSemanticTokens.state.warning,
      borderWidth: 1,
      borderRadius: rnFoundationTokens.radius.lg,
      padding: rnFoundationTokens.spacing.md,
    },
  },
  button: {
    minHeight: 48,
    borderRadius: rnFoundationTokens.radius.md,
    paddingHorizontal: rnFoundationTokens.spacing.md,
    fontSize: rnFoundationTokens.fontSize.md,
    fontWeight: '600' as const,
  },
  input: {
    minHeight: 48,
    borderRadius: rnFoundationTokens.radius.md,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: rnFoundationTokens.fontSize.md,
    backgroundColor: rnSemanticTokens.surface.card,
    borderColor: rnSemanticTokens.border.default,
    color: rnSemanticTokens.text.primary,
  },
  shadow: {
    sm: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.06,
      shadowRadius: 3,
      elevation: 1,
    },
    md: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.08,
      shadowRadius: 8,
      elevation: 3,
    },
    lg: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.1,
      shadowRadius: 20,
      elevation: 6,
    },
  },
} as const;
