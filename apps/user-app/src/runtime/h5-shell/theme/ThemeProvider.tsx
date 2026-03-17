import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  createRequestClient,
  DEFAULT_THEME_ID,
  THEME_STORAGE_KEY,
  resolveThemeId,
  type PluginRegistrySnapshot,
  type ThemeId as SharedThemeId,
} from '@familyclaw/user-core';
import {
  userAppThemeList,
  userAppThemes,
} from '@familyclaw/user-ui';
import { useOptionalHouseholdContext } from '../../household';
import { applyThemeDocument } from './applyThemeDocument';

type ThemeId = SharedThemeId;
type UserAppTheme = (typeof userAppThemeList)[number];

type ThemeFallbackNotice = {
  disabledThemeId: ThemeId;
  disabledReason: string | null;
};

type ThemeVersionInfo = {
  pluginId: string;
  version: string;
  installedVersion: string | null;
  updateState: string | null;
};

type ThemeRegistryState = {
  loaded: boolean;
  loading: boolean;
  error: string;
  availableThemeIds: ThemeId[];
  disabledReasonByThemeId: Partial<Record<ThemeId, string | null>>;
  versionInfoByThemeId: Partial<Record<ThemeId, ThemeVersionInfo>>;
};

type ThemeContextValue = {
  theme: UserAppTheme;
  themeId: ThemeId;
  themeList: UserAppTheme[];
  themeListLoading: boolean;
  themeListError: string;
  themeFallbackNotice: ThemeFallbackNotice | null;
  setTheme: (id: ThemeId) => void;
  isThemeAvailable: (id: ThemeId) => boolean;
  getThemeDisabledReason: (id: ThemeId) => string | null;
  getThemeVersionInfo: (id: ThemeId) => ThemeVersionInfo | null;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

const EMPTY_THEME_REGISTRY_STATE: ThemeRegistryState = {
  loaded: false,
  loading: false,
  error: '',
  availableThemeIds: [],
  disabledReasonByThemeId: {},
  versionInfoByThemeId: {},
};

function getStoredThemeId(): ThemeId {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME_ID;
  }

  try {
    return resolveThemeId(window.localStorage.getItem(THEME_STORAGE_KEY), DEFAULT_THEME_ID);
  } catch {
    return DEFAULT_THEME_ID;
  }
}

function getThemeById(themeId: ThemeId): UserAppTheme {
  return userAppThemes[themeId] ?? userAppThemes[DEFAULT_THEME_ID];
}

function resolveKnownThemeId(themeId: string | null | undefined): ThemeId | null {
  const normalized = (themeId ?? '').trim();
  const matched = userAppThemeList.find(item => item.id === normalized);
  return matched?.id ?? null;
}

function buildThemeRegistryState(snapshot: PluginRegistrySnapshot): ThemeRegistryState {
  const availableThemeIds: ThemeId[] = [];
  const disabledReasonByThemeId: Partial<Record<ThemeId, string | null>> = {};
  const versionInfoByThemeId: Partial<Record<ThemeId, ThemeVersionInfo>> = {};

  for (const item of snapshot.items) {
    if (!item.types.includes('theme-pack')) {
      continue;
    }

    const themeId = resolveKnownThemeId(item.capabilities.theme_pack?.theme_id);
    if (!themeId) {
      continue;
    }

    versionInfoByThemeId[themeId] = {
      pluginId: item.id,
      version: item.version,
      installedVersion: item.installed_version ?? null,
      updateState: item.update_state ?? null,
    };

    if (item.enabled) {
      if (!availableThemeIds.includes(themeId)) {
        availableThemeIds.push(themeId);
      }
      continue;
    }

    disabledReasonByThemeId[themeId] = item.disabled_reason ?? null;
  }

  return {
    loaded: true,
    loading: false,
    error: '',
    availableThemeIds,
    disabledReasonByThemeId,
    versionInfoByThemeId,
  };
}

