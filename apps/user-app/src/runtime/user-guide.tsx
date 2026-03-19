import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import Taro from '@tarojs/taro';
import type { Member, MemberGuideStatus } from '@familyclaw/user-core';
import { loadMemberGuideStatus } from '@familyclaw/user-core';
import { useAuthContext } from './auth';
import { appStorage, coreApiClient } from './core';
import { useI18n } from './h5-shell';
import { createH5UserGuidePlatformAdapter } from './h5-shell/user-guide/platformAdapter';
import { createRnUserGuidePlatformAdapter } from './rn-shell/user-guide/platformAdapter';
import { USER_GUIDE_DEFAULT_ANCHOR_TIMEOUT_MS } from './shared/user-guide/constants';
import {
  clearGuideSessionCheckpoint,
  clearPendingGuideAutoStart,
  readGuideSessionCheckpoint,
  readPendingGuideAutoStart,
  saveGuideSessionCheckpoint,
} from './shared/user-guide/localState';
import { USER_APP_GUIDE_VERSION, userAppGuideManifestV1 } from './shared/user-guide/manifest';
import { GuideOverlay } from './shared/user-guide/GuideOverlay';
import type { UserGuideOverlayProps } from './shared/user-guide/GuideOverlay.types';
import type { UserGuidePlatformAdapter } from './shared/user-guide/platformAdapter';
import {
  beginGuideCompletion,
  createGuideSession,
  markGuideAnchorResolved,
  moveGuideSession,
  restoreGuideSession,
  shouldAutoStartGuide,
  syncGuideSessionRoute,
  type UserGuideLaunchSource,
  type UserGuideSession,
} from './shared/user-guide/runtime';

type UserGuideContextValue = {
  guideStatus: MemberGuideStatus | null;
  guideStatusLoading: boolean;
  guideStatusError: string;
  currentRoute: string;
  currentStep: UserGuideSession['steps'][number] | null;
  currentStepDisplayMode: 'anchor' | 'page';
  manifestVersion: number;
  platformAdapter: UserGuidePlatformAdapter;
  session: UserGuideSession | null;
  refreshGuideStatus: () => Promise<MemberGuideStatus | null>;
  setCurrentRoute: (route: string) => void;
  startGuide: (source?: UserGuideLaunchSource) => boolean;
  nextStep: () => void;
  previousStep: () => void;
  markCurrentStepReady: () => void;
  completeGuide: () => Promise<MemberGuideStatus | null>;
  skipGuide: () => Promise<MemberGuideStatus | null>;
};

const UserGuideContext = createContext<UserGuideContextValue | null>(null);
const USER_GUIDE_AUTO_START_ROUTE = '/pages/home/index';

function normalizeRoute(route: string | null | undefined): string {
  if (!route) {
    return '';
  }

  const cleanRoute = route.split('?')[0]?.trim() ?? '';
  if (!cleanRoute) {
    return '';
  }

  return cleanRoute.startsWith('/') ? cleanRoute : `/${cleanRoute}`;
}

function resolveInitialRoute(): string {
  if (process.env.TARO_ENV === 'h5' && typeof window !== 'undefined') {
    return normalizeRoute(window.location.pathname);
  }

  try {
    return normalizeRoute(Taro.getCurrentInstance().router?.path);
  } catch {
    return '';
  }
}

function resolvePlatformAdapter(): UserGuidePlatformAdapter {
  if (process.env.TARO_ENV === 'h5') {
    return createH5UserGuidePlatformAdapter();
  }
  return createRnUserGuidePlatformAdapter();
}

function restoreGuideStepAfterError(session: UserGuideSession): UserGuideSession {
  return {
    ...session,
    status: 'showing',
    pendingRoute: null,
    waitingAnchorId: null,
  };
}

