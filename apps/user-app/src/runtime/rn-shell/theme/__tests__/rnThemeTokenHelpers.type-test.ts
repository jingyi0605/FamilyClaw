import type { PluginThemeResourcePayload } from '@familyclaw/user-ui';
import {
  applyRnThemeById,
  applyRnThemeFromPluginResource,
  getCurrentRnThemeId,
  getRnThemeRuntimeState,
} from '../../tokens';

const pluginThemePayload: PluginThemeResourcePayload = {
  plugin_id: 'theme-chun-he-jing-ming',
  theme_id: 'chun-he-jing-ming',
  display_name: '春和景明',
  description: '内置主题插件',
  tokens: {
    brandPrimary: '#d97756',
    bgApp: '#f7f5f2',
    textPrimary: '#1a1a1a',
  },
};

const normalizedTheme = applyRnThemeFromPluginResource(pluginThemePayload);
const runtimeState = getRnThemeRuntimeState();
const activeThemeId: string = getCurrentRnThemeId();
const missingState = applyRnThemeById('plugin-theme-not-exists');

if (missingState.status !== 'missing') {
  throw new Error('缺失主题必须进入 missing 状态');
}

if (missingState.reason !== 'theme_not_registered') {
  throw new Error('缺失主题必须返回 theme_not_registered 原因');
}

if (runtimeState.status === 'ready') {
  applyRnThemeById(runtimeState.themeId);
}

const backToReadyState = applyRnThemeById(activeThemeId);
if (backToReadyState.status !== 'ready') {
  throw new Error('已注册主题必须可以恢复到 ready 状态');
}
void normalizedTheme;
