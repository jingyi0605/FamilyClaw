import { THEME_STORAGE_KEY } from '@familyclaw/user-core';
import { builtinThemeBundleIndex } from './builtinThemeBundleIndex';
import {
  getHouseholdThemeResource,
  listHouseholdThemeRegistry,
} from './themeResourceClient';
import type {
  BuiltinThemeBundleEntry,
  PluginThemeRegistryItemRead,
  PluginThemeRegistrySnapshotRead,
  PluginThemeResourceRead,
  ThemeFallbackNotice,
  ThemePluginSourceType,
  ThemeRegistryItem,
  ThemeRegistryState,
  ThemeResourceSource,
  ThemeRuntimeSelection,
  ThemeRuntimeState,
  ThemeRuntimeThemeOption,
} from './types';

type ThemeRuntimeListener = (state: ThemeRuntimeState) => void;

type ThemeRuntimeDeps = {
  builtinEntries: BuiltinThemeBundleEntry[];
  fetchRegistry: (householdId: string) => Promise<PluginThemeRegistrySnapshotRead>;
  fetchResource: (
    householdId: string,
    pluginId: string,
    themeId: string,
  ) => Promise<PluginThemeResourceRead>;
  readStoredSelection: () => ThemeRuntimeSelection | null;
  writeStoredSelection: (selection: ThemeRuntimeSelection | null) => void;
};

type ActivateOptions = {
  requestSerial: number;
  registryItems: ThemeRegistryItem[];
  householdId: string | null;
  baseError: string;
};

const PLUGIN_THEME_SELECTION_STORAGE_KEY = 'familyclaw-theme-plugin-selection-v1';
const THEME_SOURCE_WEIGHT: Record<ThemePluginSourceType, number> = {
  builtin: 0,
  third_party: 1,
};
const BUILTIN_THEME_FIXED_ORDER = [
  'chun-he-jing-ming',
  'yue-lang-xing-xi',
  'feng-chi-dian-che',
  'jin-xiu-qian-cheng',
  'ming-cha-qiu-hao',
  'qing-shan-lv-shui',
  'wan-zi-qian-hong',
  'xing-he-wan-li',
] as const;
const BUILTIN_THEME_ORDER_INDEX = new Map<string, number>(
  BUILTIN_THEME_FIXED_ORDER.map((themeId, index) => [themeId, index]),
);

function readString(value: unknown, fallback = '') {
  if (typeof value !== 'string') {
    return fallback;
  }
  const normalized = value.trim();
  return normalized || fallback;
}

function readNullableString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const normalized = readString(value);
  return normalized || null;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(item => readString(item))
    .filter(item => item.length > 0);
}

function readBoolean(value: unknown, fallback: boolean) {
  if (typeof value === 'boolean') {
    return value;
  }
  return fallback;
}

function readNumber(value: unknown, fallback: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  return value;
}

function normalizeRegistryState(
  value: string,
  enabled: boolean,
): ThemeRegistryState {
  if (value === 'ready' || value === 'disabled' || value === 'invalid' || value === 'stale') {
    return value;
  }
  return enabled ? 'ready' : 'disabled';
}

function normalizeSourceType(
  value: unknown,
  fallback: ThemePluginSourceType,
): ThemePluginSourceType {
  if (value === 'builtin' || value === 'third_party') {
    return value;
  }
  if (value === 'official') {
    return 'third_party';
  }
  return fallback;
}

function normalizeResourceSource(
  value: unknown,
  fallback: ThemeResourceSource,
): ThemeResourceSource {
  if (value === 'builtin_bundle' || value === 'managed_plugin_dir') {
    return value;
  }
  return fallback;
}

function toRegistryKey(selection: ThemeRuntimeSelection) {
  return `${selection.plugin_id}::${selection.theme_id}`;
}

function toRegistryKeyByItem(item: ThemeRegistryItem) {
  return `${item.plugin_id}::${item.theme_id}`;
}

