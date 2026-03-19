import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useOptionalHouseholdContext } from '../../household';
import { applyThemeDocument } from './applyThemeDocument';
import { createThemeRuntime } from '../../shared/theme-plugin/themeRuntime';
import type {
  ThemeFallbackNotice,
  ThemeRuntimeSelection,
  ThemeRuntimeThemeOption,
  ThemeVersionInfo,
} from '../../shared/theme-plugin/types';

type ThemeId = string;

type ThemeContextValue = {
  theme: ThemeRuntimeThemeOption;
  themeId: ThemeId;
  themeList: ThemeRuntimeThemeOption[];
  themeListLoading: boolean;
  themeListError: string;
  themeFallbackNotice: ThemeFallbackNotice | null;
  setTheme: (selection: ThemeId | ThemeRuntimeSelection) => void;
  isThemeAvailable: (id: ThemeId) => boolean;
  getThemeDisabledReason: (id: ThemeId) => string | null;
  getThemeVersionInfo: (id: ThemeId) => ThemeVersionInfo | null;
};

const PLACEHOLDER_THEME: ThemeRuntimeThemeOption = {
  id: '__theme-placeholder__',
  plugin_id: '',
  label: 'Theme placeholder',
  description: '',
  emoji: 'T',
  bgApp: '',
  bgCard: '',
  brandPrimary: '',
  textPrimary: '',
  glowColor: '',
  state: 'invalid',
  source_type: 'builtin',
  resource_version: '0',
  tokens: {},
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider(props: { children: ReactNode }) {
  const householdContext = useOptionalHouseholdContext();
  const householdId = householdContext?.currentHouseholdId?.trim() ?? '';
  const runtimeRef = useRef(createThemeRuntime());
  const [snapshot, setSnapshot] = useState(() => runtimeRef.current.getState());

  useEffect(() => {
    const runtime = runtimeRef.current;
    const unsubscribe = runtime.subscribe(nextState => {
      setSnapshot(nextState);
    });
    void runtime.bootstrap();
    return unsubscribe;
  }, []);

  useEffect(() => {
    void runtimeRef.current.refreshRegistry(householdId || null);
  }, [householdId]);

  const theme = useMemo(
    () => snapshot.active_theme ?? snapshot.shell_theme ?? PLACEHOLDER_THEME,
    [snapshot.active_theme, snapshot.shell_theme],
  );

  useEffect(() => {
    applyThemeDocument(theme);
  }, [theme]);

  const themeList = useMemo(() => {
    if (snapshot.theme_list.length > 0) {
      return snapshot.theme_list;
    }
    if (snapshot.shell_theme) {
      return [snapshot.shell_theme];
    }
    return [];
  }, [snapshot.shell_theme, snapshot.theme_list]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      themeId: snapshot.selection?.theme_id ?? theme.id,
      themeList,
      themeListLoading: snapshot.loading,
      themeListError: snapshot.error,
      themeFallbackNotice: snapshot.theme_fallback_notice,
      setTheme: selection => {
        if (typeof selection === 'string') {
          void runtimeRef.current.selectThemeByThemeId(selection);
          return;
        }
        void runtimeRef.current.selectTheme(selection);
      },
      isThemeAvailable: id => themeList.some(item => item.id === id),
      getThemeDisabledReason: id => snapshot.disabled_reason_by_theme_id[id] ?? null,
      getThemeVersionInfo: id => snapshot.version_info_by_theme_id[id] ?? null,
    }),
    [
      snapshot.disabled_reason_by_theme_id,
      snapshot.error,
      snapshot.loading,
      snapshot.selection?.theme_id,
      snapshot.theme_fallback_notice,
      snapshot.version_info_by_theme_id,
      theme,
      theme.id,
      themeList,
    ],
  );

  return (
    <ThemeContext.Provider value={value}>
      {props.children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme 必须在 ThemeProvider 内使用');
  }
  return context;
}
