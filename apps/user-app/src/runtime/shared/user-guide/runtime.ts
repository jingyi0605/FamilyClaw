import type {
  Member,
  MemberGuideStatus,
  UserGuideManifest,
  UserGuideManifestStep,
  UserGuideRuntimeStatus,
} from '@familyclaw/user-core';

export type UserGuideLaunchSource = 'auto_after_setup' | 'manual';

export type UserGuideSession = {
  status: UserGuideRuntimeStatus;
  source: UserGuideLaunchSource;
  manifestVersion: number;
  currentStepIndex: number;
  currentRoute: string;
  pendingRoute: string | null;
  waitingAnchorId: string | null;
  steps: UserGuideManifestStep[];
};

export function normalizeGuideRoute(route: string | null | undefined): string {
  if (!route) {
    return '';
  }

  const cleanRoute = route.split('?')[0]?.trim() ?? '';
  if (!cleanRoute) {
    return '';
  }

  return cleanRoute.startsWith('/') ? cleanRoute : `/${cleanRoute}`;
}

export function filterGuideSteps(
  manifest: UserGuideManifest,
  options: {
    memberRole: Member['role'] | null;
    runtimeTarget: 'h5' | 'rn';
  },
): UserGuideManifestStep[] {
  return manifest.steps.filter((step) => {
    if (step.required_role && step.required_role !== options.memberRole) {
      return false;
    }

    if (step.runtime_targets && step.runtime_targets.length > 0 && !step.runtime_targets.includes(options.runtimeTarget)) {
      return false;
    }

    return true;
  });
}

function resolveSessionPhase(
  step: UserGuideManifestStep | null,
  currentRoute: string,
): Pick<UserGuideSession, 'status' | 'pendingRoute' | 'waitingAnchorId'> {
  if (!step) {
    return {
      status: 'finished',
      pendingRoute: null,
      waitingAnchorId: null,
    };
  }

  if (normalizeGuideRoute(step.route) !== normalizeGuideRoute(currentRoute)) {
    return {
      status: 'navigating',
      pendingRoute: normalizeGuideRoute(step.route),
      waitingAnchorId: null,
    };
  }

  if (step.anchor_id) {
    return {
      status: 'waiting_anchor',
      pendingRoute: null,
      waitingAnchorId: step.anchor_id,
    };
  }

  return {
    status: 'showing',
    pendingRoute: null,
    waitingAnchorId: null,
  };
}

export function createGuideSession(
  manifest: UserGuideManifest,
  options: {
    memberRole: Member['role'] | null;
    runtimeTarget: 'h5' | 'rn';
    currentRoute: string;
    source: UserGuideLaunchSource;
  },
): UserGuideSession | null {
  const steps = filterGuideSteps(manifest, {
    memberRole: options.memberRole,
    runtimeTarget: options.runtimeTarget,
  });
  if (steps.length === 0) {
    return null;
  }

  const currentRoute = normalizeGuideRoute(options.currentRoute);
  const initialStep = steps[0] ?? null;
  const phase = resolveSessionPhase(initialStep, currentRoute);

  return {
    status: phase.status,
    source: options.source,
    manifestVersion: manifest.version,
    currentStepIndex: 0,
    currentRoute,
    pendingRoute: phase.pendingRoute,
    waitingAnchorId: phase.waitingAnchorId,
    steps,
  };
}

export function restoreGuideSession(
  manifest: UserGuideManifest,
  options: {
    memberRole: Member['role'] | null;
    runtimeTarget: 'h5' | 'rn';
    currentRoute: string;
  },
  checkpoint: {
    currentStepIndex: number;
    source: UserGuideLaunchSource;
  },
): UserGuideSession | null {
  const baseSession = createGuideSession(manifest, {
    ...options,
    source: checkpoint.source,
  });
  if (!baseSession) {
    return null;
  }

  const nextIndex = Math.max(0, Math.min(baseSession.steps.length - 1, checkpoint.currentStepIndex));
  const nextStep = baseSession.steps[nextIndex] ?? null;
  const nextRoute = normalizeGuideRoute(options.currentRoute);
  const phase = resolveSessionPhase(nextStep, nextRoute);

  return {
    ...baseSession,
    currentStepIndex: nextIndex,
    currentRoute: nextRoute,
    status: phase.status,
    pendingRoute: phase.pendingRoute,
    waitingAnchorId: phase.waitingAnchorId,
  };
}

export function syncGuideSessionRoute(session: UserGuideSession, currentRoute: string): UserGuideSession {
  if (session.status === 'completing' || session.status === 'finished') {
    return {
      ...session,
      currentRoute: normalizeGuideRoute(currentRoute),
    };
  }

  const nextRoute = normalizeGuideRoute(currentRoute);
  const currentStep = session.steps[session.currentStepIndex] ?? null;
  const phase = resolveSessionPhase(currentStep, nextRoute);
  return {
    ...session,
    status: phase.status,
    currentRoute: nextRoute,
    pendingRoute: phase.pendingRoute,
    waitingAnchorId: phase.waitingAnchorId,
  };
}

export function moveGuideSession(
  session: UserGuideSession,
  direction: 'next' | 'previous',
  currentRoute: string,
): UserGuideSession {
  if (session.status === 'completing' || session.status === 'finished') {
    return session;
  }

  const delta = direction === 'next' ? 1 : -1;
  const nextIndex = Math.max(0, Math.min(session.steps.length - 1, session.currentStepIndex + delta));
  const nextStep = session.steps[nextIndex] ?? null;
  const nextRoute = normalizeGuideRoute(currentRoute);
  const phase = resolveSessionPhase(nextStep, nextRoute);

  return {
    ...session,
    status: phase.status,
    currentStepIndex: nextIndex,
    currentRoute: nextRoute,
    pendingRoute: phase.pendingRoute,
    waitingAnchorId: phase.waitingAnchorId,
  };
}

export function markGuideAnchorResolved(session: UserGuideSession): UserGuideSession {
  if (session.status !== 'waiting_anchor') {
    return session;
  }

  return {
    ...session,
    status: 'showing',
    waitingAnchorId: null,
  };
}

export function beginGuideCompletion(session: UserGuideSession): UserGuideSession {
  return {
    ...session,
    status: 'completing',
    pendingRoute: null,
    waitingAnchorId: null,
  };
}

export function finishGuideSession(session: UserGuideSession): UserGuideSession {
  return {
    ...session,
    status: 'finished',
    pendingRoute: null,
    waitingAnchorId: null,
  };
}

export function shouldAutoStartGuide(
  guideStatus: MemberGuideStatus | null,
  currentGuideVersion: number,
  flags: {
    justCompletedSetup: boolean;
  },
): boolean {
  if (!flags.justCompletedSetup) {
    return false;
  }

  return (guideStatus?.user_app_guide_version ?? 0) < currentGuideVersion;
}