function normalizeTokens(tokens: Record<string, unknown> | null | undefined) {
  const normalized: Record<string, string> = {};
  if (!tokens) {
    return normalized;
  }
  for (const [key, value] of Object.entries(tokens)) {
    if (typeof value === 'string') {
      const candidate = value.trim();
      if (candidate) {
        normalized[key] = candidate;
      }
    }
  }
  return normalized;
}

function readPreviewString(
  preview: Record<string, unknown> | undefined,
  key: string,
) {
  if (!preview) {
    return '';
  }
  return readString(preview[key]);
}

function sortRegistryItems(items: ThemeRegistryItem[]) {
  return [...items].sort((left, right) => {
    if (left.source_type === 'builtin' && right.source_type === 'builtin') {
      const leftOrder = BUILTIN_THEME_ORDER_INDEX.get(left.theme_id) ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = BUILTIN_THEME_ORDER_INDEX.get(right.theme_id) ?? Number.MAX_SAFE_INTEGER;
      const builtinOrderDiff = leftOrder - rightOrder;
      if (builtinOrderDiff !== 0) {
        return builtinOrderDiff;
      }
    }
    const sourceDiff = THEME_SOURCE_WEIGHT[left.source_type] - THEME_SOURCE_WEIGHT[right.source_type];
    if (sourceDiff !== 0) {
      return sourceDiff;
    }
    const nameDiff = left.display_name.localeCompare(right.display_name, 'zh-CN');
    if (nameDiff !== 0) {
      return nameDiff;
    }
    const themeDiff = left.theme_id.localeCompare(right.theme_id, 'zh-CN');
    if (themeDiff !== 0) {
      return themeDiff;
    }
    return left.plugin_id.localeCompare(right.plugin_id, 'zh-CN');
  });
}

function buildBuiltinRegistryItems(entries: BuiltinThemeBundleEntry[]) {
  return sortRegistryItems(entries.map((entry) => ({
    plugin_id: entry.plugin_id,
    theme_id: entry.theme_id,
    display_name: readString(entry.display_name, entry.theme_id),
    description: readString(entry.description),
    source_type: 'builtin' as const,
    enabled: true,
    state: 'ready' as const,
    disabled_reason: null,
    resource_source: 'builtin_bundle' as const,
    resource_version: readString(entry.resource_version, '1.0.0'),
    theme_schema_version: readNumber(entry.theme_schema_version, 1),
    platform_targets: readStringArray(entry.platform_targets),
    preview: entry.preview ?? {},
    version: readString(entry.resource_version, '1.0.0'),
    installed_version: readNullableString(entry.resource_version),
    update_state: null,
  })));
}

function normalizeRemoteRegistryItem(
  rawItem: PluginThemeRegistryItemRead,
  builtinPluginIds: Set<string>,
): ThemeRegistryItem | null {
  const raw = rawItem as Record<string, unknown>;
  const pluginId = readString(raw.plugin_id ?? raw.pluginId);
  const themeId = readString(raw.theme_id ?? raw.themeId);
  if (!pluginId || !themeId) {
    return null;
  }

  const defaultSourceType: ThemePluginSourceType = builtinPluginIds.has(pluginId)
    ? 'builtin'
    : 'third_party';

  const enabled = readBoolean(raw.enabled, true);
  const sourceType = normalizeSourceType(raw.source_type ?? raw.sourceType, defaultSourceType);
  const state = normalizeRegistryState(readString(raw.state), enabled);
  const resourceSource = normalizeResourceSource(
    raw.resource_source ?? raw.resourceSource,
    builtinPluginIds.has(pluginId) ? 'builtin_bundle' : 'managed_plugin_dir',
  );

  return {
    plugin_id: pluginId,
    theme_id: themeId,
    display_name: readString(raw.display_name ?? raw.displayName, themeId),
    description: readString(raw.description),
    source_type: sourceType,
    enabled,
    state,
    disabled_reason: readNullableString(raw.disabled_reason ?? raw.disabledReason),
    resource_source: resourceSource,
    resource_version: readString(raw.resource_version ?? raw.resourceVersion, '1.0.0'),
    theme_schema_version: readNumber(raw.theme_schema_version ?? raw.themeSchemaVersion, 1),
    platform_targets: readStringArray(raw.platform_targets ?? raw.platformTargets),
    preview: (raw.preview && typeof raw.preview === 'object') ? raw.preview as Record<string, unknown> : {},
    version: readString(raw.version, readString(raw.resource_version ?? raw.resourceVersion, '1.0.0')),
    installed_version: readNullableString(raw.installed_version ?? raw.installedVersion),
    update_state: readNullableString(raw.update_state ?? raw.updateState),
  };
}

