import type { PluginRegistryItem } from '../settings/settingsTypes';

type ToggleGuardPlugin = Pick<PluginRegistryItem, 'id' | 'enabled' | 'types'>;
type DeleteGuardPlugin = Pick<PluginRegistryItem, 'id' | 'types'>;

function isActiveThemePlugin(
  plugin: Pick<PluginRegistryItem, 'id' | 'types'>,
  activeThemePluginId: string | null | undefined,
): boolean {
  if (!plugin.types.includes('theme-pack')) {
    return false;
  }

  const normalizedActiveThemePluginId = activeThemePluginId?.trim();
  if (!normalizedActiveThemePluginId) {
    return false;
  }

  return plugin.id === normalizedActiveThemePluginId;
}

export function shouldBlockDisableCurrentThemePlugin(
  plugin: ToggleGuardPlugin,
  activeThemePluginId: string | null | undefined,
): boolean {
  if (!plugin.enabled) {
    return false;
  }

  return isActiveThemePlugin(plugin, activeThemePluginId);
}

export function shouldBlockDeleteCurrentThemePlugin(
  plugin: DeleteGuardPlugin,
  activeThemePluginId: string | null | undefined,
): boolean {
  return isActiveThemePlugin(plugin, activeThemePluginId);
}
