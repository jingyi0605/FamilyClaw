type GuideAnchorRecord = {
  anchorId: string;
  route: string;
  ready: boolean;
  element?: HTMLElement | null;
};

type GuideAnchorListener = () => void;

const anchorRegistry = new Map<string, GuideAnchorRecord>();
const anchorListeners = new Set<GuideAnchorListener>();

function normalizeGuideAnchorRoute(route: string | null | undefined) {
  if (!route) {
    return '';
  }

  const cleanRoute = route.split('?')[0]?.trim() ?? '';
  if (!cleanRoute) {
    return '';
  }

  return cleanRoute.startsWith('/') ? cleanRoute : `/${cleanRoute}`;
}

function emitGuideAnchorChange() {
  anchorListeners.forEach(listener => listener());
}

export function registerGuideAnchor(record: GuideAnchorRecord) {
  anchorRegistry.set(record.anchorId, {
    ...record,
    route: normalizeGuideAnchorRoute(record.route),
  });
  emitGuideAnchorChange();
}

export function unregisterGuideAnchor(anchorId: string) {
  if (!anchorRegistry.has(anchorId)) {
    return;
  }

  anchorRegistry.delete(anchorId);
  emitGuideAnchorChange();
}

export function getGuideAnchor(anchorId: string) {
  return anchorRegistry.get(anchorId) ?? null;
}

export function subscribeGuideAnchorChanges(listener: GuideAnchorListener) {
  anchorListeners.add(listener);
  return () => {
    anchorListeners.delete(listener);
  };
}

export async function waitForGuideAnchor(anchorId: string, timeoutMs: number): Promise<'resolved' | 'timeout'> {
  const existingAnchor = getGuideAnchor(anchorId);
  if (existingAnchor?.ready) {
    return 'resolved';
  }

  return new Promise((resolve) => {
    const timer = globalThis.setTimeout(() => {
      dispose();
      resolve('timeout');
    }, timeoutMs);

    const dispose = subscribeGuideAnchorChanges(() => {
      const nextAnchor = getGuideAnchor(anchorId);
      if (!nextAnchor?.ready) {
        return;
      }

      globalThis.clearTimeout(timer);
      dispose();
      resolve('resolved');
    });
  });
}