function mergeRegistryItems(
  builtinItems: ThemeRegistryItem[],
  remoteItems: PluginThemeRegistryItemRead[],
  builtinPluginIds: Set<string>,
) {
  const merged = new Map<string, ThemeRegistryItem>();

  for (const item of builtinItems) {
    merged.set(toRegistryKeyByItem(item), item);
  }

  for (const rawItem of remoteItems) {
    const normalized = normalizeRemoteRegistryItem(rawItem, builtinPluginIds);
    if (!normalized) {
      continue;
    }
    merged.set(toRegistryKeyByItem(normalized), normalized);
  }

  return sortRegistryItems([...merged.values()]);
}

function buildDisabledReasonByThemeId(registryItems: ThemeRegistryItem[]) {
  const result: Record<string, string | null> = {};
  for (const item of registryItems) {
    if (item.state === 'ready') {
      continue;
    }
    if (result[item.theme_id] !== undefined) {
      continue;
    }
    result[item.theme_id] = item.disabled_reason ?? null;
  }
  return result;
}

function buildVersionInfoByThemeId(
  registryItems: ThemeRegistryItem[],
  selection: ThemeRuntimeSelection | null,
) {
  const result: ThemeRuntimeState['version_info_by_theme_id'] = {};
  const sorted = [...registryItems].sort((left, right) => {
    const leftSelected = selection && toRegistryKey(selection) === toRegistryKeyByItem(left);
    const rightSelected = selection && toRegistryKey(selection) === toRegistryKeyByItem(right);
    if (leftSelected !== rightSelected) {
      return leftSelected ? -1 : 1;
    }
    if (left.state !== right.state) {
      return left.state === 'ready' ? -1 : 1;
    }
    const sourceDiff = THEME_SOURCE_WEIGHT[left.source_type] - THEME_SOURCE_WEIGHT[right.source_type];
    if (sourceDiff !== 0) {
      return sourceDiff;
    }
    return 0;
  });

  for (const item of sorted) {
    if (result[item.theme_id]) {
      continue;
    }
    result[item.theme_id] = {
      pluginId: item.plugin_id,
      version: item.version,
      installedVersion: item.installed_version,
      updateState: item.update_state,
    };
  }
  return result;
}

function buildThemeOption(
  item: ThemeRegistryItem,
  tokens: Record<string, string>,
  displayName?: string,
  description?: string,
  preview?: Record<string, unknown>,
): ThemeRuntimeThemeOption {
  const previewSurface = readString(readPreviewString(preview ?? item.preview, 'preview_surface'));
  const accentColor = readString(readPreviewString(preview ?? item.preview, 'accent_color'));
  const previewTextPrimary = readString(readPreviewString(preview ?? item.preview, 'text_primary'));
  const mergedPreview = {
    ...item.preview,
    ...(preview ?? {}),
  };

  return {
    id: item.theme_id,
    plugin_id: item.plugin_id,
    label: readString(displayName, item.display_name),
    description: readString(description, item.description),
    emoji: readString(
      readPreviewString(mergedPreview, 'emoji'),
      '🎨',
    ),
    bgApp: readString(
      tokens.bgApp,
      readString(readPreviewString(mergedPreview, 'bgApp'), previewSurface),
    ),
    bgCard: readString(
      tokens.bgCard,
      readString(readPreviewString(mergedPreview, 'bgCard'), previewSurface),
    ),
    brandPrimary: readString(
      tokens.brandPrimary,
      readString(readPreviewString(mergedPreview, 'brandPrimary'), accentColor),
    ),
    textPrimary: readString(
      tokens.textPrimary,
      readString(readPreviewString(mergedPreview, 'textPrimary'), previewTextPrimary),
    ),
    glowColor: readString(
      tokens.glowColor,
      readString(readPreviewString(mergedPreview, 'glowColor'), accentColor),
    ),
    state: item.state,
    source_type: item.source_type,
    resource_version: item.resource_version,
    tokens,
  };
}

