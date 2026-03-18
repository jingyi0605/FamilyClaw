import type { PluginRegistryItem } from '../settings/settingsTypes';

type ToggleGuardPlugin = Pick<PluginRegistryItem, 'id' | 'enabled' | 'types'>;

export function shouldBlockDisableCurrentThemePlugin(
  plugin: ToggleGuardPlugin,
  activeThemePluginId: string | null | undefined,
): boolean {
  if (!plugin.enabled) {
    return false;
  }

  if (!plugin.types.includes('theme-pack')) {
    return false;
  }

  const normalizedActiveThemePluginId = activeThemePluginId?.trim();
  if (!normalizedActiveThemePluginId) {
    return false;
  }

  return plugin.id === normalizedActiveThemePluginId;
}
