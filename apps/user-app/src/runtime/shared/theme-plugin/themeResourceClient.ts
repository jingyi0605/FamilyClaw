import { createRequestClient } from '@familyclaw/user-core';
import type {
  PluginThemeRegistrySnapshotRead,
  PluginThemeResourceRead,
} from './types';

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

export function listHouseholdThemeRegistry(householdId: string) {
  return request<PluginThemeRegistrySnapshotRead>(
    `/ai-config/${encodeURIComponent(householdId)}/themes`,
  );
}

export function getHouseholdThemeResource(
  householdId: string,
  pluginId: string,
  themeId: string,
) {
  return request<PluginThemeResourceRead>(
    `/ai-config/${encodeURIComponent(householdId)}/plugin-themes/${encodeURIComponent(pluginId)}/${encodeURIComponent(themeId)}`,
  );
}