function pickDefaultSelection(registryItems: ThemeRegistryItem[]) {
  const readyBuiltin = registryItems.find(item => item.state === 'ready' && item.source_type === 'builtin');
  if (readyBuiltin) {
    return {
      plugin_id: readyBuiltin.plugin_id,
      theme_id: readyBuiltin.theme_id,
    };
  }

  const readyAny = registryItems.find(item => item.state === 'ready');
  if (readyAny) {
    return {
      plugin_id: readyAny.plugin_id,
      theme_id: readyAny.theme_id,
    };
  }

  return null;
}

function pickShellTheme(
  registryItems: ThemeRegistryItem[],
  cachedThemeByKey: Map<string, ThemeRuntimeThemeOption>,
  selection: ThemeRuntimeSelection | null,
) {
  const preferred = selection
    ? registryItems.find(item => item.state === 'ready' && toRegistryKey(selection) === toRegistryKeyByItem(item))
    : null;
  const shellSource = preferred
    ?? registryItems.find(item => item.state === 'ready' && item.source_type === 'builtin')
    ?? registryItems.find(item => item.state === 'ready')
    ?? null;

  if (!shellSource) {
    return null;
  }

  const cacheKey = `${toRegistryKeyByItem(shellSource)}::${shellSource.resource_version}`;
  const cached = cachedThemeByKey.get(cacheKey);
  if (cached) {
    return cached;
  }

  return buildThemeOption(shellSource, {}, undefined, undefined, shellSource.preview);
}

function buildThemeList(
  registryItems: ThemeRegistryItem[],
  cachedThemeByKey: Map<string, ThemeRuntimeThemeOption>,
  selection: ThemeRuntimeSelection | null,
  activeTheme: ThemeRuntimeThemeOption | null,
) {
  const sorted = sortRegistryItems(registryItems);

  const byRegistryKey = new Map<string, ThemeRuntimeThemeOption>();

  for (const item of sorted) {
    if (item.state !== 'ready') {
      continue;
    }
    const registryKey = toRegistryKeyByItem(item);
    if (byRegistryKey.has(registryKey)) {
      continue;
    }
    if (
      activeTheme
      && activeTheme.id === item.theme_id
      && activeTheme.plugin_id === item.plugin_id
    ) {
      byRegistryKey.set(registryKey, activeTheme);
      continue;
    }
    const cacheKey = `${registryKey}::${item.resource_version}`;
    const cached = cachedThemeByKey.get(cacheKey);
    byRegistryKey.set(registryKey, cached ?? buildThemeOption(item, {}, undefined, undefined, item.preview));
  }

  return [...byRegistryKey.values()];
}

