import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';
import { type PluginThemeResourcePayload } from '@familyclaw/user-ui';
import {
  applyRnThemeById,
  applyRnThemeFromPluginResource,
  getRnThemeRuntimeState,
  rnComponentTokens,
  rnFoundationTokens,
  rnSemanticTokens,
  type RnThemeRuntimeState,
} from '../tokens';

type RnThemeProviderProps = PropsWithChildren<{
  themeId?: string | null;
  themeResource?: PluginThemeResourcePayload | null;
}>;

type RnThemeContextValue = RnThemeRuntimeState & {
  applyThemeById: (themeId: string) => void;
  applyThemeResource: (resource: PluginThemeResourcePayload) => void;
};

const RnThemeContext = createContext<RnThemeContextValue | null>(null);

export function RnThemeProvider({ themeId, themeResource, children }: RnThemeProviderProps) {
  const [state, setState] = useState<RnThemeRuntimeState>(() => getRnThemeRuntimeState());

  useEffect(() => {
    if (themeResource) {
      applyRnThemeFromPluginResource(themeResource);
      setState(getRnThemeRuntimeState());
      return;
    }
    if (themeId !== undefined) {
      setState(applyRnThemeById(themeId ?? ''));
      return;
    }
    setState(getRnThemeRuntimeState());
  }, [themeId, themeResource]);

  const contextValue = useMemo<RnThemeContextValue>(() => ({
    ...state,
    applyThemeById: nextThemeId => {
      setState(applyRnThemeById(nextThemeId));
    },
    applyThemeResource: resource => {
      applyRnThemeFromPluginResource(resource);
      setState(getRnThemeRuntimeState());
    },
  }), [state]);

  return (
    <RnThemeContext.Provider value={contextValue}>
      {children}
    </RnThemeContext.Provider>
  );
}

export function useRnTheme() {
  const context = useContext(RnThemeContext);
  if (!context) {
    throw new Error('useRnTheme 必须在 RnThemeProvider 内使用');
  }
  return context;
}

export function useRnThemeTokens() {
  const theme = useRnTheme();
  return {
    theme,
    foundation: rnFoundationTokens,
    semantic: rnSemanticTokens,
    component: rnComponentTokens,
  };
}
