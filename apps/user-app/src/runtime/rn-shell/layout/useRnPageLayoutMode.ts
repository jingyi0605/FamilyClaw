import { useMemo } from 'react';
import { useWindowDimensions } from 'react-native';
import { resolvePageLayoutMode, type SharedLayoutSurface } from '../../shared/layout/pageLayout';

export function useRnPageLayoutMode(surface: SharedLayoutSurface) {
  const { width } = useWindowDimensions();

  return useMemo(
    () => resolvePageLayoutMode({
      platform: 'rn',
      surface,
      viewportWidth: width,
      pointerType: 'coarse',
      safeAreaEnabled: true,
    }),
    [surface, width],
  );
}