function createLocalSelectionStore(
  builtinEntries: BuiltinThemeBundleEntry[],
): Pick<ThemeRuntimeDeps, 'readStoredSelection' | 'writeStoredSelection'> {
  const builtinByThemeId = new Map<string, string>();
  for (const entry of builtinEntries) {
    if (!builtinByThemeId.has(entry.theme_id)) {
      builtinByThemeId.set(entry.theme_id, entry.plugin_id);
    }
  }

  return {
    readStoredSelection() {
      if (typeof window === 'undefined') {
        return null;
      }

      try {
        const storedSelectionText = window.localStorage.getItem(PLUGIN_THEME_SELECTION_STORAGE_KEY);
        if (storedSelectionText) {
          const parsed = JSON.parse(storedSelectionText) as Partial<ThemeRuntimeSelection>;
          const pluginId = readString(parsed.plugin_id);
          const themeId = readString(parsed.theme_id);
          if (pluginId && themeId) {
            return { plugin_id: pluginId, theme_id: themeId };
          }
        }
      } catch {
        // 本地数据损坏时走兼容读取，不中断启动流程。
      }

      try {
        const legacyThemeId = readString(window.localStorage.getItem(THEME_STORAGE_KEY));
        if (!legacyThemeId) {
          return null;
        }
        const builtinPluginId = builtinByThemeId.get(legacyThemeId);
        if (!builtinPluginId) {
          return null;
        }
        return {
          plugin_id: builtinPluginId,
          theme_id: legacyThemeId,
        };
      } catch {
        return null;
      }
    },
    writeStoredSelection(selection) {
      if (typeof window === 'undefined') {
        return;
      }

      try {
        if (!selection) {
          window.localStorage.removeItem(PLUGIN_THEME_SELECTION_STORAGE_KEY);
          return;
        }
        window.localStorage.setItem(PLUGIN_THEME_SELECTION_STORAGE_KEY, JSON.stringify(selection));
        window.localStorage.setItem(THEME_STORAGE_KEY, selection.theme_id);
      } catch {
        // 忽略持久化失败，不阻断主题切换。
      }
    },
  };
}

function createInitialState(selection: ThemeRuntimeSelection | null): ThemeRuntimeState {
  return {
    status: 'booting',
    loading: false,
    error: '',
    household_id: null,
    registry_items: [],
    theme_list: [],
    active_theme: null,
    shell_theme: null,
    selection,
    missing_selection: null,
    theme_fallback_notice: null,
    version_info_by_theme_id: {},
    disabled_reason_by_theme_id: {},
  };
}

export class ThemeRuntime {
  private readonly deps: ThemeRuntimeDeps;
  private readonly builtinPluginIds: Set<string>;
  private readonly builtinEntryByRegistryKey: Map<string, BuiltinThemeBundleEntry>;
  private readonly listeners = new Set<ThemeRuntimeListener>();
  private readonly cachedThemeByVersionKey = new Map<string, ThemeRuntimeThemeOption>();
  private state: ThemeRuntimeState;
  private requestSerial = 0;

  constructor(deps: ThemeRuntimeDeps) {
    this.deps = deps;
    this.builtinPluginIds = new Set(deps.builtinEntries.map(item => item.plugin_id));
    this.builtinEntryByRegistryKey = new Map(
      deps.builtinEntries.map(item => [toRegistryKey(item), item]),
    );
    this.state = createInitialState(this.deps.readStoredSelection());
  }

  getState() {
    return this.state;
  }

