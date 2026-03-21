import { sharedPageLayoutBlueprint } from '@familyclaw/user-ui';

export type SharedLayoutSurface = 'content' | 'dashboard' | 'settings' | 'assistant';
export type SharedLayoutPlatform = 'h5' | 'rn';
export type SharedLayoutPointerType = 'coarse' | 'fine';
export type SharedHeaderDensity = 'compact' | 'regular';
export type SharedNavVariant = 'none' | 'sidebar' | 'tabs' | 'segmented';
export type SharedPanelBehavior = 'none' | 'docked' | 'overlay' | 'stacked';

export type PlatformLayoutContext = {
  platform: SharedLayoutPlatform;
  surface: SharedLayoutSurface;
  viewportWidth: number;
  pointerType?: SharedLayoutPointerType;
  safeAreaEnabled?: boolean;
};

export type PageLayoutMode = {
  id: string;
  platform: SharedLayoutPlatform;
  surface: SharedLayoutSurface;
  columns: 1 | 2 | 3;
  allowMouseResize: boolean;
  allowDragSort: boolean;
  headerDensity: SharedHeaderDensity;
  navVariant: SharedNavVariant;
  panelBehavior: SharedPanelBehavior;
  isTouchLayout: boolean;
  isCompact: boolean;
  maxContentWidth: string;
  contentGap: string;
};

type SharedSurfaceRule = {
  mobileBreakpoint: number;
  desktopColumns: 1 | 2 | 3;
  mobileColumns: 1 | 2 | 3;
  desktopNavVariant: SharedNavVariant;
  touchNavVariant: SharedNavVariant;
  desktopPanelBehavior: SharedPanelBehavior;
  touchPanelBehavior: SharedPanelBehavior;
  allowDesktopMouseResize: boolean;
  allowDesktopDragSort: boolean;
};

const SURFACE_RULES: Record<SharedLayoutSurface, SharedSurfaceRule> = {
  content: {
    mobileBreakpoint: 768,
    desktopColumns: 1,
    mobileColumns: 1,
    desktopNavVariant: 'none',
    touchNavVariant: 'none',
    desktopPanelBehavior: 'stacked',
    touchPanelBehavior: 'stacked',
    allowDesktopMouseResize: false,
    allowDesktopDragSort: false,
  },
  dashboard: {
    mobileBreakpoint: sharedPageLayoutBlueprint.dashboard.mobileBreakpoint,
    desktopColumns: 2,
    mobileColumns: 1,
    desktopNavVariant: 'none',
    touchNavVariant: 'tabs',
    desktopPanelBehavior: 'docked',
    touchPanelBehavior: 'stacked',
    allowDesktopMouseResize: true,
    allowDesktopDragSort: true,
  },
  settings: {
    mobileBreakpoint: sharedPageLayoutBlueprint.settings.mobileBreakpoint,
    desktopColumns: 2,
    mobileColumns: 1,
    desktopNavVariant: 'sidebar',
    touchNavVariant: 'tabs',
    desktopPanelBehavior: 'stacked',
    touchPanelBehavior: 'stacked',
    allowDesktopMouseResize: false,
    allowDesktopDragSort: false,
  },
  assistant: {
    mobileBreakpoint: sharedPageLayoutBlueprint.assistant.mobileBreakpoint,
    desktopColumns: 2,
    mobileColumns: 1,
    desktopNavVariant: 'segmented',
    touchNavVariant: 'segmented',
    desktopPanelBehavior: 'docked',
    touchPanelBehavior: 'overlay',
    allowDesktopMouseResize: false,
    allowDesktopDragSort: false,
  },
};

function isTouchLayout(context: PlatformLayoutContext, mobileBreakpoint: number) {
  if (context.platform === 'rn') {
    return true;
  }
  if (context.pointerType === 'coarse') {
    return true;
  }
  return context.viewportWidth <= mobileBreakpoint;
}

export function resolvePageLayoutMode(context: PlatformLayoutContext): PageLayoutMode {
  const surfaceRule = SURFACE_RULES[context.surface];
  const touchLayout = isTouchLayout(context, surfaceRule.mobileBreakpoint);
  const columns = touchLayout ? surfaceRule.mobileColumns : surfaceRule.desktopColumns;

  return {
    id: `${touchLayout ? 'touch' : 'desktop'}-${context.surface}-${context.platform}`,
    platform: context.platform,
    surface: context.surface,
    columns,
    allowMouseResize: touchLayout ? false : surfaceRule.allowDesktopMouseResize,
    allowDragSort: touchLayout ? false : surfaceRule.allowDesktopDragSort,
    headerDensity: touchLayout ? 'compact' : 'regular',
    navVariant: touchLayout ? surfaceRule.touchNavVariant : surfaceRule.desktopNavVariant,
    panelBehavior: touchLayout ? surfaceRule.touchPanelBehavior : surfaceRule.desktopPanelBehavior,
    isTouchLayout: touchLayout,
    isCompact: touchLayout || context.viewportWidth <= 1100,
    maxContentWidth: sharedPageLayoutBlueprint.pageContentMaxWidth,
    contentGap: touchLayout ? 'var(--spacing-sm)' : 'var(--spacing-md)',
  };
}
