/**
 * RN Shell - 移动端设计系统入口
 *
 * 统一导出所有 RN 端 token 和公共组件。
 */

// Token
export {
  applyRnTheme,
  applyRnThemeById,
  applyRnThemeFromPluginResource,
  buildRnThemeTokenBundleFromPluginResource,
  getCurrentRnTheme,
  getCurrentRnThemeId,
  getRnThemeRuntimeState,
  rnFoundationTokens,
  rnSemanticTokens,
  rnComponentTokens,
} from './tokens';
export { RnThemeProvider, useRnTheme, useRnThemeTokens } from './theme/RnThemeProvider';

// 组件
export { RnPageShell } from './components/RnPageShell';
export { RnPageHeader } from './components/RnPageHeader';
export { RnSection } from './components/RnSection';
export { RnCard } from './components/RnCard';
export { RnText } from './components/RnText';
export type { RnTextVariant, RnTextTone } from './components/RnText';
export { RnButton } from './components/RnButton';
export { RnInput } from './components/RnInput';
export { RnFormItem } from './components/RnFormItem';
export { RnEmptyState } from './components/RnEmptyState';
export { RnTabBar } from './components/RnTabBar';