  subscribe(listener: ThemeRuntimeListener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async bootstrap() {
    await this.refreshRegistry(this.state.household_id);
  }

  async refreshRegistry(nextHouseholdId: string | null = this.state.household_id) {
    const requestSerial = ++this.requestSerial;
    this.setState({
      loading: true,
      status: 'loading',
      household_id: nextHouseholdId,
      error: '',
    });

    const builtinRegistryItems = buildBuiltinRegistryItems(this.deps.builtinEntries);
    let registryItems = builtinRegistryItems;
    let baseError = '';

    if (nextHouseholdId) {
      try {
        const snapshot = await this.deps.fetchRegistry(nextHouseholdId);
        if (requestSerial !== this.requestSerial) {
          return;
        }
        registryItems = mergeRegistryItems(
          builtinRegistryItems,
          snapshot.items,
          this.builtinPluginIds,
        );
      } catch (error) {
        baseError = error instanceof Error ? error.message : '加载主题插件注册表失败';
      }
    }

    await this.activateSelection({
      requestSerial,
      registryItems,
      householdId: nextHouseholdId,
      baseError,
    });
  }

  async selectThemeByThemeId(themeId: string) {
    const normalizedThemeId = readString(themeId);
    if (!normalizedThemeId) {
      return;
    }

    const preferredReady = this.state.registry_items.find(
      item => item.theme_id === normalizedThemeId && item.state === 'ready',
    );
    if (preferredReady) {
      await this.selectTheme({
        plugin_id: preferredReady.plugin_id,
        theme_id: preferredReady.theme_id,
      });
      return;
    }

    const matchedAny = this.state.registry_items.find(
      item => item.theme_id === normalizedThemeId,
    );
    await this.selectTheme({
      plugin_id: matchedAny?.plugin_id ?? readString(this.state.selection?.plugin_id),
      theme_id: normalizedThemeId,
    });
  }

  async selectTheme(selection: ThemeRuntimeSelection) {
    const normalized: ThemeRuntimeSelection = {
      plugin_id: readString(selection.plugin_id),
      theme_id: readString(selection.theme_id),
    };
    if (!normalized.theme_id) {
      return;
    }

    this.deps.writeStoredSelection(normalized);
    const requestSerial = ++this.requestSerial;
    this.setState({
      selection: normalized,
      loading: true,
      status: 'loading',
      error: '',
    });

    await this.activateSelection({
      requestSerial,
      registryItems: this.state.registry_items,
      householdId: this.state.household_id,
      baseError: '',
    });
  }

  private async activateSelection(options: ActivateOptions) {
    if (options.requestSerial !== this.requestSerial) {
      return;
    }

    let selection = this.state.selection;
    if (selection) {
      const selectedEntry = options.registryItems.find(
        item => toRegistryKey(selection as ThemeRuntimeSelection) === toRegistryKeyByItem(item),
      );
      if (!selectedEntry) {
        const sameThemeReady = options.registryItems.find(
          item => item.theme_id === selection?.theme_id && item.state === 'ready',
        );
        if (sameThemeReady) {
          selection = {
            plugin_id: sameThemeReady.plugin_id,
            theme_id: sameThemeReady.theme_id,
          };
        }
      }
    }

    if (!selection) {
      selection = pickDefaultSelection(options.registryItems);
      if (selection) {
        this.deps.writeStoredSelection(selection);
      }
    }

    const disabledReasonByThemeId = buildDisabledReasonByThemeId(options.registryItems);
    const versionInfoByThemeId = buildVersionInfoByThemeId(options.registryItems, selection);

    if (!selection) {
      const shellTheme = pickShellTheme(
        options.registryItems,
        this.cachedThemeByVersionKey,
        null,
      );
      this.setState({
        status: options.baseError ? 'error' : 'missing',
        loading: false,
        error: options.baseError || '未发现可用主题插件',
        registry_items: options.registryItems,
        theme_list: [],
        active_theme: null,
        shell_theme: shellTheme,
        selection: null,
        missing_selection: null,
        theme_fallback_notice: null,
        version_info_by_theme_id: versionInfoByThemeId,
        disabled_reason_by_theme_id: disabledReasonByThemeId,
      });
      return;
    }

    const selectedEntry = options.registryItems.find(
      item => toRegistryKey(selection as ThemeRuntimeSelection) === toRegistryKeyByItem(item),
    );

    if (!selectedEntry || selectedEntry.state !== 'ready') {
      const fallbackNotice: ThemeFallbackNotice = {
        disabledThemeId: selection.theme_id,
        disabledReason: selectedEntry?.disabled_reason ?? null,
      };
      const shellTheme = pickShellTheme(
        options.registryItems,
        this.cachedThemeByVersionKey,
        selection,
      );
      this.setState({
        status: 'missing',
        loading: false,
        error: options.baseError,
        registry_items: options.registryItems,
        theme_list: buildThemeList(
          options.registryItems,
          this.cachedThemeByVersionKey,
          selection,
          null,
        ),
        active_theme: null,
        shell_theme: shellTheme,
        selection,
        missing_selection: selection,
        theme_fallback_notice: fallbackNotice,
        version_info_by_theme_id: versionInfoByThemeId,
        disabled_reason_by_theme_id: disabledReasonByThemeId,
      });
      return;
    }

    try {
      const activeTheme = await this.loadThemeOption(
        selectedEntry,
        options.householdId,
      );
      if (options.requestSerial !== this.requestSerial) {
        return;
      }

      const shellTheme = pickShellTheme(
        options.registryItems,
        this.cachedThemeByVersionKey,
        selection,
      );
      this.setState({
        status: 'ready',
        loading: false,
        error: options.baseError,
        registry_items: options.registryItems,
        theme_list: buildThemeList(
          options.registryItems,
          this.cachedThemeByVersionKey,
          selection,
          activeTheme,
        ),
        active_theme: activeTheme,
        shell_theme: shellTheme,
        selection,
        missing_selection: null,
        theme_fallback_notice: null,
        version_info_by_theme_id: versionInfoByThemeId,
        disabled_reason_by_theme_id: disabledReasonByThemeId,
      });
    } catch (error) {
      if (options.requestSerial !== this.requestSerial) {
        return;
      }
      const shellTheme = pickShellTheme(
        options.registryItems,
        this.cachedThemeByVersionKey,
        selection,
      );
      const errorMessage = error instanceof Error
        ? error.message
        : '加载主题资源失败';
      this.setState({
        status: 'error',
        loading: false,
        error: options.baseError ? `${options.baseError}；${errorMessage}` : errorMessage,
        registry_items: options.registryItems,
        theme_list: buildThemeList(
          options.registryItems,
          this.cachedThemeByVersionKey,
          selection,
          null,
        ),
        active_theme: null,
        shell_theme: shellTheme,
        selection,
        missing_selection: selection,
        theme_fallback_notice: {
          disabledThemeId: selection.theme_id,
          disabledReason: null,
        },
        version_info_by_theme_id: versionInfoByThemeId,
        disabled_reason_by_theme_id: disabledReasonByThemeId,
      });
    }
  }

  private async loadThemeOption(
    registryItem: ThemeRegistryItem,
    householdId: string | null,
  ) {
    const cacheKey = `${toRegistryKeyByItem(registryItem)}::${registryItem.resource_version}`;
    const cached = this.cachedThemeByVersionKey.get(cacheKey);
    if (cached) {
      return cached;
    }

    let themeOption: ThemeRuntimeThemeOption;
    if (registryItem.resource_source === 'builtin_bundle') {
      const builtinEntry = this.builtinEntryByRegistryKey.get(toRegistryKeyByItem(registryItem));
      if (!builtinEntry) {
        throw new Error(`缺少内置主题包资源：${registryItem.plugin_id}/${registryItem.theme_id}`);
      }
      const bundlePayload = await builtinEntry.load_bundle();
      themeOption = buildThemeOption(
        registryItem,
        normalizeTokens(bundlePayload.tokens),
        readString(bundlePayload.display_name),
        readString(bundlePayload.description),
        bundlePayload.preview,
      );
    } else {
      if (!householdId) {
        throw new Error('当前没有家庭上下文，无法加载远端主题资源');
      }
      const payload = await this.deps.fetchResource(
        householdId,
        registryItem.plugin_id,
        registryItem.theme_id,
      );
      themeOption = buildThemeOption(
        registryItem,
        normalizeTokens(payload.tokens),
        readString(payload.display_name),
        readString(payload.description),
        payload.preview ?? undefined,
      );
    }

    this.cachedThemeByVersionKey.set(cacheKey, themeOption);
    return themeOption;
  }

  private setState(patch: Partial<ThemeRuntimeState>) {
    this.state = {
      ...this.state,
      ...patch,
    };
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

export function createThemeRuntime(
  overrides: Partial<ThemeRuntimeDeps> = {},
) {
  const localStore = createLocalSelectionStore(
    overrides.builtinEntries ?? builtinThemeBundleIndex,
  );
  return new ThemeRuntime({
    builtinEntries: overrides.builtinEntries ?? builtinThemeBundleIndex,
    fetchRegistry: overrides.fetchRegistry ?? listHouseholdThemeRegistry,
    fetchResource: overrides.fetchResource ?? getHouseholdThemeResource,
    readStoredSelection: overrides.readStoredSelection ?? localStore.readStoredSelection,
    writeStoredSelection: overrides.writeStoredSelection ?? localStore.writeStoredSelection,
  });
}