export function ThemeProvider(props: { children: ReactNode }) {
  const householdContext = useOptionalHouseholdContext();
  const householdId = householdContext?.currentHouseholdId ?? '';
  const [themeId, setThemeId] = useState<ThemeId>(getStoredThemeId);
  const [themeRegistryState, setThemeRegistryState] = useState<ThemeRegistryState>(EMPTY_THEME_REGISTRY_STATE);
  const [themeFallbackNotice, setThemeFallbackNotice] = useState<ThemeFallbackNotice | null>(null);

  useEffect(() => {
    if (!householdId) {
      setThemeRegistryState(EMPTY_THEME_REGISTRY_STATE);
      setThemeFallbackNotice(null);
      return;
    }

    let cancelled = false;
    setThemeRegistryState(current => ({
      ...current,
      loaded: false,
      loading: true,
      error: '',
      availableThemeIds: [],
      disabledReasonByThemeId: {},
      versionInfoByThemeId: {},
    }));

    void request<PluginRegistrySnapshot>(`/ai-config/${encodeURIComponent(householdId)}/plugins`)
      .then(snapshot => {
        if (cancelled) {
          return;
        }
        setThemeRegistryState(buildThemeRegistryState(snapshot));
      })
      .catch(error => {
        if (cancelled) {
          return;
        }
        setThemeRegistryState({
          loaded: false,
          loading: false,
          error: error instanceof Error ? error.message : '加载主题插件状态失败',
          availableThemeIds: [],
          disabledReasonByThemeId: {},
          versionInfoByThemeId: {},
        });
      });

    return () => {
      cancelled = true;
    };
  }, [householdId]);

  const themeList = useMemo(() => {
    if (!householdId) {
      return userAppThemeList;
    }
    if (!themeRegistryState.loaded) {
      return [] as UserAppTheme[];
    }
    return userAppThemeList.filter(item => themeRegistryState.availableThemeIds.includes(item.id));
  }, [householdId, themeRegistryState.availableThemeIds, themeRegistryState.loaded]);

  const fallbackThemeId = themeList[0]?.id ?? DEFAULT_THEME_ID;
  const activeThemeId = useMemo(() => {
    if (!householdId || !themeRegistryState.loaded) {
      return themeId;
    }
    if (themeRegistryState.availableThemeIds.includes(themeId)) {
      return themeId;
    }
    return fallbackThemeId;
  }, [fallbackThemeId, householdId, themeId, themeRegistryState.availableThemeIds, themeRegistryState.loaded]);
  const theme = getThemeById(activeThemeId);

  useEffect(() => {
    if (!householdId || !themeRegistryState.loaded) {
      return;
    }
    if (themeRegistryState.availableThemeIds.includes(themeId)) {
      return;
    }

    setThemeFallbackNotice({
      disabledThemeId: themeId,
      disabledReason: themeRegistryState.disabledReasonByThemeId[themeId] ?? null,
    });
    setThemeId(fallbackThemeId);
  }, [
    fallbackThemeId,
    householdId,
    themeId,
    themeRegistryState.availableThemeIds,
    themeRegistryState.disabledReasonByThemeId,
    themeRegistryState.loaded,
  ]);

  useEffect(() => {
    applyThemeDocument(theme);
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, themeId);
    } catch {
      // 忽略本地持久化失败，不影响界面切换
    }
  }, [theme, themeId]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      themeId: activeThemeId,
      themeList,
      themeListLoading: Boolean(householdId) && themeRegistryState.loading,
      themeListError: themeRegistryState.error,
      themeFallbackNotice,
      setTheme: id => {
        setThemeFallbackNotice(null);
        setThemeId(resolveThemeId(id, DEFAULT_THEME_ID));
      },
      isThemeAvailable: id => {
        if (!householdId) {
          return true;
        }
        return themeRegistryState.availableThemeIds.includes(id);
      },
      getThemeDisabledReason: id => {
        if (!householdId) {
          return null;
        }
        return themeRegistryState.disabledReasonByThemeId[id] ?? null;
      },
      getThemeVersionInfo: id => {
        if (!householdId) {
          return null;
        }
        return themeRegistryState.versionInfoByThemeId[id] ?? null;
      },
    }),
    [
      activeThemeId,
      householdId,
      theme,
      themeFallbackNotice,
      themeList,
      themeRegistryState.availableThemeIds,
      themeRegistryState.disabledReasonByThemeId,
      themeRegistryState.error,
      themeRegistryState.loading,
      themeRegistryState.versionInfoByThemeId,
    ],
  );

  return <ThemeContext.Provider value={value}>{props.children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme 必须在 ThemeProvider 内使用');
  }
  return context;
}
