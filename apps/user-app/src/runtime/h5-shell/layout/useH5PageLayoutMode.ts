import { useEffect, useMemo, useState } from 'react';
import {
  resolvePageLayoutMode,
  type PlatformLayoutContext,
  type PageLayoutMode,
  type SharedLayoutPointerType,
  type SharedLayoutSurface,
} from '../../shared/layout/pageLayout';

function detectPointerType(): SharedLayoutPointerType {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'fine';
  }
  return window.matchMedia('(pointer: coarse)').matches ? 'coarse' : 'fine';
}

function buildContext(surface: SharedLayoutSurface): PlatformLayoutContext {
  if (typeof window === 'undefined') {
    return {
      platform: 'h5',
      surface,
      viewportWidth: Number.POSITIVE_INFINITY,
      pointerType: 'fine',
    };
  }

  return {
    platform: 'h5',
    surface,
    viewportWidth: window.innerWidth,
    pointerType: detectPointerType(),
  };
}

export function useH5PageLayoutMode(surface: SharedLayoutSurface): PageLayoutMode {
  const [context, setContext] = useState(() => buildContext(surface));

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const mediaQuery = window.matchMedia?.('(pointer: coarse)');
    const update = () => {
      setContext(buildContext(surface));
    };

    update();
    window.addEventListener('resize', update);
    mediaQuery?.addEventListener?.('change', update);

    return () => {
      window.removeEventListener('resize', update);
      mediaQuery?.removeEventListener?.('change', update);
    };
  }, [surface]);

  return useMemo(() => resolvePageLayoutMode(context), [context]);
}
