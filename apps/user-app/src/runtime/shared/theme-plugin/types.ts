export type ThemeResourceSource = 'builtin_bundle' | 'managed_plugin_dir';
export type ThemeRegistryState = 'ready' | 'disabled' | 'invalid' | 'stale';
export type ThemePluginSourceType = 'builtin' | 'official' | 'third_party';
export type ThemeRuntimeStatus = 'booting' | 'loading' | 'ready' | 'missing' | 'error';

export type ThemeRuntimeSelection = {
  plugin_id: string;
  theme_id: string;
};

export type ThemeFallbackNotice = {
  disabledThemeId: string;
  disabledReason: string | null;
};

export type ThemeVersionInfo = {
  pluginId: string;
  version: string;
  installedVersion: string | null;
  updateState: string | null;
};

export type PluginThemeRegistryItemRead = {
  plugin_id: string;
  theme_id: string;
  display_name: string;
  description?: string | null;
  source_type?: ThemePluginSourceType | null;
  enabled?: boolean | null;
  state?: ThemeRegistryState | null;
  disabled_reason?: string | null;
  resource_source: ThemeResourceSource;
  resource_version: string;
  theme_schema_version: number;
  platform_targets?: string[] | null;
  preview?: Record<string, unknown> | null;
  version?: string | null;
  installed_version?: string | null;
  update_state?: string | null;
};

export type PluginThemeRegistrySnapshotRead = {
  items: PluginThemeRegistryItemRead[];
};

export type PluginThemeResourceRead = {
  plugin_id: string;
  theme_id: string;
  display_name?: string | null;
  description?: string | null;
  resource_version: string;
  theme_schema_version: number;
  tokens: Record<string, string>;
  preview?: Record<string, unknown> | null;
};

export type BuiltinThemeBundlePayload = {
  display_name?: string;
  description?: string;
  resource_version?: string;
  theme_schema_version?: number;
  preview?: Record<string, unknown>;
  tokens: Record<string, string>;
};

export type BuiltinThemeBundleEntry = {
  plugin_id: string;
  theme_id: string;
  display_name: string;
  description: string;
  source_type: 'builtin';
  resource_source: 'builtin_bundle';
  resource_version: string;
  theme_schema_version: number;
  platform_targets: string[];
  preview?: Record<string, unknown>;
  bundle_module: string;
  load_bundle: () => Promise<BuiltinThemeBundlePayload>;
};

export type ThemeRuntimeThemeOption = {
  id: string;
  plugin_id: string;
  label: string;
  description: string;
  emoji: string;
  bgApp: string;
  bgCard: string;
  brandPrimary: string;
  textPrimary: string;
  glowColor: string;
  state: ThemeRegistryState;
  source_type: ThemePluginSourceType;
  resource_version: string;
  tokens: Record<string, string>;
};

export type ThemeRegistryItem = {
  plugin_id: string;
  theme_id: string;
  display_name: string;
  description: string;
  source_type: ThemePluginSourceType;
  enabled: boolean;
  state: ThemeRegistryState;
  disabled_reason: string | null;
  resource_source: ThemeResourceSource;
  resource_version: string;
  theme_schema_version: number;
  platform_targets: string[];
  preview: Record<string, unknown>;
  version: string;
  installed_version: string | null;
  update_state: string | null;
};

export type ThemeRuntimeState = {
  status: ThemeRuntimeStatus;
  loading: boolean;
  error: string;
  household_id: string | null;
  registry_items: ThemeRegistryItem[];
  theme_list: ThemeRuntimeThemeOption[];
  active_theme: ThemeRuntimeThemeOption | null;
  shell_theme: ThemeRuntimeThemeOption | null;
  selection: ThemeRuntimeSelection | null;
  missing_selection: ThemeRuntimeSelection | null;
  theme_fallback_notice: ThemeFallbackNotice | null;
  version_info_by_theme_id: Record<string, ThemeVersionInfo>;
  disabled_reason_by_theme_id: Record<string, string | null>;
};