export function UserGuideProvider(props: { children: ReactNode }) {
  const { actor } = useAuthContext();
  const { t } = useI18n();
  const [guideStatus, setGuideStatus] = useState<MemberGuideStatus | null>(null);
  const [guideStatusLoading, setGuideStatusLoading] = useState(false);
  const [guideStatusError, setGuideStatusError] = useState('');
  const [guideActionPending, setGuideActionPending] = useState(false);
  const [guideRestoreChecked, setGuideRestoreChecked] = useState(false);
  const [session, setSession] = useState<UserGuideSession | null>(null);
  const [currentRoute, setCurrentRouteState] = useState(resolveInitialRoute);
  const [currentStepDisplayMode, setCurrentStepDisplayMode] = useState<'anchor' | 'page'>('page');
  const platformAdapter = useMemo(resolvePlatformAdapter, []);
  const navigationKeyRef = useRef('');
  const anchorWaitKeyRef = useRef('');
  const autoCheckKeyRef = useRef('');

  const refreshGuideStatus = useCallback(async () => {
    if (!actor?.member_id) {
      setGuideStatus(null);
      setGuideStatusError('');
      return null;
    }

    setGuideStatusLoading(true);
    setGuideStatusError('');

    try {
      const result = await loadMemberGuideStatus(coreApiClient, actor.member_id);
      setGuideStatus(result);
      return result;
    } catch (error) {
      setGuideStatus(null);
      setGuideStatusError(error instanceof Error ? error.message : t('userGuide.error.loadFailed'));
      return null;
    } finally {
      setGuideStatusLoading(false);
    }
  }, [actor?.member_id, t]);

  useEffect(() => {
    void refreshGuideStatus();
  }, [refreshGuideStatus]);

  useEffect(() => {
    if (!actor?.member_id) {
      setSession(null);
      setCurrentStepDisplayMode('page');
      navigationKeyRef.current = '';
      anchorWaitKeyRef.current = '';
      autoCheckKeyRef.current = '';
      setGuideRestoreChecked(false);
    }
  }, [actor?.member_id]);

  useEffect(() => {
    if (actor?.member_id) {
      setGuideRestoreChecked(false);
    }
  }, [actor?.member_id]);

  const setCurrentRoute = useCallback((route: string) => {
    const nextRoute = normalizeRoute(route);
    setCurrentRouteState((currentValue) => (currentValue === nextRoute ? currentValue : nextRoute));
    setSession((currentSession) => {
      if (!currentSession) {
        return currentSession;
      }
      if (currentSession.currentRoute === nextRoute) {
        return currentSession;
      }
      return syncGuideSessionRoute(currentSession, nextRoute);
    });
  }, []);

  useEffect(() => {
    if (process.env.TARO_ENV === 'h5' && typeof window !== 'undefined') {
      const syncRouteFromLocation = () => {
        setCurrentRoute(window.location.pathname);
      };

      syncRouteFromLocation();
      window.addEventListener('popstate', syncRouteFromLocation);
      return () => {
        window.removeEventListener('popstate', syncRouteFromLocation);
      };
    }

    return undefined;
  }, [setCurrentRoute]);

  const startGuide = useCallback((source: UserGuideLaunchSource = 'manual') => {
    setGuideStatusError('');
    const nextSession = createGuideSession(userAppGuideManifestV1, {
      memberRole: (actor?.member_role as Member['role'] | null) ?? null,
      runtimeTarget: platformAdapter.runtimeTarget,
      currentRoute,
      source,
    });
    setCurrentStepDisplayMode('page');
    setSession(nextSession);
    return Boolean(nextSession);
  }, [actor?.member_role, currentRoute, platformAdapter.runtimeTarget]);

  useEffect(() => {
    if (!actor?.member_id || guideStatusLoading || session || guideRestoreChecked) {
      return;
    }

    let cancelled = false;

    const maybeRestoreGuideSession = async () => {
      const checkpoint = await readGuideSessionCheckpoint(appStorage);
      if (!checkpoint) {
        if (!cancelled) {
          setGuideRestoreChecked(true);
        }
        return;
      }

      if (
        checkpoint.manifest_version !== USER_APP_GUIDE_VERSION
        || (guideStatus?.user_app_guide_version ?? 0) >= USER_APP_GUIDE_VERSION
      ) {
        await clearGuideSessionCheckpoint(appStorage);
        if (!cancelled) {
          setGuideRestoreChecked(true);
        }
        return;
      }

      const restoredSession = restoreGuideSession(userAppGuideManifestV1, {
        memberRole: (actor?.member_role as Member['role'] | null) ?? null,
        runtimeTarget: platformAdapter.runtimeTarget,
        currentRoute,
      }, {
        currentStepIndex: checkpoint.current_step_index,
        source: checkpoint.source,
      });

      if (!restoredSession) {
        await clearGuideSessionCheckpoint(appStorage);
        if (!cancelled) {
          setGuideRestoreChecked(true);
        }
        return;
      }

      if (!cancelled) {
        setCurrentStepDisplayMode('page');
        setSession(restoredSession);
        setGuideRestoreChecked(true);
      }
    };

    void maybeRestoreGuideSession();

    return () => {
      cancelled = true;
    };
  }, [
    actor?.member_id,
    actor?.member_role,
    currentRoute,
    guideRestoreChecked,
    guideStatus?.user_app_guide_version,
    guideStatusLoading,
    platformAdapter.runtimeTarget,
    session,
  ]);

  useEffect(() => {
    if (!session) {
      if (guideRestoreChecked) {
        void clearGuideSessionCheckpoint(appStorage).catch(() => undefined);
      }
      return;
    }

    if (session.status === 'finished') {
      void clearGuideSessionCheckpoint(appStorage).catch(() => undefined);
      return;
    }

    void saveGuideSessionCheckpoint(appStorage, {
      manifest_version: session.manifestVersion,
      current_step_index: session.currentStepIndex,
      source: session.source,
      updated_at: new Date().toISOString(),
    }).catch(() => undefined);
  }, [guideRestoreChecked, session]);

  const nextStep = useCallback(() => {
    setSession((currentSession) => {
      if (!currentSession) {
        return currentSession;
      }

      if (currentSession.currentStepIndex >= currentSession.steps.length - 1) {
        return beginGuideCompletion(currentSession);
      }

      return moveGuideSession(currentSession, 'next', currentRoute);
    });
  }, [currentRoute]);

  const previousStep = useCallback(() => {
    setSession((currentSession) => {
      if (!currentSession) {
        return currentSession;
      }
      return moveGuideSession(currentSession, 'previous', currentRoute);
    });
  }, [currentRoute]);

  const markCurrentStepReady = useCallback(() => {
    setSession((currentSession) => {
      if (!currentSession) {
        return currentSession;
      }
      return markGuideAnchorResolved(currentSession);
    });
  }, []);

  useEffect(() => {
    const currentStep = session?.steps[session.currentStepIndex] ?? null;
    if (!currentStep) {
      setCurrentStepDisplayMode('page');
      navigationKeyRef.current = '';
      anchorWaitKeyRef.current = '';
      return;
    }

    setCurrentStepDisplayMode('page');
  }, [session?.currentStepIndex, session?.steps]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const currentStep = session.steps[session.currentStepIndex] ?? null;
    if (!currentStep || session.status !== 'navigating' || !session.pendingRoute) {
      navigationKeyRef.current = '';
      return;
    }

    const navigationKey = `${currentStep.step_id}:${session.pendingRoute}`;
    if (navigationKeyRef.current === navigationKey) {
      return;
    }
    navigationKeyRef.current = navigationKey;

    let cancelled = false;

    const navigateToStepRoute = async () => {
      await platformAdapter.beforeStepChange(currentStep);
      if (cancelled) {
        return;
      }

      try {
        await Taro.switchTab({ url: session.pendingRoute! });
        return;
      } catch {
        // 主导航页优先尝试 switchTab，失败后继续兜底。
      }

      try {
        await Taro.redirectTo({ url: session.pendingRoute! });
        return;
      } catch {
        // H5 / RN 统一继续降级。
      }

      try {
        await Taro.navigateTo({ url: session.pendingRoute! });
      } catch {
        setGuideStatusError(t('userGuide.error.navigateFailed'));
      }
    };

    void navigateToStepRoute();

    return () => {
      cancelled = true;
    };
  }, [platformAdapter, session, t]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const currentStep = session.steps[session.currentStepIndex] ?? null;
    if (!currentStep?.anchor_id || session.status !== 'waiting_anchor') {
      anchorWaitKeyRef.current = '';
      return;
    }

    const waitKey = `${currentStep.step_id}:${currentStep.anchor_id}:${currentRoute}`;
    if (anchorWaitKeyRef.current === waitKey) {
      return;
    }
    anchorWaitKeyRef.current = waitKey;

    let cancelled = false;

    void platformAdapter.waitForAnchor(currentStep.anchor_id, USER_GUIDE_DEFAULT_ANCHOR_TIMEOUT_MS).then((result) => {
      if (cancelled) {
        return;
      }

      setCurrentStepDisplayMode(result === 'resolved' ? 'anchor' : 'page');
      markCurrentStepReady();
    });

    return () => {
      cancelled = true;
    };
  }, [currentRoute, markCurrentStepReady, platformAdapter, session]);

  useEffect(() => {
    if (
      !actor?.member_id
      || guideStatusLoading
      || session
      || guideStatusError
      || !guideRestoreChecked
      || currentRoute !== USER_GUIDE_AUTO_START_ROUTE
    ) {
      return;
    }

    const autoCheckKey = `${actor.member_id}:${guideStatus?.user_app_guide_version ?? 'null'}:${guideStatusError}`;
    if (autoCheckKeyRef.current === autoCheckKey) {
      return;
    }
    autoCheckKeyRef.current = autoCheckKey;

    let cancelled = false;

    const maybeAutoStartGuide = async () => {
      const pendingLaunch = await readPendingGuideAutoStart(appStorage);
      if (cancelled || !pendingLaunch) {
        return;
      }

      if (!shouldAutoStartGuide(guideStatus, USER_APP_GUIDE_VERSION, { justCompletedSetup: true })) {
        await clearPendingGuideAutoStart(appStorage);
        return;
      }

      const started = startGuide(pendingLaunch.source);
      if (!started) {
        return;
      }

      await clearPendingGuideAutoStart(appStorage);
    };

    void maybeAutoStartGuide();

    return () => {
      cancelled = true;
    };
  }, [
    actor?.member_id,
    currentRoute,
    guideStatus,
    guideStatusError,
    guideStatusLoading,
    guideRestoreChecked,
    session,
    startGuide,
  ]);

  const persistGuideCompletion = useCallback(async () => {
    if (!actor?.member_id) {
      return null;
    }

    const result = await coreApiClient.upsertMemberGuideStatus(actor.member_id, {
      user_app_guide_version: USER_APP_GUIDE_VERSION,
    });
    setGuideStatus(result);
    return result;
  }, [actor?.member_id]);

  const completeGuide = useCallback(async () => {
    setSession((currentSession) => (currentSession ? beginGuideCompletion(currentSession) : currentSession));
    setGuideActionPending(true);
    try {
      const result = await persistGuideCompletion();
      await clearGuideSessionCheckpoint(appStorage);
      await clearPendingGuideAutoStart(appStorage);
      setSession(null);
      return result;
    } catch (error) {
      setSession((currentSession) => (
        currentSession ? restoreGuideStepAfterError(currentSession) : currentSession
      ));
      setGuideStatusError(error instanceof Error ? error.message : t('userGuide.error.saveFailed'));
      return null;
    } finally {
      setGuideActionPending(false);
    }
  }, [persistGuideCompletion, t]);

  const skipGuide = useCallback(async () => {
    setSession((currentSession) => (currentSession ? beginGuideCompletion(currentSession) : currentSession));
    setGuideActionPending(true);
    try {
      const result = await persistGuideCompletion();
      await clearGuideSessionCheckpoint(appStorage);
      await clearPendingGuideAutoStart(appStorage);
      setSession(null);
      return result;
    } catch (error) {
      setSession((currentSession) => (
        currentSession ? restoreGuideStepAfterError(currentSession) : currentSession
      ));
      setGuideStatusError(error instanceof Error ? error.message : t('userGuide.error.saveFailed'));
      return null;
    } finally {
      setGuideActionPending(false);
    }
  }, [persistGuideCompletion, t]);

  const currentStep = session?.steps[session.currentStepIndex] ?? null;

  const value = useMemo<UserGuideContextValue>(() => ({
    guideStatus,
    guideStatusLoading,
    guideStatusError,
    currentRoute,
    currentStep,
    currentStepDisplayMode,
    manifestVersion: userAppGuideManifestV1.version,
    platformAdapter,
    session,
    refreshGuideStatus,
    setCurrentRoute,
    startGuide,
    nextStep,
    previousStep,
    markCurrentStepReady,
    completeGuide,
    skipGuide,
  }), [
    completeGuide,
    currentRoute,
    currentStep,
    currentStepDisplayMode,
    guideStatus,
    guideStatusError,
    guideStatusLoading,
    markCurrentStepReady,
    nextStep,
    platformAdapter,
    previousStep,
    refreshGuideStatus,
    session,
    setCurrentRoute,
    skipGuide,
    startGuide,
  ]);

  const overlayProps: UserGuideOverlayProps | null = currentStep && session ? {
    currentStepIndex: session.currentStepIndex,
    totalSteps: session.steps.length,
    title: t(currentStep.title_key),
    content: t(currentStep.content_key),
    anchorId: currentStep.anchor_id,
    status: session.status,
    errorMessage: guideStatusError,
    isLastStep: session.currentStepIndex >= session.steps.length - 1,
    isActionPending: guideActionPending,
    onPrevious: previousStep,
    onNext: nextStep,
    onFinish: () => {
      void completeGuide();
    },
    onSkip: () => {
      void skipGuide();
    },
  } : null;

  const shouldRenderOverlay = Boolean(
    overlayProps
    && session
    && session.status !== 'navigating'
    && session.status !== 'finished',
  );

  return (
    <UserGuideContext.Provider value={value}>
      <>
        {props.children}
        {shouldRenderOverlay && overlayProps ? <GuideOverlay {...overlayProps} /> : null}
      </>
    </UserGuideContext.Provider>
  );
}

export function useUserGuideContext() {
  const context = useContext(UserGuideContext);
  if (!context) {
    throw new Error('useUserGuideContext 必须在 UserGuideProvider 内使用');
  }
  return context;
}

export function useOptionalUserGuideContext() {
  return useContext(UserGuideContext);
}
